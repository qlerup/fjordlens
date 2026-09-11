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

    def authenticated_client(self, uid=1):
        client = fjordlens.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(uid)
            session["_fresh"] = True
        return client

    def test_design_can_be_enabled_and_disabled_globally(self):
        client = self.authenticated_client()
        initial = client.get("/api/me").get_json()["item"]
        self.assertEqual(initial["ui_design"], "classic")

        enabled = client.post("/api/me/ui-design", json={"ui_design": "fjord"})
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.get_json()["ui_design"], "fjord")
        self.assertEqual(client.get("/api/me").get_json()["item"]["ui_design"], "fjord")
        self.assertEqual(fjordlens.app.test_client().get("/api/ui-design").get_json()["ui_design"], "fjord")

        page = client.get("/")
        stylesheet_tag = next(
            line for line in page.data.splitlines() if b'id="fjordDesignStylesheet"' in line
        )
        self.assertNotIn(b" disabled", stylesheet_tag)
        self.assertIn(b'media="all"', stylesheet_tag)
        self.assertIn(b"uiDesignIntroModal", page.data)

        disabled = client.post("/api/me/ui-design", json={"ui_design": "classic"})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(client.get("/api/me").get_json()["item"]["ui_design"], "classic")
        self.assertEqual(fjordlens.app.test_client().get("/api/ui-design").get_json()["ui_design"], "classic")

    def add_user(self, role="user", design="classic"):
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            cursor = conn.execute(
                "INSERT INTO users(username,password_hash,is_admin,role,created_at,ui_design) VALUES(?,?,?,?,?,?)",
                (role, generate_password_hash("test-password"), int(role == "admin"), role, fjordlens.now_iso(), design),
            )
            conn.commit()
            return cursor.lastrowid

    def test_all_accounts_and_fresh_login_ignore_old_user_and_cookie_designs(self):
        uid = self.add_user()
        admin = self.authenticated_client()
        user = self.authenticated_client(uid)
        guest = fjordlens.app.test_client()
        guest.set_cookie("fl_ui_design", "classic")
        self.assertEqual(admin.post("/api/settings/ui-design", json={"ui_design": "fjord"}).status_code, 200)
        for client in (admin, user):
            self.assertEqual(client.get("/api/me").get_json()["item"]["ui_design"], "fjord")
            self.assertIn(b'data-ui-design="fjord"', client.get("/").data)
        for client in (guest, fjordlens.app.test_client()):
            response = client.get("/login")
            self.assertIn(b'data-ui-design="fjord"', response.data)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn(b'id="uiDesignSelect"', user.get("/").data)
        # A new DB bootstrap/process must not restore a legacy user's choice.
        fjordlens.DB_BOOTSTRAP_READY = False
        self.assertEqual(guest.get("/api/ui-design").get_json()["ui_design"], "fjord")

    def test_only_admin_can_change_design_on_both_urls(self):
        for role in ("user", "manager"):
            client = self.authenticated_client(self.add_user(role))
            for url in ("/api/me/ui-design", "/api/settings/ui-design"):
                self.assertEqual(client.post(url, json={"ui_design": "fjord"}).status_code, 403)
        guest = fjordlens.app.test_client()
        for url in ("/api/me/ui-design", "/api/settings/ui-design"):
            self.assertEqual(guest.post(url, json={"ui_design": "fjord"}).status_code, 401)
        self.assertEqual(guest.get("/api/ui-design").get_json()["ui_design"], "classic")

    def test_existing_admin_selection_is_migrated_once(self):
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("UPDATE users SET ui_design='fjord' WHERE id=1")
            conn.commit()
        guest = fjordlens.app.test_client()
        self.assertEqual(guest.get("/api/ui-design").get_json()["ui_design"], "fjord")
        self.authenticated_client().post("/api/settings/ui-design", json={"ui_design": "classic"})
        self.assertEqual(guest.get("/api/ui-design").get_json()["ui_design"], "classic")

    def test_public_design_endpoint_exposes_only_design_and_is_not_cached(self):
        response = fjordlens.app.test_client().get("/api/ui-design")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "ui_design": "classic"})
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_invalid_design_is_rejected(self):
        for value in ("unknown", "", None):
            response = self.authenticated_client().post(
                "/api/me/ui-design", json={"ui_design": value}
            )
            self.assertEqual(response.status_code, 400)

    def test_login_bootstraps_last_selected_design_and_theme(self):
        page = fjordlens.app.test_client().get("/login")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="fjordDesignStylesheet"', page.data)
        self.assertIn(b"fl_ui_design", page.data)
        self.assertIn(b"fl_theme_mode", page.data)
        self.assertIn(b'class="fjord-backdrop"', page.data)

        design_script = (Path(fjordlens.app.static_folder) / "theme-design.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem(DESIGN_KEY, current)", design_script)


if __name__ == "__main__":
    unittest.main()
