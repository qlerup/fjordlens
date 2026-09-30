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
                CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT,ext TEXT,thumb_name TEXT,width REAL,height REAL);
                CREATE TABLE faces(id INTEGER PRIMARY KEY,photo_id INTEGER,person_id INTEGER,embedding_json TEXT,frame_sec REAL,bbox_x REAL,bbox_y REAL,bbox_w REAL,bbox_h REAL);
                INSERT INTO people(id,name,centroid_json) VALUES(1,'Ukendt-1','[1,0]'),(2,'Known','[0,1]');
                INSERT INTO photos VALUES(1,'one.jpg','.jpg','one.webp',400,200),(2,'two.mp4','.mp4',NULL,400,200);
                INSERT INTO faces VALUES(1,1,1,'[0,1]',NULL,100,50,80,60),(2,1,2,'[0,1]',NULL,200,50,80,60),(3,2,1,'[1,0]',12.5,100,50,80,60),(4,2,NULL,'[1,1]',12.5,200,50,80,60);
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
        # Face 3 has no independent evidence supporting its current person:
        # its own stored centroid must not let it confirm itself.
        self.assertEqual(len(result['results']), 2)
        self.assertEqual((result['suggested'], result['manual_review']), (1, 1))
        self.assertEqual(result['results'][0]['target_id'], 2)
        self.assertEqual(result['results'][0]['face_ids'], [1])
        self.assertEqual(result['results'][0]['faces'][0]['image_url'], '/api/thumbs/one.webp')
        self.assertEqual(self.owners(), [1, 2, 1, None])

    def test_review_lists_low_confidence_outliers_for_manual_decision(self):
        with self.connect() as conn:
            conn.execute("INSERT INTO photos VALUES(3,'three.jpg','.jpg','three.webp',400,200)")
            conn.execute("INSERT INTO faces VALUES(5,3,1,'[0,0,1]',NULL,100,50,80,60)")
            conn.commit()
        job_id = 'review-unmatched'
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
        unmatched = next(group for group in result['results'] if group['target_id'] is None)
        self.assertEqual(unmatched['face_ids'], [3, 5])
        self.assertEqual(self.owners()[-1], 1)

    def review_fixture(self, people, faces, allowed=None):
        with self.connect() as conn:
            conn.execute('DELETE FROM faces')
            conn.execute('DELETE FROM photos')
            conn.execute('DELETE FROM people')
            for pid, name, hidden, centroid in people:
                conn.execute('INSERT INTO people(id,name,hidden,centroid_json) VALUES(?,?,?,?)',
                             (pid, name, hidden, json.dumps(centroid)))
            for face_id, photo_id, pid, vector in faces:
                conn.execute('INSERT OR IGNORE INTO photos VALUES(?,?,?,NULL,400,200)',
                             (photo_id, f'{photo_id}.jpg', '.jpg'))
                conn.execute('INSERT INTO faces VALUES(?,?,?,?,NULL,0,0,100,100)',
                             (face_id, photo_id, pid, json.dumps(vector)))
        before = self.owners()
        fake = SimpleNamespace(get_conn=self.connect,
                               _is_rel_path_allowed_for_current_user=allowed or (lambda path, conn: True),
                               FACE_MATCH_THRESHOLD_CENTROID=0.5, FACE_MATCH_THRESHOLD=0.5)
        _run_face_review('fixture', 1, fake)
        result = _REVIEW_JOBS.pop('fixture')
        self.assertEqual(result['status'], 'done', result.get('error'))
        self.assertEqual(self.owners(), before)
        return result

    def test_review_uses_individual_references_when_mean_hides_a_matching_appearance(self):
        result = self.review_fixture(
            [(1,'Source',0,[0,1,0]), (2,'Target',0,[0,0,1])],
            [(1,1,1,[1,0,0]), (2,2,1,[0,1,0]), (3,3,2,[1,0,0]), (4,4,2,[0.9,0,0.436])]
            + [(i,i,2,[0,0,1]) for i in range(5,15)])
        target = next(g for g in result['results'] if g['target_id'] == 2)
        self.assertEqual(target['face_ids'], [1])
        self.assertEqual(target['faces'][0]['reason'], 'better_match')
        self.assertEqual(target['faces'][0]['face_url'], '/api/face-thumb/1')

    def test_review_cannot_confirm_itself_or_other_frames_of_same_video(self):
        result = self.review_fixture(
            [(1,'Source',0,[1,0]), (2,'Target',0,[1,0])],
            [(1,1,1,[1,0]), (2,1,1,[1,0]), (3,2,1,[0,1]),
             (4,3,2,[1,0]), (5,4,2,[1,0])])
        target = next(g for g in result['results'] if g['target_id'] == 2)
        self.assertEqual(target['face_ids'], [1,2])

    def test_review_does_not_turn_one_bad_target_reference_into_a_match(self):
        result = self.review_fixture(
            [(1,'Source',0,[1,0]), (2,'Target',0,[0,1])],
            [(1,1,1,[1,0]), (2,2,2,[1,0]), (3,3,2,[0,1]), (4,4,2,[0,1])])
        self.assertEqual(result['suggested'], 0)
        self.assertEqual(result['manual_review'], 1)

    def test_review_marks_equal_alternatives_ambiguous_instead_of_picking_first(self):
        result = self.review_fixture(
            [(1,'Source',0,[1,0]), (2,'Alice',0,[1,0]), (3,'Bob',0,[1,0])],
            [(1,1,1,[1,0]), (2,2,2,[1,0]), (3,3,3,[1,0])])
        self.assertEqual(result['suggested'], 0)
        self.assertEqual(result['results'][0]['faces'][0]['reason'], 'ambiguous')

    def test_review_retains_independently_supported_current_person(self):
        result = self.review_fixture(
            [(1,'Source',0,[1,0]), (2,'Target',0,[0.8,0.6])],
            [(1,1,1,[1,0]), (2,2,1,[1,0]), (3,3,1,[1,0]), (4,4,2,[0.8,0.6])])
        self.assertEqual(result['results'], [])
        self.assertEqual(result['kept'], 3)

    def test_review_excludes_hidden_unnamed_and_inaccessible_reference_faces(self):
        result = self.review_fixture(
            [(1,'Source',0,[0,1]), (2,'Hidden',1,[1,0]), (3,'Ukendt-3',0,[1,0]), (4,'Private',0,[1,0])],
            [(1,1,1,[1,0]), (2,2,2,[1,0]), (3,3,3,[1,0]), (4,4,4,[1,0])],
            allowed=lambda path, conn: path != '4.jpg')
        self.assertEqual(result['suggested'], 0)
        self.assertEqual(result['reference_faces'], 1)

    def test_review_reports_invalid_vectors_and_handles_multiple_dimensions(self):
        result = self.review_fixture(
            [(1,'Source',0,[1,0]), (2,'Target',0,[1,0,0])],
            [(1,1,1,[1,0]), (2,2,1,[0,0]), (3,3,1,[float('nan'),1]),
             (4,4,1,[]), (5,5,1,None), (6,6,2,[1,0,0])])
        self.assertEqual(result['suggested'], 0)
        self.assertEqual(result['skipped'], 4)
        self.assertEqual(result['scanned'], 5)
