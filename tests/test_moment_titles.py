import json
import unittest
import app
import moment_titles
import moment_cinema
import moments_service
from tests import test_moments_v2 as legacy


class TitleFormatTests(unittest.TestCase):
    def test_existing_formats_become_consistent_without_duplicate_dates(self):
        cases = [
            ('Basse 2021', '2021-01-06', '2021-01-06', 'Basse · 06.01.2021'),
            ('Basse 2020', '2020-05-29', '2020-05-30', 'Basse · 2020'),
            ('Cecilie Konfirmation - 13.06.2020', '2020-06-13', '2020-06-13', 'Cecilie Konfirmation · 13.06.2020'),
            ('Rejse til Tyrkiet · 26.05.2018', '2018-05-26', '2018-05-30', 'Rejse til Tyrkiet · 2018'),
            ('Året der gik 2018', '2018-01-01', '2018-12-31', 'Året der gik · 2018'),
            ('Juleaften 2020', '2020-12-24', '2020-12-24', 'Juleaften · 24.12.2020'),
            ('En tur til Bakken', '2026-05-24', '2026-05-24', 'En tur til Bakken · 24.05.2026'),
            ('Route 66', '2018-06-26', '2018-06-26', 'Route 66 · 26.06.2018'),
        ]
        for title, start, end, expected in cases:
            with self.subTest(title=title):
                actual = moment_titles.format_title(title, start, end)
                self.assertEqual(actual, expected)
                self.assertEqual(moment_titles.format_title(actual, start, end), expected)
                moment = dict(title=actual, start_date=start, end_date=end, primary_place=None)
                intro = moment_cinema.timeline(moment, [dict(id=1, captured_at=start)])[0]
                self.assertEqual(intro['text'], expected.split(' · ')[0])


class TitleMigrationTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_full_migration_is_stable_for_folder_and_attraction_titles(self):
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE photos SET rel_path='uploads/originals/Konfirmation - 10.07.2024/'||id||'.jpg'")
            moments_service.migrate(conn)
            row = conn.execute('SELECT * FROM moments WHERE id=?', (moment['id'],)).fetchone()
            self.assertEqual(row['title'], 'Konfirmation · 10.07.2024')
            moments_service.migrate(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?', (moment['id'],)).fetchone()[0], row['revision'])
            conn.execute('UPDATE moments SET evidence_json=? WHERE id=?',
                         (json.dumps(dict(attraction=dict(name='Bakken'))), moment['id']))
            moments_service.migrate(conn)
            row = conn.execute('SELECT * FROM moments WHERE id=?', (moment['id'],)).fetchone()
            self.assertEqual(row['title'], 'En tur til Bakken · 10.07.2024')
            moments_service.migrate(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?', (moment['id'],)).fetchone()[0], row['revision'])

    def test_saved_automatic_titles_updated_manual_titles_preserved(self):
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE moments SET title='Sommer 2024',status='saved' WHERE id=?", (moment['id'],))
            moment_titles.upgrade(conn)
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?', (moment['id'],)).fetchone()[0], 'Sommer · 10.07.2024')
            conn.execute("UPDATE moments SET title='Mit eget navn',user_edited=1 WHERE id=?", (moment['id'],))
            moment_titles.upgrade(conn)
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?', (moment['id'],)).fetchone()[0], 'Mit eget navn')
