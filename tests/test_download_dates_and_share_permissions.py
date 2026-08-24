import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from unittest.mock import patch

import piexif
from PIL import Image
from werkzeug.security import generate_password_hash

import app as fjordlens


class DownloadDatesAndSharePermissionsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {
            "DATA_DIR": fjordlens.DATA_DIR,
            "PHOTO_DIR": fjordlens.PHOTO_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "THUMB_DIR": fjordlens.THUMB_DIR,
            "CONVERT_DIR": fjordlens.CONVERT_DIR,
            "TUS_TMP_DIR": fjordlens.TUS_TMP_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
        }
        fjordlens.DATA_DIR = root / "data"
        fjordlens.PHOTO_DIR = root / "library"
        fjordlens.UPLOAD_DIR = root / "uploads"
        fjordlens.THUMB_DIR = root / "thumbs"
        fjordlens.CONVERT_DIR = fjordlens.DATA_DIR / "converted"
        fjordlens.TUS_TMP_DIR = fjordlens.DATA_DIR / "tus_uploads"
        fjordlens.DB_PATH = fjordlens.DATA_DIR / "fjordlens.db"
        fjordlens.INSTALL_STATE_PATH = fjordlens.DATA_DIR / "fjordlens.install.json"
        fjordlens.DB_BOOTSTRAP_READY = False
        for path in (
            fjordlens.DATA_DIR,
            fjordlens.PHOTO_DIR,
            fjordlens.UPLOAD_DIR,
            fjordlens.THUMB_DIR,
            fjordlens.CONVERT_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)
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

    def _add_jpeg(self, folder: str, filename: str, color=(20, 40, 60)):
        target_dir = fjordlens.UPLOAD_DIR / "originals" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        old_stamp = b"2020:01:02 03:04:05"
        exif = {
            "0th": {
                piexif.ImageIFD.Make: b"FjordLens Test Camera",
                piexif.ImageIFD.DateTime: old_stamp,
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: old_stamp,
                piexif.ExifIFD.DateTimeDigitized: old_stamp,
                piexif.ExifIFD.OffsetTimeOriginal: b"+01:00",
            },
            "GPS": {},
            "1st": {},
            "thumbnail": None,
        }
        Image.new("RGB", (12, 8), color).save(path, "JPEG", quality=93, exif=piexif.dump(exif))
        original_mtime = datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()
        os.utime(path, (original_mtime, original_mtime))
        rel = f"uploads/originals/{folder}/{filename}"
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            cur = conn.execute(
                """
                INSERT INTO photos(rel_path, filename, ext, file_size, captured_at, imported_at, last_scanned_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    rel,
                    filename,
                    ".jpg",
                    path.stat().st_size,
                    "2020-01-02T03:04:05+01:00",
                    fjordlens.now_iso(),
                    fjordlens.now_iso(),
                ),
            )
            photo_id = int(cur.lastrowid)
            conn.commit()
        return photo_id, path

    def _add_share(self, token: str, folder: str, *, can_download=0, can_upload=0, can_delete=0):
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
                    folder,
                    folder,
                    can_download,
                    can_upload,
                    can_delete,
                    0,
                    0,
                    0,
                    1,
                    now,
                ),
            )
            share_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO share_link_folders(share_id, folder_path, created_at) VALUES(?,?,?)",
                (share_id, folder, now),
            )
            conn.commit()
        return share_id

    def test_single_original_is_byte_identical_and_today_only_changes_copy(self):
        photo_id, source = self._add_jpeg("album", "photo.jpg")
        source_bytes = source.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        source_mtime = source.stat().st_mtime_ns

        original = self.client.get(
            f"/api/photos/download/{photo_id}?mode=original&date_mode=original"
        )
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.data, source_bytes)
        self.assertEqual(original.headers["X-FjordLens-Captured-At"], "2020-01-02T03:04:05+01:00")
        self.assertIn("no-store", original.headers.get("Cache-Control", ""))

        fixed = datetime(2026, 7, 13, 18, 30, 45, tzinfo=timezone.utc)
        with patch.object(fjordlens, "_download_now", return_value=fixed):
            today = self.client.get(
                f"/api/photos/download/{photo_id}?mode=original&date_mode=today"
            )

        self.assertEqual(today.status_code, 200)
        self.assertEqual(today.headers["X-FjordLens-Captured-At"], fixed.isoformat(timespec="seconds"))
        self.assertEqual(parsedate_to_datetime(today.headers["Last-Modified"]), fixed)
        self.assertIn("no-store", today.headers.get("Cache-Control", ""))
        downloaded_exif = piexif.load(today.data)
        self.assertEqual(
            downloaded_exif["Exif"][piexif.ExifIFD.DateTimeOriginal],
            b"2026:07:13 18:30:45",
        )
        self.assertEqual(
            downloaded_exif["Exif"][piexif.ExifIFD.OffsetTimeOriginal],
            b"+00:00",
        )
        self.assertEqual(
            downloaded_exif["0th"][piexif.ImageIFD.Make],
            b"FjordLens Test Camera",
        )
        with Image.open(io.BytesIO(source_bytes)) as before, Image.open(io.BytesIO(today.data)) as after:
            self.assertEqual(list(before.convert("RGB").getdata()), list(after.convert("RGB").getdata()))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
        self.assertEqual(source.stat().st_mtime_ns, source_mtime)

    def test_zip_today_stamps_every_member_with_one_time_and_keeps_sources(self):
        first_id, first = self._add_jpeg("one", "same.jpg", (10, 20, 30))
        second_id, second = self._add_jpeg("two", "same.jpg", (30, 20, 10))
        before = {first: first.read_bytes(), second: second.read_bytes()}
        fixed = datetime(2026, 7, 13, 20, 15, 0, tzinfo=timezone.utc)
        with patch.object(fjordlens, "_download_now", return_value=fixed):
            response = self.client.post(
                "/api/photos/download-zip",
                json={
                    "photo_ids": [first_id, second_id],
                    "mode": "original",
                    "date_mode": "today",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        with zipfile.ZipFile(io.BytesIO(response.data), "r") as archive:
            self.assertEqual(archive.namelist(), ["same.jpg", "same_2.jpg"])
            for name in archive.namelist():
                exif = piexif.load(archive.read(name))
                self.assertEqual(
                    exif["Exif"][piexif.ExifIFD.DateTimeOriginal],
                    b"2026:07:13 20:15:00",
                )
        for path, original_bytes in before.items():
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_invalid_download_options_are_rejected(self):
        photo_id, _ = self._add_jpeg("album", "photo.jpg")
        response = self.client.get(
            f"/api/photos/download/{photo_id}?mode=wrong&date_mode=tomorrow"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/photos/download-zip",
            json={"photo_ids": [photo_id], "mode": "original", "date_mode": "tomorrow"},
        )
        self.assertEqual(response.status_code, 400)

    def test_every_share_can_select_and_download(self):
        photo_id, source = self._add_jpeg("shared", "photo.jpg")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        source_mtime = source.stat().st_mtime_ns
        token = "view-token"
        self._add_share(token, "shared", can_download=0)

        info = self.client.get(f"/api/share/{token}/info")
        self.assertEqual(info.status_code, 200)
        self.assertTrue(info.get_json()["can_download"])
        with patch.object(fjordlens, "_sync_upload_folder_from_disk", return_value=None):
            photos = self.client.get(f"/api/share/{token}/photos")
        self.assertIsNotNone(photos.get_json()["items"][0]["download_url"])
        self.assertIsNotNone(photos.get_json()["items"][0]["download_converted_url"])
        view = self.client.get(f"/api/share/{token}/view/{photo_id}")
        self.assertEqual(view.status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/share/{token}/download/{photo_id}?mode=original").status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/share/{token}/download-zip",
                json={"photo_ids": [photo_id], "mode": "original"},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(f"/api/share/{token}/original/{photo_id}").status_code, 200)
        fixed = datetime(2026, 7, 13, 21, 10, 5, tzinfo=timezone.utc)
        with patch.object(fjordlens, "_download_now", return_value=fixed):
            allowed = self.client.get(
                f"/api/share/{token}/download/{photo_id}?mode=original&date_mode=today"
            )
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("no-store", allowed.headers.get("Cache-Control", ""))
        self.assertEqual(
            allowed.headers["X-FjordLens-Captured-At"],
            fixed.isoformat(timespec="seconds"),
        )
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
        self.assertEqual(source.stat().st_mtime_ns, source_mtime)
        batch = self.client.post(
            f"/api/share/{token}/download-zip",
            json={"photo_ids": [photo_id], "mode": "original", "date_mode": "original"},
        )
        self.assertEqual(batch.status_code, 200)

    def test_share_photos_are_paged_and_include_folder_summaries(self):
        for index in range(3):
            self._add_jpeg("shared", f"photo-{index}.jpg")
        self._add_jpeg("shared/child", "nested.jpg")
        token = "paged-share-token"
        self._add_share(token, "shared", can_download=1)

        with patch.object(fjordlens, "_sync_upload_folder_from_disk", return_value=None):
            first = self.client.get(f"/api/share/{token}/photos?limit=2&offset=0&path=")
            second = self.client.get(f"/api/share/{token}/photos?limit=2&offset=2&path=")

        self.assertEqual(first.status_code, 200)
        first_data = first.get_json()
        self.assertEqual(len(first_data["items"]), 2)
        self.assertEqual(first_data["total"], 3)
        self.assertTrue(first_data["has_more"])
        self.assertEqual(first_data["folders"][0]["path"], "child")
        self.assertEqual(first_data["folders"][0]["count"], 1)
        self.assertEqual(len(second.get_json()["items"]), 1)
        self.assertFalse(second.get_json()["has_more"])

    def test_create_update_and_admin_list_include_download_for_all_permissions(self):
        (fjordlens.UPLOAD_DIR / "originals" / "shared").mkdir(parents=True, exist_ok=True)
        created = self.client.post(
            "/api/shares",
            json={
                "share_name": "Download only",
                "folder_paths": ["shared"],
                "permission": "view",
                "expires_value": 0,
            },
        )
        self.assertEqual(created.status_code, 200)
        payload = created.get_json()
        self.assertEqual(payload["permission"], "view")
        self.assertTrue(payload["can_download"])
        self.assertFalse(payload["can_upload"])

        listing = self.client.get("/api/admin/shares?include_inactive=1")
        item = next(row for row in listing.get_json()["items"] if row["share_name"] == "Download only")
        self.assertEqual(item["permission"], "view")
        self.assertTrue(item["can_download"])

        updated = self.client.put(
            f"/api/admin/shares/{item['id']}",
            json={
                "share_name": "Upload",
                "folder_paths": ["shared"],
                "permission": "upload",
                "expires_value": 0,
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["can_download"])
        self.assertTrue(updated.get_json()["can_upload"])

    def test_legacy_permission_migration_enables_download_for_all_shares(self):
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("DROP TABLE share_link_folders")
            conn.execute("DROP TABLE share_links")
            conn.execute(
                """
                CREATE TABLE share_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT UNIQUE NOT NULL,
                    token_plain TEXT,
                    share_name TEXT,
                    folder_path TEXT NOT NULL,
                    can_upload INTEGER DEFAULT 0,
                    can_delete INTEGER DEFAULT 0,
                    require_visitor_name INTEGER DEFAULT 0,
                    link_use_duckdns INTEGER DEFAULT 0,
                    password_hash TEXT,
                    expires_at TEXT,
                    revoked INTEGER DEFAULT 0,
                    created_by_user_id INTEGER,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
                """
            )
            for name, upload, delete in (("view", 0, 0), ("upload", 1, 0), ("manage", 1, 1)):
                conn.execute(
                    """
                    INSERT INTO share_links(token_hash, token_plain, share_name, folder_path,
                                            can_upload, can_delete, created_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (name, name, name, name, upload, delete, fjordlens.now_iso()),
                )
            conn.commit()

        fjordlens.init_db()
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            rows = conn.execute(
                "SELECT share_name, can_download FROM share_links ORDER BY id"
            ).fetchall()
        self.assertEqual(
            [(row["share_name"], int(row["can_download"] or 0)) for row in rows],
            [("view", 1), ("upload", 1), ("manage", 1)],
        )


if __name__ == "__main__":
    unittest.main()
