import json
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
import app as fl
import folder_privacy
import moments_service
from tests.test_folder_previews import FolderPreviewTests


class FolderPrivacyTests(unittest.TestCase):
    setUp = FolderPreviewTests.setUp
    tearDown = FolderPreviewTests.tearDown
    photo = FolderPreviewTests.photo
    get_previews = FolderPreviewTests.get

    def toggle(self, name='Secret', value=True, manager=True):
        with fl.app.test_request_context('/api/folder-privacy', method='POST', json={'folder':name, 'private':value}), patch.object(folder_privacy, 'current_user', SimpleNamespace(can_manage_media=manager)):
            return fl.app.view_functions['api_folder_privacy'].__wrapped__()

    def seed(self):
        self.photo('Secret', 'private')
        self.photo('Secret/Child', 'child')
        self.photo('SecretSibling', 'public')
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("UPDATE photos SET ext='.jpg',camera_model='Camera',gps_lat=55,gps_lon=12")
            conn.execute("INSERT INTO people(id,name,created_at) VALUES(1,'Private person','2026')")
            pid=conn.execute("SELECT id FROM photos WHERE filename='private.jpg'").fetchone()[0]
            conn.execute("INSERT INTO faces(id,photo_id,person_id,embedding_json,created_at) VALUES(1,?,1,'[1,0]','2026')",(pid,))
            conn.commit()
        return pid

    def test_permissions_validation_and_inheritance(self):
        self.seed()
        self.assertEqual(self.toggle(manager=False)[1],403)
        self.assertEqual(self.toggle('../Secret')[1],400)
        self.assertEqual(self.toggle(value='true')[1],400)
        self.assertTrue(self.toggle().get_json()['private'])
        result=self.toggle('Secret/Child',False).get_json()
        self.assertTrue(result['private'])
        self.assertTrue(result['inherited'])

    def test_discovery_and_faces_restore_without_deleting_data(self):
        self.seed()
        with fl.closing(fl.get_conn()) as conn:
            before=[tuple(r) for r in conn.execute('SELECT * FROM faces')]
        self.toggle()
        with fl.app.test_request_context('/api/people'), patch.object(fl,'_current_user_acl_prefixes',return_value=None), patch.object(fl,'_enqueue_face_thumb_generation'):
            self.assertEqual(fl.api_people_list().get_json()['items'],[])
        with fl.app.test_request_context('/api/cameras'), patch.object(fl,'_is_rel_visible_for_current_user',return_value=True):
            self.assertEqual(fl.api_cameras.__wrapped__().get_json()['cameras'][0]['count'],1)
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual(fl._load_person_centroids(conn),[])
        for view in ['timeline','steder','kameraer','favorites']:
            with fl.app.test_request_context(), patch.object(fl,'_is_rel_visible_for_current_user',return_value=True):
                rows=fl.query_photos(view,'name_asc')
                self.assertFalse(any('Secret/' in r['rel_path'] for r in rows))
        with fl.app.test_request_context(), patch.object(fl,'_is_rel_visible_for_current_user',return_value=True):
            self.assertEqual(len(fl.query_photos('mapper','name_asc',folder='Secret')),2)
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM discovery_faces').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM photos').fetchone()[0],3)
            self.assertEqual(before,[tuple(r) for r in conn.execute('SELECT * FROM faces')])
        fl.init_db()
        self.assertEqual(self.get_previews(['Secret'])['Secret'],[])
        self.toggle(value=False)
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM discovery_faces').fetchone()[0],1)
        self.assertTrue(self.get_previews(['Secret'])['Secret'])

    def test_blur_is_backend_only_and_original_thumbnail_restores(self):
        self.seed()
        path=fl.THUMB_DIR/'private.jpg'
        image=Image.new('RGB',(64,64),'white')
        for x in range(64):
            for y in range(64):
                image.putpixel((x,y),(255,0,0) if (x+y)%2 else (0,0,255))
        image.save(path)
        original=path.read_bytes()
        self.toggle()
        with fl.app.test_request_context(), patch.object(fl,'_is_rel_visible_for_current_user',return_value=True):
            response=fl.api_thumb_file('private.jpg')
            response.direct_passthrough=False
            blurred=response.get_data()
            self.assertNotEqual(blurred,original)
            self.assertEqual(Image.open(BytesIO(blurred)).size,(64,64))
            self.assertIn('no-store',response.headers['Cache-Control'])
            self.assertEqual(fl.api_face_thumb(1)[1],404)
        self.assertEqual(path.read_bytes(),original)
        self.toggle(value=False)
        with fl.app.test_request_context(), patch.object(fl,'_is_rel_visible_for_current_user',return_value=True):
            response=fl.api_thumb_file('private.jpg');response.direct_passthrough=False
            self.assertEqual(response.get_data(),original)
            response.close()

    def test_private_moment_hidden_even_for_manager_and_indexing_skips(self):
        pid=self.seed()
        moment={'status':'accepted','photo_ids_json':json.dumps([pid])}
        manager=SimpleNamespace(can_manage_media=True)
        with patch.object(moments_service,'current_user',manager):
            self.assertTrue(moments_service.can_view(vars(fl),moment))
            self.toggle()
            self.assertFalse(moments_service.can_view(vars(fl),moment))
            with patch.object(fl,'_disk_path_from_rel_path') as disk:
                self.assertEqual(fl.index_faces_for_photo('uploads/originals/Secret/private.jpg'),0)
                disk.assert_not_called()
            self.toggle(value=False)
            self.assertTrue(moments_service.can_view(vars(fl),moment))

    def test_literal_paths_and_storage_mirrors(self):
        with fl.closing(fl.get_conn()) as conn:
            for rel in ['uploads/A_%/a.jpg','uploads/converted/A_%/b.jpg','uploads/originals/A_%/c.jpg','uploads/A_XX/d.jpg']:
                conn.execute('INSERT INTO photos(rel_path,filename) VALUES(?,?)',(rel,rel.rsplit('/',1)[-1]))
            conn.commit()
        self.toggle('A_%')
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual([r[0] for r in conn.execute('SELECT rel_path FROM discovery_photos')],['uploads/A_XX/d.jpg'])
