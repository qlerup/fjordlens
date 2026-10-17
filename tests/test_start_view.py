import unittest
from unittest.mock import patch

import app as fl
import test_manager_role as fixtures


class StartViewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ManagerRoleTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def test_saved_per_user_and_loaded_in_new_session(self):
        client = self.fixture.client(2)
        self.assertEqual(client.get('/api/me').get_json()['item']['start_view'], 'timeline')
        response = client.post('/api/me/start-view', json={'start_view': 'mapper', 'user_id': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fixture.client(2).get('/api/me').get_json()['item']['start_view'], 'mapper')
        self.assertEqual(self.fixture.client(1).get('/api/me').get_json()['item']['start_view'], 'timeline')
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT start_view FROM users WHERE id=2').fetchone()[0], 'mapper')
        # The initial HTML profile carries the setting before JavaScript starts.
        with patch.object(fl, 'render_template', side_effect=lambda name, **kw: fl.jsonify(kw['user_profile'])):
            self.assertEqual(self.fixture.client(2).get('/').get_json()['start_view'], 'mapper')
        self.assertEqual(client.post('/api/me/start-view', json={'start_view': 'timeline'}).status_code, 200)
        self.assertEqual(self.fixture.client(2).get('/api/me').get_json()['item']['start_view'], 'timeline')

    def test_invalid_choice_rejected_without_changing_preference(self):
        client = self.fixture.client(2)
        for value in ('settings', '', None, ['mapper'], {'view': 'mapper'}):
            self.assertEqual(client.post('/api/me/start-view', json={'start_view': value}).status_code, 400)
        self.assertEqual(client.get('/api/me').get_json()['item']['start_view'], 'timeline')

    def test_login_required(self):
        response = fl.app.test_client().post('/api/me/start-view', json={'start_view':'mapper'})
        self.assertIn(response.status_code, (302, 401))
