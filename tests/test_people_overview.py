from unittest.mock import patch
import unittest

import app
import people_stats
from tests.test_moments import MomentDetectionTests


class PeopleOverviewTests(unittest.TestCase):
    setUp = MomentDetectionTests.setUp
    tearDown = MomentDetectionTests.tearDown

    def seed(self):
        with app.closing(app.get_conn()) as conn:
            conn.execute("INSERT INTO people(id,name,created_at) VALUES(1,'Ukendt-1','2026'),(2,'Anna','2026')")
            conn.execute("INSERT INTO photos(id,rel_path,filename,ext) VALUES(1,'allowed/a.jpg','a.jpg','.jpg'),(2,'allowed/a.MOV','a.MOV',NULL),(3,'private/b.jpg','b.jpg','.jpg')")
            for fid, photo, person, frame, confidence in [(1,1,1,None,.8),(2,1,1,None,.9),(3,2,1,1,.99),(4,2,2,None,.99),(5,2,None,2,.99)]:
                conn.execute('INSERT INTO faces(id,photo_id,person_id,frame_sec,confidence,created_at) VALUES(?,?,?,?,?,?)', (fid,photo,person,frame,confidence,'2026'))
            conn.commit()

    def items(self, acl=None, query=''):
        with app.app.test_request_context('/api/people'+query), patch.object(app, '_current_user_acl_prefixes', return_value=acl), patch.object(app, '_enqueue_face_thumb_generation'):
            return {x['id']: x for x in app.api_people_list().get_json()['items']}

    def test_still_portrait_unique_counts_and_automatic_promotion(self):
        self.seed()
        for acl in (None, ['allowed']):
            items = self.items(acl)
            self.assertEqual(items[1]['thumb_url'], '/api/face-thumb/2')
            self.assertEqual(items[1]['count'], 2)
            self.assertEqual(items[1]['image_count'], 1)
            self.assertTrue(items[1]['single_find'])
            self.assertFalse(items[2]['single_find'])
            self.assertIsNone(items[2]['thumb_url'])
            self.assertIsNone(items['unknown']['thumb_url'])
        with app.closing(app.get_conn()) as conn:
            conn.execute("INSERT INTO faces(photo_id,person_id,created_at) VALUES(3,1,'2026')")
            conn.commit()
        self.assertFalse(self.items()[1]['single_find'])
        self.assertTrue(self.items(['allowed'])[1]['single_find'])
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE people SET name='Peter' WHERE id=1")
            conn.commit()
        self.assertFalse(self.items(['allowed'])[1]['single_find'])

    def test_single_find_does_not_change_explicit_hidden_state(self):
        self.seed()
        with app.closing(app.get_conn()) as conn:
            conn.execute('UPDATE people SET hidden=1 WHERE id=1')
            conn.commit()
        self.assertNotIn(1, self.items())
        self.assertTrue(self.items(query='?include_hidden=1')[1]['single_find'])

    def test_explicit_rename_never_merges_an_existing_name(self):
        self.seed()
        with app.app.test_request_context('/api/people/1/rename', method='POST', json={'name':'Anna','action':'rename'}), patch.object(app, '_forbid_user_role_for_maintenance', return_value=None):
            response, status = app.api_people_rename(1)
            self.assertEqual(status, 409)
        with app.closing(app.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM people').fetchone()[0], 2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM faces WHERE person_id=1').fetchone()[0], 3)
        with app.app.test_request_context('/api/people/1/rename', method='POST', json={'name':'Peter','action':'rename'}), patch.object(app, '_forbid_user_role_for_maintenance', return_value=None):
            self.assertEqual(app.api_people_rename(1).get_json()['name'], 'Peter')


class FastPeopleOverviewTests(PeopleOverviewTests):
    def setUp(self):
        super().setUp()
        with app.closing(app.get_conn()) as conn:
            people_stats._ensure_people_stats_columns(conn)
            people_stats._install_people_stats_triggers(conn)
            people_stats._backfill_people_stats(conn)

    def items(self, acl=None, query=''):
        people_stats._refresh_dirty_covers(app)
        view = people_stats._make_fast_people_view(app.app, app, app.api_people_list)
        with app.app.test_request_context('/api/people'+query), patch.object(app, '_current_user_acl_prefixes', return_value=acl), patch.object(app, '_enqueue_face_thumb_generation'), patch.dict(app.app.view_functions, api_people_list=view):
            return {x['id']: x for x in app.app.dispatch_request().get_json()['items']}

    def test_backfill_replaces_old_video_covers(self):
        self.seed()
        with app.closing(app.get_conn()) as conn:
            conn.execute('UPDATE people SET cover_face_id=3,cover_policy_version=0')
            conn.commit()
            self.assertTrue(people_stats._ensure_people_stats_columns(conn))
            people_stats._backfill_people_stats(conn)
            self.assertFalse(people_stats._ensure_people_stats_columns(conn))
        self.assertEqual(self.items()[1]['thumb_url'], '/api/face-thumb/2')
