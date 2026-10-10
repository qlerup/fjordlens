import json
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

import chatgpt_connection as connection

ACCOUNT = {'type': 'chatgpt', 'email': 'test@example.com', 'planType': 'plus'}
AUTH = {'auth_mode': 'chatgpt', 'tokens': {'access_token': 'secret-access', 'refresh_token': 'secret-refresh'}}


@pytest.fixture
def store(tmp_path):
    return connection.ConnectionStore(tmp_path, 'test-secret')


def test_persistence_is_encrypted_and_excludes_tokens_from_status(store):
    attempt = store.start('1')
    assert store.complete(attempt, ACCOUNT, AUTH)
    assert b'secret-access' not in store.path.read_bytes()
    assert b'secret-refresh' not in store.path.read_bytes()
    reopened = connection.ConnectionStore(store.path.parent, 'test-secret')
    status = reopened.status('1')
    assert status['connected'] and status['email'] == 'test@example.com'
    assert not status['inference_enabled']
    assert 'secret-access' not in json.dumps(status)
    reopened.cancel('1', disconnect=True)
    assert not reopened.status('1')['connected']


def test_concurrent_workers_can_only_start_one_login(store):
    def start():
        try:
            return store.start('1')
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: start(), range(4)))
    assert sum(bool(x) for x in results) == 1


def test_codes_are_only_visible_to_initiating_admin_and_clear_on_cancel(store):
    attempt = store.start('1')
    store.update(attempt, state='waiting', user_code='ABCD-1234', verification_url='https://auth.openai.com/codex/device')
    assert store.status('1')['login']['user_code'] == 'ABCD-1234'
    assert store.status('2')['login'] == {'state': 'busy'}
    store.cancel('2')
    assert store.active(attempt)
    store.cancel('1')
    assert not store.active(attempt)
    assert not store.complete(attempt, ACCOUNT, AUTH)
    assert not store.status('1')['connected']


def test_failed_or_expired_replacement_preserves_connected_account(store):
    first = store.start('1')
    store.complete(first, ACCOUNT, AUTH)
    second = store.start('1')
    store.update(second, state='failed')
    assert store.status('1')['connected']
    third = store.start('1')
    store.update(third, expires_at=time.time() - 1, user_code='EXPIRED')
    assert store.status('1')['login']['state'] == 'expired'
    assert 'user_code' not in store.status('1')['login']
    assert not store.complete(third, ACCOUNT, AUTH)
    assert store.status('1')['email'] == ACCOUNT['email']


def fake_rpc(monkeypatch, url='https://auth.openai.com/codex/device', success=True, cancel=None):
    calls = []
    class FakeRPC:
        def __init__(self, home, executable):
            self.home = home
            self.notifications = []
            self.messages = queue.Queue()
        def request(self, method, params=None, timeout=20):
            calls.append((method, params))
            if method == 'initialize':
                return {}
            if method == 'account/login/start':
                self.messages.put({'method': 'account/login/completed', 'params': {'loginId': 'login-1', 'success': success}})
                return {'loginId': 'login-1', 'userCode': 'ABCD-1234', 'verificationUrl': url}
            if method == 'account/read':
                (self.home / 'auth.json').write_text(json.dumps(AUTH))
                if cancel:
                    cancel()
                return {'account': ACCOUNT}
            return {}
        def send(self, message):
            calls.append((message['method'], message.get('params')))
        def close(self):
            calls.append(('close', None))
    monkeypatch.setattr(connection, 'CodexRPC', FakeRPC)
    return calls


def test_worker_uses_official_device_protocol_and_saves_only_after_completion(store, monkeypatch):
    calls = fake_rpc(monkeypatch)
    attempt = store.start('1')
    connection.run_login(store, attempt, 'codex')
    assert store.status('1')['connected']
    assert ('account/login/start', {'type': 'chatgptDeviceCode'}) in calls
    assert ('account/read', {'refreshToken': False}) in calls
    assert not any(name.startswith('thread/') or name.startswith('turn/') for name, _ in calls)
    assert calls[-1][0] == 'close'


@pytest.mark.parametrize('url,success', [('https://evil.example/device', True),
                                         ('http://auth.openai.com/device', True),
                                         ('https://auth.openai.com/codex/device', False)])
def test_worker_rejects_bad_url_or_failed_login(store, monkeypatch, url, success):
    fake_rpc(monkeypatch, url, success)
    attempt = store.start('1')
    connection.run_login(store, attempt, 'codex')
    assert not store.status('1')['connected']
    assert store.status('1')['login']['state'] == 'failed'
    assert 'user_code' not in store.status('1')['login']


def test_cancel_racing_success_cannot_restore_credentials(store, monkeypatch):
    fake_rpc(monkeypatch, cancel=lambda: store.cancel('1', disconnect=True))
    connection.run_login(store, store.start('1'), 'codex')
    assert not store.status('1')['connected']


def test_routes_roles_csrf_start_cancel_logout_and_no_file_import(tmp_path, monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test-secret'
    login = LoginManager(app)
    class User(UserMixin):
        def __init__(self, ident):
            self.id = ident
            self.role = ident
    login.user_loader(lambda ident: User(ident))
    connection.register(app, tmp_path)
    launch = Mock()
    monkeypatch.setattr(connection, 'launch_login', launch)
    monkeypatch.setattr(connection.shutil, 'which', lambda _: '/bin/codex')
    client = app.test_client()
    assert client.get('/api/ai/chatgpt/connection').status_code == 401
    for role in ['user', 'manager', 'admin']:
        with client.session_transaction() as session:
            session['_user_id'] = role
        status = client.get('/api/ai/chatgpt/connection')
        assert status.status_code == (200 if role == 'admin' else 403)
        assert client.post('/api/ai/chatgpt/login').status_code == 403
    csrf = client.get('/api/ai/chatgpt/connection').json['csrf']
    headers = {'X-ChatGPT-CSRF': csrf}
    result = client.post('/api/ai/chatgpt/login', headers=headers)
    assert result.status_code == 202 and result.json['login']['state'] == 'starting'
    launch.assert_called_once()
    assert client.post('/api/ai/chatgpt/login', headers=headers).status_code == 409
    assert client.delete('/api/ai/chatgpt/login', headers=headers).status_code == 200
    assert client.delete('/api/ai/chatgpt/connection', headers=headers).json['connected'] is False
    assert client.get('/api/ai/chatgpt/login-helper').status_code == 404
    assert client.post('/api/ai/chatgpt/connection', headers=headers).status_code == 405
    assert client.get('/api/ai/chatgpt/connection').headers['Cache-Control'] == 'no-store'
    monkeypatch.setattr(connection.shutil, 'which', lambda _: None)
    assert client.post('/api/ai/chatgpt/login', headers=headers).status_code == 503
