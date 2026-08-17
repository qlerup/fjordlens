import tempfile
import unittest
from pathlib import Path

from PIL import Image

import app as fjordlens


class DeleteCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.originals = root / "photos"
        self.uploads = root / "uploads"
        self.thumbs = root / "thumbs"
        self.converted = root / "converted"
        self.originals.mkdir()
        self.uploads.mkdir()
        self.thumbs.mkdir()
        self.converted.mkdir()

        self.previous = {
            "DB_PATH": fjordlens.DB_PATH,
            "PHOTO_DIR": fjordlens.PHOTO_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "THUMB_DIR": fjordlens.THUMB_DIR,
            "CONVERT_DIR": fjordlens.CONVERT_DIR,
            "CONVERSION_WORK_DIR": fjordlens.CONVERSION_WORK_DIR,
        }
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.PHOTO_DIR = self.originals
        fjordlens.UPLOAD_DIR = self.uploads
        fjordlens.THUMB_DIR = self.thumbs
        fjordlens.CONVERT_DIR = self.converted
        fjordlens.CONVERSION_WORK_DIR = root / "conversion_work"
        with fjordlens.UPLOAD_PENDING_LOCK:
            fjordlens.UPLOAD_PENDING_BY_USER.clear()
        fjordlens.init_db()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _insert_photo_with_face(self, rel_path: str) -> tuple[int, int, Path, Path]:
        leaf = rel_path.split("/", 1)[1]
        src = self.uploads / leaf
        src.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 60), color="green").save(src, format="JPEG")

        thumb_name = f"thumb_{leaf.replace('/', '_')}.jpg"
        thumb_path = self.thumbs / thumb_name
        Image.new("RGB", (16, 12), color="green").save(thumb_path, format="JPEG")

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            cur = conn.execute(
                "INSERT INTO photos(rel_path, filename, thumb_name) VALUES(?, ?, ?)",
                (rel_path, Path(leaf).name, thumb_name),
            )
            photo_id = int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO faces(photo_id, created_at) VALUES(?, ?)",
                (photo_id, fjordlens.now_iso()),
            )
            face_id = int(cur.lastrowid)
            conn.commit()
        return photo_id, face_id, src, thumb_path

    def test_delete_photo_removes_face_thumbs_and_photoframe_copy(self):
        rel = "uploads/originals/video.mp4"
        photo_id, face_id, src, thumb_path = self._insert_photo_with_face(rel)

        face_thumb = self.thumbs / fjordlens._face_thumb_name(face_id)
        face_thumb.write_bytes(b"jpg")
        legacy_face_thumb = self.thumbs / f"face_{face_id}.jpg"
        legacy_face_thumb.write_bytes(b"jpg")
        pf_copy = fjordlens._photoframe_video_prepared_path(rel)
        pf_copy.parent.mkdir(parents=True, exist_ok=True)
        pf_copy.write_bytes(b"mp4")

        removed = fjordlens._delete_indexed_photos_by_ids([photo_id])

        self.assertEqual(removed["photos"], 1)
        self.assertEqual(removed["faces"], 1)
        self.assertFalse(src.exists(), "original file should be deleted")
        self.assertFalse(thumb_path.exists(), "photo thumbnail should be deleted")
        self.assertFalse(face_thumb.exists(), "versioned face thumb should be deleted")
        self.assertFalse(legacy_face_thumb.exists(), "legacy face thumb should be deleted")
        self.assertFalse(pf_copy.exists(), "photoframe copy should be deleted")
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM photos").fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM faces").fetchone()["c"], 0)

    def test_delete_by_prefix_removes_face_thumbs_and_photoframe_copy(self):
        rel = "uploads/originals/tur/klip.mp4"
        photo_id, face_id, src, thumb_path = self._insert_photo_with_face(rel)

        face_thumb = self.thumbs / fjordlens._face_thumb_name(face_id)
        face_thumb.write_bytes(b"jpg")
        pf_copy = fjordlens._photoframe_video_prepared_path(rel)
        pf_copy.parent.mkdir(parents=True, exist_ok=True)
        pf_copy.write_bytes(b"mp4")

        removed = fjordlens._delete_indexed_photos_for_prefixes(["uploads/originals/tur"])

        self.assertEqual(removed["photos"], 1)
        self.assertEqual(removed["faces"], 1)
        self.assertFalse(face_thumb.exists(), "face thumb should be deleted")
        self.assertFalse(thumb_path.exists(), "photo thumbnail should be deleted")
        self.assertFalse(pf_copy.exists(), "photoframe copy should be deleted")

    def test_orphan_cleanup_protects_current_face_thumbs(self):
        rel = "uploads/originals/billede.jpg"
        photo_id, face_id, src, thumb_path = self._insert_photo_with_face(rel)

        current = self.thumbs / fjordlens._face_thumb_name(face_id)
        current.write_bytes(b"jpg")
        legacy = self.thumbs / f"face_{face_id}.jpg"
        legacy.write_bytes(b"jpg")
        stale_version = self.thumbs / f"face_{face_id}_v1.jpg"
        stale_version.write_bytes(b"jpg")

        fjordlens._cleanup_orphan_thumbs(dry_run=False)

        self.assertTrue(current.exists(), "current face thumb must survive cleanup")
        self.assertTrue(thumb_path.exists(), "referenced photo thumb must survive cleanup")
        self.assertFalse(legacy.exists(), "legacy face thumb should be cleaned up")
        self.assertFalse(stale_version.exists(), "stale-version face thumb should be cleaned up")

    def test_folder_cleanup_removes_local_staging_and_matching_queue_entries(self):
        staged_deleted = fjordlens._staged_upload_path("uploads/originals/Bryllup (2026)/clip.mov")
        staged_kept = fjordlens._staged_upload_path("uploads/originals/Anden mappe/keep.mov")
        staged_deleted.parent.mkdir(parents=True, exist_ok=True)
        staged_kept.parent.mkdir(parents=True, exist_ok=True)
        staged_deleted.write_bytes(b"delete")
        staged_kept.write_bytes(b"keep")
        with fjordlens.UPLOAD_PENDING_LOCK:
            fjordlens.UPLOAD_PENDING_BY_USER["Anna"] = [
                "uploads/originals/Bryllup (2026)/clip.mov",
                "uploads/originals/Anden mappe/keep.mov",
            ]

        result = fjordlens._cleanup_staged_upload_folders(["Bryllup (2026)"])

        self.assertEqual(result, {"files": 1, "queue_items": 1})
        self.assertFalse(staged_deleted.exists())
        self.assertTrue(staged_kept.exists())
        with fjordlens.UPLOAD_PENDING_LOCK:
            self.assertEqual(
                fjordlens.UPLOAD_PENDING_BY_USER["Anna"],
                ["uploads/originals/Anden mappe/keep.mov"],
            )


if __name__ == "__main__":
    unittest.main()
