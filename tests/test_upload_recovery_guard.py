import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from upload_recovery_guard import (
    _is_permanently_unreadable_recovery_jpeg,
    _load_terminal,
    init_upload_recovery_guard,
)


class UploadRecoveryGuardTests(unittest.TestCase):
    def test_corrupt_recovered_jpeg_is_skipped_but_current_upload_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload_dir = root / "uploads"
            corrupt = upload_dir / "originals" / "old.jpg"
            corrupt.parent.mkdir(parents=True, exist_ok=True)
            corrupt.write_bytes(b"not a jpeg")

            core = SimpleNamespace(
                UPLOAD_DIR=upload_dir,
                DATA_DIR=root / "data",
                logger=None,
            )
            core._merge_recovered_uploaded_rels = (
                lambda _user, rels, *args, **kwargs: list(rels) + ["uploads/originals/old.jpg"]
            )

            init_upload_recovery_guard(core)

            merged = core._merge_recovered_uploaded_rels(
                "Anna", ["uploads/originals/new.jpg"]
            )
            self.assertEqual(merged, ["uploads/originals/new.jpg"])

            # A deliberate current upload still gets a fresh chance.
            current = core._merge_recovered_uploaded_rels(
                "Anna", ["uploads/originals/old.jpg"]
            )
            self.assertEqual(current[0], "uploads/originals/old.jpg")

    def test_valid_recovered_jpeg_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload_dir = root / "uploads"
            valid = upload_dir / "originals" / "valid.jpg"
            valid.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), "white").save(valid, format="JPEG")

            core = SimpleNamespace(UPLOAD_DIR=upload_dir, DATA_DIR=root / "data")
            self.assertFalse(
                _is_permanently_unreadable_recovery_jpeg(
                    core, "uploads/originals/valid.jpg"
                )
            )

    def test_failed_current_upload_retries_once_then_becomes_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "uploads/originals/fail.jpg"
            pending = {rel}
            calls = []

            def merge(_user, rels, *args, **kwargs):
                out = list(rels)
                for item in pending:
                    if item not in out:
                        out.append(item)
                return out

            def postprocess(_user, rels, *args, **kwargs):
                calls.append(list(rels))
                return {"ok": False, "indexed": 0, "index_errors": len(rels)}

            core = SimpleNamespace(
                DATA_DIR=root / "data",
                UPLOAD_DIR=root / "uploads",
                logger=None,
                _merge_recovered_uploaded_rels=merge,
                _postprocess_uploaded_rels=postprocess,
            )

            init_upload_recovery_guard(core)
            core._postprocess_uploaded_rels("Anna", [rel])

            self.assertEqual(calls, [[rel], [rel]])
            self.assertIn(rel, _load_terminal(core))

            # A later unrelated upload must not resurrect the terminal failure.
            merged = core._merge_recovered_uploaded_rels(
                "Anna", ["uploads/originals/new.jpg"]
            )
            self.assertEqual(merged, ["uploads/originals/new.jpg"])

    def test_transient_failure_succeeds_on_single_retry_and_is_not_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "uploads/originals/transient.jpg"
            pending = {rel}
            calls = []

            def merge(_user, rels, *args, **kwargs):
                out = list(rels)
                for item in pending:
                    if item not in out:
                        out.append(item)
                return out

            def postprocess(_user, rels, *args, **kwargs):
                calls.append(list(rels))
                if len(calls) == 2:
                    pending.discard(rel)
                return {"ok": True}

            core = SimpleNamespace(
                DATA_DIR=root / "data",
                UPLOAD_DIR=root / "uploads",
                logger=None,
                _merge_recovered_uploaded_rels=merge,
                _postprocess_uploaded_rels=postprocess,
            )

            init_upload_recovery_guard(core)
            core._postprocess_uploaded_rels("Anna", [rel])

            self.assertEqual(calls, [[rel], [rel]])
            self.assertNotIn(rel, _load_terminal(core))


if __name__ == "__main__":
    unittest.main()
