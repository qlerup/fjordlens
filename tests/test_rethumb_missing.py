import tempfile
import unittest
from pathlib import Path

from PIL import Image

import app as fjordlens


class RethumbMissingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.originals = root / "photos"
        self.uploads = root / "uploads"
        self.thumbs = root / "thumbs"
        self.originals.mkdir()
        self.uploads.mkdir()
        self.thumbs.mkdir()

        self.previous = {
            "DB_PATH": fjordlens.DB_PATH,
            "PHOTO_DIR": fjordlens.PHOTO_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "THUMB_DIR": fjordlens.THUMB_DIR,
        }
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.PHOTO_DIR = self.originals
        fjordlens.UPLOAD_DIR = self.uploads
        fjordlens.THUMB_DIR = self.thumbs
        fjordlens.init_db()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _create_photo(self, rel_path: str, color: str) -> Path:
        path = self.originals / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 60), color=color).save(path, format="JPEG")
        return path

    def test_generates_only_missing_thumbnail_and_reports_scan_counts(self):
        missing_path = self._create_photo("missing.jpg", "red")
        complete_path = self._create_photo("complete.jpg", "blue")
        complete_stat = complete_path.stat()
        with Image.open(complete_path) as image:
            complete_thumb = fjordlens.make_thumb(
                image, "complete.jpg", complete_stat.st_mtime, complete_stat.st_size
            )

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                "INSERT INTO photos(rel_path, filename, thumb_name) VALUES(?, ?, ?)",
                ("missing.jpg", missing_path.name, None),
            )
            conn.execute(
                "INSERT INTO photos(rel_path, filename, thumb_name) VALUES(?, ?, ?)",
                ("complete.jpg", complete_path.name, complete_thumb),
            )
            conn.commit()

        result = fjordlens.rethumb_missing()

        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["up_to_date"], 1)
        self.assertEqual(result["source_missing"], 0)
        self.assertEqual(result["errors"], 0)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute(
                "SELECT thumb_name FROM photos WHERE rel_path='missing.jpg'"
            ).fetchone()
        self.assertTrue(row["thumb_name"])
        self.assertTrue((self.thumbs / row["thumb_name"]).is_file())


if __name__ == "__main__":
    unittest.main()
