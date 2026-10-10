import io
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask
from flask_login import LoginManager, UserMixin

import chatgpt_connection as connection
from scripts import chatgpt_login as helper


@pytest.fixture
def credentials(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=public))
    monkeypatch.setattr(connection, 'KEYS', keys)
    monkeypatch.setattr(helper.jwt, 'PyJWKClient', lambda *a, **k: keys)
    claims = dict(iss=connection.ISSUER, aud='oaiapp_test', sub='account-1',
                  exp=int(time.time()) + 3600, iat=int(time.time()), nonce='nonce', email='test@example.com')
    record = dict(client_id='oaiapp_test', issuer=connection.ISSUER, subject='account-1',
                  id_token=jwt.encode(claims, private, algorithm='RS256'),
                  access_token='secret-access', refresh_token='secret-refresh', scopes=helper.SCOPES.split())
    return record, claims, private


def test_official_authorization_parameters_and_pkce():
    url = helper.authorization_url('urn:uuid:host', 'http://127.0.0.1:1455/auth/callback', 'state', 'nonce', 'verifier')
    params = parse_qs(urlsplit(url).query)
    assert params['client_id'] == ['dynamic_agent_client']
    assert params['agent_name_hint'] == ['FjordLens']
    assert params['code_challenge_method'] == ['S256']
    assert params['code_challenge'] != ['verifier']
    assert 'chatgpt.tokens.use.direct' in params['scope'][0]
    assert 'agent_name_hint' not in parse_qs(urlsplit(helper.authorization_url('host', 'uri', 's', 'n', 'v', 'oaiapp_existing')).query)


def test_exchange_rejects_state_denial_and_changed_registration_before_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr(helper.requests, 'post', post)
    for params, expected in [({'state': ['wrong']}, None),
                             ({'state': ['s'], 'error': ['access_denied']}, None),
                             ({'state': ['s'], 'client_id': ['oaiapp_other'], 'code': ['c']}, 'oaiapp_selected'),
                             ({'state': ['s'], 'code': ['c']}, None)]:
        with pytest.raises(ValueError):
            helper.exchange(params, 's', 'n', 'v', 'uri', expected)
    post.assert_not_called()


def test_exchange_uses_issued_client_and_checks_nonce_and_scope(credentials, monkeypatch):
    record, claims, private = credentials
    tokens = dict(record, scope=helper.SCOPES)
    post = Mock(return_value=SimpleNamespace(status_code=200, json=lambda: tokens))
    monkeypatch.setattr(helper.requests, 'post', post)
    params = {'state': ['s'], 'client_id': ['oaiapp_test'], 'code': ['code']}
    result = helper.exchange(params, 's', 'nonce', 'verifier', 'http://127.0.0.1:1455/auth/callback')
    assert result['subject'] == 'account-1'
    body = post.call_args.kwargs['data']
    assert body['client_id'] == 'oaiapp_test' and body['code_verifier'] == 'verifier'
    with pytest.raises(ValueError):
        helper.exchange(params, 's', 'different-nonce', 'v', 'uri')
    tokens['scope'] = 'openid email'
    with pytest.raises(ValueError):
        helper.exchange(params, 's', 'nonce', 'v', 'uri')


@pytest.mark.parametrize('field,value', [('iss', 'https://evil.example'), ('aud', 'wrong-client'), ('exp', 1)])
def test_import_rejects_invalid_signed_claims(credentials, field, value):
    record, claims, private = credentials
    claims[field] = value
    record['id_token'] = jwt.encode(claims, private, algorithm='RS256')
    with pytest.raises(jwt.PyJWTError):
        connection.verify_identity(record)


def test_import_rejects_bad_signature_and_subject(credentials):
    record, claims, _ = credentials
    record['subject'] = 'different-account'
    with pytest.raises(ValueError):
        connection.verify_identity(record)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    record['id_token'] = jwt.encode(claims, other, algorithm='RS256')
    with pytest.raises(jwt.PyJWTError):
        connection.verify_identity(record)


def test_encrypted_persistence_host_id_and_disconnect(tmp_path, credentials):
    record, _, _ = credentials
    store = connection.ConnectionStore(tmp_path, 'local-secret')
    identity = connection.verify_identity(record)
    record['ext_agent_host_id'] = 'laptop-host'
    store.save(record, identity)
    assert b'secret-access' not in store.path.read_bytes()
    assert b'secret-refresh' not in store.path.read_bytes()
    assert connection.ConnectionStore(tmp_path, 'local-secret').status()['email'] == 'test@example.com'
    with store.db() as db:
        host = db.execute('SELECT value FROM host').fetchone()[0]
        encrypted = db.execute('SELECT value FROM connection').fetchone()[0]
    assert json.loads(store.cipher.decrypt(encrypted))['ext_agent_host_id'] == host
    assert host != 'laptop-host'
    store.disconnect()
    assert store.status() == {'connected': False}
    with store.db() as db:
        assert db.execute('SELECT value FROM host').fetchone()[0] == host


def test_routes_require_admin_csrf_secure_transport_and_return_no_tokens(tmp_path, credentials):
    app = Flask(__name__)
    app.secret_key = 'test-secret'
    app.config['SERVER_NAME'] = 'server.example'
    login = LoginManager(app)

    class User(UserMixin):
        def __init__(self, role):
            self.id = role
            self.role = role

    login.user_loader(lambda role: User(role))
    connection.register(app, tmp_path)
    client = app.test_client()
    assert client.get('/api/ai/chatgpt/connection').status_code == 401
    for role in ['user', 'manager']:
        with client.session_transaction() as sess:
            sess['_user_id'] = role
        assert client.get('/api/ai/chatgpt/connection').status_code == 403
        assert client.get('/api/ai/chatgpt/login-helper').status_code == 403
    with client.session_transaction() as sess:
        sess['_user_id'] = 'admin'
    csrf = client.get('/api/ai/chatgpt/connection').json['csrf']
    assert client.delete('/api/ai/chatgpt/connection').status_code == 403
    headers = {'X-ChatGPT-CSRF': csrf}
    data = lambda: {'connection': (io.BytesIO(json.dumps(credentials[0]).encode()), 'connection.json')}
    assert client.post('/api/ai/chatgpt/connection', headers=headers, data=data(), base_url='http://server.example').status_code == 400
    result = client.post('/api/ai/chatgpt/connection', headers=headers, data=data(), base_url='https://server.example')
    assert result.status_code == 200
    assert result.json['connected'] and not result.json['inference_enabled']
    invalid = dict(credentials[0], subject='different-account')
    rejected = client.post('/api/ai/chatgpt/connection', headers=headers,
                           data={'connection': (io.BytesIO(json.dumps(invalid).encode()), 'bad.json')},
                           base_url='https://server.example')
    assert rejected.status_code == 400
    assert client.get('/api/ai/chatgpt/connection').json['email'] == 'test@example.com'
    status = client.get('/api/ai/chatgpt/connection')
    assert 'secret-access' not in status.get_data(as_text=True)
    assert 'secret-refresh' not in status.get_data(as_text=True)
    assert status.headers['Cache-Control'] == 'no-store'
    assert client.get('/api/ai/chatgpt/login-helper').mimetype == 'application/zip'
    assert client.delete('/api/ai/chatgpt/connection', headers=headers).json['connected'] is False
