import unittest
import place_names
import moment_venues
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
import moment_places


class PlaceNamesTests(unittest.TestCase):
    def test_native_names_and_safe_unchanged_text(self):
        for old, new in [('Naestved, Denmark', 'Næstved, Denmark'), ('Koge, Denmark', 'Køge, Denmark'),
                         ('Solrod, Denmark', 'Solrød, Denmark'), ('Praesto, Denmark', 'Præstø, Denmark'),
                         ('Loddekopinge, Sweden', 'Löddeköpinge, Sweden'), ('Copenhagen, Denmark', 'København, Denmark')]:
            self.assertEqual(place_names.place_name(old), new)
        for value in ['Aalborg, Denmark', 'Aarhus, Denmark', 'Berlin, Germany', 'Naestved, Germany', 'Naestved']:
            self.assertEqual(place_names.place_name(value), value)

    def test_photo_location_does_not_rewrite_captions(self):
        photo = {'gps_name': 'Koge, Denmark', 'metadata_json': {'geo': {'city': 'Koge', 'country': 'Denmark'},
                                                              'caption': 'Koge is the filename'}}
        place_names.photo_places(photo)
        self.assertEqual(photo['metadata_json']['geo']['city'], 'Køge')
        self.assertEqual(photo['metadata_json']['caption'], 'Koge is the filename')


class AttractionVisitsTests(unittest.TestCase):
    def test_many_photos_inside_an_arbitrary_foreign_venue_name_multiday_trip(self):
        rows = [dict(id=i, gps_lat=48.851+i*.00001, gps_lon=2.35) for i in range(12)]
        candidate = dict(kind='trip', start_date='2026-05-24', photo_ids=[r['id'] for r in rows],
                         title='Tur til Frankrig', evidence={'reasons': []})
        venue = moment_venues.parse_venue(dict(type='way',id=123,tags={'name':'Et museum i Paris','tourism':'museum'},
            geometry=[dict(lat=a,lon=b) for a,b in [(48.85,2.34),(48.85,2.36),(48.86,2.36),(48.86,2.34),(48.85,2.34)]]))
        with tempfile.TemporaryDirectory() as folder:
            def conn():
                c=sqlite3.connect(Path(folder)/'cache.db')
                c.row_factory=sqlite3.Row
                c.execute('CREATE TABLE IF NOT EXISTS moment_place_cache(point TEXT PRIMARY KEY,result_json TEXT,expires REAL)')
                return c
            with patch('moment_venues.lookup_region',return_value=[venue]) as lookup:
                moment_places.enrich([candidate],rows,conn)
                self.assertEqual(lookup.call_count,1)
        self.assertEqual(candidate['title'], 'En tur til Et museum i Paris')
        self.assertEqual(candidate['evidence']['attraction']['photo_matches'], 12)

    def test_holes_and_nearby_locations_are_not_inside(self):
        park = dict(bounds=(0, 0, 10, 10), outer=[[(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]],
                    inner=[[(4, 4), (4, 6), (6, 6), (6, 4), (4, 4)]])
        self.assertTrue(moment_venues.matches(park, (2, 2)))
        self.assertFalse(moment_venues.matches(park, (5, 5)))
        self.assertFalse(moment_venues.matches(park, (10.1, 5)))

    def test_incomplete_geometry_is_not_invented(self):
        self.assertEqual(moment_venues.join_rings([[[1,1],[2,2],[3,3]]]), [])

    def test_expired_budget_does_not_make_a_request(self):
        with patch('moment_venues.requests.post') as post:
            with self.assertRaises(moment_venues.requests.Timeout):
                moment_venues.lookup_region((2400,120),deadline=0)
        post.assert_not_called()
