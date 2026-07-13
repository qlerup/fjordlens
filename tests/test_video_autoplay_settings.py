import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as fjordlens


class VideoAutoplaySettingsTests(unittest.TestCase):
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
                "INSERT INTO users(username, password_hash, is_admin, role, created_at) VALUES(?,?,?,?,?)",
                ("viewer", generate_password_hash("test-password"), 0, "user", fjordlens.now_iso()),
            )
            conn.commit()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _authenticated_client(self, user_id=1):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    def _add_share(self, token="video-share"):
        now = fjordlens.now_iso()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            cur = conn.execute(
                """
                INSERT INTO share_links(
                    token_hash, token_plain, share_name, folder_path,
                    can_download, can_upload, can_delete,
                    require_visitor_name, link_use_duckdns, revoked,
                    created_by_user_id, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    fjordlens._share_token_digest(token),
                    token,
                    "Video share",
                    "album",
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO share_link_folders(share_id, folder_path, created_at) VALUES(?,?,?)",
                (int(cur.lastrowid), "album", now),
            )
            conn.commit()
        return token

    def test_default_is_off_and_saved_values_survive_hard_refresh(self):
        client = self._authenticated_client()
        default = client.get("/api/settings/video")
        self.assertEqual(default.status_code, 200)
        self.assertFalse(default.get_json()["autoplay"])
        self.assertIn("no-store", default.headers.get("Cache-Control", ""))

        enabled = client.post("/api/settings/video", json={"autoplay": True})
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.get_json()["autoplay"])
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='video_autoplay'").fetchone()
        self.assertEqual(row["value"], "1")

        refreshed = self._authenticated_client().get("/api/settings/video")
        self.assertEqual(refreshed.status_code, 200)
        self.assertTrue(refreshed.get_json()["autoplay"])
        index_html = self._authenticated_client().get("/").data
        self.assertIn(b'"video_autoplay": true', index_html)
        basic_user_index = self._authenticated_client(user_id=2).get("/").data
        self.assertIn(b'"video_autoplay": true', basic_user_index)

        disabled = self._authenticated_client().post("/api/settings/video", json={"autoplay": False})
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["autoplay"])
        self.assertFalse(self._authenticated_client().get("/api/settings/video").get_json()["autoplay"])

    def test_invalid_values_are_rejected_without_changing_the_setting(self):
        client = self._authenticated_client()
        self.assertEqual(client.post("/api/settings/video", json={"autoplay": True}).status_code, 200)
        for payload in ({}, {"autoplay": "false"}, {"autoplay": 1}, {"autoplay": None}):
            with self.subTest(payload=payload):
                response = client.post("/api/settings/video", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()["ok"])
        self.assertTrue(client.get("/api/settings/video").get_json()["autoplay"])

    def test_settings_endpoint_requires_an_elevated_authenticated_user(self):
        anonymous = fjordlens.app.test_client()
        self.assertEqual(anonymous.get("/api/settings/video").status_code, 401)
        basic_user = self._authenticated_client(user_id=2)
        self.assertEqual(basic_user.get("/api/settings/video").status_code, 403)
        self.assertEqual(basic_user.post("/api/settings/video", json={"autoplay": True}).status_code, 403)

    def test_write_failure_is_reported(self):
        with patch.object(
            fjordlens,
            "_set_setting",
            side_effect=sqlite3.OperationalError("attempt to write a readonly database"),
        ):
            response = self._authenticated_client().post(
                "/api/settings/video",
                json={"autoplay": True},
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["ok"])
        self.assertIn("databasen", response.get_json()["error"])
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_authorized_share_info_includes_the_global_setting(self):
        token = self._add_share()
        public_client = fjordlens.app.test_client()
        initial = public_client.get(f"/api/share/{token}/info")
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.get_json()["video_autoplay"])
        self.assertIn("no-store", initial.headers.get("Cache-Control", ""))

        self.assertEqual(
            self._authenticated_client().post("/api/settings/video", json={"autoplay": True}).status_code,
            200,
        )
        updated = public_client.get(f"/api/share/{token}/info")
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["video_autoplay"])


if __name__ == "__main__":
    unittest.main()
