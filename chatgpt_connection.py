"""Server-side ChatGPT device login through the official Codex app-server."""
import base64
import hashlib
import json
import os
import queue
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

LOGIN_ERROR = 'ChatGPT-login kunne ikke gennemføres. Prøv igen, og kontrollér at device-login er tilladt i din ChatGPT-kontos sikkerhedsindstillinger.'


class ConnectionStore:
    def __init__(self, data_dir, secret):
        self.path = Path(data_dir) / 'chatgpt-connection.sqlite3'
        secret = secret.encode() if isinstance(secret, str) else secret
        self.key = base64.urlsafe_b64encode(hashlib.sha256(b'fjordlens-chatgpt-v1:' + secret).digest())
        self.cipher = Fernet(self.key)

    @contextmanager
    def db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            self.path.chmod(0o600)
            conn.execute('CREATE TABLE IF NOT EXISTS connection (id INTEGER PRIMARY KEY, value BLOB)')
            conn.execute('CREATE TABLE IF NOT EXISTS device_login (id INTEGER PRIMARY KEY, value BLOB)')
            conn.execute('CREATE TABLE IF NOT EXISTS test_analysis (id INTEGER PRIMARY KEY, value BLOB)')
            conn.execute('CREATE TABLE IF NOT EXISTS account_operation (id INTEGER PRIMARY KEY, value BLOB)')
            conn.commit()
            with conn:
                yield conn
        finally:
            conn.close()

    def read(self, db, table):
        row = db.execute(f'SELECT value FROM {table} WHERE id=1').fetchone()
        return json.loads(self.cipher.decrypt(row[0])) if row else None

    def write(self, db, table, value):
        encrypted = self.cipher.encrypt(json.dumps(value).encode())
        db.execute(f'INSERT OR REPLACE INTO {table} VALUES (1, ?)', (encrypted,))

    def start(self, owner):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = self.read(db, 'device_login')
            if previous and previous['expires_at'] > time.time() and previous['state'] in {'starting', 'waiting'}:
                raise ValueError('Et login er allerede i gang. Afslut eller annullér det først.')
            attempt = uuid.uuid4().hex
            self.write(db, 'device_login', dict(attempt=attempt, owner=str(owner), state='starting',
                                              expires_at=time.time() + 600))
        return attempt

    def update(self, attempt, **changes):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.read(db, 'device_login')
            if not job or job['attempt'] != attempt or job['state'] not in {'starting', 'waiting'}:
                return False
            job.update(changes)
            self.write(db, 'device_login', job)
            return True

    def active(self, attempt):
        with self.db() as db:
            job = self.read(db, 'device_login')
        return bool(job and job['attempt'] == attempt and job['state'] in {'starting', 'waiting'} and job['expires_at'] > time.time())

    def complete(self, attempt, account, auth):
        if account.get('type') != 'chatgpt' or not isinstance(auth.get('tokens'), dict):
            raise ValueError('ChatGPT-kontoen kunne ikke bekræftes.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.read(db, 'device_login')
            if not job or job['attempt'] != attempt or job['state'] not in {'starting', 'waiting'} or job['expires_at'] <= time.time():
                return False
            self.write(db, 'connection', dict(email=account.get('email') or '', plan=account.get('planType'),
                                              connected_at=int(time.time()), codex_auth=auth))
            self.write(db, 'device_login', dict(job, state='completed', user_code=None, verification_url=None))
            return True

    def status(self, owner):
        with self.db() as db:
            record = self.read(db, 'connection')
            job = self.read(db, 'device_login')
        result = {'connected': bool(record), 'inference_enabled': False}
        if record:
            result.update(email=record.get('email', ''), plan=record.get('plan'), connected_at=record.get('connected_at'))
        if job and job['owner'] == str(owner):
            state = job['state']
            if state in {'starting', 'waiting'} and job['expires_at'] <= time.time():
                state = 'expired'
            result['login'] = dict(state=state, expires_at=job['expires_at'])
            if state == 'waiting':
                result['login'].update(user_code=job.get('user_code'), verification_url=job.get('verification_url'))
            if state == 'failed':
                result['login']['error'] = LOGIN_ERROR
        elif job and job['state'] in {'starting', 'waiting'} and job['expires_at'] > time.time():
            result['login'] = {'state': 'busy'}
        return result

    def cancel(self, owner, disconnect=False):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.read(db, 'device_login')
            if job and (disconnect or job['owner'] == str(owner)):
                db.execute('DELETE FROM device_login')
            if disconnect:
                db.execute('DELETE FROM connection')


class CodexRPC:
    """Private stdio transport; server tool/approval requests are always rejected."""
    def __init__(self, home, executable):
        env = os.environ.copy()
        env['CODEX_HOME'] = str(home)
        for key in ['OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN']:
            env.pop(key, None)
        self.process = subprocess.Popen([executable, 'app-server', '--listen', 'stdio://',
                                         '-c', 'cli_auth_credentials_store="file"'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8', env=env,
                                        cwd=str(home),
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.messages = queue.Queue()
        self.notifications = []
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def request(self, method, params=None, timeout=20):
        if hasattr(self, 'deadline'):
            timeout = min(timeout, self.deadline - time.monotonic())
            if timeout <= 0:
                raise TimeoutError(LOGIN_ERROR)
        self.sequence += 1
        ident = self.sequence
        self.send(dict(id=ident, method=method, params=params or {}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self.messages.get(timeout=max(.01, deadline - time.monotonic()))
            if message is None:
                raise ValueError(LOGIN_ERROR)
            if message.get('id') == ident:
                if 'error' in message:
                    raise ValueError(LOGIN_ERROR)
                return message['result']
            if 'id' not in message:
                self.notifications.append(message)
            else:
                # This adapter implements no execution or approval capabilities.
                self.send(dict(id=message['id'], error={'code': -32601, 'message': 'Unsupported method'}))
        raise TimeoutError(LOGIN_ERROR)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in [self.process.stdin, self.process.stdout]:
            pipe.close()


def run_login(store, attempt, executable):
    rpc = None
    # Codex's temporary native credential file never leaves the server.
    with tempfile.TemporaryDirectory(prefix='fjordlens-chatgpt-') as directory:
        home = Path(directory)
        home.chmod(0o700)
        try:
            rpc = CodexRPC(home, executable)
            rpc.request('initialize', {'clientInfo': {'name': 'fjordlens', 'title': 'FjordLens', 'version': '1.0'}})
            rpc.send({'method': 'initialized', 'params': {}})
            login = rpc.request('account/login/start', {'type': 'chatgptDeviceCode'})
            url = login.get('verificationUrl', '')
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'auth.openai.com' or parsed.username or parsed.password:
                raise ValueError(LOGIN_ERROR)
            code = login.get('userCode')
            if not isinstance(code, str) or not code or len(code) > 128:
                raise ValueError(LOGIN_ERROR)
            if not store.update(attempt, state='waiting', verification_url=url, user_code=code):
                return
            while store.active(attempt):
                if rpc.notifications:
                    message = rpc.notifications.pop(0)
                else:
                    try:
                        message = rpc.messages.get(timeout=1)
                    except queue.Empty:
                        continue
                if message is None:
                    raise ValueError(LOGIN_ERROR)
                if message.get('method') == 'account/login/completed':
                    params = message.get('params', {})
                    if params.get('loginId') != login.get('loginId'):
                        continue
                    if not params.get('success'):
                        raise ValueError(LOGIN_ERROR)
                    account = rpc.request('account/read', {'refreshToken': False}).get('account') or {}
                    auth = json.loads((home / 'auth.json').read_text())
                    store.complete(attempt, account, auth)
                    return
            rpc.request('account/login/cancel', {'loginId': login['loginId']}, timeout=5)
        except Exception:
            # Never expose native errors, credentials, device codes or raw RPC messages.
            store.update(attempt, state='failed', user_code=None, verification_url=None)
        finally:
            if rpc:
                rpc.close()


def launch_login(store, attempt, executable):
    # A dedicated bounded worker survives web-worker recycling. State is in SQLite
    # so status/cancel work with multiple Gunicorn workers and after refresh.
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker',
                                str(store.path), attempt, executable], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=os.name != 'nt',
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    process.stdin.write(store.key)
    process.stdin.close()
    threading.Thread(target=process.wait, daemon=True).start()


def register(app, data_dir):
    store = ConnectionStore(data_dir, app.secret_key)
    bp = Blueprint('chatgpt_connection', __name__)

    @bp.before_request
    @login_required
    def protect():
        if getattr(current_user, 'role', 'user') != 'admin':
            return jsonify(ok=False, error='Forbidden'), 403
        if request.method != 'GET':
            supplied = request.headers.get('X-ChatGPT-CSRF', '')
            expected = session.get('chatgpt_csrf', '')
            if not expected or not secrets.compare_digest(supplied, expected):
                return jsonify(ok=False, error='Genindlæs indstillingerne og prøv igen.'), 403

    @bp.after_request
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    @bp.get('/api/ai/chatgpt/connection')
    def status():
        csrf = session.setdefault('chatgpt_csrf', secrets.token_urlsafe(32))
        try:
            return jsonify(ok=True, csrf=csrf, **store.status(current_user.id))
        except Exception:
            return jsonify(ok=False, error='ChatGPT-kontostatus kunne ikke læses.'), 503

    @bp.post('/api/ai/chatgpt/login')
    def login():
        executable = shutil.which('codex')
        if not executable:
            return jsonify(ok=False, error='ChatGPT-login mangler i serverinstallationen. Opdatér FjordLens-containeren.'), 503
        try:
            attempt = store.start(current_user.id)
        except ValueError as error:
            return jsonify(ok=False, error=str(error)), 409
        try:
            launch_login(store, attempt, executable)
        except Exception:
            store.update(attempt, state='failed')
            return jsonify(ok=False, error=LOGIN_ERROR), 503
        return jsonify(ok=True, **store.status(current_user.id)), 202

    @bp.delete('/api/ai/chatgpt/login')
    def cancel():
        store.cancel(current_user.id)
        return jsonify(ok=True, **store.status(current_user.id))

    @bp.delete('/api/ai/chatgpt/connection')
    def disconnect():
        store.cancel(current_user.id, disconnect=True)
        return jsonify(ok=True, connected=False)

    app.register_blueprint(bp)
    from chatgpt_analysis import register as register_analysis
    register_analysis(app=app, store=store, protect=protect, no_cache=no_cache)


if __name__ == '__main__' and len(sys.argv) == 5 and sys.argv[1] == '--worker':
    store = ConnectionStore(Path(sys.argv[2]).parent, b'worker-placeholder')
    store.key = sys.stdin.buffer.read(1024)
    store.cipher = Fernet(store.key)
    run_login(store, sys.argv[3], sys.argv[4])
