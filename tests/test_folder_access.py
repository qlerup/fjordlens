import unittest
from unittest.mock import patch
import app as fl
import test_manager_role as fixtures


class FolderAccessTests(unittest.TestCase):
    setUp = fixtures.ManagerRoleTests.setUp
    tearDown = fixtures.ManagerRoleTests.tearDown
    client = fixtures.ManagerRoleTests.client

    def mixed_grants(self):
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [
                {'folder_path': 'uploads/private', 'permission': 'view'},
                {'folder_path': 'uploads/Editable', 'permission': 'edit'}])
            path = fl.UPLOAD_DIR / 'originals/Editable/b.jpg'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test')
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES('uploads/originals/Editable/b.jpg','b.jpg','.jpg')")
            conn.commit()

    def test_view_folder_cannot_be_deleted_while_other_folder_has_edit(self):
        self.mixed_grants()
        user = self.client(3)
        self.assertEqual(user.get('/api/me').json['item']['allowed_folders'][1]['permission'], 'view')
        result = user.post('/api/photos/delete', json={'photo_ids':[1]})
        self.assertEqual(result.status_code, 403, result.json)
        result = user.post('/api/settings/upload-folder-delete', json={'paths':['Editable', 'private']})
        self.assertEqual(result.status_code, 403, result.json)
        self.assertTrue((fl.UPLOAD_DIR / 'originals/private/a.jpg').exists())
        self.assertTrue((fl.UPLOAD_DIR / 'originals/Editable/b.jpg').exists())
        result = user.post('/api/photos/delete', json={'photo_ids':[1,3]})
        self.assertEqual(result.json['deleted_ids'], [3])
        self.assertTrue((fl.UPLOAD_DIR / 'originals/private/a.jpg').exists())

    def test_edit_folder_can_be_deleted_but_upload_folder_cannot(self):
        self.mixed_grants()
        user = self.client(3)
        result = user.post('/api/settings/upload-folder-delete', json={'paths':['Editable']})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertFalse((fl.UPLOAD_DIR / 'originals/Editable').exists())
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [{'folder_path':'uploads/private','permission':'upload'}])
            conn.commit()
        self.assertEqual(user.post('/api/settings/upload-folder-delete', json={'paths':['private']}).status_code, 403)

    def test_read_only_child_prevents_recursive_parent_deletion(self):
        self.mixed_grants()
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [
                {'folder_path':'uploads/Editable','permission':'edit'},
                {'folder_path':'uploads/Editable/Protected','permission':'view'}])
            conn.commit()
        result = self.client(3).post('/api/settings/upload-folder-delete', json={'paths':['Editable']})
        self.assertEqual(result.status_code, 403, result.json)
        self.assertTrue((fl.UPLOAD_DIR / 'originals/Editable/b.jpg').exists())

    def test_admin_and_manager_list_only_needed_user_fields_and_save_access(self):
        for uid in (1, 2):
            with self.subTest(actor=uid):
                client = self.client(uid)
                listing = client.get('/api/folder-access/users')
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(set(listing.json['items'][0]), {'id', 'username', 'role', 'allowed_folders'})
                grants = [{'folder_path': 'uploads/private', 'permission': 'upload'}]
                result = client.put('/api/folder-access/users/3', json={'allowed_folders': grants})
                self.assertEqual(result.status_code, 200, result.json)
                self.assertEqual(result.json['allowed_folders'], grants)
                self.assertEqual(self.client(3).get('/api/me').json['item']['role'], 'user')
                self.assertTrue(self.client(3).get('/api/photos?view=timeline').json['items'])
        self.assertEqual(self.client(2).get('/api/admin/users').status_code, 403)

    def test_ordinary_users_cannot_list_or_change_permissions(self):
        self.assertEqual(self.client(3).get('/api/folder-access/users').status_code, 403)
        self.assertEqual(self.client(3).put('/api/folder-access/users/3', json={'allowed_folders': []}).status_code, 403)

    def test_stale_edit_does_not_overwrite_existing_permissions(self):
        client = self.client()
        grants = [{'folder_path': 'uploads/private', 'permission': 'view'}]
        client.put('/api/folder-access/users/3', json={'allowed_folders': grants})
        result = client.put('/api/folder-access/users/3', json={'allowed_folders': [], 'previous_allowed_folders': []})
        self.assertEqual(result.status_code, 409)
        user = next(u for u in client.get('/api/folder-access/users').json['items'] if u['id'] == 3)
        self.assertEqual(user['allowed_folders'], grants)

    def test_bad_paths_levels_and_unknown_users_are_rejected(self):
        for path, permission in (('../private', 'view'), ('uploads', 'edit'), ('uploads/private', 'admin')):
            result = self.client().put('/api/folder-access/users/3', json={'allowed_folders': [{'folder_path':path, 'permission':permission}]})
            self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client().put('/api/folder-access/users/999', json={'allowed_folders':[]}).status_code, 404)

    def test_hub_list_excludes_users_without_app_access_and_uses_local_ids(self):
        hub_users = [{'id':77, 'username':'hub-viewer', 'role':'user'}]
        with patch.object(fl, '_fjordhub_managed', return_value=True), patch.object(fl, '_hub_api', return_value={'ok':True, 'items':hub_users}):
            listing = self.client().get('/api/folder-access/users')
            self.assertEqual(listing.status_code, 200, listing.json)
            self.assertEqual([u['username'] for u in listing.json['items']], ['hub-viewer'])
            uid = listing.json['items'][0]['id']
            result = self.client().put(f'/api/folder-access/users/{uid}', json={'allowed_folders':[{'folder_path':'uploads/private','permission':'view'}]})
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(self.client().put('/api/folder-access/users/3', json={'allowed_folders':[]}).status_code, 404)

    def test_unavailable_hub_does_not_change_permissions(self):
        with patch.object(fl, '_fjordhub_managed', return_value=True), patch.object(fl, '_hub_api', return_value={'ok':False}):
            self.assertEqual(self.client().get('/api/folder-access/users').status_code, 503)
            self.assertEqual(self.client().put('/api/folder-access/users/3', json={'allowed_folders':[]}).status_code, 503)
