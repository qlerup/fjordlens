import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

import app as fjordlens


class UiDesignTests(unittest.TestCase):
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

    def authenticated_client(self):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True
        return client

    def test_design_can_be_enabled_and_disabled_per_user(self):
        client = self.authenticated_client()
        initial = client.get("/api/me").get_json()["item"]
        self.assertEqual(initial["ui_design"], "classic")

        enabled = client.post("/api/me/ui-design", json={"ui_design": "fjord"})
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.get_json()["ui_design"], "fjord")
        self.assertEqual(client.get("/api/me").get_json()["item"]["ui_design"], "fjord")

        page = client.get("/")
        stylesheet_tag = next(
            line for line in page.data.splitlines() if b'id="fjordDesignStylesheet"' in line
        )
        self.assertNotIn(b" disabled", stylesheet_tag)
        self.assertIn(b"uiDesignIntroModal", page.data)

        disabled = client.post("/api/me/ui-design", json={"ui_design": "classic"})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(client.get("/api/me").get_json()["item"]["ui_design"], "classic")

    def test_invalid_design_is_rejected(self):
        response = self.authenticated_client().post(
            "/api/me/ui-design", json={"ui_design": "unknown"}
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
