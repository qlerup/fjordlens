import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import app as fjordlens


class FolderPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {key: getattr(fjordlens, key) for key in ('DB_PATH', 'THUMB_DIR', 'UPLOAD_DIR')}
        fjordlens.DB_PATH = root / 'test.db'
        fjordlens.THUMB_DIR = root / 'thumbs'
        fjordlens.UPLOAD_DIR = root / 'uploads'
        fjordlens.THUMB_DIR.mkdir()
        fjordlens.UPLOAD_DIR.mkdir()
        fjordlens.init_db()

    def tearDown(self):
        for key, value in self.previous.items():
            setattr(fjordlens, key, value)
        self.tempdir.cleanup()

    def photo(self, folder, name, thumb=True):
        # No original file is created: previews must work from the thumbnail
        # and database even while the NAS is unavailable.
        thumb_name = name + '.jpg'
        if thumb:
            Image.new('RGB', (16, 12), 'green').save(fjordlens.THUMB_DIR / thumb_name)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('INSERT INTO photos(rel_path,filename,thumb_name) VALUES(?,?,?)',
                         (f'uploads/originals/{folder}/{name}.jpg', name + '.jpg', thumb_name))
            conn.commit()
        return '/api/thumbs/' + thumb_name

    def get(self, folders):
        with fjordlens.app.test_request_context('/api/folder-previews', query_string={'folders_format': 'multi', 'folders': folders}), \
             patch.object(fjordlens, '_sync_upload_folder_from_disk') as sync, \
             patch.object(fjordlens, '_disk_path_from_rel_path') as original, \
             patch.object(fjordlens, 'row_to_public') as public:
            result = fjordlens.api_folder_previews_get().get_json()['items']
            sync.assert_not_called()
            original.assert_not_called()
            public.assert_not_called()
            return result

    def test_cold_and_saved_previews_use_thumbs_without_reading_nas(self):
        urls = [self.photo('Family, 2026', str(i)) for i in range(4)]
        for _ in range(2):
            self.assertEqual(set(self.get(['Family, 2026'])['Family, 2026']), set(urls))

    def test_missing_thumbnails_never_fall_back_to_originals(self):
        self.photo('Empty', 'missing', thumb=False)
        self.assertEqual(self.get(['Empty'])['Empty'], [])
        url = self.photo('Empty', 'ready')
        self.assertEqual(self.get(['Empty'])['Empty'], [url])

    def test_legacy_original_covers_are_replaced_and_manual_thumbs_preserved(self):
        urls = [self.photo('Folder', str(i)) for i in range(5)]
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('INSERT INTO folder_previews(folder_path,previews_json,updated_at) VALUES(?,?,?)',
                         ('Folder', json.dumps(['/api/viewable/uploads/originals/Folder/0.jpg']), fjordlens.now_iso()))
            conn.commit()
        self.assertTrue(all(url.startswith('/api/thumbs/') for url in self.get(['Folder'])['Folder']))
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('UPDATE folder_previews SET previews_json=?', (json.dumps([urls[4], urls[1]]),))
            conn.commit()
        self.assertEqual(self.get(['Folder'])['Folder'], [urls[4], urls[1]])

    def test_removed_photo_does_not_stay_in_saved_cover(self):
        url = self.photo('Folder', 'one')
        self.assertEqual(self.get(['Folder'])['Folder'], [url])
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('DELETE FROM photos')
            conn.commit()
        self.assertEqual(self.get(['Folder'])['Folder'], [])

    def test_folder_listing_skips_hidden_storage_trees(self):
        for rel in ['Visible/Child', 'originals/Hidden', 'converted/Hidden', '@eaDir/Hidden']:
            (fjordlens.UPLOAD_DIR / rel).mkdir(parents=True)
        original_walk = fjordlens.os.walk
        walked = []
        def walk(*args, **kwargs):
            for entry in original_walk(*args, **kwargs):
                walked.append(Path(entry[0]).relative_to(fjordlens.UPLOAD_DIR).as_posix())
                yield entry
        with patch.object(fjordlens.os, 'walk', side_effect=walk):
            self.assertEqual(fjordlens._list_upload_subdirs(fjordlens.UPLOAD_DIR), ['', 'Visible', 'Visible/Child'])
        self.assertEqual(walked, ['.', 'Visible', 'Visible/Child'])


if __name__ == '__main__':
    unittest.main()
