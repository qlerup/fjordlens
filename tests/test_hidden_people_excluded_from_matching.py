import json
import tempfile
import unittest
from pathlib import Path

import app as fjordlens


class HiddenPeopleExcludedFromMatchingTests(unittest.TestCase):
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

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _add_person(self, conn, name, vec, hidden=0, with_face=True):
        conn.execute(
            "INSERT INTO people(name, created_at, hidden, centroid_json) VALUES (?,?,?,?)",
            (name, fjordlens.now_iso(), hidden, json.dumps(vec)),
        )
        pid = conn.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()["id"]
        if with_face:
            conn.execute(
                """INSERT INTO photos(rel_path, filename, ext, file_size, width, height, created_fs, modified_fs, captured_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (f"uploads/originals/{name}.jpg", f"{name}.jpg", "jpg", 10, 100, 100,
                 fjordlens.now_iso(), fjordlens.now_iso(), fjordlens.now_iso()),
            )
            photo_id = conn.execute("SELECT id FROM photos WHERE rel_path=?", (f"uploads/originals/{name}.jpg",)).fetchone()["id"]
            conn.execute(
                "INSERT INTO faces(photo_id, person_id, bbox_x, bbox_y, bbox_w, bbox_h, embedding_json, confidence, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (photo_id, pid, 1, 1, 5, 5, json.dumps(vec), 0.9, fjordlens.now_iso()),
            )
        return pid

    def test_find_or_create_person_id_never_returns_a_hidden_person(self):
        target_vec = [1.0, 0.0, 0.0, 0.0]
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            hidden_pid = self._add_person(conn, "HiddenGuy", target_vec, hidden=1)
            conn.commit()

            # Only a hidden person exists with a matching centroid/face -> must not match it,
            # so this should fall through to creating a brand new "Ukendt-*" person instead.
            new_pid, created, score = fjordlens._find_or_create_person_id(conn, target_vec)

        self.assertTrue(created)
        self.assertNotEqual(new_pid, hidden_pid)

    def test_find_or_create_person_id_matches_visible_person_over_hidden(self):
        target_vec = [1.0, 0.0, 0.0, 0.0]
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            hidden_pid = self._add_person(conn, "HiddenGuy", target_vec, hidden=1)
            visible_pid = self._add_person(conn, "VisibleGuy", target_vec, hidden=0)
            conn.commit()

            found_pid, created, score = fjordlens._find_or_create_person_id(conn, target_vec)

        self.assertFalse(created)
        self.assertEqual(found_pid, visible_pid)
        self.assertNotEqual(found_pid, hidden_pid)

    def test_load_person_centroids_excludes_hidden(self):
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            hidden_pid = self._add_person(conn, "HiddenGuy", [1.0, 0.0, 0.0, 0.0], hidden=1, with_face=False)
            visible_pid = self._add_person(conn, "VisibleGuy", [0.0, 1.0, 0.0, 0.0], hidden=0, with_face=False)
            conn.commit()
            centroids = fjordlens._load_person_centroids(conn)

        ids = {pid for pid, _ in centroids}
        self.assertIn(visible_pid, ids)
        self.assertNotIn(hidden_pid, ids)


if __name__ == "__main__":
    unittest.main()
