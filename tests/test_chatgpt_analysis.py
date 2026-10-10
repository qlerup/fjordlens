import io
import json
import queue
import time

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin
from PIL import Image

import chatgpt_analysis as analysis
import chatgpt_connection as connection
from chatgpt_analysis_schema import SCHEMA


def sample(schema):
    kind = schema['type']
    if isinstance(kind, list):
        return None
    if kind == 'object':
        return {k: sample(v) for k, v in schema['properties'].items()}
    if kind == 'array':
        return []
    if kind == 'string':
        return schema.get('enum', ['Et barn holder en rød bold.'])[0]
    if kind == 'number':
        return 0.8


def capacity(used=20, secondary=30):
    return dict(ordinaryUsageAllowed=True, rateLimitsByLimitId={'codex': {
        'primary': dict(usedPercent=used, windowDurationMins=300, resetsAt=1900000000),
        'secondary': dict(usedPercent=secondary, windowDurationMins=10080, resetsAt=1900000100)}})


def image_bytes():
    output = io.BytesIO()
    Image.new('RGB', (50, 20), 'red').save(output, 'PNG')
    return output.getvalue()


@pytest.fixture
def store(tmp_path):
    store = connection.ConnectionStore(tmp_path, 'test-secret')
    attempt = store.start('admin')
    store.complete(attempt, {'type': 'chatgpt', 'email': 'test@example.com'},
                   {'tokens': {'access_token': 'test-secret', 'refresh_token': 'refresh'}})
    return store


def running_job(store):
    with store.db() as db:
        store.write(db, 'test_analysis', dict(id='test', owner='admin', state='running',
                    deadline=time.time() + 180, expires_at=time.time() + 900))


def fake_rpc(monkeypatch, quota=None, text=None, status='completed', logout=None, tools=False):
    calls, homes = [], []
    class FakeRPC:
        def __init__(self, home, executable):
            homes.append(home)
            self.home = home
            self.messages = queue.Queue()
            self.notifications = []
        def send(self, message):
            calls.append(message)
        def request(self, method, params=None, timeout=20):
            calls.append(dict(method=method, params=params))
            if method == 'account/read':
                if logout:
                    logout()
                return {'account': {'type': 'chatgpt'}}
            if method == 'model/list':
                return {'data': [{'model': 'image-model', 'displayName': 'Billedmodel',
                                  'inputModalities': ['text', 'image'], 'defaultReasoningEffort': 'low'}]}
            if method == 'account/rateLimits/read':
                return quota if quota is not None else capacity()
            if method == 'thread/start':
                return {'thread': {'id': 'thread'}}
            if method == 'turn/start':
                if tools:
                    self.messages.put({'id': 'tool-1', 'method': 'item/tool/call'})
                self.notifications = [dict(method='item/completed', params=dict(threadId='thread', turnId='turn',
                    item=dict(id='answer', type='agentMessage', text=text if text is not None else json.dumps(sample(SCHEMA))))),
                    dict(method='turn/completed', params=dict(threadId='thread', turn=dict(id='turn', status=status)))]
                if tools:
                    self.notifications = []
                return {'turn': {'id': 'turn'}}
            return {}
        def close(self):
            calls.append(dict(method='close'))
    monkeypatch.setattr(analysis, 'CodexRPC', FakeRPC)
    return calls, homes


@pytest.mark.parametrize('used,secondary', [(78, 10), (10, 90), (80, 80)])
def test_any_window_blocks_with_safety_margin(used, secondary):
    with pytest.raises(analysis.AnalysisError, match='forbrugsgrænsen'):
        analysis.usage_status(capacity(used, secondary), 80)


@pytest.mark.parametrize('value', [None, True, -1, 101, float('nan'), '0'])
def test_invalid_usage_never_means_free_capacity(value):
    with pytest.raises(analysis.AnalysisError, match='ukendt'):
        analysis.usage_status(capacity(value), 80)


def test_missing_ordinary_capacity_is_blocked_even_with_low_percent():
    data = capacity()
    data['ordinaryUsageAllowed'] = None
    with pytest.raises(analysis.AnalysisError, match='inkluderet kapacitet'):
        analysis.usage_status(data, 80)
    data['ordinaryUsageAllowed'] = False
    with pytest.raises(analysis.AnalysisError):
        analysis.usage_status(data, 80)
    assert analysis.usage_status(capacity(), 80)['windows'][1]['duration_minutes'] == 10080


def test_invalid_json_and_schema_are_rejected():
    for value in ['not JSON', '{"summary":"hej"}', json.dumps(dict(sample(SCHEMA), extra='unexpected'))]:
        with pytest.raises(analysis.AnalysisError):
            analysis.validate_result(value)


def test_image_is_reencoded_and_not_written_to_library():
    prepared = analysis.prepare_image(io.BytesIO(image_bytes()))
    with Image.open(io.BytesIO(prepared)) as image:
        assert image.format == 'JPEG' and image.size == (50, 20)
        assert not image.getexif()
    with pytest.raises(analysis.AnalysisError):
        analysis.prepare_image(io.BytesIO(b'<svg>not an image</svg>'))


def test_success_has_isolated_image_turn_schema_and_temp_cleanup(store, monkeypatch):
    calls, homes = fake_rpc(monkeypatch)
    running_job(store)
    analysis.run_analysis(store, 'test', image_bytes(), 'image-model', 80, 'codex')
    with store.db() as db:
        job = store.read(db, 'test_analysis')
    assert job['state'] == 'completed'
    assert job['result']['summary'] == 'Et barn holder en rød bold.'
    assert job['metadata']['temporary'] and job['metadata']['image_id'] is None
    turn = next(c for c in calls if c['method'] == 'turn/start')['params']
    assert turn['outputSchema'] == SCHEMA
    assert turn['input'][1]['url'].startswith('data:image/jpeg;base64,')
    thread = next(c for c in calls if c['method'] == 'thread/start')['params']
    assert thread['ephemeral'] and thread['sandbox'] == 'read-only'
    assert thread['config']['features.shell_tool'] is False
    assert not any(h.exists() for h in homes)
    assert b'Et barn' not in store.path.read_bytes()


@pytest.mark.parametrize('quota,text,status', [(capacity(90), None, 'completed'),
    ({}, None, 'completed'), (capacity(), '{}', 'completed'), (capacity(), None, 'failed')])
def test_blocked_and_failed_runs_are_never_success(store, monkeypatch, quota, text, status):
    calls, homes = fake_rpc(monkeypatch, quota, text, status)
    running_job(store)
    analysis.run_analysis(store, 'test', image_bytes(), 'image-model', 80, 'codex')
    with store.db() as db:
        job = store.read(db, 'test_analysis')
    assert job['state'] == 'failed' and 'result' not in job
    if not quota or quota == capacity(90):
        assert not any(c['method'] == 'turn/start' for c in calls)
    assert not any(h.exists() for h in homes)


def test_tool_requests_are_rejected(store, monkeypatch):
    calls, _ = fake_rpc(monkeypatch, tools=True)
    running_job(store)
    analysis.run_analysis(store, 'test', image_bytes(), 'image-model', 80, 'codex')
    assert any(c.get('error', {}).get('code') == -32601 for c in calls)
    with store.db() as db:
        assert store.read(db, 'test_analysis')['state'] == 'failed'


def test_logout_during_rpc_cannot_restore_credentials(store, monkeypatch):
    fake_rpc(monkeypatch, logout=lambda: store.cancel('admin', disconnect=True))
    with analysis.connected_rpc(store, 'codex'):
        pass
    assert not store.status('admin')['connected']


def test_account_gate_is_shared_between_workers(store, monkeypatch):
    fake_rpc(monkeypatch)
    second = connection.ConnectionStore(store.path.parent, 'test-secret')
    with analysis.connected_rpc(store, 'codex'):
        with pytest.raises(analysis.AnalysisError, match='optaget'):
            with analysis.connected_rpc(second, 'codex'):
                pass
    with analysis.connected_rpc(second, 'codex'):
        pass


def test_expired_worker_is_recoverable_and_result_expires(store, monkeypatch):
    running_job(store)
    time_now = time.time()
    monkeypatch.setattr(analysis.time, 'time', lambda: time_now + 181)
    with store.db() as db:
        job = analysis.read_job(store, db)
    assert job['state'] == 'failed'
    with store.db() as db:
        job['expires_at'] = 0
        store.write(db, 'test_analysis', job)
    with store.db() as db:
        assert analysis.read_job(store, db) is None


def test_routes_auth_csrf_owner_concurrency_and_delete(store, monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test-secret'
    login = LoginManager(app)
    class User(UserMixin):
        def __init__(self, ident):
            self.id, self.role = ident, 'admin' if ident.startswith('admin') else 'user'
    login.user_loader(User)
    connection.register(app, store.path.parent)
    monkeypatch.setattr(analysis.shutil, 'which', lambda _: 'codex')
    # Keep job running to exercise serialization across requests.
    monkeypatch.setattr(analysis.threading.Thread, 'start', lambda _: None)
    client = app.test_client()
    assert client.post('/api/ai/chatgpt/test-analysis').status_code == 401
    with client.session_transaction() as session:
        session['_user_id'] = 'user'
    assert client.get('/api/ai/chatgpt/test-models').status_code == 403
    with client.session_transaction() as session:
        session['_user_id'] = 'admin'
    csrf = client.get('/api/ai/chatgpt/connection').json['csrf']
    headers = {'X-ChatGPT-CSRF': csrf}
    assert client.post('/api/ai/chatgpt/test-analysis').status_code == 403
    def start():
        return client.post('/api/ai/chatgpt/test-analysis', headers=headers,
                           data={'model': 'image-model', 'threshold': '80', 'image': (io.BytesIO(image_bytes()), 'photo.png')})
    response = start()
    assert response.status_code == 202
    ident = response.json['id']
    assert start().status_code == 409
    assert client.get('/api/ai/chatgpt/test-analysis/' + ident).json['state'] == 'running'
    assert client.delete('/api/ai/chatgpt/test-analysis/' + ident, headers=headers).status_code == 409
    with client.session_transaction() as session:
        session['_user_id'] = 'admin-other'
    assert client.get('/api/ai/chatgpt/test-analysis/' + ident).status_code == 404
    analysis.update_job(store, ident, state='failed', error='simulated')
    with client.session_transaction() as session:
        session['_user_id'] = 'admin'
    assert client.delete('/api/ai/chatgpt/test-analysis/' + ident, headers=headers).status_code == 200
    assert client.get('/api/ai/chatgpt/test-analysis/' + ident).status_code == 404
    assert client.get('/api/ai/chatgpt/test-analysis/' + ident).headers['Cache-Control'] == 'no-store'
