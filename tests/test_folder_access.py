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

    def test_edit_grant_protects_entry_folder_but_allows_deleting_contents(self):
        self.mixed_grants()
        user = self.client(3)
        result = user.post('/api/settings/upload-folder-delete', json={'paths':['Editable']})
        self.assertEqual(result.status_code, 403, result.json)
        self.assertTrue((fl.UPLOAD_DIR / 'originals/Editable/b.jpg').exists())
        child = fl.UPLOAD_DIR / 'originals/Editable/Child'
        child.mkdir()
        (child / 'c.jpg').write_bytes(b'test')
        result = user.post('/api/settings/upload-folder-delete', json={'paths':['Editable/Child']})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertFalse(child.exists())
        result = user.post('/api/photos/delete', json={'photo_ids':[3]})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertFalse((fl.UPLOAD_DIR / 'originals/Editable/b.jpg').exists())
        self.assertTrue((fl.UPLOAD_DIR / 'originals/Editable').exists())
        self.assertEqual(user.post('/api/settings/upload-folder-delete', json={'paths':['Editable']}).status_code, 403)
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [{'folder_path':'uploads/private','permission':'upload'}])
            conn.commit()
        self.assertEqual(user.post('/api/settings/upload-folder-delete', json={'paths':['private']}).status_code, 403)

    def test_read_only_child_prevents_recursive_parent_deletion(self):
        self.mixed_grants()
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [
                {'folder_path':'uploads/Editable','permission':'edit'},
                {'folder_path':'uploads/Editable/Content/Protected','permission':'view'}])
            conn.commit()
        result = self.client(3).post('/api/settings/upload-folder-delete', json={'paths':['Editable/Content']})
        self.assertEqual(result.status_code, 403, result.json)
        self.assertTrue((fl.UPLOAD_DIR / 'originals/Editable/b.jpg').exists())

    def test_inherited_grants_allow_creating_nested_folders(self):
        for permission in ('upload', 'edit'):
            with self.subTest(permission=permission):
                with fl.closing(fl.get_conn()) as conn:
                    fl._set_user_allowed_folders(conn, 3, [{'folder_path': 'private', 'permission': permission}])
                    conn.commit()
                response = self.client(3).post('/api/settings/upload-folder', json={
                    'destination': 'uploads', 'parent': 'private/Existing/Nested', 'path': permission})
                self.assertEqual(response.status_code, 200, response.json)
                self.assertTrue((fl.UPLOAD_DIR / 'originals/private/Existing/Nested' / permission).is_dir())
                self.assertTrue((fl.UPLOAD_DIR / 'converted/private/Existing/Nested' / permission).is_dir())

    def test_child_override_applies_to_all_descendants(self):
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 3, [
                {'folder_path': 'private', 'permission': 'edit'},
                {'folder_path': 'uploads/private/ReadOnly', 'permission': 'view'},
                {'folder_path': 'uploads/private/ReadOnly/Uploads', 'permission': 'upload'}])
            conn.execute("INSERT INTO folder_owners(folder_path,user_id) VALUES('uploads/private/ReadOnly',3)")
            conn.commit()
        with fl.app.test_request_context():
            with patch.object(fl, 'current_user', fl.User(3, 'user', 'user')):
                for root in ('uploads/', 'uploads/originals/', 'uploads/converted/'):
                    for suffix, expected in [('Other/Deep/a.jpg', 'edit'), ('ReadOnly/Deep/a.jpg', 'view'),
                                             ('ReadOnly/Uploads/Deep/a.jpg', 'upload')]:
                        self.assertEqual(fl._current_user_folder_permission_for_rel(root + 'private/' + suffix), expected)
        user = self.client(3)
        for parent, path in [('private/ReadOnly/Deep', 'new'), ('private', 'ReadOnly/Deep/new')]:
            response = user.post('/api/settings/upload-folder', json={'destination': 'uploads', 'parent': parent, 'path': path})
            self.assertEqual(response.status_code, 403, response.json)
        response = user.post('/api/settings/upload-folder', json={
            'destination': 'uploads', 'parent': 'private/ReadOnly/Uploads/Deep', 'path': 'new'})
        self.assertEqual(response.status_code, 200, response.json)

    def test_scoped_user_cannot_create_in_root_sibling_or_library(self):
        self.mixed_grants()
        user = self.client(3)
        for destination, parent in [('uploads', ''), ('uploads', 'private'), ('uploads', 'EditableSibling'), ('library', 'Editable')]:
            response = user.post('/api/settings/upload-folder', json={'destination': destination, 'parent': parent, 'path': 'new'})
            self.assertEqual(response.status_code, 403, response.json)

    def test_inherited_edit_allows_rename_but_protects_grant_entry(self):
        self.mixed_grants()
        child = fl.UPLOAD_DIR / 'originals/Editable/Child'
        child.mkdir()
        user = self.client(3)
        response = user.post('/api/settings/upload-folder-rename', json={'path': 'Editable/Child', 'new_name': 'Renamed'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue((child.parent / 'Renamed').is_dir())
        for path in ('Editable', 'private'):
            response = user.post('/api/settings/upload-folder-rename', json={'path': path, 'new_name': 'Blocked'})
            self.assertEqual(response.status_code, 403, response.json)

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
