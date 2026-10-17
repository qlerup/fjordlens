import tempfile
import time
import unittest
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as fjordlens


class DeviceLoginTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        values = {name: root / name.lower() for name in (
            'DATA_DIR', 'PHOTO_DIR', 'UPLOAD_DIR', 'THUMB_DIR', 'CONVERT_DIR',
            'TUS_TMP_DIR', 'CONVERSION_WORK_DIR')}
        for path in values.values():
            path.mkdir(parents=True)
        values.update(DB_PATH=root / 'fjordlens.db', INSTALL_STATE_PATH=root / 'install.json',
                      DB_BOOTSTRAP_READY=False)
        self.previous = {name: getattr(fjordlens, name) for name in values}
        for name, value in values.items():
            setattr(fjordlens, name, value)
        self.managed = patch.object(fjordlens, '_fjordhub_managed', return_value=False)
        self.managed.start()
        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?)',
                         ('demo', generate_password_hash('test-password'), 0, 'user', fjordlens.now_iso()))
            conn.commit()
        self.client = fjordlens.app.test_client()

    def tearDown(self):
        self.managed.stop()
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def login(self):
        return self.client.post('/login', data={'username': 'demo', 'password': 'test-password'})

    def test_login_survives_browser_restart_then_expires_at_fixed_deadline(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        cookies = SimpleCookie()
        for header in response.headers.getlist('Set-Cookie'):
            cookies.load(header)
        cookie_name = fjordlens.app.config['SESSION_COOKIE_NAME']
        cookie = cookies[cookie_name]
        remaining = parsedate_to_datetime(cookie['expires']) - datetime.now(timezone.utc)
        self.assertAlmostEqual(remaining.total_seconds(), 30 * 86400, delta=5)
        self.assertTrue(cookie['httponly'])
        browser = fjordlens.app.test_client()
        browser.set_cookie(cookie_name, cookie.value)
        self.assertTrue(browser.get('/api/auth/session').json['authenticated'])
        with browser.session_transaction() as session:
            deadline = session['login_expires_at']
            self.assertTrue(session.permanent)
        # A later session write must not prolong authentication.
        with patch.object(fjordlens.time, 'time', return_value=deadline - 60):
            with browser.session_transaction() as session:
                session['other_preference'] = 'changed'
            response = browser.get('/api/auth/session')
            self.assertTrue(response.json['authenticated'])
            self.assertNotIn('Set-Cookie', response.headers)
        with patch.object(fjordlens.time, 'time', return_value=deadline):
            self.assertFalse(browser.get('/api/auth/session').json['authenticated'])

    def test_logout_ends_persistent_login(self):
        self.login()
        self.assertEqual(self.client.get('/logout').status_code, 302)
        self.assertFalse(self.client.get('/api/auth/session').json['authenticated'])
        with self.client.session_transaction() as session:
            self.assertNotIn('login_expires_at', session)
            self.assertFalse(session.permanent)

    def test_failed_password_does_not_persist_login(self):
        self.client.post('/login', data={'username': 'demo', 'password': 'wrong'})
        with self.client.session_transaction() as session:
            self.assertNotIn('login_expires_at', session)
            self.assertNotIn('_user_id', session)

    def test_two_factor_only_persists_after_verification(self):
        secret = fjordlens.pyotp.random_base32()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('UPDATE users SET totp_enabled=1, totp_setup_done=1, totp_secret=?', (secret,))
            conn.commit()
        self.assertIn('/login/2fa', self.login().location)
        with self.client.session_transaction() as session:
            self.assertNotIn('login_expires_at', session)
            self.assertNotIn('_user_id', session)
        response = self.client.post('/login/2fa', data={'code': fjordlens.pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertTrue(session.permanent)
            self.assertGreater(session['login_expires_at'], time.time())

    def test_managed_login_persists(self):
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
                patch.object(fjordlens, '_hub_authenticate', return_value={'username': 'demo'}), \
                patch.object(fjordlens, '_ensure_managed_local_user') as ensure_user:
            with fjordlens.closing(fjordlens.get_conn()) as conn:
                ensure_user.return_value = fjordlens._row_to_user(conn.execute('SELECT * FROM users').fetchone())
            self.assertEqual(self.login().status_code, 302)
        with self.client.session_transaction() as session:
            self.assertTrue(session.permanent)
            self.assertGreater(session['login_expires_at'], time.time())


    def test_managed_first_login_only_asks_for_email_and_new_password(self):
        from unittest.mock import patch

        def hub_login(username, password):
            self.assertEqual(username, 'demo')
            self.assertEqual(password, 'test-password')
            if not fjordlens.request.form.get('first_login_password'):
                return {'username': 'demo', 'email_required': True, 'must_change_password': True}
            self.assertEqual(fjordlens.request.form['first_login_email'], 'demo@example.com')
            self.assertEqual(fjordlens.request.form['first_login_password'], 'new-private-password')
            self.assertEqual(fjordlens.request.form['first_login_password_confirm'], 'new-private-password')
            return {'username': 'demo', 'email_required': False, 'must_change_password': False}

        headers = {'X-FjordLens-Login': '1', 'Accept': 'application/json'}
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
                patch.object(fjordlens, '_hub_authenticate', side_effect=hub_login), \
                patch.object(fjordlens, '_ensure_managed_local_user') as ensure_user:
            with fjordlens.closing(fjordlens.get_conn()) as conn:
                ensure_user.return_value = fjordlens._row_to_user(conn.execute('SELECT * FROM users').fetchone())

            html = self.client.get('/login').get_data(as_text=True)
            self.assertIn('id="firstLoginSetupForm"', html)
            self.assertIn('id="firstLoginSetupForm" class="login-card small" method="post"', html)
            self.assertIn('hidden>', html)
            self.assertIn('name="first_login_email"', html)
            self.assertIn('name="first_login_password_confirm"', html)

            initial = self.client.post('/login', headers=headers, data={
                'username': 'demo', 'password': 'test-password',
            })
            self.assertEqual(initial.status_code, 200)
            self.assertTrue(initial.json['first_login_required'])
            self.assertTrue(initial.json['email_required'])
            self.assertTrue(initial.json['password_required'])
            self.assertFalse(self.client.get('/api/auth/session').json['authenticated'])
            ensure_user.assert_not_called()
            # Only the three new onboarding fields are added. The original credentials
            # are kept in browser memory and sent with the final request.
            completed = self.client.post('/login?next=%2Ftimeline', headers=headers, data={
                'username': 'demo', 'password': 'test-password',
                'first_login_email': 'demo@example.com',
                'first_login_password': 'new-private-password',
                'first_login_password_confirm': 'new-private-password',
            })
            self.assertEqual(completed.status_code, 200)
            self.assertTrue(completed.json['ok'])
            self.assertEqual(completed.json['redirect'], '/timeline')
            self.assertTrue(self.client.get('/api/auth/session').json['authenticated'])
            ensure_user.assert_called_once()

    def test_managed_first_login_error_stays_in_setup_without_signing_in(self):
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
                patch.object(fjordlens, '_hub_authenticate', return_value={
                    'username': 'demo', 'email_required': True, 'must_change_password': True,
                    'email_error': 'De nye adgangskoder matcher ikke.',
                }), patch.object(fjordlens, '_ensure_managed_local_user') as ensure_user:
            response = self.client.post('/login', headers={'X-FjordLens-Login': '1'},
                                        data={'username': 'demo', 'password': 'test-password',
                                              'first_login_email': 'demo@example.com',
                                              'first_login_password': 'new-private-password',
                                              'first_login_password_confirm': 'different-password'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json['first_login_required'])
            self.assertIn('matcher ikke', response.json['error'])
            self.assertFalse(self.client.get('/api/auth/session').json['authenticated'])
            ensure_user.assert_not_called()

    def test_managed_first_login_never_renders_old_password_into_html(self):
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
                patch.object(fjordlens, '_hub_authenticate', return_value={
                    'username': 'demo', 'email_required': True, 'must_change_password': True,
                }):
            response = self.client.post('/login', data={
                'username': 'demo', 'password': 'unique-temporary-secret',
            })
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('unique-temporary-secret', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
