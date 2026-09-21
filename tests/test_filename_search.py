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

    def test_metadata_and_folder_names_are_not_searched(self):
        self.assertFalse(fl.matches_search({'filename': 'IMG_0398_1.jpg', 'ai_desc_caption': 'En hund',
                                           'people_names': 'hund', 'rel_path': 'uploads/hund/image.jpg'}, 'hund'))

    def test_sparse_search_in_5000_photos_only_materializes_matching_records(self):
        fixture = fixtures.GalleryBrowseTests()
        fixture.setUp()
        try:
            with fl.closing(fl.get_conn()) as conn:
                conn.executemany('INSERT INTO photos(rel_path,filename,ai_desc_caption) VALUES(?,?,?)',
                                 [(f'uploads/originals/Album/IMG_{i:04}.jpg', f'IMG_{i:04}.jpg', 'unique-target')
                                  for i in range(5000)])
                conn.execute('INSERT INTO photos(rel_path,filename) VALUES(?,?)',
                             ('uploads/originals/Album/unique-target.jpg', 'unique-target.jpg'))
                conn.commit()
            with patch.object(fl, 'row_to_public', wraps=fl.row_to_public) as convert, \
                 patch.object(fl, 'matches_search', side_effect=AssertionError('No Python filtering')), \
                 patch.object(fl, '_ai_expand_query_tags', side_effect=AssertionError('No AI expansion')):
                data = fixture.page(fixture._authenticated_client(), 'mapper', folder='Album', q='unique-target')
            self.assertEqual([p['filename'] for p in data['items']], ['unique-target.jpg'])
            self.assertEqual(convert.call_count, 1)
            self.assertFalse(data['has_more'])
        finally:
            fixture.tearDown()

    def test_sql_search_treats_wildcards_and_quotes_literally(self):
        fixture = fixtures.GalleryBrowseTests()
        fixture.setUp()
        try:
            with fl.closing(fl.get_conn()) as conn:
                for name in ('part_1.jpg', 'partA1.jpg', '100%.jpg', "Peter's.jpg", 'BLÅBÆR.jpg'):
                    conn.execute('INSERT INTO photos(rel_path,filename) VALUES(?,?)', ('uploads/originals/Album/'+name, name))
                conn.commit()
            for query, expected in [('part_1', 'part_1.jpg'), ('%', '100%.jpg'), ("Peter's", "Peter's.jpg"), ('blåbær', 'BLÅBÆR.jpg')]:
                data = fixture.page(fixture._authenticated_client(), q=query)
                self.assertEqual([p['filename'] for p in data['items']], [expected])
        finally:
            fixture.tearDown()

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
