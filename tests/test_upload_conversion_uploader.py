import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as fjordlens


class UploadConversionUploaderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.previous = {
            "DATA_DIR": fjordlens.DATA_DIR,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "THUMB_DIR": fjordlens.THUMB_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
        }
        fjordlens.DATA_DIR = root / "data"
        fjordlens.UPLOAD_DIR = root / "uploads"
        fjordlens.THUMB_DIR = root / "thumbs"
        fjordlens.DB_PATH = fjordlens.DATA_DIR / "fjordlens.db"
        fjordlens.INSTALL_STATE_PATH = fjordlens.DATA_DIR / "fjordlens.install.json"
        fjordlens.DB_BOOTSTRAP_READY = False
        fjordlens.DATA_DIR.mkdir(parents=True, exist_ok=True)
        fjordlens.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        fjordlens.THUMB_DIR.mkdir(parents=True, exist_ok=True)
        fjordlens.init_db()

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def test_recovered_mov_conversion_preserves_share_visitor_name(self):
        source = fjordlens.UPLOAD_DIR / "originals" / "shared" / "clip.mov"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test mov")
        rel = "uploads/originals/shared/clip.mov"
        fjordlens._upsert_uploaded_stub(rel, source, "Mobilgæst")

        indexed = []

        def fake_convert(src, dst):
            shutil.copyfile(src, dst)

        def fake_extract(_path, converted_rel, generate_thumb=False):
            return {"rel_path": converted_rel, "ext": ".mp4"}

        with (
            patch.object(fjordlens, "mov_convert_on_upload_enabled", return_value=True),
            patch.object(fjordlens, "mov_keep_originals_enabled", return_value=True),
            patch.object(fjordlens, "faces_auto_index_enabled", return_value=False),
            patch.object(fjordlens, "ai_auto_ingest_enabled", return_value=False),
            patch.object(fjordlens, "ai_desc_auto_ingest_enabled", return_value=False),
            patch.object(fjordlens, "_mov_to_mp4", side_effect=fake_convert),
            patch.object(fjordlens, "extract_metadata", side_effect=fake_extract),
            patch.object(fjordlens, "upsert_photo", side_effect=lambda meta: indexed.append(dict(meta))),
            patch.object(fjordlens, "_make_video_thumb", return_value=None),
        ):
            result = fjordlens._postprocess_uploaded_rels(
                "",
                [rel],
                workflow_mode=fjordlens.UPLOAD_WORKFLOW_MODE_GENTLE,
            )

        self.assertEqual(result["indexed"], 1)
        self.assertEqual(len(indexed), 1)
        self.assertEqual(indexed[0]["rel_path"], "uploads/converted/shared/clip.mp4")
        self.assertEqual(indexed[0]["uploaded_by"], "Mobilgæst")

    def test_failed_converted_index_keeps_uploader_stub_for_recovery(self):
        source = fjordlens.UPLOAD_DIR / "originals" / "shared" / "retry.mov"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test mov")
        rel = "uploads/originals/shared/retry.mov"
        fjordlens._upsert_uploaded_stub(rel, source, "Anna")

        def fake_convert(src, dst):
            shutil.copyfile(src, dst)

        with (
            patch.object(fjordlens, "mov_convert_on_upload_enabled", return_value=True),
            patch.object(fjordlens, "mov_keep_originals_enabled", return_value=True),
            patch.object(fjordlens, "faces_auto_index_enabled", return_value=False),
            patch.object(fjordlens, "ai_auto_ingest_enabled", return_value=False),
            patch.object(fjordlens, "ai_desc_auto_ingest_enabled", return_value=False),
            patch.object(fjordlens, "_mov_to_mp4", side_effect=fake_convert),
            patch.object(fjordlens, "extract_metadata", side_effect=RuntimeError("metadata failed")),
        ):
            result = fjordlens._postprocess_uploaded_rels(
                "",
                [rel],
                workflow_mode=fjordlens.UPLOAD_WORKFLOW_MODE_GENTLE,
            )

        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["index_errors"], 1)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute(
                "SELECT uploaded_by FROM photos WHERE rel_path=?",
                (rel,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["uploaded_by"], "Anna")


if __name__ == "__main__":
    unittest.main()
