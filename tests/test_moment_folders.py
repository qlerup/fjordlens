import json
import unittest
from unittest.mock import patch
import app
import moment_folders
import moment_cinema
from tests import test_moments_v2 as legacy


class FolderTitlesTests(unittest.TestCase):
    def candidate(self, **values):
        return dict(dict(title='En dag i Næstved, Danmark · 26.06.2026',primary_place='Næstved, Danmark',
                         photo_ids=[1,2,3,4],evidence={}),**values)

    def test_dominant_folder_combines_storage_variants_and_strips_notes(self):
        candidate = self.candidate()
        rows = [dict(id=1,rel_path='uploads/originals/Bryllup (2026) (privat)/a.jpg'),
                dict(id=2,rel_path='uploads/converted/Bryllup (2026) (privat)/b.jpg'),
                dict(id=3,rel_path='uploads/originals/Bryllup (2026) (privat)/c.jpg'),
                dict(id=4,rel_path='uploads/originals/Fra Danni/d.jpg')]
        self.assertEqual(moment_folders.apply([candidate],rows),1)
        self.assertEqual(candidate['title'],'Bryllup')
        self.assertEqual(candidate['evidence']['folder_title']['photo_count'],3)
        self.assertEqual(moment_folders.clean_name('Ærø (weekend (2026)) med Søren (2)'),'Ærø med Søren')

    def test_stronger_titles_and_unhelpful_folder_names_are_preserved(self):
        for evidence in ({'attraction':{'name':'Bakken'}},{'occasion':{'name':'Jul'}},{'title_source':'journey'},{'title_source':'activity'}):
            candidate = self.candidate(evidence=evidence)
            self.assertEqual(moment_folders.apply([candidate],[dict(id=i,rel_path='uploads/originals/Bryllup/a.jpg') for i in range(1,5)]),0)
        for folder in ('DCIM','(2026)','2026-06-26','originals','100APPLE'):
            candidate = self.candidate()
            self.assertEqual(moment_folders.apply([candidate],[dict(id=i,rel_path=f'{folder}/a.jpg') for i in range(1,5)]),0)
        self.assertFalse(moment_folders.generic_title(self.candidate(title='Rejse til Tyrkiet · 26.05.2018')))
        self.assertFalse(moment_folders.generic_title(self.candidate(title='Tur til Danmark · 26.05.2026')))

    def test_at_least_three_quarters_must_come_from_the_same_folder(self):
        for percentage in (40,50,60,74,75,90,100):
            candidate = self.candidate(photo_ids=list(range(100)))
            original_title = candidate['title']
            rows = [dict(id=i,rel_path=f"uploads/originals/{'Bryllup (2026)' if i < percentage else 'Andre billeder'}/{i}.jpg") for i in range(100)]
            moment_folders.apply([candidate],rows)
            self.assertEqual(candidate['title'], 'Bryllup' if percentage >= 75 else original_title)

    def test_unknown_folders_count_towards_the_total(self):
        candidate = self.candidate()
        self.assertEqual(moment_folders.apply([candidate],[dict(id=i,rel_path=f'Bryllup/{i}.jpg') for i in (1,2)]),0)

    def test_year_comes_from_most_common_day_not_most_common_year(self):
        dates = ['2025-12-30', '2025-12-30', '2025-12-31', '2025-12-31',
                 '2026-01-01', '2026-01-01', '2026-01-01']
        rows = [dict(id=i, rel_path=f'Bryllup (1999)/{i}.jpg', captured_at=f'{day}T12:00:00+02:00')
                for i, day in enumerate(dates)]
        candidate = self.candidate(photo_ids=list(range(7)))
        moment_folders.apply([candidate], rows)
        self.assertEqual(candidate['title'], 'Bryllup · 2026')
        self.assertEqual(candidate['evidence']['folder_title']['dominant_date'], '2026-01-01')
        moment = dict(candidate, start_date='2025-12-30', end_date='2026-01-01')
        intro = moment_cinema.timeline(moment, rows)[0]
        self.assertEqual(intro['text'], 'Bryllup')
        self.assertIn('2026', intro['detail'])
        moment['evidence_json'] = json.dumps(moment.pop('evidence'))
        self.assertEqual(moment_cinema.timeline(moment, rows)[0]['text'], 'Bryllup')
        moment['user_edited'] = 1
        self.assertEqual(moment_cinema.timeline(moment, rows)[0]['text'], 'Bryllup · 2026')

    def test_date_fallback_ties_and_existing_year(self):
        for folder in ('Bryllup', 'Bryllup 2026'):
            rows = [dict(id=1,rel_path=f'{folder}/a.jpg',captured_at='invalid',modified_fs='2026-12-31T23:59:00'),
                    dict(id=2,rel_path=f'{folder}/b.jpg',captured_at='2027-01-01T00:01:00')]
            candidate = self.candidate(photo_ids=[1,2])
            moment_folders.apply([candidate],rows)
            self.assertEqual(candidate['title'],'Bryllup · 2026')


class FolderTitlePersistenceTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_existing_generic_suggestion_updates_once_and_survives_rescan(self):
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            ids = json.loads(moment['photo_ids_json'])
            for pid in ids:
                conn.execute('UPDATE photos SET rel_path=? WHERE id=?',(f'uploads/originals/Bryllup (2024)/{pid}.jpg',pid))
            moment_folders.upgrade_suggestions(conn)
            row = conn.execute('SELECT * FROM moments WHERE id=?',(moment['id'],)).fetchone()
            self.assertEqual(row['title'],'Bryllup · 10.07.2024')
            revision = row['revision']
            moment_folders.upgrade_suggestions(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],revision)
            conn.commit()
        with patch('moment_places.enrich',return_value={}):
            app._detect_moment_candidates()
        with app.closing(app.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],'Bryllup · 10.07.2024')

    def test_legacy_folder_title_gets_year_and_regenerates_script_once(self):
        moment = self.make_moment()
        info = json.loads(moment['evidence_json'])
        info.update(title_source='folder',folder_title=dict(name='Bryllup',photo_count=4,total_photos=4))
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE photos SET rel_path='uploads/originals/Bryllup (2024)/'||id||'.jpg'")
            conn.execute("UPDATE moments SET title='Bryllup',evidence_json=?,script_json='[]' WHERE id=?",(json.dumps(info),moment['id']))
            moment_folders.upgrade_suggestions(conn)
            row = conn.execute('SELECT * FROM moments WHERE id=?',(moment['id'],)).fetchone()
            self.assertEqual(row['title'],'Bryllup · 10.07.2024')
            self.assertIsNone(row['script_json'])
            moment_folders.upgrade_suggestions(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],row['revision'])

    def test_saved_and_manually_edited_moments_are_not_renamed(self):
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE photos SET rel_path='uploads/originals/Bryllup (2024)/'||id||'.jpg'")
            for status,edited in (('saved',0),('suggested',1)):
                conn.execute('UPDATE moments SET status=?,user_edited=? WHERE id=?',(status,edited,moment['id']))
                moment_folders.upgrade_suggestions(conn)
                self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],moment['title'])

    def test_legacy_weak_folder_title_is_restored_once(self):
        moment = self.make_moment()
        ids = json.loads(moment['photo_ids_json'])
        info = json.loads(moment['evidence_json'])
        info.update(title_source='folder',folder_title=dict(name='Bryllup',photo_count=2,total_photos=4))
        info['reasons'].append('Titlen kommer fra mappen “Bryllup”.')
        with app.closing(app.get_conn()) as conn:
            for index,pid in enumerate(ids):
                folder = 'Bryllup (2024)' if index < 2 else 'Andre billeder'
                conn.execute('UPDATE photos SET rel_path=? WHERE id=?',(f'uploads/originals/{folder}/{pid}.jpg',pid))
            conn.execute("UPDATE moments SET title='Bryllup',evidence_json=? WHERE id=?",(json.dumps(info),moment['id']))
            moment_folders.upgrade_suggestions(conn)
            row = conn.execute('SELECT * FROM moments WHERE id=?',(moment['id'],)).fetchone()
            self.assertEqual(row['title'],moment['title'])
            self.assertNotIn('folder_title',json.loads(row['evidence_json']))
            self.assertIsNone(row['script_json'])
            moment_folders.upgrade_suggestions(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],row['revision'])
