import json
import unittest
from unittest.mock import patch
import app
import moment_folders
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
            self.assertEqual(row['title'],'Bryllup')
            revision = row['revision']
            moment_folders.upgrade_suggestions(conn)
            self.assertEqual(conn.execute('SELECT revision FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],revision)
            conn.commit()
        with patch('moment_places.enrich',return_value={}):
            app._detect_moment_candidates()
        with app.closing(app.get_conn()) as conn:
            self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],'Bryllup')

    def test_saved_and_manually_edited_moments_are_not_renamed(self):
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE photos SET rel_path='uploads/originals/Bryllup (2024)/'||id||'.jpg'")
            for status,edited in (('saved',0),('suggested',1)):
                conn.execute('UPDATE moments SET status=?,user_edited=? WHERE id=?',(status,edited,moment['id']))
                moment_folders.upgrade_suggestions(conn)
                self.assertEqual(conn.execute('SELECT title FROM moments WHERE id=?',(moment['id'],)).fetchone()[0],moment['title'])
