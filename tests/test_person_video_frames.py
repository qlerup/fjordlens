import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from person_video_frames import decorate, register


class VideoFrameTests(unittest.TestCase):
    def test_preview_uses_the_strongest_person_detection_and_one_box(self):
        faces = [
            {'id': 1, 'frame_sec': 9.5, 'confidence': 0.72, 'pixel_box': [0, 0, 60, 60]},
            {'id': 2, 'frame_sec': 20, 'confidence': 0.98, 'pixel_box': [0, 0, 80, 80]},
            {'id': 3, 'frame_sec': 9.5, 'confidence': 0.91, 'pixel_box': [0, 0, 120, 120]},
        ]
        item = decorate([{'is_video':True,'faces':faces,'thumb_url':'default'}])[0]
        self.assertEqual(item['thumb_url'],'/api/people/video-frame/2?t=20')
        self.assertEqual([f['id'] for f in item['thumbnail_faces']],[2])
        self.assertEqual(len(item['faces']),3)

    def test_old_detection_uses_crop_without_misleading_boxes_and_photos_unchanged(self):
        old, photo = decorate([{'is_video':True,'faces':[{'id':4,'frame_sec':None}]}, {'is_video':False,'thumb_url':'photo'}])
        self.assertEqual(old['thumb_url'],'/api/face-thumb/4')
        self.assertEqual(old['thumbnail_faces'],[])
        self.assertEqual(photo,{'is_video':False,'thumb_url':'photo'})

    def test_exact_timestamp_cache_and_access_control(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); video = root / 'test.mp4'; video.write_bytes(b'video')
            database = root / 'test.db'
            conn = sqlite3.connect(database)
            conn.executescript("CREATE TABLE photos(id INTEGER,rel_path TEXT); CREATE TABLE faces(id INTEGER,photo_id INTEGER,frame_sec REAL); INSERT INTO photos VALUES(1,'uploads/test.mp4'); INSERT INTO faces VALUES(7,1,12.5);")
            conn.commit(); conn.close()
            def connect():
                conn = sqlite3.connect(database); conn.row_factory = sqlite3.Row; return conn
            calls = []; allowed = [True]
            def extract(path,rel,sec):
                calls.append(sec); return b'jpeg-test'
            fake = SimpleNamespace(get_conn=connect, UPLOAD_DIR=root, PHOTO_DIR=root, THUMB_DIR=root/'thumbs', VIDEO_EXTS={'.mp4'},
                                   _is_rel_path_allowed_for_current_user=lambda rel:allowed[0], _extract_video_frame_bytes=extract)
            app = Flask(__name__); register(app,fake)
            client = app.test_client()
            for _ in range(2):
                response = client.get('/api/people/video-frame/7')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.data,b'jpeg-test'); response.close()
            self.assertEqual(calls,[12.5])
            allowed[0] = False
            self.assertEqual(client.get('/api/people/video-frame/7').status_code,403)
            self.assertEqual(client.get('/api/people/video-frame/99').status_code,404)
            allowed[0] = True; video.write_bytes(b'changed video')
            response = client.get('/api/people/video-frame/7'); response.get_data(); response.close()
            self.assertEqual(calls,[12.5,12.5])
