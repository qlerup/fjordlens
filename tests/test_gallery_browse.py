"""Gallery page regressions: bounded reads, filtering, mirror copies and no disk scan."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import app as fl
import test_video_autoplay_settings as fixtures


class GalleryBrowseTests(unittest.TestCase):
    setUp = fixtures.VideoAutoplaySettingsTests.setUp
    tearDown = fixtures.VideoAutoplaySettingsTests.tearDown
    _authenticated_client = fixtures.VideoAutoplaySettingsTests._authenticated_client
    def seed(self, count=180, mirrors=False):
        with fl.closing(fl.get_conn()) as conn:
            for i in range(count):
                folder = 'Allowed' if i % 5 == 0 else 'Other'
                filename = f"{'needle' if i % 7 == 0 else 'image'}-{i:04}.jpg"
                date = (datetime(2026, 1, 1) + timedelta(seconds=i)).isoformat()
                for storage in (['originals', 'converted'] if mirrors else ['originals']):
                    conn.execute('INSERT INTO photos(rel_path,filename,ext,captured_at,camera_model,favorite) VALUES(?,?,?,?,?,?)',
                                 (f'uploads/{storage}/{folder}/{filename}', filename, '.jpg', date, 'Test camera', 1))
            conn.commit()

    def page(self, client, view='timeline', **params):
        response = client.get('/api/photos', query_string={'browse': '1', 'view': view, 'limit': 20, **params})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertNotIn('error', data)
        return data

    def test_all_four_views_return_small_pages_without_disk_sync_or_count(self):
        self.seed()
        with patch.object(fl, '_sync_upload_folder_from_disk', side_effect=AssertionError('must not scan')) as sync, \
             patch.object(fl, 'count_mapper_photos', side_effect=AssertionError('must not count')) as count:
            for view in ('timeline', 'kameraer', 'favorites', 'mapper'):
                with self.subTest(view=view):
                    data = self.page(self._authenticated_client(), view, folder='Allowed' if view == 'mapper' else '', direct='1' if view == 'mapper' else '0')
                    self.assertEqual(len(data['items']), 20)
                    self.assertTrue(data['has_more'])
                    self.assertIsNone(data['total'])
            sync.assert_not_called()
            count.assert_not_called()

    def test_full_last_page_and_mirrors_do_not_drop_or_repeat_photos(self):
        self.seed(240, mirrors=True)
        client = self._authenticated_client()
        ids, offset = [], 0
        for _ in range(12):
            data = self.page(client, 'kameraer', offset=offset, limit=20)
            self.assertEqual(len(data['items']), 20)
            ids.extend(item['filename'] for item in data['items'])
            self.assertTrue(all('/converted/' in item['rel_path'] for item in data['items']))
            offset = data['next_offset']
        self.assertFalse(data['has_more'])
        self.assertEqual(len(set(ids)), 240)

    def test_search_and_folder_permissions_fill_pages_before_deciding_the_end(self):
        self.seed(350)
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn, 2, [{'folder_path': 'Allowed', 'permission': 'view'}])
            conn.commit()
        client = self._authenticated_client(2)
        with patch.object(fl, 'AI_QUERY_EXPAND_ENABLED', False):
            first = self.page(client, 'favorites', limit=6, q='needle')
            last = self.page(client, 'favorites', limit=6, q='needle', offset=first['next_offset'])
        self.assertEqual(len(first['items']), 6)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(last['items']), 4)
        self.assertFalse(last['has_more'])
        items = first['items'] + last['items']
        self.assertEqual(len({item['id'] for item in items}), 10)
        self.assertTrue(all('/Allowed/' in item['rel_path'] and 'needle' in item['filename'] for item in items))

    def test_missing_permissions_return_empty_page(self):
        self.seed()
        data = self.page(self._authenticated_client(2))
        self.assertEqual(data['items'], [])
        self.assertFalse(data['has_more'])

    def test_first_page_builds_only_a_bounded_number_of_public_photo_records(self):
        self.seed(1000)
        with patch.object(fl, 'row_to_public', wraps=fl.row_to_public) as convert:
            data = self.page(self._authenticated_client(), 'kameraer', limit=60)
        self.assertEqual(len(data['items']), 60)
        self.assertLessEqual(convert.call_count, 64)

    def test_mapper_direct_only_does_not_include_descendants(self):
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("INSERT INTO photos(rel_path,filename) VALUES('uploads/originals/Allowed/direct.jpg','direct.jpg')")
            conn.execute("INSERT INTO photos(rel_path,filename) VALUES('uploads/originals/Allowed/Nested/deep.jpg','deep.jpg')")
            conn.commit()
        data = self.page(self._authenticated_client(), 'mapper', folder='Allowed', direct='1')
        self.assertEqual([item['filename'] for item in data['items']], ['direct.jpg'])

    def test_camera_folders_are_deduplicated_without_loading_photo_metadata(self):
        self.seed(240, mirrors=True)
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("UPDATE photos SET camera_model=' Second camera ' WHERE rel_path LIKE '%/Allowed/%'")
            conn.commit()
        with patch.object(fl, 'row_to_public', side_effect=AssertionError('overview must not load photos')):
            response = self._authenticated_client().get('/api/cameras')
        self.assertEqual(response.status_code, 200)
        cameras = response.get_json()['cameras']
        self.assertEqual([(c['model'], c['count']) for c in cameras], [('Second camera', 48), ('Test camera', 192)])
        client = self._authenticated_client()
        first = self.page(client, 'kameraer', camera='Second camera', limit=20)
        second = self.page(client, 'kameraer', camera='Second camera', limit=20, offset=first['next_offset'])
        self.assertEqual(len(first['items']), 20)
        self.assertEqual(len(second['items']), 20)
        self.assertTrue(all(i['camera_model'].strip() == 'Second camera' for i in first['items'] + second['items']))
        self.assertEqual(len({i['id'] for i in first['items'] + second['items']}), 40)
        self.assertEqual(self.page(client, 'kameraer', camera="' OR 1=1 --")['items'], [])

    def test_camera_folder_names_counts_and_covers_respect_permissions(self):
        self.seed(100)
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("UPDATE photos SET camera_model='Private camera', thumb_name='private.jpg' WHERE rel_path LIKE '%/Other/%'")
            conn.execute("UPDATE photos SET thumb_name='allowed.jpg' WHERE rel_path LIKE '%/Allowed/%'")
            fl._set_user_allowed_folders(conn, 2, [{'folder_path': 'Allowed', 'permission': 'view'}])
            conn.commit()
        viewer = self._authenticated_client(2)
        self.assertEqual(viewer.get('/api/cameras').get_json()['cameras'],
                         [{'model': 'Test camera', 'count': 20, 'thumb_url': '/api/thumbs/allowed.jpg'}])
        self.assertEqual(self.page(viewer, 'kameraer', camera='Private camera')['items'], [])
        self.assertEqual(fl.app.test_client().get('/api/cameras').status_code, 401)

    def test_camera_folder_search_and_missing_camera_metadata(self):
        self.seed(100)
        with fl.closing(fl.get_conn()) as conn:
            conn.execute("UPDATE photos SET camera_model='   ' WHERE rel_path LIKE '%/Other/%'")
            conn.commit()
        client = self._authenticated_client()
        self.assertEqual(len(client.get('/api/cameras?q=TEST').get_json()['cameras']), 1)
        self.assertEqual(client.get('/api/cameras?q=missing').get_json()['cameras'], [])
