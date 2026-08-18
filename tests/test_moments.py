import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import app as fjordlens


class MomentDetectionTests(unittest.TestCase):
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
            "MOMENT_MIN_PHOTOS": fjordlens.MOMENT_MIN_PHOTOS,
            "MOMENT_MIN_SPAN_HOURS": fjordlens.MOMENT_MIN_SPAN_HOURS,
            "MOMENT_GAP_HOURS": fjordlens.MOMENT_GAP_HOURS,
        }
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.PHOTO_DIR = self.originals
        fjordlens.UPLOAD_DIR = self.uploads
        fjordlens.THUMB_DIR = self.thumbs
        fjordlens.CONVERT_DIR = self.converted
        fjordlens.MOMENT_MIN_PHOTOS = 3
        fjordlens.MOMENT_MIN_SPAN_HOURS = 1.0
        fjordlens.MOMENT_GAP_HOURS = 12.0
        fjordlens.init_db()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _insert_photo(self, rel_path: str, captured_at: str, gps_name=None, favorite: int = 0) -> None:
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO photos(rel_path, filename, captured_at, gps_name, favorite) VALUES(?, ?, ?, ?, ?)",
                (rel_path, Path(rel_path).name, captured_at, gps_name, favorite),
            )
            conn.commit()

    def test_gap_splits_into_two_moments(self):
        # Cluster A: 4 photos, one hour apart.
        base_a = datetime(2024, 7, 10, 9, 0, 0)
        for i in range(4):
            dt = base_a + timedelta(hours=i)
            self._insert_photo(f"uploads/originals/a_{i}.jpg", dt.isoformat(timespec="seconds"))
        # Cluster B: starts well beyond MOMENT_GAP_HOURS after cluster A ends.
        base_b = base_a + timedelta(hours=40)
        for i in range(4):
            dt = base_b + timedelta(hours=i)
            self._insert_photo(f"uploads/originals/b_{i}.jpg", dt.isoformat(timespec="seconds"))

        stats = fjordlens._detect_moment_candidates()
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["scanned"], 8)
        self.assertEqual(stats["dated"], 8)
        self.assertEqual(stats["segments"], 2)
        self.assertEqual(stats["rejected_too_few"], 0)
        self.assertEqual(stats["rejected_too_short"], 0)
        self.assertEqual(stats["rejected_home_only"], 0)

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            rows = conn.execute("SELECT * FROM moments ORDER BY start_date ASC").fetchall()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["status"], "suggested")
        ids_a = set(fjordlens.json.loads(rows[0]["photo_ids_json"]))
        ids_b = set(fjordlens.json.loads(rows[1]["photo_ids_json"]))
        self.assertEqual(len(ids_a), 4)
        self.assertEqual(len(ids_b), 4)
        self.assertTrue(ids_a.isdisjoint(ids_b))

    def test_small_cluster_below_minimum_is_skipped(self):
        base = datetime(2024, 7, 10, 9, 0, 0)
        for i in range(2):  # below MOMENT_MIN_PHOTOS=3
            dt = base + timedelta(hours=i)
            self._insert_photo(f"uploads/originals/x_{i}.jpg", dt.isoformat(timespec="seconds"))

        stats = fjordlens._detect_moment_candidates()
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["rejected_too_few"], 1)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM moments").fetchone()["c"]
        self.assertEqual(count, 0)

    def test_running_detection_twice_does_not_duplicate(self):
        base = datetime(2024, 7, 10, 9, 0, 0)
        for i in range(4):
            dt = base + timedelta(hours=i)
            self._insert_photo(f"uploads/originals/c_{i}.jpg", dt.isoformat(timespec="seconds"))

        first = fjordlens._detect_moment_candidates()
        second = fjordlens._detect_moment_candidates()
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["rejected_too_few"], 1, "photos from the first run should now be excluded as already-claimed")
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM moments").fetchone()["c"]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
