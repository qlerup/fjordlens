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


if __name__ == '__main__':
    unittest.main()
