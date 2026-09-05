import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as fjordlens


class ForgotPasswordStandaloneTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        values = {name: root / name.lower() for name in (
            'DATA_DIR', 'PHOTO_DIR', 'UPLOAD_DIR', 'THUMB_DIR', 'CONVERT_DIR', 'TUS_TMP_DIR', 'CONVERSION_WORK_DIR')}
        for path in values.values():
            path.mkdir(parents=True)
        values.update(DB_PATH=root / 'fjordlens.db', INSTALL_STATE_PATH=root / 'install.json', DB_BOOTSTRAP_READY=False)
        self.previous = {name: getattr(fjordlens, name) for name in values}
        for name, value in values.items():
            setattr(fjordlens, name, value)
        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO users(username,password_hash,is_admin,role,email,created_at) VALUES(?,?,?,?,?,?)",
                ('demo', generate_password_hash('old-secret'), 0, 'user', 'demo@example.com', fjordlens.now_iso()),
            )
            conn.commit()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def test_complete_flow_changes_the_password(self):
        sent = []
        with patch.object(fjordlens, '_send_reset_code_email', lambda to, code: sent.append((to, code))):
            client = fjordlens.app.test_client()
            resp = client.post('/glemt-adgangskode', data={'step': 'email', 'email': 'DEMO@example.com'})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(sent[0][0], 'demo@example.com')
            code = sent[0][1]

            # challenge_id is embedded as a hidden field in the rendered "code" step
            html = resp.get_data(as_text=True)
            import re
            challenge_id = re.search(r'name="challenge_id" value="([^"]+)"', html).group(1)

            resp = client.post('/glemt-adgangskode', data={'step': 'code', 'challenge_id': challenge_id, 'code': code})
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            reset_token = re.search(r'name="reset_token" value="([^"]+)"', html).group(1)
            self.assertTrue(reset_token)

            resp = client.post('/glemt-adgangskode', data={
                'step': 'password', 'challenge_id': challenge_id, 'reset_token': reset_token,
                'password': 'new-secret', 'password2': 'new-secret',
            })
            self.assertEqual(resp.status_code, 200)

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE username='demo'").fetchone()
        from werkzeug.security import check_password_hash
        self.assertTrue(check_password_hash(row['password_hash'], 'new-secret'))
        self.assertFalse(check_password_hash(row['password_hash'], 'old-secret'))

    def test_unknown_email_does_not_error_and_sends_nothing(self):
        sent = []
        with patch.object(fjordlens, '_send_reset_code_email', lambda to, code: sent.append((to, code))):
            client = fjordlens.app.test_client()
            resp = client.post('/glemt-adgangskode', data={'step': 'email', 'email': 'nobody@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sent, [])

    def test_mail_settings_roundtrip_encrypts_password_at_rest(self):
        with patch.object(fjordlens, '_mail_smtp') as mock_smtp:
            mock_smtp.return_value.__enter__ = lambda self_: self_
            mock_smtp.return_value.__exit__ = lambda *a: None
            fjordlens._save_mail_settings('resend', 'my-api-key', 'smtp.resend.com', 465, 'noreply@gleruphub.dk')
        settings = fjordlens._mail_settings()
        self.assertEqual(settings['user'], 'resend')
        self.assertEqual(settings['password'], 'my-api-key')
        self.assertEqual(settings['from_address'], 'noreply@gleruphub.dk')
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='smtp_password'").fetchone()
        self.assertNotIn('my-api-key', row['value'])


class ForgotPasswordHubManagedTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        values = {name: root / name.lower() for name in (
            'DATA_DIR', 'PHOTO_DIR', 'UPLOAD_DIR', 'THUMB_DIR', 'CONVERT_DIR', 'TUS_TMP_DIR', 'CONVERSION_WORK_DIR')}
        for path in values.values():
            path.mkdir(parents=True)
        values.update(DB_PATH=root / 'fjordlens.db', INSTALL_STATE_PATH=root / 'install.json', DB_BOOTSTRAP_READY=False)
        self.previous = {name: getattr(fjordlens, name) for name in values}
        for name, value in values.items():
            setattr(fjordlens, name, value)
        fjordlens.init_db()
        self.previous_hub = (fjordlens._FJORDHUB_URL, fjordlens._FJORDHUB_API_KEY, fjordlens._FJORDHUB_APP_ID)
        fjordlens._FJORDHUB_URL = 'http://fjordhub.test'
        fjordlens._FJORDHUB_API_KEY = 'test-hub-key'
        fjordlens._FJORDHUB_APP_ID = 'fjordlens'

    def tearDown(self):
        fjordlens._FJORDHUB_URL, fjordlens._FJORDHUB_API_KEY, fjordlens._FJORDHUB_APP_ID = self.previous_hub
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def test_delegates_every_step_to_fjordhub_api(self):
        calls = []

        def fake_hub_api(path, payload=None, method='POST'):
            calls.append(path)
            if path == '/api/hub/apps/password-reset/request':
                return {'ok': True, 'challenge_id': 'chal-1'}
            if path == '/api/hub/apps/password-reset/verify':
                return {'ok': True, 'reset_token': 'tok-1'}
            if path == '/api/hub/apps/password-reset/complete':
                return {'ok': True}
            return {'ok': False}

        with patch.object(fjordlens, '_hub_api', side_effect=fake_hub_api):
            client = fjordlens.app.test_client()
            r1 = client.post('/glemt-adgangskode', data={'step': 'email', 'email': 'someone@example.com'})
            self.assertIn('chal-1', r1.get_data(as_text=True))
            r2 = client.post('/glemt-adgangskode', data={'step': 'code', 'challenge_id': 'chal-1', 'code': '123456'})
            self.assertIn('tok-1', r2.get_data(as_text=True))
            r3 = client.post('/glemt-adgangskode', data={
                'step': 'password', 'challenge_id': 'chal-1', 'reset_token': 'tok-1',
                'password': 'new-secret', 'password2': 'new-secret',
            })
            self.assertEqual(r3.status_code, 200)

        self.assertEqual(calls, [
            '/api/hub/apps/password-reset/request',
            '/api/hub/apps/password-reset/verify',
            '/api/hub/apps/password-reset/complete',
        ])
        # No local challenge should have been created - it all lives on FjordHub's side.
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM password_reset_challenges").fetchone()
        self.assertEqual(count['c'], 0)


if __name__ == '__main__':
    unittest.main()
