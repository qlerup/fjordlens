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
            "CONVERSION_WORK_DIR": fjordlens.CONVERSION_WORK_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
        }
        fjordlens.DATA_DIR = root / "data"
        fjordlens.UPLOAD_DIR = root / "uploads"
        fjordlens.THUMB_DIR = root / "thumbs"
        fjordlens.CONVERSION_WORK_DIR = root / "conversion_work"
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

    def test_disk_sync_does_not_claim_system_uploaded_file_after_queue_handoff(self):
        source = fjordlens.UPLOAD_DIR / "camera.jpg"
        source.write_bytes(b"uploaded through FjordLens")
        rel = "uploads/camera.jpg"
        fjordlens._upsert_uploaded_stub(rel, source, "Anna")

        with fjordlens.UPLOAD_PENDING_LOCK:
            fjordlens.UPLOAD_PENDING_BY_USER.clear()

        with (
            patch.object(fjordlens, "UPLOAD_FOLDER_SYNC_SETTLE_SEC", 0),
            patch.object(fjordlens, "UPLOAD_FOLDER_SYNC_TTL_SEC", 0),
            patch.object(fjordlens, "_start_direct_upload_postprocess") as start_direct,
        ):
            result = fjordlens._sync_upload_folder_from_disk(
                "",
                recursive=False,
                queue_postprocess=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["postprocess_queued"], 0)
        start_direct.assert_not_called()

    def test_conversion_uses_local_work_dir_before_publishing(self):
        source = fjordlens.UPLOAD_DIR / "originals" / "clip.mov"
        destination = fjordlens.UPLOAD_DIR / "converted" / "clip.mp4"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"source video")
        observed = {}

        def fake_converter(local_source, local_destination):
            observed["source"] = local_source
            observed["destination"] = local_destination
            self.assertTrue(local_source.is_relative_to(fjordlens.CONVERSION_WORK_DIR))
            self.assertTrue(local_destination.is_relative_to(fjordlens.CONVERSION_WORK_DIR))
            local_destination.write_bytes(b"converted video")

        fjordlens._convert_on_local_storage(source, destination, fake_converter)

        self.assertEqual(destination.read_bytes(), b"converted video")
        self.assertFalse(observed["source"].exists())
        self.assertFalse(observed["destination"].exists())
        self.assertEqual(list(destination.parent.glob("*.publish.mp4")), [])

    def test_mov_upload_stays_local_until_conversion_then_publishes_both_files(self):
        incoming = fjordlens.DATA_DIR / "incoming.mov"
        incoming.write_bytes(b"source video")
        originals = fjordlens.UPLOAD_DIR / "originals" / "album"
        rel = "uploads/originals/album/clip.mov"

        with patch.object(fjordlens, "mov_convert_on_upload_enabled", return_value=True):
            ok, saved_name, error = fjordlens._commit_uploaded_file(
                target_dir=originals,
                rel_prefix="uploads/originals/",
                subdir="album",
                source_path=incoming,
                original_name="clip.mov",
                last_modified_ms=None,
                uploaded_by="Anna",
            )

        self.assertTrue(ok, error)
        self.assertEqual(saved_name, "clip.mov")
        self.assertFalse((originals / "clip.mov").exists())
        self.assertTrue(fjordlens._staged_upload_path(rel).exists())

        def fake_convert(src, dst):
            self.assertTrue(src.is_relative_to(fjordlens.CONVERSION_WORK_DIR))
            self.assertTrue(dst.is_relative_to(fjordlens.CONVERSION_WORK_DIR))
            dst.write_bytes(b"converted video")

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
            patch.object(fjordlens, "upsert_photo"),
            patch.object(fjordlens, "_make_video_thumb", return_value=None),
        ):
            result = fjordlens._postprocess_uploaded_rels(
                "Anna",
                [rel],
                workflow_mode=fjordlens.UPLOAD_WORKFLOW_MODE_GENTLE,
            )

        self.assertEqual(result["indexed"], 1)
        self.assertEqual((originals / "clip.mov").read_bytes(), b"source video")
        self.assertEqual(
            (fjordlens.UPLOAD_DIR / "converted" / "album" / "clip.mp4").read_bytes(),
            b"converted video",
        )
        self.assertFalse(fjordlens._staged_upload_path(rel).exists())


if __name__ == "__main__":
    unittest.main()
