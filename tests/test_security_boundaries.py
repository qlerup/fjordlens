import base64
import io
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flask_login import login_user
from PIL import Image
from werkzeug.security import generate_password_hash

import app as core
import cast_airplay as cast


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        values = {n: root / n.lower() for n in (
            'DATA_DIR', 'PHOTO_DIR', 'UPLOAD_DIR', 'THUMB_DIR', 'CONVERT_DIR',
            'TUS_TMP_DIR', 'CONVERSION_WORK_DIR')}
        for directory in values.values():
            directory.mkdir()
        values.update(DB_PATH=root / 'test.db', INSTALL_STATE_PATH=root / 'installed.json',
                      DB_BOOTSTRAP_READY=True)
        self.previous = {k: getattr(core, k) for k in values}
        for key, value in values.items():
            setattr(core, key, value)
        core.init_db()
        with core.closing(core.get_conn()) as conn:
            for uid, role in enumerate(('admin', 'manager', 'user', 'user'), 1):
                conn.execute('INSERT INTO users(id,username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?,?)',
                             (uid, f'user{uid}', generate_password_hash('test-password'), int(role == 'admin'), role, core.now_iso()))
            for pid, folder in enumerate(('parent/allowed', 'parent/private'), 1):
                rel = f'uploads/originals/{folder}/{pid}.jpg'
                path = core.UPLOAD_DIR / rel[len('uploads/'):]
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new('RGB', (8, 8), 'green').save(path)
                conn.execute('INSERT INTO photos(id,rel_path,filename,ext,thumb_name,favorite) VALUES(?,?,?,?,?,0)',
                             (pid, rel, path.name, '.jpg', f'thumb{pid}.jpg'))
                (core.THUMB_DIR / f'thumb{pid}.jpg').write_bytes(b'thumbnail')
            core._set_user_allowed_folders(conn, 3, [{'folder': 'uploads/parent/allowed', 'permission': 'view'}])
            conn.commit()
        self.admin = self.client(1)
        self.user = self.client(3)
        self.anonymous = self.client()
        self.background = patch.object(core, '_refresh_photo_weather_if_possible')
        self.background.start()

    def tearDown(self):
        self.background.stop()
        for key, value in self.previous.items():
            setattr(core, key, value)
        self.temp.cleanup()

    def client(self, uid=None):
        client = core.app.test_client()
        if uid:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(uid)
                sess['_fresh'] = True
        return client

    def grant(self, permission='edit'):
        with core.closing(core.get_conn()) as conn:
            core._set_user_allowed_folders(conn, 3, [{'folder': 'uploads/parent/allowed', 'permission': permission}])
            conn.commit()

    def share(self, token='share-a', folder='parent/allowed'):
        with core.closing(core.get_conn()) as conn:
            cursor = conn.execute('''INSERT INTO share_links(token_hash,token_plain,share_name,folder_path,
                can_upload,can_download,can_delete,require_visitor_name,revoked,created_by_user_id,created_at)
                VALUES(?,?,?,?,1,1,1,0,0,1,?)''',
                (core._share_token_digest(token), token, token, folder, core.now_iso()))
            conn.commit()
            return cursor.lastrowid

    def start_upload(self, client, url, destination='uploads', subdir='parent/allowed'):
        metadata = ','.join(k + ' ' + base64.b64encode(v.encode()).decode() for k, v in (
            ('filename', 'new.jpg'), ('destination', destination), ('subdir', subdir)))
        return client.post(url, headers={'Tus-Resumable': '1.0.0', 'Upload-Length': '4', 'Upload-Metadata': metadata})

    def chunk(self, client, url, override=False):
        headers = {'Tus-Resumable': '1.0.0', 'Upload-Offset': '0', 'Content-Type': 'application/offset+octet-stream'}
        if override:
            headers['X-HTTP-Method-Override'] = 'PATCH'
        return getattr(client, 'post' if override else 'patch')(url, data=b'data', headers=headers)

    def test_nested_grant_keeps_navigation_without_sibling_media(self):
        with core.app.test_request_context('/'), core.closing(core.get_conn()) as conn:
            login_user(core._row_to_user(conn.execute('SELECT * FROM users WHERE id=3').fetchone()))
            self.assertTrue(core._is_rel_visible_for_current_user('uploads/originals/parent/allowed/1.jpg', conn))
            self.assertFalse(core._is_rel_visible_for_current_user('uploads/parent/private/2.jpg', conn))
            folders = core._filter_folders_by_current_user_acl(['parent', 'parent/allowed', 'parent/private'], conn)
            self.assertIn('parent', folders)
            self.assertNotIn('parent/private', folders)

    def test_legacy_ancestor_migration_is_conservative_and_runs_once(self):
        with core.closing(core.get_conn()) as conn:
            conn.execute("DELETE FROM settings WHERE key='folder_acl_explicit_grants_v1'")
            conn.execute("INSERT INTO user_folder_access VALUES(3,'uploads/parent','view',?)", (core.now_iso(),))
            core._migrate_legacy_folder_grants(conn)
            self.assertEqual([r['folder_path'] for r in core._get_user_allowed_folders(conn, 3)], ['uploads/parent/allowed'])
            core._set_user_allowed_folders(conn, 3, ['uploads/parent', 'uploads/parent/allowed'])
            core._migrate_legacy_folder_grants(conn)
            self.assertIn('uploads/parent', [r['folder_path'] for r in core._get_user_allowed_folders(conn, 3)])
            conn.commit()

    def test_metadata_mutations_require_edit_and_preserve_authorized_edits(self):
        for action, body in [('captured-at', {'captured_at': '2024-01-02T03:04:05'}),
                             ('gps', {'lat': 55, 'lon': 12}), ('favorite', {})]:
            with self.subTest(action=action), patch.object(core, 'reverse_geocode_with_cache', return_value=('Denmark', 'Copenhagen')) as geocode:
                self.assertEqual(self.user.post(f'/api/photos/2/{action}', json=body).status_code, 403)
                self.assertEqual(self.user.post(f'/api/photos/1/{action}', json=body).status_code, 403)
                geocode.assert_not_called()
                self.grant()
                self.assertEqual(self.user.post(f'/api/photos/1/{action}', json=body).status_code, 200)
                self.grant('view')

    def test_private_photo_face_and_orphan_cache_are_denied(self):
        with core.closing(core.get_conn()) as conn:
            conn.execute('INSERT INTO faces(id,photo_id,bbox_x,bbox_y,bbox_w,bbox_h,created_at) VALUES(10,2,0,0,1,1,?)', (core.now_iso(),))
            conn.commit()
        for name in ['face_10.jpg', 'face_10_v7.jpg', 'orphan.jpg']:
            (core.THUMB_DIR / name).write_bytes(b'private')
        for name in ['thumb2.jpg', 'face_10.jpg', 'face_10_v7.jpg', 'orphan.jpg']:
            with self.subTest(name=name):
                self.assertEqual(self.user.get('/api/thumbs/' + name).status_code, 404)
        with self.user.get('/api/thumbs/thumb1.jpg') as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['Cache-Control'])
        with self.admin.get('/api/thumbs/face_10_v7.jpg') as response:
            self.assertEqual(response.status_code, 200)

    def test_debug_sample_is_administrator_only(self):
        self.assertEqual(self.user.get('/api/debug/sample').status_code, 403)
        self.assertEqual(self.client(2).get('/api/debug/sample').status_code, 403)
        self.assertEqual(self.admin.get('/api/debug/sample').status_code, 200)

    def test_cast_selection_and_old_capabilities_enforce_current_creator_scope(self):
        with core.app.test_request_context('/'), core.closing(core.get_conn()) as conn:
            user = core._row_to_user(conn.execute('SELECT * FROM users WHERE id=3').fetchone())
            login_user(user)
            self.assertEqual([r['id'] for r in cast._resolve_rows([1, 2], [])], [1])
            self.assertEqual([r['id'] for r in cast._resolve_rows([], ['originals/parent'])], [1])
            rows = cast._resolve_rows([1], [])
        cast._put_session('test-cast', {'expires_at': time.time() + 600, 'created_by_user_id': 3, 'items': rows})
        self.assertIsNotNone(cast._get_session('test-cast'))
        with core.closing(core.get_conn()) as conn:
            core._set_user_allowed_folders(conn, 3, [])
            conn.commit()
        self.assertIsNone(cast._get_session('test-cast'))
        # Even a previously minted session for an unauthorized object is denied.
        cast._put_session('old-cast', {'expires_at': time.time() + 600, 'created_by_user_id': 3,
                                     'items': [{'id': 2, 'rel_path': 'uploads/originals/parent/private/2.jpg'}]})
        self.assertIsNone(cast._get_session('old-cast'))

    def test_library_upload_requires_manager_even_when_storage_is_writable(self):
        for client, expected in [(self.user, 403), (self.client(2), 201)]:
            response = self.start_upload(client, '/api/upload/tus', 'library', 'writable')
            self.assertEqual(response.status_code, expected, response.data)
        response = self.user.post('/api/upload', data={'destination': 'library', 'subdir': 'writable',
                                                      'files': (io.BytesIO(b'jpeg'), 'p.jpg')})
        self.assertEqual(response.status_code, 403)

    def test_share_resume_checks_revocation_permission_and_matching_share(self):
        share_id = self.share()
        self.share('share-b')
        location = self.start_upload(self.anonymous, '/api/share/share-a/upload/tus').headers['Location']
        with patch.object(core, '_commit_uploaded_file', return_value=(True, 'new.jpg', None)) as commit:
            self.assertEqual(self.chunk(self.anonymous, location.replace('share-a', 'share-b')).status_code, 403)
            self.assertEqual(self.chunk(self.user, '/api/upload/tus/' + location.rsplit('/', 1)[-1]).status_code, 403)
            with core.closing(core.get_conn()) as conn:
                conn.execute('UPDATE share_links SET revoked=1 WHERE id=?', (share_id,))
                conn.commit()
            self.assertEqual(self.anonymous.head(location, headers={'Tus-Resumable': '1.0.0'}).status_code, 403)
            self.assertEqual(self.chunk(self.anonymous, location, override=True).status_code, 403)
            commit.assert_not_called()
            with core.closing(core.get_conn()) as conn:
                conn.execute('UPDATE share_links SET revoked=0 WHERE id=?', (share_id,))
                conn.commit()
            self.assertEqual(self.chunk(self.anonymous, location, override=True).status_code, 204)
            commit.assert_called_once()

    def test_resume_rechecks_current_share_password_upload_flag_and_folder(self):
        share_id = self.share()
        location = self.start_upload(self.anonymous, '/api/share/share-a/upload/tus').headers['Location']
        for assignment, value in [('can_upload', 0), ('password_hash', generate_password_hash('new-secret')),
                                  ('folder_path', 'parent/private')]:
            with self.subTest(field=assignment), core.closing(core.get_conn()) as conn:
                conn.execute(f'UPDATE share_links SET {assignment}=? WHERE id=?', (value, share_id))
                conn.commit()
                self.assertEqual(self.chunk(self.anonymous, location).status_code, 403)
                conn.execute("UPDATE share_links SET can_upload=1,password_hash=NULL,folder_path='parent/allowed' WHERE id=?", (share_id,))
                conn.commit()

    def test_user_upload_resume_is_bound_to_owner_and_current_permission(self):
        self.grant('upload')
        self.share()
        location = self.start_upload(self.user, '/api/upload/tus').headers['Location']
        foreign = '/api/share/share-a/upload/tus/' + location.rsplit('/', 1)[-1]
        self.assertEqual(self.chunk(self.anonymous, foreign).status_code, 403)
        self.assertEqual(self.chunk(self.client(4), location).status_code, 403)
        self.grant('view')
        self.assertEqual(self.chunk(self.user, location).status_code, 403)
        self.grant('upload')
        with patch.object(core, '_commit_uploaded_file', return_value=(True, 'new.jpg', None)) as commit:
            self.assertEqual(self.chunk(self.user, location, override=True).status_code, 204)
            commit.assert_called_once()

    def test_share_folder_wildcards_are_literal_for_all_storage_variants(self):
        for folder, sibling in [('A_B', 'AxB'), ('A%B', 'AxxB'), ('A!_B', 'A!xB'), ('Public', 'public')]:
            with self.subTest(folder=folder), core.closing(core.get_conn()) as conn:
                for i, name in enumerate([folder, sibling], 20):
                    conn.execute('INSERT OR REPLACE INTO photos(id,rel_path,filename) VALUES(?,?,?)',
                                 (i, f'uploads/originals/{name}/p.jpg', 'p.jpg'))
                sql, params = core._share_scope_sql(core._share_rel_prefixes([folder]))
                ids = [r['id'] for r in conn.execute('SELECT id FROM photos WHERE ' + sql, params)]
                self.assertEqual(ids, [20])
                conn.rollback()

    def test_admin_forms_require_csrf_and_render_hostile_username_as_data(self):
        payload = {'username': 'injected-admin', 'password': 'test-password', 'role': 'admin'}
        self.assertEqual(self.admin.post('/admin/users', data=payload).status_code, 403)
        hostile = "</strong><img src=x onerror=alert(1)>'\";alert(2)//"
        self.assertEqual(self.user.post('/api/me/profile', json={'username': hostile}).status_code, 200)
        html = self.admin.get('/admin/users').get_data(as_text=True)
        self.assertNotIn('<img src=x', html)
        self.assertIn('onsubmit="return confirm(this.dataset.confirm);"', html)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        self.assertEqual(self.admin.post('/admin/users', data={**payload, 'csrf_token': token}).status_code, 200)
        with core.closing(core.get_conn()) as conn:
            self.assertEqual(conn.execute("SELECT role FROM users WHERE username='injected-admin'").fetchone()['role'], 'admin')

    def totp_challenge(self, client, issued=None):
        with client.session_transaction() as sess:
            sess['2fa_user_id'] = 3
            sess['2fa_issued_at'] = time.time() if issued is None else issued

    def test_totp_budget_survives_cookie_replay_and_new_password_login(self):
        secret = core.pyotp.random_base32()
        with core.closing(core.get_conn()) as conn:
            conn.execute('UPDATE users SET totp_secret=?,totp_enabled=1,totp_setup_done=1 WHERE id=3', (secret,))
            conn.commit()
        with patch.object(core.pyotp.TOTP, 'verify', return_value=False):
            for _ in range(core.TOTP_MAX_ATTEMPTS):
                self.totp_challenge(self.anonymous)
                self.assertEqual(self.anonymous.post('/login/2fa', data={'code': '000000'}).status_code, 200)
            self.assertEqual(self.anonymous.post('/login', data={'username': 'user3', 'password': 'test-password'}).status_code, 302)
            self.assertEqual(self.anonymous.post('/login/2fa', data={'code': '000000'}).status_code, 429)
            self.totp_challenge(self.anonymous)
            self.assertEqual(self.anonymous.post('/login/2fa', data={'code': '000000'}).status_code, 429)

    def test_totp_expiry_and_valid_code(self):
        secret = core.pyotp.random_base32()
        with core.closing(core.get_conn()) as conn:
            conn.execute('UPDATE users SET totp_secret=?,totp_enabled=1,totp_setup_done=1 WHERE id=3', (secret,))
            conn.commit()
        self.totp_challenge(self.anonymous, time.time() - 301)
        self.assertEqual(self.anonymous.post('/login/2fa', data={'code': core.pyotp.TOTP(secret).now()}).location, '/login')
        self.totp_challenge(self.anonymous)
        self.assertEqual(self.anonymous.post('/login/2fa', data={'code': core.pyotp.TOTP(secret).now()}).status_code, 302)
        with self.anonymous.session_transaction() as sess:
            self.assertEqual(sess['_user_id'], '3')
            self.assertNotIn('2fa_user_id', sess)

    def frame(self, token='frame-secret', frame_id='frame-1'):
        record = {'id': frame_id, 'token_hash': core._share_token_digest(token), 'token_plain': token,
                  'scope_mode': 'all', 'allowed_folders': [], 'allowed_photo_ids': []}
        # Seed an existing installation without relying on the mutation helper.
        core._set_setting('photoframe_tokens', json.dumps({'tokens': [record]}))
        return core._load_photoframe_token_records()

    def test_stale_telemetry_cannot_restore_deleted_token(self):
        stale = self.frame()
        self.assertEqual(self.admin.delete('/api/photoframes/frame-1').status_code, 200)
        core._save_photoframe_token_records(stale)
        self.assertEqual(core._load_photoframe_token_records(), [])
        self.assertEqual(self.anonymous.get('/api/frame/frame-secret/view/1').status_code, 403)

    def test_stale_telemetry_preserves_scope_reduction_and_concurrent_creation(self):
        stale = self.frame()
        response = self.admin.put('/api/photoframes/frame-1/scope', json={'scope_mode': 'photos', 'allowed_photo_ids': [1]})
        self.assertEqual(response.status_code, 200, response.data)
        created = self.admin.post('/api/photoframes', json={})
        self.assertEqual(created.status_code, 200, created.data)
        stale[0]['last_seen_at'] = core.now_iso()
        core._save_photoframe_token_records(stale)
        current = core._load_photoframe_token_records()
        self.assertEqual(len(current), 2)
        record = next(r for r in current if r['id'] == 'frame-1')
        self.assertEqual(record['scope_mode'], 'photos')
        self.assertEqual(record['allowed_photo_ids'], [1])
        self.assertEqual(record['last_seen_at'], stale[0]['last_seen_at'])
        self.assertEqual(self.anonymous.get('/api/frame/frame-secret/view/2').status_code, 403)
        with self.anonymous.get('/api/frame/frame-secret/view/1') as response:
            self.assertEqual(response.status_code, 200)

    def test_device_active_content_is_never_proxied_but_settings_ui_remains(self):
        self.frame()
        with patch.object(core.requests, 'request') as upstream:
            self.assertEqual(self.admin.get('/api/photoframes/frame-1/settings-proxy/evil').status_code, 404)
            self.assertEqual(self.admin.get('/api/photoframes/frame-1/settings-proxy', follow_redirects=True).status_code, 200)
            self.assertEqual(self.user.get('/api/photoframes/frame-1/settings-proxy', follow_redirects=True).status_code, 403)
            upstream.assert_not_called()

    def test_ai_service_has_no_published_host_port_and_keeps_internal_control(self):
        import yaml
        compose = yaml.safe_load((Path(__file__).parents[1] / 'docker-compose.yml').read_text(encoding='utf-8'))
        ai = compose['services']['fjordlens-ai']
        self.assertFalse(ai.get('ports'))
        app = compose['services']['fjordlens']
        self.assertEqual(app['environment']['AI_URL'], 'http://fjordlens-ai:8000')
        with patch.object(core.requests, 'post') as post:
            post.return_value.ok = True
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'ok': True, 'hard': True}
            self.assertTrue(core._ai_stop_description_runtime(force=True)['ok'])
            self.assertEqual(post.call_args.kwargs['params'], {'hard': '1'})


if __name__ == '__main__':
    unittest.main()
