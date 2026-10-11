import pytest
import chatgpt_analysis as analysis
import chatgpt_connection as connection
from test_chatgpt_analysis import store, capacity, fake_rpc, running_job, image_bytes


def test_62_percent_remaining_can_start_at_50_but_boundary_waits(store):
    analysis.budget_settings(store, 50)
    status = analysis.budget_status(store, capacity(38, 38))
    assert not status['waiting']
    assert all(window['remaining_percent'] == 62 for window in status['usage']['windows'])
    assert not analysis.budget_status(store, capacity(49.9, 49.9))['waiting']
    assert analysis.budget_status(store, capacity(50, 50))['waiting']


def test_pause_and_preference_survive_reopening_store_and_result_expiry(store, monkeypatch):
    analysis.budget_settings(store, 50)
    assert analysis.budget_status(store, capacity(50, 50))['waiting']
    running_job(store)
    with store.db() as db:
        job = store.read(db, 'test_analysis')
        job['expires_at'] = 0
        store.write(db, 'test_analysis', job)
        assert analysis.read_job(store, db) is None
    reopened = connection.ConnectionStore(store.path.parent, 'test-secret')
    assert analysis.budget_settings(reopened)['remaining_percent'] == 50
    assert analysis.budget_settings(reopened)['wait']
    # Lowering the threshold or a small correction to usage cannot cancel a pause.
    analysis.budget_settings(reopened, 20)
    assert analysis.budget_status(reopened, capacity(45, 45))['waiting']
    monkeypatch.setattr(analysis.time, 'time', lambda: 1900000200)
    # Passing the recorded reset timestamp alone is not proof of fresh capacity.
    assert analysis.budget_status(reopened, capacity(45, 45))['waiting']
    reset = capacity(1, 1)
    reset['rateLimitsByLimitId']['codex']['primary']['resetsAt'] += 300*60
    reset['rateLimitsByLimitId']['codex']['secondary']['resetsAt'] += 10080*60
    assert not analysis.budget_status(reopened, reset)['waiting']
    assert analysis.budget_settings(reopened)['wait'] is None


def test_every_blocked_window_needs_confirmed_reset(store, monkeypatch):
    analysis.budget_settings(store, 50)
    analysis.budget_status(store, capacity(70, 70))
    monkeypatch.setattr(analysis.time, 'time', lambda: 1900000200)
    reset = capacity(1, 1)
    reset['rateLimitsByLimitId']['codex']['primary']['resetsAt'] += 300*60
    assert analysis.budget_status(store, reset)['waiting'], 'weekly reset still unconfirmed'
    reset['rateLimitsByLimitId']['codex']['secondary']['resetsAt'] += 10080*60
    assert not analysis.budget_status(store, reset)['waiting']


def test_unknown_capacity_preserves_wait_and_never_starts_inference(store, monkeypatch):
    analysis.budget_settings(store, 50)
    analysis.budget_status(store, capacity(70, 70))
    with pytest.raises(analysis.AnalysisError):
        analysis.budget_status(store, {})
    assert analysis.budget_settings(store)['wait']
    calls, _ = fake_rpc(monkeypatch, capacity(38, 38))
    running_job(store)
    analysis.run_analysis(store, 'test', image_bytes(), 'image-model', 'codex')
    assert not any(call['method'] in ('thread/start', 'turn/start') for call in calls)
    with store.db() as db:
        job = store.read(db, 'test_analysis')
        assert job['state'] == 'waiting' and 'result' not in job


def test_account_rotation_keeps_pause_but_other_account_checks_its_own_capacity(store):
    analysis.budget_status(store, capacity(70, 70))
    with store.db() as db:
        record = store.read(db, 'connection')
        record['codex_auth']['tokens']['access_token'] = 'rotated'
        store.write(db, 'connection', record)
    assert analysis.budget_status(store, capacity(38, 38))['waiting']
    with store.db() as db:
        record['email'] = 'other@example.com'
        store.write(db, 'connection', record)
    assert not analysis.budget_status(store, capacity(38, 38))['waiting']


def test_exhausted_included_capacity_also_persists_the_pause(store):
    data = capacity(100, 100)
    data['ordinaryUsageAllowed'] = False
    assert analysis.budget_status(store, data)['waiting']
    assert analysis.budget_settings(store)['wait']


def test_budget_api_saves_threshold_and_fetches_real_rpc_status(store, monkeypatch):
    from flask import Flask
    from flask_login import LoginManager, UserMixin
    app = Flask(__name__)
    app.secret_key = 'test-secret'
    login = LoginManager(app)
    class User(UserMixin):
        id = 'admin'
        role = 'admin'
    login.user_loader(lambda ident: User())
    connection.register(app, store.path.parent)
    monkeypatch.setattr(analysis.shutil, 'which', lambda _: 'codex')
    calls, _ = fake_rpc(monkeypatch, capacity(38, 38))
    client = app.test_client()
    url = '/api/ai/chatgpt/analysis-budget'
    assert client.get(url).status_code == 401
    with client.session_transaction() as session:
        session['_user_id'] = 'admin'
    csrf = client.get('/api/ai/chatgpt/connection').json['csrf']
    assert client.put(url, json={'remaining_percent':50}).status_code == 403
    headers = {'X-ChatGPT-CSRF':csrf}
    for value in (-1, 100, True, '50'):
        assert client.put(url, json={'remaining_percent':value}, headers=headers).status_code == 400
    data = client.put(url, json={'remaining_percent':50}, headers=headers).json
    assert data['budget']['remaining_percent'] == 50
    assert data['budget']['usage']['windows'][0]['remaining_percent'] == 62
    assert data['budget']['fresh'] and not data['budget']['waiting']
    assert any(call['method'] == 'account/rateLimits/read' for call in calls)
    assert not any(call['method'] == 'turn/start' for call in calls)
    # A failed later read cannot manufacture fresh capacity or erase a saved pause.
    analysis.budget_status(store, capacity(70, 70))
    fake_rpc(monkeypatch, {})
    data = client.get(url).json
    assert data['budget']['waiting'] and not data['budget']['fresh']
