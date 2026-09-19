"""Authenticated HTTP/mutation integration for the persistent folder index."""
from pathlib import Path
from unittest.mock import patch
import unittest

import app as fl
import folder_index as index
import test_video_autoplay_settings as fixtures


class FolderIndexApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.VideoAutoplaySettingsTests()
        self.fixture.setUp()
        self.root = Path(self.fixture.tempdir.name)
        self.previous = fl.UPLOAD_DIR, fl.THUMB_DIR
        fl.UPLOAD_DIR = self.root / 'uploads'; fl.UPLOAD_DIR.mkdir()
        fl.THUMB_DIR = self.root / 'thumbs'; fl.THUMB_DIR.mkdir()
        self.admin = self.fixture._authenticated_client()
        self.viewer = self.fixture._authenticated_client(2)
        self.admin.get('/api/folder-index')

    def tearDown(self):
        fl.UPLOAD_DIR, fl.THUMB_DIR = self.previous
        self.fixture.tearDown()

    def seed(self, path, thumb):
        with fl.closing(fl.get_conn()) as conn:
            conn.execute('INSERT INTO photos(rel_path,filename,thumb_name) VALUES(?,?,?)', (f'uploads/originals/{path}/a.jpg','a.jpg',thumb))
            conn.commit()
            index.refresh_covers(conn,100)

    def test_names_and_covers_load_without_nas_or_photo_metadata_work(self):
        self.seed('A/Sub', 'a.jpg')
        with (
            patch.object(fl,'_list_upload_subdirs',side_effect=AssertionError('disk walk')),
            patch.object(fl,'_sync_upload_folder_from_disk',side_effect=AssertionError('disk sync')),
            patch.object(fl,'row_to_public',side_effect=AssertionError('metadata')),
            patch.object(Path,'is_file',side_effect=AssertionError('stat')),
        ):
            response=self.admin.get('/api/folder-index')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.get_json()['items'],[{'path':'A','name':'A','previews':['/api/thumbs/a.jpg']}])
            picker=self.admin.get('/api/settings/upload-destination?destination=uploads')
            self.assertEqual(picker.status_code,200)
            self.assertIn('A/Sub',picker.get_json()['folders'])
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertIn('Cookie',response.headers['Vary'])

    def test_shared_catalogue_does_not_share_permissions_or_cover_refs(self):
        self.seed('Public','public.jpg'); self.seed('Private','private.jpg')
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn,2,[{'folder_path':'Public','permission':'view'}]); conn.commit()
        self.assertEqual(self.admin.get('/api/folder-index').get_json()['folders'],['Private','Public'])
        data=self.viewer.get('/api/folder-index').get_json()
        self.assertEqual(data['folders'],['Public'])
        self.assertNotIn('private.jpg',str(data))
        self.assertEqual(self.viewer.get('/api/folder-index?parent=Private').status_code,403)
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn,2,[]); conn.commit()
        self.assertEqual(self.viewer.get('/api/folder-index').get_json()['folders'],[])
        self.assertEqual(fl.app.test_client().get('/api/folder-index').status_code,401)

    def test_nested_grant_can_navigate_ancestors_but_not_private_siblings(self):
        self.seed('Family/Shared/Trip','shared.jpg'); self.seed('Family/Private','private.jpg')
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn,2,[{'folder_path':'Family/Shared','permission':'view'}]); conn.commit()
        self.assertEqual(self.viewer.get('/api/folder-index').get_json()['folders'],['Family'])
        self.assertEqual(self.viewer.get('/api/folder-index?parent=Family').get_json()['folders'],['Family/Shared'])
        tree=self.viewer.get('/api/folder-index?tree=1').get_json()['folders']
        self.assertNotIn('Family/Private',tree)

    def test_explicit_parent_grants_still_include_children(self):
        self.seed('Family/Private','private.jpg'); self.seed('Family/Shared','shared.jpg')
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn,2,[{'folder_path':'Family','permission':'view'}]); conn.commit()
        self.assertEqual(self.viewer.get('/api/folder-index?parent=Family').get_json()['folders'],['Family/Private','Family/Shared'])

    def test_create_rename_move_and_delete_empty_folders_update_index_immediately(self):
        for parent,name in [('', 'A'),('A','Empty'),('A/Empty','Nested'),('', 'B')]:
            response=self.admin.post('/api/settings/upload-folder',json={'destination':'uploads','parent':parent,'path':name})
            self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(self.admin.get('/api/folder-index?parent=A/Empty').get_json()['folders'],['A/Empty/Nested'])
        rename=self.admin.post('/api/settings/upload-folder-rename',json={'destination':'uploads','path':'A/Empty','new_name':'Renamed'})
        self.assertEqual(rename.status_code,200,rename.get_json())
        move=self.admin.post('/api/settings/upload-folder-move',json={'path':'A/Renamed','parent':'B'})
        self.assertEqual(move.status_code,200,move.get_json())
        self.assertEqual(self.admin.get('/api/folder-index?parent=B/Renamed').get_json()['folders'],['B/Renamed/Nested'])
        deleted=self.admin.post('/api/settings/upload-folder-delete',json={'destination':'uploads','paths':['B/Renamed']})
        self.assertEqual(deleted.status_code,200,deleted.get_json())
        self.assertEqual(self.admin.get('/api/folder-index?parent=B').get_json()['folders'],[])
        self.assertEqual(self.admin.get('/api/folder-index?parent=A/Empty').status_code,404)

    def test_invalid_and_missing_parent_do_not_return_false_empty_results(self):
        for path in ('..','A/../B','originals','converted/A'):
            self.assertEqual(self.admin.get('/api/folder-index',query_string={'parent':path}).status_code,400)
        self.assertEqual(self.admin.get('/api/folder-index?parent=Missing').status_code,404)

    def test_same_database_reopened_by_another_client_uses_persisted_index(self):
        self.seed('Existing','saved.jpg')
        fl.init_db()
        other=self.fixture._authenticated_client()
        self.assertEqual(other.get('/api/folder-index').get_json()['folders'],['Existing'])
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("INSERT INTO photos(rel_path,filename,thumb_name) VALUES('uploads/originals/New/a.jpg','a.jpg','new.jpg')")
            conn.commit()
        self.assertEqual(self.admin.get('/api/folder-index').get_json()['folders'],['Existing','New'])


if __name__ == '__main__':
    unittest.main()
