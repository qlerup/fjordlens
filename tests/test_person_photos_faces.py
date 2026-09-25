import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

import app as fjordlens


class PersonPhotosFacesTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {
            "DATA_DIR": fjordlens.DATA_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
        }
        fjordlens.DATA_DIR = root
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.INSTALL_STATE_PATH = root / "fjordlens.install.json"
        fjordlens.DB_BOOTSTRAP_READY = False
        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, is_admin, role, created_at) VALUES(?,?,?,?,?)",
                ("admin", generate_password_hash("test-password"), 1, "admin", fjordlens.now_iso()),
            )
            conn.execute(
                "INSERT INTO people(name, created_at, hidden) VALUES (?,?,0)",
                ("Testperson", fjordlens.now_iso()),
            )
            self.person_id = conn.execute("SELECT id FROM people WHERE name='Testperson'").fetchone()["id"]
            conn.execute(
                """INSERT INTO photos(rel_path, filename, ext, file_size, width, height, created_fs, modified_fs, captured_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                ("uploads/originals/p.jpg", "p.jpg", "jpg", 100, 400, 200,
                 fjordlens.now_iso(), fjordlens.now_iso(), fjordlens.now_iso()),
            )
            photo_id = conn.execute("SELECT id FROM photos WHERE rel_path='uploads/originals/p.jpg'").fetchone()["id"]
            conn.execute(
                "INSERT INTO faces(photo_id, person_id, bbox_x, bbox_y, bbox_w, bbox_h, confidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (photo_id, self.person_id, 100, 50, 80, 60, 0.9, fjordlens.now_iso()),
            )
            conn.commit()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def authenticated_client(self):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True
        return client

    def add_photo_with_face(self, name):
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                """INSERT INTO photos(rel_path, filename, ext, file_size, width, height, created_fs, modified_fs, captured_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (f"uploads/originals/{name}.jpg", f"{name}.jpg", "jpg", 100, 400, 200,
                 fjordlens.now_iso(), fjordlens.now_iso(), fjordlens.now_iso()),
            )
            photo_id = conn.execute("SELECT id FROM photos WHERE rel_path=?", (f"uploads/originals/{name}.jpg",)).fetchone()["id"]
            conn.execute(
                "INSERT INTO faces(photo_id, person_id, bbox_x, bbox_y, bbox_w, bbox_h, confidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (photo_id, self.person_id, 100, 50, 80, 60, 0.9, fjordlens.now_iso()),
            )
            conn.commit()

    def test_photos_endpoint_returns_normalized_face_box(self):
        client = self.authenticated_client()
        res = client.get(f"/api/people/{self.person_id}/photos")
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["items"]), 1)
        faces = data["items"][0]["faces"]
        self.assertEqual(len(faces), 1)
        self.assertAlmostEqual(faces[0]["x"], 100 / 400)
        self.assertAlmostEqual(faces[0]["y"], 50 / 200)
        self.assertAlmostEqual(faces[0]["w"], 80 / 400)
        self.assertAlmostEqual(faces[0]["h"], 60 / 200)

    def test_photos_endpoint_pages_unique_photos(self):
        self.add_photo_with_face("p2")
        self.add_photo_with_face("p3")
        client = self.authenticated_client()

        first = client.get(f"/api/people/{self.person_id}/photos?offset=0&limit=2").get_json()
        second = client.get(f"/api/people/{self.person_id}/photos?offset=2&limit=2").get_json()

        self.assertTrue(first["has_more"])
        self.assertEqual(first["next_offset"], 2)
        self.assertEqual(len(first["items"]), 2)
        self.assertFalse(second["has_more"])
        self.assertEqual(len(second["items"]), 1)
        self.assertTrue({item["id"] for item in first["items"]}.isdisjoint({item["id"] for item in second["items"]}))


if __name__ == "__main__":
    unittest.main()
