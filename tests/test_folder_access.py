import unittest
from unittest.mock import patch
import app as fl
import test_manager_role as fixtures


class FolderAccessTests(unittest.TestCase):
    setUp = fixtures.ManagerRoleTests.setUp
    tearDown = fixtures.ManagerRoleTests.tearDown
    client = fixtures.ManagerRoleTests.client

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
