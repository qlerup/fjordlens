import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from upload_recovery_guard import (
    _is_permanently_unreadable_recovery_jpeg,
    init_upload_recovery_guard,
)


class UploadRecoveryGuardTests(unittest.TestCase):
    def test_corrupt_recovered_jpeg_is_skipped_but_current_upload_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            corrupt = upload_dir / "originals" / "old.jpg"
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_bytes(b"not a jpeg")

            core = SimpleNamespace(
                UPLOAD_DIR=upload_dir,
                logger=None,
            )
            core._merge_recovered_uploaded_rels = (
                lambda _user, rels: list(rels) + ["uploads/originals/old.jpg"]
            )

            init_upload_recovery_guard(core)

            merged = core._merge_recovered_uploaded_rels(
                "Anna", ["uploads/originals/new.jpg"]
            )
            self.assertEqual(merged, ["uploads/originals/new.jpg"])

            # A corrupt file still gets its first normal processing attempt.
            current = core._merge_recovered_uploaded_rels(
                "Anna", ["uploads/originals/old.jpg"]
            )
            self.assertEqual(current[0], "uploads/originals/old.jpg")

    def test_valid_recovered_jpeg_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            valid = upload_dir / "originals" / "valid.jpg"
            valid.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), "white").save(valid, format="JPEG")

            core = SimpleNamespace(UPLOAD_DIR=upload_dir)
            self.assertFalse(
                _is_permanently_unreadable_recovery_jpeg(
                    core, "uploads/originals/valid.jpg"
                )
            )


if __name__ == "__main__":
    unittest.main()
