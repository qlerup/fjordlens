import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as fl


class FolderMoveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = []
        overrides = dict(DATA_DIR=root, DB_PATH=root/'db.sqlite', UPLOAD_DIR=root/'uploads', THUMB_DIR=root/'thumbs',
                         INSTALL_STATE_PATH=root/'install.json', DB_BOOTSTRAP_READY=False)
        for key,value in overrides.items():
            p = patch.object(fl,key,value); p.start(); self.patches.append(p)
        fl.init_db()
        for kind in ('originals','converted'):
            path = fl.UPLOAD_DIR/kind/'Old'/'Album'/'Nested'; path.mkdir(parents=True)
            (path/'file.jpg').write_bytes(kind.encode())
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES('uploads/originals/Old/Album/Nested/file.jpg','file.jpg','.jpg')")
            self.photo_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.commit()
        for key,value in {
            '_forbid_media_management':lambda:None,
            '_current_user_folder_permission_for_rel':lambda rel:'edit',
            '_any_upload_transfer_active':lambda:False,
            '_any_regular_upload_postprocess_running':lambda:False,
            '_direct_upload_active_rels_snapshot':lambda:set(),
            '_pending_upload_rels_snapshot':lambda:set(),
            'UPLOAD_FOLDER_SYNC_RUNNING':set(),
            'current_user':SimpleNamespace(is_admin=True,id=1),
            '_upload_settings_payload':lambda destination:{'ok':True,'folders':[]},
            '_audit_actor':lambda:'test', 'log_event':lambda *a,**kw:None,
        }.items():
            p = patch.object(fl,key,value); p.start(); self.patches.append(p)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def move(self,parent,source='Old/Album'):
        with fl.app.test_request_context('/api/settings/upload-folder-move',method='POST',json={'path':source,'parent':parent}):
            result = fl.api_settings_upload_folder_rename()
            if isinstance(result,tuple): return result[1], result[0].get_json()
            return result.status_code,result.get_json()

    def test_moves_both_trees_and_preserves_photo_id(self):
        status,data = self.move('New')
        self.assertEqual(status,200,data)
        for kind in ('originals','converted'):
            self.assertEqual((fl.UPLOAD_DIR/kind/'New/Album/Nested/file.jpg').read_bytes(),kind.encode())
            self.assertFalse((fl.UPLOAD_DIR/kind/'Old/Album').exists())
            self.assertTrue((fl.UPLOAD_DIR/kind/'Old').is_dir())
        with fl.closing(fl.get_conn()) as conn:
            row = conn.execute('SELECT id,rel_path FROM photos').fetchone()
            self.assertEqual(row['id'],self.photo_id)
            self.assertEqual(row['rel_path'],'uploads/originals/New/Album/Nested/file.jpg')
        self.assertEqual(self.move('',source='New/Album')[0],200)
        self.assertTrue((fl.UPLOAD_DIR/'originals/Album/Nested/file.jpg').exists())

    def test_conflicts_self_and_descendants_leave_files_unchanged(self):
        self.assertEqual(self.move('Old/Album')[0],400)
        self.assertEqual(self.move('Old/Album/Nested')[0],400)
        self.assertEqual(self.move('../escape')[0],400)
        target = fl.UPLOAD_DIR/'converted/New/Album'; target.mkdir(parents=True)
        self.assertEqual(self.move('New')[0],409)
        self.assertTrue((fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').exists())

    def test_database_failure_rolls_back_both_trees_and_new_parents(self):
        with patch.object(fl,'_apply_upload_folder_rename_db',side_effect=RuntimeError('test failure')):
            self.assertEqual(self.move('New')[0],500)
        for kind in ('originals','converted'):
            self.assertTrue((fl.UPLOAD_DIR/kind/'Old/Album/Nested/file.jpg').exists())
            self.assertFalse((fl.UPLOAD_DIR/kind/'New').exists())

    def test_stale_database_conflict_is_not_deleted(self):
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES('uploads/originals/New/Album/Nested/file.jpg','file.jpg','.jpg')")
            conn.commit()
        self.assertEqual(self.move('New')[0],500)
        with fl.closing(fl.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0],2)
        self.assertTrue((fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').exists())

    def test_busy_upload_is_rejected(self):
        with patch.object(fl,'_any_upload_transfer_active',return_value=True):
            self.assertEqual(self.move('New')[0],409)

    def test_destination_permission_is_required(self):
        with patch.object(fl,'current_user',SimpleNamespace(is_admin=False,id=1)), patch.object(fl,'_current_user_folder_permission_for_rel',return_value='view'):
            self.assertEqual(self.move('New')[0],403)

    def test_wildcards_in_folder_names_do_not_change_neighbour_metadata(self):
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("INSERT INTO folder_previews(folder_path,previews_json,updated_at) VALUES('A_/Nested','[]','now'),('AB/Nested','[]','now')")
            conn.commit()
        fl._apply_upload_folder_rename_db('A_','Moved',reject_conflicts=True)
        with fl.closing(fl.get_conn()) as conn:
            paths = [r[0] for r in conn.execute('SELECT folder_path FROM folder_previews')]
        self.assertIn('AB/Nested',paths)
        self.assertIn('Moved/Nested',paths)
        self.assertNotIn('A_/Nested',paths)
