import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from person_faces import _REVIEW_JOBS, _REVIEW_JOBS_LOCK, _run_face_review, _set_review_job, register


class FaceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'test.db'
        self.connections = []
        def connect():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self.connections.append(conn)
            return conn
        self.connect = connect
        with connect() as conn:
            conn.executescript('''
                CREATE TABLE people(id INTEGER PRIMARY KEY,name TEXT UNIQUE,hidden INTEGER DEFAULT 0,created_at TEXT,centroid_json TEXT);
                CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT,width REAL,height REAL);
                CREATE TABLE faces(id INTEGER PRIMARY KEY,photo_id INTEGER,person_id INTEGER,embedding_json TEXT,bbox_x REAL,bbox_y REAL,bbox_w REAL,bbox_h REAL);
                INSERT INTO people(id,name,centroid_json) VALUES(1,'Ukendt-1','[1,0]'),(2,'Known','[0,1]');
                INSERT INTO photos VALUES(1,'one.jpg',400,200),(2,'two.jpg',400,200);
                INSERT INTO faces VALUES(1,1,1,'[0,1]',100,50,80,60),(2,1,2,'[0,1]',200,50,80,60),(3,2,1,'[1,0]',100,50,80,60),(4,2,NULL,'[1,1]',200,50,80,60);
            ''')
        self.allowed = True
        self.manage = True
        fake = SimpleNamespace(get_conn=connect, now_iso=lambda:'now',
                               _is_rel_path_allowed_for_current_user=lambda path,conn:self.allowed,
                               _compute_centroid=lambda vectors:vectors[0] if vectors else None)
        app = Flask(__name__)
        register(app, fake, lambda:self.manage)
        self.client = app.test_client()

    def tearDown(self):
        for conn in self.connections:
            conn.close()
        self.folder.cleanup()

    def post(self, **kwargs):
        return self.client.post('/api/people/faces/selection', json={'source_id':1,'face_ids':[1], 'action':'assign','target_id':2, **kwargs})

    def owners(self):
        with self.connect() as conn:
            return [r[0] for r in conn.execute('SELECT person_id FROM faces ORDER BY id')]

    def test_only_selected_face_moves_and_photos_remain(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.owners(), [2,2,1,None])
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0], 2)
            self.assertEqual(json.loads(conn.execute('SELECT centroid_json FROM people WHERE id=1').fetchone()[0]), [1,0])

    def test_hide_uses_recoverable_hidden_person(self):
        response = self.post(action='hide', face_ids=[1,3])
        self.assertEqual(response.status_code,200)
        target = response.json['target_id']
        self.assertEqual(self.owners(), [target,2,target,None])
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT hidden FROM people WHERE id=?',(target,)).fetchone()[0],1)

    def test_create_from_unknown_and_reject_duplicate(self):
        self.assertEqual(self.post(source_id='unknown',face_ids=[4],action='create',name='New').status_code,200)
        self.assertEqual(self.post(action='create',name='known').status_code,409)
        self.assertEqual(self.owners()[0],1)

    def test_stale_selection_rejects_entire_batch(self):
        self.assertEqual(self.post(face_ids=[1,2]).status_code,409)
        self.assertEqual(self.owners(),[1,2,1,None])

    def test_permissions_and_validation(self):
        self.manage = False
        self.assertEqual(self.post().status_code,403)
        self.manage = True; self.allowed = False
        self.assertEqual(self.post().status_code,403)
        self.allowed = True
        self.assertEqual(self.post(face_ids=[]).status_code,409)
        self.assertEqual(self.post(target_id=1).status_code,409)
        self.assertEqual(self.owners(),[1,2,1,None])

    def test_review_suggests_wrong_faces_without_moving_them(self):
        job_id = 'review-test'
        _set_review_job(job_id, status='queued', source_id=1, scanned=0, total=0, results=[])
        fake = SimpleNamespace(
            get_conn=self.connect,
            _is_rel_path_allowed_for_current_user=lambda path, conn: self.allowed,
            FACE_MATCH_THRESHOLD_CENTROID=0.45,
        )
        _run_face_review(job_id, 1, fake)
        with _REVIEW_JOBS_LOCK:
            result = dict(_REVIEW_JOBS[job_id])
            _REVIEW_JOBS.pop(job_id, None)
        self.assertEqual(result['status'], 'done')
        self.assertEqual(result['scanned'], 2)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['target_id'], 2)
        self.assertEqual(result['results'][0]['face_ids'], [1])
        self.assertEqual(self.owners(), [1, 2, 1, None])
