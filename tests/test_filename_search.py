import unittest
from unittest.mock import patch

import app as fl
import test_gallery_browse as fixtures


class FilenameSearchTests(unittest.TestCase):
    def test_names_and_partial_names_ignore_case_and_media_extension(self):
        for ext in ('.jpg', '.mp4', '.heic'):
            photo = {'filename': 'IMG_0398_1' + ext}
            for query in ('IMG_0398_1', 'img_0398_1', '0398', 'IMG_0398', 'IMG_0398_1.jpg'):
                with self.subTest(ext=ext, query=query):
                    self.assertTrue(fl.matches_search(photo, query))
            self.assertFalse(fl.matches_search(photo, 'IMG_0399_1'))

    def test_hyphens_spaces_and_danish_characters(self):
        for name, query in [('image-0001.jpg', 'image-0001'),
                            ('Min ferie 2026.mp4', 'Min ferie'), ('Blåbær.jpg', 'blåbær')]:
            self.assertTrue(fl.matches_search({'filename': name}, query))

    def test_extension_alone_does_not_match_filename_or_path(self):
        photo = {'filename': 'IMG_0398_1.jpg', 'rel_path': 'uploads/Album/IMG_0398_1.jpg'}
        self.assertFalse(fl.matches_search(photo, 'jpg'))

    def test_description_search_is_preserved(self):
        self.assertTrue(fl.matches_search({'filename': 'IMG_0398_1.jpg', 'ai_desc_caption': 'En hund'}, 'hund'))

    def test_api_returns_matching_names_across_media_types(self):
        fixture = fixtures.GalleryBrowseTests()
        fixture.setUp()
        try:
            with fl.closing(fl.get_conn()) as conn:
                for name in ('IMG_0398_1.jpg', 'IMG_0398_1.mp4', 'IMG_0399_1.jpg'):
                    conn.execute('INSERT INTO photos(rel_path,filename,ext) VALUES(?,?,?)',
                                 ('uploads/originals/Album' + fl.Path(name).suffix + '/' + name, name, fl.Path(name).suffix))
                conn.commit()
            with patch.object(fl, 'AI_QUERY_EXPAND_ENABLED', False):
                data = fixture.page(fixture._authenticated_client(), q='IMG_0398_1')
            self.assertEqual({p['filename'] for p in data['items']}, {'IMG_0398_1.jpg', 'IMG_0398_1.mp4'})
        finally:
            fixture.tearDown()
