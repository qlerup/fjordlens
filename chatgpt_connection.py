"""ChatGPT account linking only. No inference or photo transfer."""
import base64
import hashlib
import io
import json
import os
import secrets
import sqlite3
import time
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

import jwt
from cryptography.fernet import Fernet
from flask import Blueprint, jsonify, request, session, send_file
from flask_login import current_user, login_required

ISSUER = 'https://auth.openai.com'
JWKS = ISSUER + '/.well-known/jwks.json'
KEYS = jwt.PyJWKClient(JWKS, timeout=10, lifespan=300)


def verify_identity(record):
    client = record.get('client_id', '')
    if not isinstance(client, str) or not client.startswith('oaiapp_') or len(client) > 256:
        raise ValueError('Forbindelsesfilen mangler et registreret ChatGPT-klient-ID.')
    token = record.get('id_token')
    if not isinstance(token, str) or not token:
        raise ValueError('Forbindelsesfilen mangler et identitetstoken.')
    key = KEYS.get_signing_key_from_jwt(token).key
    identity = jwt.decode(token, key, algorithms=['RS256'], issuer=ISSUER,
                          audience=client, options={'require': ['sub', 'exp', 'iat']}, leeway=5)
    if not isinstance(identity['sub'], str) or not identity['sub']:
        raise ValueError('ChatGPT-identiteten kunne ikke bekræftes.')
    if identity['sub'] != record.get('subject') or record.get('issuer') != ISSUER:
        raise ValueError('Forbindelsesfilens identitet stemmer ikke overens.')
    for name in ['access_token', 'refresh_token']:
        if not isinstance(record.get(name), str) or not record[name] or len(record[name]) > 32768:
            raise ValueError('Forbindelsesfilen mangler loginoplysninger.')
    scopes = record.get('scopes', [])
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes) or 'chatgpt.tokens.use.direct' not in scopes:
        raise ValueError('Adgang til ChatGPT-abonnementet mangler.')
    return identity


class ConnectionStore:
    def __init__(self, data_dir, secret):
        self.path = Path(data_dir) / 'chatgpt-connection.sqlite3'
        secret = secret.encode() if isinstance(secret, str) else secret
        self.cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'fjordlens-chatgpt-v1:' + secret).digest()))

    @contextmanager
    def db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        self.path.chmod(0o600)
        conn.execute('CREATE TABLE IF NOT EXISTS connection (id INTEGER PRIMARY KEY, value BLOB)')
        conn.execute('CREATE TABLE IF NOT EXISTS host (id INTEGER PRIMARY KEY, value TEXT)')
        conn.execute('INSERT OR IGNORE INTO host VALUES (1, ?)', ('urn:uuid:' + str(uuid.uuid4()),))
        conn.commit()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def save(self, record, identity):
        with self.db() as conn:
            host = conn.execute('SELECT value FROM host WHERE id=1').fetchone()[0]
            # The VM keeps its own stable host ID when importing a local session.
            clean = {k: record[k] for k in ['client_id', 'access_token', 'refresh_token', 'id_token']}
            clean.update(issuer=ISSUER, subject=identity['sub'], email=identity.get('email', ''),
                         ext_agent_host_id=host, connected_at=int(time.time()),
                         scopes=record['scopes'], expires_at=int(record.get('expires_at', 0)))
            conn.execute('INSERT OR REPLACE INTO connection VALUES (1, ?)',
                         (self.cipher.encrypt(json.dumps(clean).encode()),))

    def status(self):
        with self.db() as conn:
            row = conn.execute('SELECT value FROM connection WHERE id=1').fetchone()
        if not row:
            return {'connected': False}
        record = json.loads(self.cipher.decrypt(row[0]))
        return {'connected': True, 'email': record['email'], 'connected_at': record['connected_at'],
                'inference_enabled': False}

    def disconnect(self):
        with self.db() as conn:
            conn.execute('DELETE FROM connection')


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
            return jsonify(ok=True, csrf=csrf, **store.status())
        except Exception:
            return jsonify(ok=False, error='Den gemte ChatGPT-forbindelse kunne ikke læses.'), 503

    @bp.post('/api/ai/chatgpt/connection')
    def connect():
        proxy_https = (os.environ.get('CHATGPT_TRUST_PROXY_HTTPS') == '1'
                       and request.headers.get('X-Forwarded-Proto', '').lower() == 'https')
        if not request.is_secure and not proxy_https and request.host.split(':')[0] not in {'127.0.0.1', 'localhost'}:
            return jsonify(ok=False, error='Åbn FjordLens via HTTPS for at overføre loginoplysninger sikkert.'), 400
        if request.content_length is None or request.content_length > 100000:
            return jsonify(ok=False, error='Forbindelsesfilen er for stor.'), 413
        uploaded = request.files.get('connection')
        if uploaded is None:
            return jsonify(ok=False, error='Vælg forbindelsesfilen fra loginprogrammet.'), 400
        try:
            raw = uploaded.read(65537)
            if len(raw) > 65536:
                return jsonify(ok=False, error='Forbindelsesfilen er for stor.'), 413
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError('Forbindelsesfilen er ugyldig.')
            identity = verify_identity(record)
            store.save(record, identity)
            return jsonify(ok=True, **store.status())
        except (ValueError, jwt.PyJWTError):
            return jsonify(ok=False, error='Login kunne ikke bekræftes. Lav et nyt login og vælg den nye forbindelsesfil.'), 400
        except Exception:
            return jsonify(ok=False, error='ChatGPT-forbindelsen kunne ikke gemmes. Prøv igen.'), 503

    @bp.delete('/api/ai/chatgpt/connection')
    def disconnect():
        store.disconnect()
        return jsonify(ok=True, connected=False)

    @bp.get('/api/ai/chatgpt/login-helper')
    def helper():
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(Path(__file__).parent / 'scripts/chatgpt_login.py', 'chatgpt_login.py')
            bundle.writestr('requirements.txt', 'requests>=2.31,<3\nPyJWT[crypto]>=2.8,<3\n')
            bundle.writestr('README.txt', 'FjordLens ChatGPT-login\n\nKræver Python 3.10 eller nyere på din computer.\n'
                             'Udpak mappen og kør:\npython -m pip install -r requirements.txt\npython chatgpt_login.py\n\n'
                             'En anden konto/workspace: python chatgpt_login.py --new-account\n\n'
                             'Login åbnes hos OpenAI i din browser. Vælg derefter forbindelsesfilen i FjordLens via HTTPS.\n'
                             'Filen indeholder loginoplysninger: del den ikke, og slet den efter overførslen.\n')
        output.seek(0)
        return send_file(output, mimetype='application/zip', as_attachment=True, download_name='fjordlens-chatgpt-login.zip')

    app.register_blueprint(bp)
