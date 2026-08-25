import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

import app as fjordlens


class ApiClientTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {
            "DATA_DIR": fjordlens.DATA_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
            "API_CLIENT_MAX_PENDING": fjordlens.API_CLIENT_MAX_PENDING,
        }
        fjordlens.DATA_DIR = root / "data"
        fjordlens.UPLOAD_DIR = root / "uploads"
        fjordlens.DB_PATH = fjordlens.DATA_DIR / "fjordlens.db"
        fjordlens.INSTALL_STATE_PATH = fjordlens.DATA_DIR / "fjordlens.install.json"
        fjordlens.DB_BOOTSTRAP_READY = False
        fjordlens.DATA_DIR.mkdir(parents=True)
        fjordlens.UPLOAD_DIR.mkdir(parents=True)
        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, is_admin, role, created_at) VALUES(?,?,?,?,?)",
                ("admin", generate_password_hash("test-password"), 1, "admin", fjordlens.now_iso()),
            )
            conn.commit()

        self.client = fjordlens.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _start_pairing(self):
        response = self.client.post(
            "/api/client-auth/pair/start",
            json={"device_name": "Testkamera"},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def _approve(self, pairing_id):
        return self.client.post(
            f"/api/admin/clients/{pairing_id}/approve",
            json={"target_folder": "Kamera/Test"},
        )

    def test_pairing_secret_is_hashed_and_approval_enables_bearer_access(self):
        pairing = self._start_pairing()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute("SELECT * FROM api_clients WHERE id=?", (pairing["pairing_id"],)).fetchone()
        self.assertNotEqual(row["secret_hash"], pairing["secret"])
        self.assertEqual(row["secret_hash"], fjordlens._share_token_digest(pairing["secret"]))

        approved = self._approve(pairing["pairing_id"])
        self.assertEqual(approved.status_code, 200)
        status = self.client.get(
            "/api/client/status",
            headers={"Authorization": f"Bearer {pairing['secret']}"},
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["target_folder"], "Kamera/Test")

    def test_expired_pairing_cannot_be_approved(self):
        pairing = self._start_pairing()
        expired_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat(timespec="seconds") + "Z"
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "UPDATE api_clients SET pairing_expires_at=? WHERE id=?",
                (expired_at, pairing["pairing_id"]),
            )
            conn.commit()

        response = self._approve(pairing["pairing_id"])
        self.assertEqual(response.status_code, 410)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            status = conn.execute(
                "SELECT status FROM api_clients WHERE id=?", (pairing["pairing_id"],)
            ).fetchone()["status"]
        self.assertEqual(status, "denied")

    def test_revoked_client_cannot_be_reapproved_and_token_stops_working(self):
        pairing = self._start_pairing()
        self.assertEqual(self._approve(pairing["pairing_id"]).status_code, 200)
        revoked = self.client.post(f"/api/admin/clients/{pairing['pairing_id']}/revoke")
        self.assertEqual(revoked.status_code, 200)

        reapproved = self._approve(pairing["pairing_id"])
        self.assertEqual(reapproved.status_code, 409)
        status = self.client.get(
            "/api/client/status",
            headers={"Authorization": f"Bearer {pairing['secret']}"},
        )
        self.assertEqual(status.status_code, 401)

    def test_folder_change_requires_an_approved_client(self):
        pairing = self._start_pairing()
        response = self.client.post(
            f"/api/admin/clients/{pairing['pairing_id']}/folder",
            json={"target_folder": "Kamera/Ny"},
        )
        self.assertEqual(response.status_code, 409)

    def test_pairing_requests_are_limited_until_one_expires(self):
        fjordlens.API_CLIENT_MAX_PENDING = 1
        first = self._start_pairing()
        limited = self.client.post(
            "/api/client-auth/pair/start",
            json={"device_name": "Kamera 2"},
        )
        self.assertEqual(limited.status_code, 429)

        expired_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat(timespec="seconds") + "Z"
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "UPDATE api_clients SET pairing_expires_at=? WHERE id=?",
                (expired_at, first["pairing_id"]),
            )
            conn.commit()
        replacement = self.client.post(
            "/api/client-auth/pair/start",
            json={"device_name": "Kamera 2"},
        )
        self.assertEqual(replacement.status_code, 200)


if __name__ == "__main__":
    unittest.main()