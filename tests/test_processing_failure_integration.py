import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import app as fjordlens


class ProcessingFailureIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.previous = {name: getattr(fjordlens, name) for name in
                         ('DB_PATH', 'PHOTO_DIR', 'UPLOAD_DIR', 'THUMB_DIR', 'CONVERSION_WORK_DIR')}
        for name, leaf in [('DB_PATH', 'db.sqlite'), ('PHOTO_DIR', 'photos'), ('UPLOAD_DIR', 'uploads'),
                           ('THUMB_DIR', 'thumbs'), ('CONVERSION_WORK_DIR', 'work')]:
            setattr(fjordlens, name, root / leaf)
            if name != 'DB_PATH':
                (root / leaf).mkdir()
        fjordlens.init_db()
        (fjordlens.PHOTO_DIR / 'a.jpg').write_bytes(b'corrupt')
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES('a.jpg','a.jpg','.jpg')")
            conn.commit()
            self.pid = conn.execute("SELECT id FROM photos WHERE rel_path='a.jpg'").fetchone()['id']

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.temp.cleanup()

    def test_face_failure_flag_and_zero_face_success(self):
        with patch.object(fjordlens, '_ai_detect_faces_path', return_value=None):
            fjordlens.index_faces_for_photo('a.jpg')
        self.assertEqual(fjordlens.processing_failures.items()[0]['stage'], 'faces')
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 1)
        with patch.object(fjordlens, '_ai_detect_faces_path', return_value=[]):
            fjordlens.index_faces_for_photo('a.jpg')
        self.assertEqual(fjordlens.processing_failures.items(), [])
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 0)
        with patch.object(fjordlens, '_ai_detect_faces_path', return_value=None):
            fjordlens.index_faces_for_photo('a.jpg')
        # Existing coverage semantics intentionally remain unchanged.
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 0)
        self.assertEqual(fjordlens.processing_failures.items()[0]['stage'], 'faces')

    def test_ai_false_results_are_flagged_by_actual_entry_points(self):
        with patch.object(fjordlens, '_ai_embed_image_path', return_value=None):
            self.assertFalse(fjordlens._embed_one_photo(self.pid, 'a.jpg'))
        with (patch.object(fjordlens, 'ai_desc_model_enabled', return_value='qwen'),
              patch.object(fjordlens, '_ai_describe_image_path', return_value=None)):
            self.assertFalse(fjordlens._describe_one_photo(self.pid, 'a.jpg'))
        self.assertEqual({r['stage'] for r in fjordlens.processing_failures.items()}, {'embeddings', 'descriptions'})

    def test_metadata_partial_failure_survives_upsert(self):
        with (patch.object(fjordlens, '_exif_from_any_source', return_value={}),
              patch.object(fjordlens, '_enrich_metadata_weather')):
            meta = fjordlens.extract_metadata(fjordlens.PHOTO_DIR / 'a.jpg', 'a.jpg', generate_thumb=False)
            fjordlens.upsert_photo(meta)
        self.assertTrue(meta.get('thumb_error'))
        self.assertEqual(fjordlens.processing_failures.items()[0]['stage'], 'metadata')

    def test_conversion_failure_tracks_staged_source_not_temporary_path(self):
        source = fjordlens._staged_upload_path('uploads/originals/a.mov')
        source.parent.mkdir(parents=True)
        source.write_bytes(b'video')
        def broken(src, dst):
            raise RuntimeError('conversion failed')
        with patch.object(fjordlens, 'CONVERT_URL_EXPLICIT', False):
            with self.assertRaisesRegex(RuntimeError, 'conversion failed'):
                fjordlens._convert_on_local_storage(source, fjordlens.UPLOAD_DIR / 'a.mp4', broken)
        row = fjordlens.processing_failures.items()[0]
        self.assertEqual((row['rel_path'], row['stage']), ('uploads/originals/a.mov', 'conversion'))


if __name__ == '__main__':
    unittest.main()
