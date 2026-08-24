import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

import app as fjordlens


class PhotoReprocessTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {
            "DB_PATH": fjordlens.DB_PATH,
            "PHOTO_DIR": fjordlens.PHOTO_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "THUMB_DIR": fjordlens.THUMB_DIR,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
        }
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.PHOTO_DIR = root / "photos"
        fjordlens.UPLOAD_DIR = root / "uploads"
        fjordlens.THUMB_DIR = root / "thumbs"
        fjordlens.DB_BOOTSTRAP_READY = False
        fjordlens.PHOTO_DIR.mkdir()
        fjordlens.UPLOAD_DIR.mkdir()
        fjordlens.THUMB_DIR.mkdir()
        fjordlens.init_db()
        source = fjordlens.PHOTO_DIR / "sample.jpg"
        Image.new("RGB", (20, 20), "blue").save(source)
        second_source = fjordlens.PHOTO_DIR / "second.jpg"
        Image.new("RGB", (20, 20), "red").save(second_source)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?)",
                ("admin", generate_password_hash("pw"), 1, "admin", fjordlens.now_iso()),
            )
            conn.execute(
                "INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?)",
                ("user", generate_password_hash("pw"), 0, "user", fjordlens.now_iso()),
            )
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES(?,?,?)", ("sample.jpg", "sample.jpg", ".jpg"))
            conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES(?,?,?)", ("second.jpg", "second.jpg", ".jpg"))
            conn.commit()
        with fjordlens.PHOTO_REPROCESS_LOCK:
            fjordlens.PHOTO_REPROCESS_BY_ID.clear()
            fjordlens.PHOTO_REPROCESS_QUEUED.clear()
            fjordlens.PHOTO_REPROCESS_WORKER_STARTED = False
        while not fjordlens.PHOTO_REPROCESS_QUEUE.empty():
            fjordlens.PHOTO_REPROCESS_QUEUE.get_nowait()
            fjordlens.PHOTO_REPROCESS_QUEUE.task_done()

    def tearDown(self):
        with fjordlens.PHOTO_REPROCESS_LOCK:
            fjordlens.PHOTO_REPROCESS_BY_ID.clear()
            fjordlens.PHOTO_REPROCESS_QUEUED.clear()
            fjordlens.PHOTO_REPROCESS_WORKER_STARTED = False
        while not fjordlens.PHOTO_REPROCESS_QUEUE.empty():
            fjordlens.PHOTO_REPROCESS_QUEUE.get_nowait()
            fjordlens.PHOTO_REPROCESS_QUEUE.task_done()
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _client(self, user_id):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    def test_only_admin_can_start_reprocess(self):
        response = self._client(2).post("/api/photos/1/reprocess")
        self.assertEqual(response.status_code, 403)

    def test_admin_starts_background_reprocess_for_selected_photo(self):
        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                return None

        with patch.object(fjordlens.threading, "Thread", FakeThread):
            response = self._client(1).post("/api/photos/1/reprocess")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["started"])
        self.assertTrue(data["running"])
        self.assertTrue(data["queued"])
        self.assertEqual(data["queue_position"], 1)
        self.assertEqual(data["current_rel"], "sample.jpg")

    def test_multiple_photos_are_queued_in_fifo_order(self):
        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                return None

        with patch.object(fjordlens.threading, "Thread", FakeThread):
            first = self._client(1).post("/api/photos/1/reprocess").get_json()
            second = self._client(1).post("/api/photos/2/reprocess").get_json()

        self.assertEqual(first["queue_position"], 1)
        self.assertEqual(second["queue_position"], 2)
        self.assertEqual(fjordlens.PHOTO_REPROCESS_QUEUE.qsize(), 2)


if __name__ == "__main__":
    unittest.main()
