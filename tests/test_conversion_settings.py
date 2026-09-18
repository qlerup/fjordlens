import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as fjordlens


class ConversionSettingsTests(unittest.TestCase):
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
            conn.commit()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _authenticated_client(self):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True
        return client

    def test_conversion_settings_survive_reload_for_all_types(self):
        for conversion_type in ("heic", "raw", "mov"):
            with self.subTest(conversion_type=conversion_type, value=False):
                response = self._authenticated_client().post(
                    f"/api/settings/{conversion_type}",
                    json={"convert_on_upload": False, "keep_originals": False},
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.get_json()["convert_on_upload"])
                self.assertFalse(response.get_json()["keep_originals"])

                reloaded = self._authenticated_client().get(f"/api/settings/{conversion_type}")
                self.assertEqual(reloaded.status_code, 200)
                self.assertFalse(reloaded.get_json()["convert_on_upload"])
                self.assertFalse(reloaded.get_json()["keep_originals"])
                self.assertIn("no-store", reloaded.headers.get("Cache-Control", ""))

            with self.subTest(conversion_type=conversion_type, value=True):
                response = self._authenticated_client().post(
                    f"/api/settings/{conversion_type}",
                    json={"convert_on_upload": True, "keep_originals": True},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_json()["convert_on_upload"])
                self.assertTrue(response.get_json()["keep_originals"])

                reloaded = self._authenticated_client().get(f"/api/settings/{conversion_type}")
                self.assertEqual(reloaded.status_code, 200)
                self.assertTrue(reloaded.get_json()["convert_on_upload"])
                self.assertTrue(reloaded.get_json()["keep_originals"])

    def test_mov_device_setting_switches_live_between_cpu_and_gpu(self):
        client = self._authenticated_client()

        cpu = client.post("/api/settings/mov", json={"device": "cpu"})
        self.assertEqual(cpu.status_code, 200)
        self.assertEqual(cpu.get_json()["device"], "cpu")

        reloaded_cpu = client.get("/api/settings/mov")
        self.assertEqual(reloaded_cpu.status_code, 200)
        self.assertEqual(reloaded_cpu.get_json()["device"], "cpu")

        gpu = client.post("/api/settings/mov", json={"device": "gpu"})
        self.assertEqual(gpu.status_code, 200)
        self.assertEqual(gpu.get_json()["device"], "gpu")

        reloaded_gpu = client.get("/api/settings/mov")
        self.assertEqual(reloaded_gpu.status_code, 200)
        self.assertEqual(reloaded_gpu.get_json()["device"], "gpu")

    def test_mov_concurrency_setting_is_live_and_bounded_to_one_through_four(self):
        client = self._authenticated_client()
        for value in (1, 2, 3, 4):
            with self.subTest(value=value):
                response = client.post("/api/settings/mov", json={"concurrency": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["concurrency"], value)
                reloaded = client.get("/api/settings/mov")
                self.assertEqual(reloaded.status_code, 200)
                self.assertEqual(reloaded.get_json()["concurrency"], value)

        for invalid in (0, 5, "banana"):
            with self.subTest(invalid=invalid):
                response = client.post("/api/settings/mov", json={"concurrency": invalid})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()["ok"])

    def test_mov_device_rejects_unknown_value(self):
        response = self._authenticated_client().post(
            "/api/settings/mov",
            json={"device": "banana"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_conversion_write_failure_is_reported(self):
        client = self._authenticated_client()
        with patch.object(
            fjordlens,
            "_set_setting",
            side_effect=sqlite3.OperationalError("attempt to write a readonly database"),
        ):
            response = client.post(
                "/api/settings/heic",
                json={"convert_on_upload": True},
            )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["ok"])
        self.assertIn("databasen", response.get_json()["error"])
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))


if __name__ == "__main__":
    unittest.main()
