import unittest
import place_names
import attraction_catalog
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
    def test_many_photos_inside_bakken_name_multiday_trip_without_network(self):
        rows = [dict(id=i, gps_lat=55.776, gps_lon=12.576) for i in range(12)]
        rows += [dict(id=99, gps_lat=55.6, gps_lon=12.3)]
        candidate = dict(kind='trip', start_date='2026-05-24', photo_ids=[r['id'] for r in rows],
                         title='Tur til Danmark', evidence={'reasons': []})
        def no_database():
            raise AssertionError('Mapped park should not need a network cache')
        moment_places.enrich([candidate], rows, no_database)
        self.assertEqual(candidate['title'], 'En tur til Bakken')
        self.assertEqual(candidate['evidence']['attraction']['photo_matches'], 12)

    def test_single_visit_photo_does_not_rename_a_whole_holiday(self):
        rows = [dict(gps_lat=55.776, gps_lon=12.576)]
        self.assertIsNone(attraction_catalog.visit(rows, 50))
        self.assertIsNone(attraction_catalog.visit(rows * 10, 100))

    def test_holes_and_nearby_locations_are_not_inside(self):
        park = dict(bounds=(0, 0, 10, 10), outer=[[(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]],
                    inner=[[(4, 4), (4, 6), (6, 6), (6, 4), (4, 4)]])
        self.assertTrue(attraction_catalog.contains(park, 2, 2))
        self.assertFalse(attraction_catalog.contains(park, 5, 5))
        self.assertFalse(attraction_catalog.contains(park, 10.1, 5))
