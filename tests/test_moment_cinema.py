import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import moment_cinema as cinema
import moment_places
from moments_engine import discover
from tests.test_moments_v2 import photo


class CinemaTests(unittest.TestCase):
    def test_timeline_has_intro_chapters_overlays_and_real_times_only(self):
        rows = [photo(i, f'2024-07-{10+i//4}T12:30:00', 'Berlin, Germany', width=800, height=1200) for i in range(8)]
        rows[-1].update(captured_at=None, modified_fs='2024-07-11T13:00:00')
        moment = dict(title='Sommer i Berlin', primary_place='Berlin', start_date='2024-07-10', end_date='2024-07-11')
        script = cinema.timeline(moment, rows)
        self.assertEqual(script[0]['style'], 'intro')
        self.assertTrue(any(s.get('style') == 'chapter' for s in script))
        self.assertEqual(script[-1]['style'], 'outro')
        images = [s for s in script if s['type'] == 'photo']
        self.assertEqual(images[0]['fit'], 'contain')
        self.assertIn('12:30', images[0]['detail'])
        self.assertNotIn('13:00', images[-1]['detail'])
        self.assertEqual(len({s['motion'] for s in images}), 4)
        self.assertFalse(cinema.needs_upgrade(json.dumps(script)))
        self.assertTrue(cinema.needs_upgrade('[{"type":"photo","photo_id":1}]'))

    def test_typography_wraps_long_titles_and_danish_letters(self):
        item = dict(type='text', text='Ærø, København og Østrig ' * 5, eyebrow='SOMMERENS ØJEBLIKKE', detail='12. juli – 19. juli 2024')
        rendered = cinema.poster(item, (1280, 720))
        self.assertEqual(rendered.size, (1280, 720))
        self.assertIsNotNone(rendered.getbbox())

    def test_real_ffmpeg_photo_and_video_segments(self):
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                self.skipTest('ffmpeg is not installed')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'portrait.jpg'
            Image.new('RGB', (240, 400), '#608b83').save(src)
            item = dict(type='photo', label="Ærø's sommer: 100%", eyebrow='DANMARK', detail='12. juli 2024 · 12:30', fit='contain', duration=2, motion=2)
            output = root / 'photo.mp4'
            self.assertTrue(cinema.render_segment(ffmpeg, item, src, output, size=(640, 360)))
            clip = root / 'clip.mp4'
            self.assertTrue(cinema.render_segment(ffmpeg, dict(item, type='video', duration=9), output, clip, size=(640, 360)))
            # Decode the actual output and verify its dimensions/frame count.
            result = subprocess.run([ffmpeg, '-v', 'error', '-i', str(clip), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
            self.assertEqual(len(result.stdout), 640*360*3*50)
            long_source = root / 'long.mp4'
            subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=25:d=13.4', str(long_source)], check=True, capture_output=True)
            long_clip = root / 'long-clip.mp4'
            self.assertTrue(cinema.render_segment(ffmpeg, dict(item, type='video', duration=2), long_source, long_clip, size=(320,180)))
            result = subprocess.run([ffmpeg, '-v', 'error', '-i', str(long_clip), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
            self.assertEqual(len(result.stdout), 320*180*3*335)
            pair = root / 'pair.mp4'
            second = root / 'second.jpg'
            Image.new('RGB', (240,400), '#d6ab77').save(second)
            self.assertTrue(cinema.render_segment(ffmpeg, dict(type='pair',duration=1), src, pair, second_src=second, size=(640,360)))
            result = subprocess.run([ffmpeg, '-v', 'error', '-ss', '0.5', '-i', str(pair), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
            frame = Image.frombytes('RGB',(640,360),result.stdout)
            self.assertGreater(frame.getpixel((480,160))[0],frame.getpixel((160,160))[0]+40)


class DayReconciliationTests(unittest.TestCase):
    def scan(self, rows):
        return discover(rows, min_photos=3, min_hours=.5)[0]

    def test_billund_cameras_are_one_event(self):
        rows = [photo(i, f'2024-07-10T{10+i}:00:00', 'Billund, Denmark', uploaded_by='a') for i in range(3)]
        rows += [photo(10+i, f'2024-07-10T{10+i}:30:00', 'Billund, Denmark', uploaded_by='b') for i in range(3)]
        result = self.scan(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['photo_ids']), 6)

    def test_unknown_gps_group_joins_single_overlapping_event(self):
        rows = [photo(i, f'2024-07-10T{10+i}:00:00', 'Naestved, Denmark', uploaded_by='a') for i in range(3)]
        rows += [photo(10+i, f'2024-07-10T{10+i}:30:00', uploaded_by='b') for i in range(3)]
        result = self.scan(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['photo_ids']), 6)
        self.assertEqual(result[0]['evidence']['confidence'], 'medium')

    def test_different_cities_same_day_stay_separate_and_unknown_is_ambiguous(self):
        rows = []
        for group, place in enumerate(('Billund, Denmark', 'Berlin, Germany', None)):
            rows += [photo(group*10+i, f'2024-07-10T{10+i}:00:00', place, uploaded_by=str(group)) for i in range(3)]
        self.assertEqual(len(self.scan(rows)), 3)


class PlaceLookupTests(unittest.TestCase):
    def test_expired_deadline_does_not_call_either_endpoint(self):
        with patch('moment_places.requests.post') as post:
            with self.assertRaises(moment_places.requests.Timeout):
                moment_places.lookup(55.735, 9.126, deadline=0)
        post.assert_not_called()

    def test_containment_query_and_nearby_confidence(self):
        payload = {'elements': [dict(type='node', id=1, tags={'name': 'Museum', 'tourism': 'museum'}),
                                dict(type='area', id=3600000010, tags={'name': 'LEGOLAND', 'tourism': 'theme_park'})]}
        with patch('moment_places.requests.post') as post:
            post.return_value.json.return_value = payload
            result = moment_places.lookup(55.735, 9.126)
        self.assertEqual(result[0]['name'], 'LEGOLAND')
        self.assertEqual(result[0]['match'], 'inside')
        self.assertIn('is_in(', post.call_args.kwargs['data']['data'])
        self.assertNotIn('photo', post.call_args.kwargs['data']['data'])

    def test_cache_and_failures_do_not_invent_places(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'test.db'
            def conn():
                connection = sqlite3.connect(db)
                connection.row_factory = sqlite3.Row
                return connection
            with closing(conn()) as connection:
                connection.execute('CREATE TABLE moment_place_cache(point TEXT PRIMARY KEY,result_json TEXT,expires REAL)')
                connection.commit()
            candidate = dict(kind='event', start_date='2024-07-10', photo_ids=list(range(1,7)), title='Billund', evidence={'reasons': []})
            rows = [dict(id=i, gps_lat=55.735, gps_lon=9.126) for i in range(1, 7)]
            found = dict(name='LEGOLAND', osm_type='way', osm_id=10, category='theme_park', source='OpenStreetMap',
                         outer=[[[55.7,9.1],[55.7,9.2],[55.8,9.2],[55.8,9.1],[55.7,9.1]]], inner=[], bounds=[55.7,9.1,55.8,9.2])
            with patch('moment_venues.lookup_region', return_value=[found]) as lookup:
                moment_places.enrich([candidate], rows, conn)
                moment_places.enrich([candidate], rows, conn, time_budget=0)
                self.assertEqual(lookup.call_count, 1)
            self.assertEqual(candidate['primary_place'], 'LEGOLAND')
            self.assertEqual(candidate['evidence']['attraction']['confidence'], 'high')
            with closing(conn()) as connection:
                connection.execute('DELETE FROM moment_place_cache')
                connection.commit()
            fresh = dict(kind='event', start_date='2024-07-10', photo_ids=list(range(1,7)), title='Billund', evidence={'reasons': []})
            with patch('moment_venues.lookup_region') as lookup:
                stats = moment_places.enrich([fresh], rows, conn, time_budget=0)
                lookup.assert_not_called()
                self.assertEqual(stats['pending'], 1)
            with patch('moment_venues.lookup_region', side_effect=moment_places.requests.Timeout):
                stats = moment_places.enrich([fresh], rows, conn)
            self.assertEqual(stats['failed'], 1)
            self.assertEqual(fresh['title'], 'Billund')
            self.assertNotIn('attraction', fresh['evidence'])
            rows = [dict(id=i, gps_lat=56 + (i//2)*.03, gps_lon=9.126) for i in range(1, 7)]
            with patch('moment_venues.lookup_region', side_effect=moment_places.requests.Timeout) as lookup:
                stats = moment_places.enrich([fresh], rows, conn)
                self.assertEqual(lookup.call_count, 2)
                self.assertGreaterEqual(stats['pending'], 1)


if __name__ == '__main__':
    unittest.main()
