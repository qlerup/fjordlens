"""NAS thumbnail checks must not hold the main SQLite writer lock."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

import folder_index as index


@pytest.mark.parametrize('mutation,expected', [
    ("UPDATE photos SET thumb_name='b.jpg'", ['/api/thumbs/b.jpg']),
    ('DELETE FROM photos', []),
])
def test_thumbnail_check_allows_other_writer_and_requeues_stale_snapshot(tmp_path, mutation, expected):
    db = tmp_path/'test.db'
    with sqlite3.connect(db) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript('''
            CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT UNIQUE,thumb_name TEXT,filename TEXT);
            CREATE TABLE folder_owners(folder_path TEXT PRIMARY KEY,user_id INTEGER);
            CREATE TABLE folder_previews(folder_path TEXT PRIMARY KEY,previews_json TEXT,updated_at TEXT);
        ''')
        index.install(conn)
        conn.execute("INSERT INTO photos(rel_path,thumb_name) VALUES('uploads/originals/Trip/a.jpg','a.jpg')")
        conn.commit()
        changed = []
        def check_thumbnail(path):
            if not changed:
                # Simulate an upload committing while a slow NAS stat is in flight.
                with sqlite3.connect(db, timeout=.05) as writer:
                    writer.execute(mutation)
                changed.append(True)
            return True
        with patch.object(Path, 'is_file', check_thumbnail):
            assert index.refresh_covers(conn, thumb_root=tmp_path) == 0
        assert changed
        assert conn.execute('SELECT path FROM folder_index_dirty').fetchone()[0] == 'Trip'
        assert conn.execute('SELECT count(*) FROM folder_previews').fetchone()[0] == 0
        with patch.object(Path, 'is_file', return_value=True):
            assert index.refresh_covers(conn, thumb_root=tmp_path) == 1
        saved = json.loads(conn.execute('SELECT previews_json FROM folder_previews').fetchone()[0])
        assert saved == expected
