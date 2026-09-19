"""Stand-alone catalogue tests; no Flask, media services, GPU or NAS required."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import folder_index as index


class FolderIndexTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
            CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT UNIQUE,thumb_name TEXT,filename TEXT);
            CREATE INDEX idx_thumb ON photos(thumb_name);
            CREATE TABLE folder_owners(folder_path TEXT PRIMARY KEY,user_id INTEGER);
            CREATE TABLE folder_previews(folder_path TEXT PRIMARY KEY,previews_json TEXT,updated_at TEXT);
        ''')
        index.install(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def photo(self, path, thumb='a.jpg'):
        self.conn.execute('INSERT INTO photos(rel_path,thumb_name) VALUES(?,?)', (path, thumb))
        self.conn.commit()

    def paths(self):
        return [r[0] for r in self.conn.execute('SELECT path FROM folder_index ORDER BY path')]

    def folders(self, parent='', visible=lambda _: True):
        return index.list_folders(self.conn, parent, visible)

    def test_legacy_catalogue_migrates_empty_folders_without_disk_reads(self):
        other = sqlite3.connect(':memory:')
        self.addCleanup(other.close)
        other.executescript("""
            CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT UNIQUE,thumb_name TEXT,filename TEXT);
            CREATE TABLE folder_owners(folder_path TEXT PRIMARY KEY,user_id INTEGER);
            CREATE TABLE folder_previews(folder_path TEXT PRIMARY KEY,previews_json TEXT,updated_at TEXT);
            CREATE TABLE folder_index(folder_path TEXT PRIMARY KEY,parent_path TEXT NOT NULL DEFAULT '',name TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE INDEX idx_folder_index_parent ON folder_index(parent_path);
            INSERT INTO folder_index VALUES('Legacy/Empty','Legacy','Empty','2026-09-19');
        """)
        with patch.object(index.os,'walk',side_effect=AssertionError('migration must not scan')):
            index.install(other)
            other.commit()
            index.install(other)
        self.assertEqual([r[0] for r in other.execute('SELECT path FROM folder_index ORDER BY path')],['Legacy','Legacy/Empty'])
        self.assertEqual([r[2] for r in other.execute('PRAGMA index_info(idx_folder_index_parent)')],['parent','name'])
        self.assertFalse(other.execute("SELECT 1 FROM sqlite_master WHERE name='folder_index_legacy_v1'").fetchone())

    def test_photo_triggers_register_ancestors_and_merge_storage_mirrors(self):
        for storage in ('originals/', 'converted/', ''):
            self.photo('uploads/'+storage+'Family/Trip/a.jpg')
        self.assertEqual(self.paths(), ['Family', 'Family/Trip'])
        self.assertEqual([i['path'] for i in self.folders()], ['Family'])
        self.assertEqual([i['path'] for i in self.folders('Family')], ['Family/Trip'])

    def test_insert_replace_and_upsert_work_with_existing_folders(self):
        self.photo('uploads/originals/A/a.jpg')
        self.photo('uploads/originals/A/b.jpg')
        self.conn.execute("INSERT OR REPLACE INTO photos(rel_path,thumb_name) VALUES('uploads/originals/A/b.jpg','new.jpg')")
        self.conn.execute("INSERT INTO photos(rel_path,thumb_name) VALUES('uploads/originals/A/b.jpg','next.jpg') ON CONFLICT(rel_path) DO UPDATE SET thumb_name=excluded.thumb_name")
        self.conn.commit()
        self.assertEqual(self.paths(), ['A'])

    def test_upload_changes_dirty_covers_but_metadata_does_not(self):
        self.photo('uploads/originals/A/a.jpg')
        index.refresh_covers(self.conn)
        self.conn.execute("UPDATE photos SET filename='new filename'")
        self.assertEqual(self.conn.execute('SELECT count(*) FROM folder_index_dirty').fetchone()[0], 0)
        self.conn.execute("UPDATE photos SET thumb_name='changed.jpg'")
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT path FROM folder_index_dirty').fetchone()[0], 'A')
        index.refresh_covers(self.conn)
        self.assertEqual(self.folders()[0]['previews'], ['/api/thumbs/changed.jpg'])

    def test_deleted_photo_cover_is_hidden_before_worker_runs(self):
        self.photo('uploads/originals/A/a.jpg')
        index.refresh_covers(self.conn)
        self.conn.execute('DELETE FROM photos'); self.conn.commit()
        self.assertEqual(self.folders()[0]['previews'], [])
        self.assertEqual(self.paths(), ['A'], 'An empty physical folder still exists')
        index.refresh_covers(self.conn)
        self.assertEqual(self.folders()[0]['previews'], [])

    def test_rename_preserves_empty_descendants_and_does_not_resurrect_old_tree(self):
        index.ensure_path(self.conn, 'Old/Empty/Nested'); self.conn.commit()
        self.photo('uploads/originals/Old/a.jpg')
        self.conn.execute("UPDATE photos SET rel_path='uploads/originals/New/a.jpg'")
        index.rename_tree(self.conn, 'Old', 'New'); self.conn.commit()
        index.refresh_covers(self.conn, 50)
        self.assertEqual(self.paths(), ['New','New/Empty','New/Empty/Nested'])
        self.assertEqual(self.folders()[0]['previews'], ['/api/thumbs/a.jpg'])

    def test_rollback_reverts_topology_and_dirty_queue_together(self):
        self.photo('uploads/originals/A/a.jpg')
        index.refresh_covers(self.conn)
        before = self.conn.execute('SELECT revision FROM folder_index_state').fetchone()[0]
        self.conn.execute("UPDATE photos SET rel_path='uploads/originals/B/a.jpg'")
        index.rename_tree(self.conn, 'A', 'B'); self.conn.rollback()
        self.assertEqual(self.paths(), ['A'])
        self.assertEqual(self.conn.execute('SELECT revision FROM folder_index_state').fetchone()[0], before)
        self.assertEqual(self.folders()[0]['previews'], ['/api/thumbs/a.jpg'])

    def test_literal_prefix_boundaries_unicode_and_percent(self):
        for name in ('A_100%', 'Ax100', 'A_100%extra', 'Æ Ø 漢字'):
            self.photo('uploads/originals/'+name+'/Sub/file.jpg', thumb=name+'.jpg')
        index.remove_tree(self.conn, 'A_100%'); self.conn.commit()
        self.assertNotIn('A_100%/Sub', self.paths())
        self.assertIn('Ax100/Sub', self.paths())
        self.assertIn('A_100%extra/Sub', self.paths())
        self.assertIn('Æ Ø 漢字/Sub', self.paths())
        index.refresh_covers(self.conn, 50)
        self.assertEqual(self.folders('Æ Ø 漢字')[0]['name'], 'Sub')

    def test_hidden_and_internal_folders_are_not_catalogued(self):
        for path in ('uploads/originals/.hidden/a.jpg', 'uploads/@eaDir/a.jpg', 'uploads/converted/#recycle/a.jpg', 'library/Private/a.jpg'):
            self.photo(path)
        self.assertEqual(self.paths(), [])
        self.photo('uploads/originals/Originals/a.jpg')
        self.assertEqual(self.paths(), ['Originals'])

    def test_empty_folder_index_is_not_truncated_at_400(self):
        for i in range(650):
            index.ensure_path(self.conn, f'Folder {i:04}')
        self.conn.commit()
        self.assertEqual(len(self.folders()), 650)
        plan = str(self.conn.execute('EXPLAIN QUERY PLAN SELECT path,name FROM folder_index WHERE parent=?', ('',)).fetchall())
        self.assertIn('idx_folder_index_parent', plan)

    def test_migration_is_persistent_and_does_not_rebuild_catalogue_each_time(self):
        self.photo('uploads/originals/A/Sub/a.jpg')
        self.conn.execute('DELETE FROM folder_index'); self.conn.commit()
        index.install(self.conn); self.conn.commit()
        self.assertEqual(self.paths(), [], 'version=1 must not rebuild deleted catalogue data')
        self.conn.execute('UPDATE folder_index_state SET version=0'); self.conn.commit()
        index.install(self.conn); self.conn.commit()
        self.assertEqual(self.paths(), ['A', 'A/Sub'])

    def test_browse_performs_no_filesystem_discovery_or_thumbnail_stat(self):
        self.photo('uploads/originals/A/a.jpg')
        index.refresh_covers(self.conn)
        with patch('os.walk', side_effect=AssertionError('no scan')), patch.object(Path, 'is_file', side_effect=AssertionError('no stat')), patch.object(Path, 'exists', side_effect=AssertionError('no stat')):
            self.assertEqual(self.folders()[0]['previews'], ['/api/thumbs/a.jpg'])

    def test_saved_selection_and_invalid_legacy_original_url(self):
        for i in range(5):
            self.photo(f'uploads/originals/A/{i}.jpg', f'{i}.jpg')
        selected = ['/api/thumbs/4.jpg', '/api/thumbs/1.jpg']
        self.conn.execute('INSERT INTO folder_previews VALUES(?,?,?)', ('A', json.dumps(selected),'now')); self.conn.commit()
        index.refresh_covers(self.conn)
        self.assertEqual(self.folders()[0]['previews'], selected)
        self.conn.execute('UPDATE folder_previews SET previews_json=?', (json.dumps(['/api/viewable/uploads/originals/A/0.jpg']),)); self.conn.commit()
        self.assertEqual(self.folders()[0]['previews'], [])

    def test_malformed_preview_json_does_not_crash_a_folder_read(self):
        index.ensure_path(self.conn, 'A')
        self.conn.execute("INSERT INTO folder_previews VALUES('A','not json','now')"); self.conn.commit()
        self.assertEqual(self.folders()[0]['previews'], [])

    def test_acl_scoped_names_and_thumbnails_and_nested_owner_override(self):
        self.photo('uploads/originals/A/Open/a.jpg', 'allowed.jpg')
        self.photo('uploads/originals/A/Secret/s.jpg', 'private.jpg')
        index.refresh_covers(self.conn, 50)
        self.conn.executemany('INSERT INTO folder_owners VALUES(?,?)', [('uploads/A', 2),('uploads/A/Secret',3)])
        self.conn.commit()
        visible = index.visibility(self.conn, 2, [])
        self.assertEqual([i['name'] for i in self.folders('A',visible)], ['Open'])
        self.assertNotIn('/api/thumbs/private.jpg', self.folders('',visible)[0]['previews'])
        self.assertEqual(self.folders('',index.visibility(self.conn,4,[])), [])
        self.assertEqual(len(self.folders('A',index.visibility(self.conn,4,[],True))), 2)

    def test_nested_grant_keeps_ancestors_navigable_without_private_covers(self):
        self.photo('uploads/originals/Family/Private/p.jpg','private.jpg')
        self.photo('uploads/originals/Family/Shared/Trip/s.jpg','shared.jpg')
        index.refresh_covers(self.conn,50)
        visible = index.visibility(self.conn,2,['uploads/Family/Shared'])
        self.assertFalse(visible('Family')); self.assertTrue(visible.navigable('Family'))
        self.assertEqual([i['name'] for i in self.folders('',visible)], ['Family'])
        self.assertEqual([i['name'] for i in self.folders('Family',visible)], ['Shared'])
        self.assertNotIn('/api/thumbs/private.jpg', self.folders('',visible)[0]['previews'])

    def test_thumbnail_must_belong_to_visible_folder_not_just_have_a_known_name(self):
        self.photo('uploads/originals/A/a.jpg','a.jpg')
        self.photo('uploads/originals/B/b.jpg','b.jpg')
        self.conn.execute('INSERT INTO folder_previews VALUES(?,?,?)', ('A',json.dumps(['/api/thumbs/b.jpg']),'now')); self.conn.commit()
        self.assertEqual(self.folders()[0]['previews'], [])

    def test_discovery_adds_legacy_empty_folders_and_preserves_index_when_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path in ('A/Empty','originals/B/Empty','converted/B/Empty','@eaDir/Hidden','.hidden/Child'):
                (root/path).mkdir(parents=True)
            self.assertTrue(index.discover(self.conn,root))
            self.assertEqual(self.paths(),['A','A/Empty','B','B/Empty'])
            with self.assertRaises(OSError):
                index.discover(self.conn,root/'offline')
            self.assertEqual(self.paths(),['A','A/Empty','B','B/Empty'])

    def test_concurrent_delete_wins_over_a_discovery_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'A').mkdir()
            index.ensure_path(self.conn,'A'); self.conn.commit()
            walk = index.os.walk
            def changed(*args,**kwargs):
                yield from walk(*args,**kwargs)
                index.remove_tree(self.conn,'A'); self.conn.commit()
            with patch.object(index.os,'walk',side_effect=changed):
                self.assertFalse(index.discover(self.conn,root))
            self.assertEqual(self.paths(),[])

    def test_rejected_paths_and_move_into_own_descendant(self):
        for path in ('..','A/../B','A//B','originals/Secret','converted'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                index.ensure_path(self.conn,path)
        with self.assertRaises(ValueError): index.rename_tree(self.conn,'A','A/B')


if __name__ == '__main__':
    unittest.main()
