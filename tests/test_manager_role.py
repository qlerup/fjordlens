import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

import app as fjordlens


class ManagerRoleTests(unittest.TestCase):
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
        password_hash = generate_password_hash('test-password')
        self.paths = ['uploads/originals/private/a.jpg', 'hidden/b.jpg']
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            for role in ('admin', 'manager', 'user'):
                conn.execute('INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?)',
                             (role, password_hash, int(role == 'admin'), role, fjordlens.now_iso()))
            for rel in self.paths:
                path = (fjordlens.UPLOAD_DIR / rel[len('uploads/'):]) if rel.startswith('uploads/') else fjordlens.PHOTO_DIR / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new('RGB', (12, 8), 'green').save(path)
                conn.execute('INSERT INTO photos(rel_path,filename,ext,file_size) VALUES(?,?,?,?)',
                             (rel, path.name, '.jpg', path.stat().st_size))
            conn.commit()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def client(self, uid=2):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(uid)
            session['_fresh'] = True
        return client

    def test_manager_reads_and_deletes_all_photos_without_folder_grants(self):
        manager = self.client()
        response = manager.get('/api/photos?view=timeline')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['rel_path'] for item in response.json['items']}, set(self.paths))
        response = manager.post('/api/photos/delete', json={'photo_ids': [1, 2]})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(set(response.json['deleted_ids']), {1, 2})

    def test_ordinary_user_still_needs_folder_permissions(self):
        user = self.client(3)
        self.assertEqual(user.get('/api/photos?view=timeline').json['items'], [])
        self.assertEqual(user.post('/api/photos/delete', json={'photo_ids': [1, 2]}).status_code, 403)
        self.assertEqual(user.post('/api/settings/upload-folder', json={'path': 'new'}).status_code, 403)

    def test_manager_can_create_root_and_nested_folders_and_delete_them(self):
        manager = self.client()
        for parent, path in (('', 'new'), ('private', 'nested')):
            response = manager.post('/api/settings/upload-folder', json={'destination': 'uploads', 'parent': parent, 'path': path})
            self.assertEqual(response.status_code, 200, response.json)
        response = manager.post('/api/settings/upload-folder-delete', json={'destination': 'uploads', 'paths': ['new', 'private/nested']})
        self.assertEqual(response.status_code, 200, response.json)

    def test_manager_can_start_uploads_in_other_users_folders(self):
        metadata = ','.join(name + ' ' + base64.b64encode(value.encode()).decode() for name, value in (
            ('filename', 'new.jpg'), ('destination', 'uploads'), ('subdir', 'private')))
        headers = {'Tus-Resumable': '1.0.0', 'Upload-Length': '100', 'Upload-Metadata': metadata}
        response = self.client().post('/api/upload/tus', headers=headers)
        self.assertEqual(response.status_code, 201, response.json)
        response = self.client(3).post('/api/upload/tus', headers=headers)
        self.assertEqual(response.status_code, 403, response.json)

    def test_manager_has_no_system_or_user_administration_rights(self):
        manager = self.client()
        for method, url in [('get', '/api/admin/users'), ('get', '/api/logs'), ('get', '/api/settings/video'),
                            ('post', '/api/settings/upload-destination'), ('post', '/api/scan'),
                            ('post', '/api/admin/users')]:
            with self.subTest(url=url):
                self.assertEqual(getattr(manager, method)(url).status_code, 403)
        profile = manager.get('/api/me').json['item']
        self.assertEqual(profile['role'], 'manager')
        user = fjordlens.User(2, 'manager', 'manager')
        self.assertFalse(user.is_admin or user.can_manage_users() or user.can_maintain())

    def test_local_admin_can_create_and_edit_manager_roles(self):
        admin = self.client(1)
        response = admin.post('/api/admin/users', json={'username': 'new-manager', 'password': 'test-password', 'role': 'manager'})
        self.assertIn(response.status_code, (200, 201), response.json)
        response = admin.put('/api/admin/users/3', json={'username': 'user', 'role': 'manager'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.client(3).get('/api/me').json['item']['role'], 'manager')

    def test_manager_role_survives_hub_sync_in_both_directions(self):
        hub_user = {'id': 77, 'username': 'hub-manager', 'role': 'manager', 'hub_role': 'user'}
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
             patch.object(fjordlens, '_hub_list_users', return_value=[hub_user]):
            response = self.client(1).get('/api/admin/users')
            self.assertEqual(response.status_code, 200, response.json)
            local = response.json['items'][0]
            self.assertEqual(local['role'], 'manager')
            self.assertFalse(local['is_admin'])
            with patch.object(fjordlens, '_hub_update_user_role', return_value={'ok': True, 'user': hub_user}) as update:
                response = self.client(1).put(f"/api/admin/users/{local['id']}", json={'role': 'manager'})
                self.assertEqual(response.status_code, 200, response.json)
                update.assert_called_once_with(77, 'manager')

    def test_hub_sso_preserves_manager_without_granting_admin(self):
        hub_user = {'ok': True, 'id': 77, 'username': 'hub-manager', 'role': 'manager', 'hub_role': 'user'}
        client = fjordlens.app.test_client()
        with patch.object(fjordlens, '_fjordhub_managed', return_value=True), \
             patch.object(fjordlens, '_hub_api', return_value=hub_user):
            response = client.get('/hub-login?token=test-token')
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/')
            self.assertEqual(client.get('/api/me').json['item']['role'], 'manager')
            self.assertEqual(len(client.get('/api/photos?view=timeline').json['items']), 2)
            self.assertEqual(client.get('/api/admin/users').status_code, 403)


if __name__ == '__main__':
    unittest.main()
