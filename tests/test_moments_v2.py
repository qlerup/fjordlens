import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import app as fjordlens
from moments_engine import curate, discover, photo_date
from tests import test_moments as legacy


def photo(pid, day, place=None, **extra):
    return dict(id=pid, captured_at=day, gps_name=place, favorite=0, **extra)


class DiscoveryTests(unittest.TestCase):
    def scan(self, rows, **kwargs):
        return discover(rows, min_photos=3, min_hours=1, **kwargs)[0]

    def test_germany_city_changes_and_quiet_days_form_one_trip(self):
        rows = [photo(1, '2024-07-12T10:00:00', 'Hamburg, Germany'),
                photo(2, '2024-07-14T12:00:00', 'Berlin, Tyskland'),
                photo(3, '2024-07-17T15:00:00', 'Dresden, Deutschland')]
        moments = self.scan(rows)
        self.assertEqual(len(moments), 1)
        self.assertEqual(moments[0]['primary_place'], 'Tyskland')
        self.assertEqual(moments[0]['end_date'], '2024-07-17')
        self.assertEqual(len(moments[0]['evidence']['chapters']), 3)

    def test_home_is_recurring_days_not_dense_holiday(self):
        rows = [photo(i+1, f'2024-0{i+1}-01T12:00:00', 'Aarhus, Denmark') for i in range(5)]
        rows += [photo(100+i, f'2024-07-12T{9+i//60:02}:{i%60:02}:00', 'Berlin, Germany') for i in range(180)]
        _, _, home = discover(rows, min_photos=3)
        self.assertEqual(home['name'], 'Aarhus, Denmark')

    def test_return_home_splits_two_visits(self):
        rows = []
        for day in (10, 13):
            rows += [photo(day*10+i, f'2024-07-{day}T{9+i:02}:00:00', 'Berlin, Germany') for i in range(3)]
        rows += [photo(999, '2024-07-12T12:00:00', 'Aarhus, Denmark')]
        self.assertEqual(len(self.scan(rows, manual_home={'name': 'Aarhus, Denmark'})), 2)

    def test_multicountry_trip_and_danish_day_visit(self):
        rows = [photo(1, '2024-07-01T10:00:00', 'Hamburg, Germany'),
                photo(2, '2024-07-02T10:00:00', 'Vienna, Austria'),
                photo(3, '2024-07-03T10:00:00', 'Venice, Italy')]
        result = self.scan(rows, manual_home={'name': 'Aarhus, Denmark'})
        self.assertEqual(result[0]['evidence']['countries'], ['DE', 'AT', 'IT'])
        rows = [photo(i, f'2024-08-01T{10+i}:00:00', 'Odense, Denmark') for i in range(1, 4)]
        self.assertEqual(self.scan(rows, manual_home={'name': 'Aarhus, Denmark'})[0]['kind'], 'event')

    def test_gpsless_photo_requires_matching_source_and_brackets(self):
        rows = [photo(1, '2024-07-01T10:00:00', 'Berlin, Germany', camera_model='Camera A'),
                photo(2, '2024-07-01T11:00:00', camera_model='Camera A'),
                photo(3, '2024-07-01T12:00:00', 'Berlin, Germany', camera_model='Camera A'),
                photo(4, '2024-07-01T11:30:00', camera_model='Camera B')]
        result = self.scan(rows)
        self.assertEqual(result[0]['photo_ids'], [1, 2, 4, 3])
        self.assertEqual(result[0]['evidence']['inferred_photo_count'], 1)
        self.assertIn('dagens eneste', ' '.join(result[0]['evidence']['reasons']))

    def test_separate_uploaders_do_not_interrupt_each_other(self):
        rows = [photo(i, f'2024-07-0{i}T10:00:00', 'Berlin, Germany', uploaded_by='a') for i in range(1, 4)]
        rows += [photo(10, '2024-07-02T11:00:00', 'Aarhus, Denmark', uploaded_by='b')]
        self.assertEqual(self.scan(rows, manual_home={'name': 'Aarhus, Denmark'})[0]['photo_ids'], [1, 2, 3])

    def test_offsets_and_fallback_dates_do_not_crash_or_claim_certainty(self):
        rows = [photo(1, '2024-07-01T10:00:00+02:00'), photo(2, '2024-07-01T11:00:00Z'),
                photo(3, None, modified_fs='2024-07-01T12:00:00')]
        result = self.scan(rows)
        self.assertEqual(result[0]['evidence']['confidence'], 'low')
        self.assertIn('fildato', ' '.join(result[0]['evidence']['reasons']))
        self.assertIsNone(photo_date({'captured_at': 'invalid'}))

    def test_short_zoo_visit_uses_repeated_existing_description(self):
        rows = [photo(i, f'2024-07-01T10:{i*15:02}:00', 'Odense, Denmark', ai_desc_caption='Giraffer i zoo') for i in range(3)]
        result = self.scan(rows)
        self.assertIn('zoo', result[0]['title'])

    def test_curation_spreads_days_and_removes_near_duplicates(self):
        rows = [photo(1, '2024-07-01T10:00:00', phash='00000000'),
                photo(2, '2024-07-01T10:01:00', phash='00000001'),
                photo(3, '2024-07-02T10:00:00', phash='ffffffff')]
        self.assertEqual([r['id'] for r in curate(rows, 3)], [1, 3])

    def test_gps_only_photos_use_offline_country(self):
        rows = [photo(i, f'2024-07-0{i}T10:00:00', gps_lat=52.52, gps_lon=13.405) for i in range(1, 4)]
        with patch('reverse_geocoder.search', return_value=[{'name': 'Berlin', 'cc': 'DE'}]) as geocode:
            result = self.scan(rows)
        self.assertEqual(result[0]['primary_place'], 'Tyskland')
        self.assertEqual(len(geocode.call_args.args[0]), 1)

    def test_invalid_partial_gps_is_ignored(self):
        rows = [photo(i, f'2024-07-01T{10+i}:00:00', gps_lat=52.0) for i in range(1, 4)]
        self.assertEqual(self.scan(rows)[0]['evidence']['confidence'], 'low')

    def test_repeated_work_visits_are_not_holidays(self):
        rows = []
        for month in range(1, 7):
            rows += [photo(month*10+i, f'2024-{month:02}-01T{10+i}:00:00', 'Hamburg, Germany') for i in range(3)]
        self.assertEqual(self.scan(rows, manual_home={'name': 'Aarhus, Denmark'}), [])


class MomentEditingTests(unittest.TestCase):
    tearDown = legacy.MomentDetectionTests.tearDown
    _insert_photo = legacy.MomentDetectionTests._insert_photo

    def setUp(self):
        legacy.MomentDetectionTests.setUp(self)
        self.previous.update(INSTALL_STATE_PATH=fjordlens.INSTALL_STATE_PATH,
                             DB_BOOTSTRAP_READY=fjordlens.DB_BOOTSTRAP_READY)
        fjordlens.INSTALL_STATE_PATH = self.uploads / 'install.json'
        fjordlens.DB_BOOTSTRAP_READY = True
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES('admin','unused',1,'admin',?)", (fjordlens.now_iso(),))
            conn.execute("INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES('viewer','unused',0,'user',?)", (fjordlens.now_iso(),))
            conn.commit()
        self.client = fjordlens.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = '1'
            session['_fresh'] = True

    def make_moment(self, day=10):
        for i in range(4):
            self._insert_photo(f'uploads/originals/{day}_{i}.jpg', f'2024-07-{day}T{10+i}:00:00', 'Berlin, Germany')
        fjordlens._detect_moment_candidates()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            return conn.execute("SELECT * FROM moments ORDER BY id DESC").fetchone()

    def test_scan_updates_suggestion_but_preserves_edit_and_removed_photo(self):
        row = self.make_moment()
        self._insert_photo('uploads/originals/new.jpg', '2024-07-10T15:00:00', 'Berlin, Germany')
        self.assertEqual(fjordlens._detect_moment_candidates()['updated'], 1)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute('SELECT * FROM moments').fetchone()
        ids = json.loads(row['photo_ids_json'])
        response = self.client.patch(f"/api/moments/{row['id']}", json=dict(title='Min tur', start_date='2024-07-10', end_date='2024-07-10', photo_ids=ids[:-1], revision=row['revision']))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(fjordlens._detect_moment_candidates()['created'], 0)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            edited = conn.execute('SELECT * FROM moments').fetchone()
        self.assertEqual(edited['title'], 'Min tur')
        self.assertEqual(json.loads(edited['photo_ids_json']), ids[:-1])

    def test_split_merge_and_rescan_keep_membership(self):
        row = self.make_moment()
        ids = json.loads(row['photo_ids_json'])
        response = self.client.post(f"/api/moments/{row['id']}/split", json=dict(photo_ids=ids[:2], revision=row['revision']))
        self.assertEqual(response.status_code, 200, response.get_json())
        other_id = response.get_json()['id']
        self.assertEqual(fjordlens._detect_moment_candidates()['created'], 0)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            rows = conn.execute('SELECT * FROM moments ORDER BY id').fetchall()
        self.assertEqual(len(rows), 2)
        self.assertFalse(set(json.loads(rows[0]['photo_ids_json'])) & set(json.loads(rows[1]['photo_ids_json'])))
        response = self.client.post(f"/api/moments/{row['id']}/merge", json=dict(other_id=other_id, revision=rows[0]['revision'], other_revision=rows[1]['revision']))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(fjordlens._detect_moment_candidates()['created'], 0)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            merged = conn.execute("SELECT * FROM moments WHERE status != 'dismissed'").fetchall()
        self.assertEqual(len(merged), 1)
        self.assertEqual(json.loads(merged[0]['photo_ids_json']), ids)

    def test_stale_revision_and_invalid_dates_rejected(self):
        row = self.make_moment()
        payload = dict(title='Test', start_date='2024-07-10', end_date='2024-07-10', photo_ids=json.loads(row['photo_ids_json']), revision=99)
        self.assertEqual(self.client.patch(f"/api/moments/{row['id']}", json=payload).status_code, 409)
        payload['revision'] = None
        self.assertEqual(self.client.patch(f"/api/moments/{row['id']}", json=payload).status_code, 409)
        payload.update(revision=0, end_date='2024-07-01')
        self.assertEqual(self.client.patch(f"/api/moments/{row['id']}", json=payload).status_code, 400)

    def test_saved_and_dismissed_are_not_regenerated(self):
        row = self.make_moment()
        self.client.post(f"/api/moments/{row['id']}/dismiss")
        self.assertEqual(fjordlens._detect_moment_candidates()['created'], 0)

    def test_edit_data_skips_ai_and_search_finds_library_photos(self):
        row = self.make_moment()
        with patch.object(fjordlens, '_ai_narrate_moment', side_effect=AssertionError('Must not call AI')):
            response = self.client.get(f"/api/moments/{row['id']}/edit-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(len(response.get_json()['item']['photos']), 4)
        self._insert_photo('archive/trip.jpg', '2024-07-10T16:00:00', 'Berlin, Germany')
        response = self.client.get('/api/moments/photo-search?start_date=2024-07-10&end_date=2024-07-10&place=berlin')
        self.assertEqual(len(response.get_json()['photos']), 5)
        response = self.client.get('/api/moments/photo-search?start_date=2024-07-10&end_date=2024-07-10&place=Tyskland')
        self.assertEqual(len(response.get_json()['photos']), 5)

    def test_settings_and_viewer_permissions(self):
        response = self.client.put('/api/moments/settings', json={'home': {'name': 'Aarhus, Denmark', 'lat': 56.15, 'lon': 10.2}})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get('/api/moments/settings').get_json()['home']['name'], 'Aarhus, Denmark')
        with self.client.session_transaction() as session:
            session['_user_id'] = '2'
        self.assertEqual(self.client.put('/api/moments/settings', json={'home': None}).status_code, 403)
        self.assertEqual(self.client.patch('/api/moments/1', json={}).status_code, 403)

    def test_running_video_blocks_edit(self):
        row = self.make_moment()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("UPDATE moments SET video_status='running'")
            conn.commit()
        response = self.client.post(f"/api/moments/{row['id']}/split", json=dict(photo_ids=json.loads(row['photo_ids_json'])[:2], revision=0))
        self.assertEqual(response.status_code, 409)

    def test_year_review_keeps_membership_and_updates_only_suggestions(self):
        self.make_moment()
        with patch.object(fjordlens, 'MOMENT_YEAR_REVIEW_MIN_PHOTOS', 3):
            self.assertEqual(fjordlens._detect_year_review_candidates()['created'], 1)
            self._insert_photo('archive/new.jpg', '2024-08-10T12:00:00')
            self.assertEqual(fjordlens._detect_year_review_candidates()['updated'], 1)
            with fjordlens.closing(fjordlens.get_conn()) as conn:
                row = conn.execute("SELECT * FROM moments WHERE kind='year_review'").fetchone()
            self.assertEqual(len(json.loads(row['photo_ids_json'])), 5)
            self.client.post(f"/api/moments/{row['id']}/accept")
            self._insert_photo('archive/newer.jpg', '2024-08-10T13:00:00')
            self.assertEqual(fjordlens._detect_year_review_candidates()['updated'], 0)

    def test_scan_state_is_shared_and_duplicate_start_is_rejected(self):
        # Hold the worker without timing-dependent sleeps; the DB remains the source
        # of truth even when another process has no local thread object.
        with patch('moments_service.threading.Thread'):
            response = self.client.post('/api/moments/detect')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(self.client.get('/api/moments/detect/status').get_json()['running'])
            self.assertEqual(self.client.post('/api/moments/detect').status_code, 409)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("UPDATE moment_scan_state SET result_json=?", (json.dumps({'phase': 'places', 'current': 2, 'total': 8}),))
            conn.commit()
        status = self.client.get('/api/moments/detect/status').get_json()
        self.assertTrue(status['running'])
        self.assertEqual(status['progress'], {'phase': 'places', 'current': 2, 'total': 8})
        self.assertIsNone(status['result'])
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("UPDATE moment_scan_state SET running=0,result_json=?", (json.dumps({'ok': True, 'created': 2}),))
            conn.commit()
        self.assertEqual(self.client.get('/api/moments/detect/status').get_json()['result']['created'], 2)

    def test_pending_regions_continue_without_another_user_click(self):
        import moments_service
        with patch.object(fjordlens, '_run_moment_detection', side_effect=[
                {'ok':True,'debug':{'poi_pending':3,'poi_lookups':18}},
                {'ok':True,'debug':{'poi_pending':0,'poi_lookups':3}}]) as run:
            result = moments_service.complete_detection(dict(get_conn=fjordlens.get_conn,_run_moment_detection=run))
            self.assertEqual(run.call_count,2)
            self.assertEqual(result['debug']['poi_pending'],0)

    def test_pending_regions_stop_if_a_batch_cannot_make_progress(self):
        import moments_service
        with patch.object(fjordlens, '_run_moment_detection', return_value=
                {'ok':True,'debug':{'poi_pending':3,'poi_lookups':0}}) as run:
            moments_service.complete_detection(dict(get_conn=fjordlens.get_conn,_run_moment_detection=run))
            self.assertEqual(run.call_count,1)

    def test_attraction_title_upgrade_preserves_user_choices(self):
        import moments_service
        row = self.make_moment()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            evidence = json.dumps({'attraction': {'name': 'Knuthenborg Safaripark', 'confidence': 'possible'}})
            conn.execute("UPDATE moments SET kind='event',evidence_json=? WHERE id=?", (evidence, row['id']))
            moments_service.migrate(conn)
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?', (row['id'],)).fetchone()[0],
                             'En tur til Knuthenborg Safaripark')
            for status, edited in [('accepted', 0), ('suggested', 1)]:
                conn.execute('UPDATE moments SET title=?,status=?,user_edited=? WHERE id=?',
                             ('Min egen titel', status, edited, row['id']))
                moments_service.migrate(conn)
                self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?', (row['id'],)).fetchone()[0], 'Min egen titel')

    def test_native_place_migration_updates_existing_photos_and_moment(self):
        import place_names
        row = self.make_moment()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("DELETE FROM settings WHERE key='native_place_names_v1'")
            conn.execute("UPDATE photos SET gps_name='Naestved, Denmark',metadata_json=?",
                         (json.dumps({'geo': {'city': 'Naestved', 'country': 'Denmark'}}),))
            conn.execute("INSERT INTO geo_cache(lat_rounded,lon_rounded,country,city,created_at) VALUES(1,2,'Denmark','Naestved','2026-09-06')")
            conn.execute("UPDATE moments SET primary_place='Naestved, Denmark',title='En dag i Naestved, Denmark' WHERE id=?", (row['id'],))
            place_names.migrate(conn)
            photo = conn.execute('SELECT gps_name,metadata_json FROM photos LIMIT 1').fetchone()
            self.assertEqual(photo['gps_name'], 'Næstved, Denmark')
            self.assertEqual(json.loads(photo['metadata_json'])['geo']['city'], 'Næstved')
            self.assertEqual(conn.execute('SELECT city FROM geo_cache WHERE lat_rounded=1').fetchone()[0], 'Næstved')
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?', (row['id'],)).fetchone()[0], 'En dag i Næstved, Denmark')
            place_names.migrate(conn)  # Idempotent on subsequent startup.

    def test_viewer_cannot_see_moment_from_hidden_folders(self):
        row = self.make_moment()
        with self.client.session_transaction() as session:
            session['_user_id'] = '2'
        response = self.client.get('/api/moments')
        self.assertEqual(response.get_json()['suggested'], [])
        for suffix in ('', '/render-video/status', '/video'):
            self.assertEqual(self.client.get(f"/api/moments/{row['id']}{suffix}").status_code, 404)

    def test_manual_title_survives_ai_and_playback_is_capped(self):
        row = self.make_moment()
        ids = json.loads(row['photo_ids_json'])
        self.client.patch(f"/api/moments/{row['id']}", json=dict(title='Min titel', start_date='2024-07-10', end_date='2024-07-10', photo_ids=ids, revision=0))
        with patch.object(fjordlens, '_ai_narrate_moment', return_value={'title': 'AI title', 'cards': []}), patch.object(fjordlens, 'MOMENT_MAX_SLIDES', 2):
            response = self.client.get(f"/api/moments/{row['id']}")
        self.assertEqual(response.status_code, 200, response.get_json())
        item = response.get_json()['item']
        self.assertEqual(item['title'], 'Min titel')
        self.assertEqual(len(item['photo_ids']), 4)
        self.assertEqual(len(item['photos']), 2)
        self.assertEqual(sum(s['type'] in ('photo', 'video') for s in item['script']), 2)
        self.assertEqual(item['script'][0]['style'], 'intro')
        self.assertEqual(item['script'][-1]['style'], 'outro')

    def test_migration_is_repeatable_and_keeps_existing_data(self):
        row = self.make_moment()
        fjordlens.init_db()
        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            stored = conn.execute('SELECT * FROM moments').fetchone()
        self.assertEqual(stored['photo_ids_json'], row['photo_ids_json'])

    def test_corrected_home_retires_only_automatic_suggestions(self):
        self.make_moment()
        self.client.put('/api/moments/settings', json={'home': {'name': 'Berlin, Germany'}})
        result = fjordlens._detect_moment_candidates()
        self.assertEqual(result['retired'], 1)
        self.assertEqual(self.client.get('/api/moments').get_json()['suggested'], [])

    def test_complete_video_export_writes_playable_mp4(self):
        import shutil
        from PIL import Image
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                self.skipTest('ffmpeg is not installed')
        row = self.make_moment()
        directory = self.uploads / 'originals'
        directory.mkdir(exist_ok=True)
        for i in range(4):
            Image.new('RGB', (800, 600), '#709181').save(directory / f'10_{i}.jpg')
        with patch.object(fjordlens.shutil, 'which', return_value=ffmpeg), patch.object(fjordlens, '_ai_narrate_moment', return_value=None), patch.object(fjordlens, 'MOMENT_MAX_SLIDES', 2), patch.object(fjordlens, 'MOMENT_VIDEO_WIDTH', 640), patch.object(fjordlens, 'MOMENT_VIDEO_HEIGHT', 360):
            fjordlens._render_moment_video(row['id'])
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            result = conn.execute('SELECT * FROM moments WHERE id=?', (row['id'],)).fetchone()
        self.assertEqual(result['video_status'], 'done', result['video_error'])
        self.assertTrue((self.converted / result['video_rel_path']).is_file())


if __name__ == '__main__':
    unittest.main()
