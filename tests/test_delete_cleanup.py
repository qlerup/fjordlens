import tempfile
import unittest
from unittest.mock import patch
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

    def _guard(self, body, operation):
        with fjordlens.app.test_request_context(json=body):
            return fjordlens._media_deletion_guard(operation)()

    def test_unrelated_photos_and_folders_can_be_deleted_during_flow(self):
        busy, _, _, _ = self._insert_photo_with_face('uploads/originals/trip/busy.jpg')
        free, _, src, _ = self._insert_photo_with_face('uploads/originals/other/free.jpg')
        with fjordlens.media_activity.processing(['uploads/originals/trip/busy.jpg']):
            self.assertEqual(self._guard({'photo_ids': [free]}, lambda: 'deleted'), 'deleted')
            self.assertEqual(self._guard({'paths': ['other']}, lambda: 'deleted'), 'deleted')
            # A different file in the same folder is independent too.
            sibling, _, _, _ = self._insert_photo_with_face('uploads/originals/trip/free.jpg')
            self.assertEqual(self._guard({'photo_ids': [sibling]}, lambda: 'deleted'), 'deleted')
            for body in ({'photo_ids': [busy]}, {'paths': ['trip']}, {'paths': ['originals/trip']}):
                operation = unittest.mock.Mock()
                response, status = self._guard(body, operation)
                self.assertEqual(status, 409)
                self.assertEqual(response.get_json()['code'], 'media_processing')
                operation.assert_not_called()
        self.assertEqual(self._guard({'photo_ids': [busy]}, lambda: 'deleted'), 'deleted')

    def test_deletion_rejects_only_overlapping_pending_uploads(self):
        busy, _, _, _ = self._insert_photo_with_face('uploads/originals/trip/busy.jpg')
        free, _, _, _ = self._insert_photo_with_face('uploads/originals/other/free.jpg')
        with patch.object(fjordlens, '_pending_upload_rels_snapshot', return_value={'uploads/originals/trip/busy.jpg'}):
            _, status = self._guard({'photo_ids': [busy]}, lambda: 'deleted')
            self.assertEqual(status, 409)
            self.assertEqual(self._guard({'photo_ids': [free]}, lambda: 'deleted'), 'deleted')

    def test_converted_photo_is_protected_by_original_flow(self):
        photo, _, _, _ = self._insert_photo_with_face('uploads/converted/trip/a_1.jpg')
        import json
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('UPDATE photos SET metadata_json=? WHERE id=?',
                         (json.dumps({'conversion': {'from_rel_path': 'uploads/originals/trip/a.heic',
                                                     'to_rel_path': 'uploads/converted/trip/a_1.jpg'}}), photo))
            conn.commit()
        with fjordlens.media_activity.processing(['uploads/originals/trip/a.heic']):
            _, status = self._guard({'photo_ids': [photo]}, lambda: 'deleted')
            self.assertEqual(status, 409)

    def test_deleting_selection_excludes_new_processing_until_release(self):
        token = fjordlens.media_activity.acquire('deleting', [], ['uploads/trip'])
        try:
            self.assertIsNone(fjordlens.media_activity.acquire('processing', ['uploads/originals/trip/a.jpg']))
            unrelated = fjordlens.media_activity.acquire('processing', ['uploads/originals/trip2/a.jpg'])
            self.assertIsNotNone(unrelated)
            fjordlens.media_activity.release(unrelated)
        finally:
            fjordlens.media_activity.release(token)

    def test_delete_does_not_scan_thumbnails_or_compute_covers(self):
        photo_id, face_id, src, thumb = self._insert_photo_with_face('uploads/originals/trip/a.jpg')
        with patch.object(Path, 'glob', side_effect=AssertionError('directory scan')), \
             patch.object(fjordlens, '_compute_and_store_folder_previews', side_effect=AssertionError('cover rebuild')), \
             patch.object(fjordlens, '_find_existing_converted_for_upload_rel', return_value=None):
            removed = fjordlens._delete_indexed_photos_by_ids([photo_id])
        self.assertEqual(removed['photos'], 1)
        self.assertIn('trip', removed['preview_folders'])
        self.assertFalse(src.exists())
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            self.assertIsNotNone(conn.execute("SELECT 1 FROM folder_index_dirty WHERE path='trip'").fetchone())

    def test_normal_video_delete_never_scans_conversion_directory(self):
        photo_id, _, src, _ = self._insert_photo_with_face('uploads/originals/trip/clip.mp4')
        unrelated = self.uploads / 'converted/trip/clip.jpg'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b'unrelated image')
        with patch.object(Path, 'glob', side_effect=AssertionError('directory scan')), \
             patch.object(fjordlens, '_find_existing_converted_for_upload_rel', side_effect=AssertionError('conversion lookup')):
            result = fjordlens._delete_indexed_photos_by_ids([photo_id])
        self.assertEqual(result['photos'], 1)
        self.assertFalse(src.exists())
        self.assertTrue(unrelated.exists())

    def test_failed_source_unlink_preserves_index_and_thumbnail_for_retry(self):
        photo_id, face_id, src, thumb = self._insert_photo_with_face('uploads/originals/trip/clip.mp4')
        unlink = Path.unlink
        def fail_source(path, *args, **kwargs):
            if path == src:
                raise PermissionError('Storage denied deletion')
            return unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_source):
            with self.assertRaisesRegex(PermissionError, 'Storage denied deletion'):
                fjordlens._delete_indexed_photos_by_ids([photo_id])
        self.assertTrue(src.exists())
        self.assertTrue(thumb.exists())
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            self.assertIsNotNone(conn.execute('SELECT id FROM photos WHERE id=?', (photo_id,)).fetchone())
            self.assertIsNotNone(conn.execute('SELECT id FROM faces WHERE id=?', (face_id,)).fetchone())
        self.assertEqual(fjordlens._delete_indexed_photos_by_ids([photo_id])['photos'], 1)

    def test_delete_removes_both_staged_and_persistent_upload(self):
        rel = 'uploads/originals/trip/clip.mp4'
        photo_id, _, src, _ = self._insert_photo_with_face(rel)
        staged = fjordlens._staged_upload_path(rel)
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b'staged')
        self.assertEqual(fjordlens._delete_indexed_photos_by_ids([photo_id])['files'], 2)
        self.assertFalse(src.exists())
        self.assertFalse(staged.exists())

    def test_legacy_mov_and_explicit_conversion_links_are_deleted(self):
        import json
        for filename, metadata in (
            ('legacy.mov', None),
            ('linked.mov', {'conversion': {'to_rel_path': 'uploads/converted/trip/linked_1.mp4'}}),
        ):
            photo_id, _, src, _ = self._insert_photo_with_face('uploads/originals/trip/' + filename)
            converted = self.uploads / 'converted/trip' / ('legacy.mp4' if metadata is None else 'linked_1.mp4')
            converted.parent.mkdir(parents=True, exist_ok=True)
            converted.write_bytes(b'converted')
            if metadata:
                with fjordlens.closing(fjordlens.get_conn()) as conn:
                    conn.execute('UPDATE photos SET metadata_json=? WHERE id=?', (json.dumps(metadata), photo_id))
                    conn.commit()
            self.assertEqual(fjordlens._delete_indexed_photos_by_ids([photo_id])['photos'], 1)
            self.assertFalse(src.exists())
            self.assertFalse(converted.exists())

    def test_missing_source_can_still_be_removed_from_index(self):
        photo_id, _, src, _ = self._insert_photo_with_face('uploads/originals/trip/clip.mp4')
        src.unlink()
        self.assertEqual(fjordlens._delete_indexed_photos_by_ids([photo_id])['photos'], 1)

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

    def test_rebuild_single_thumbnail_updates_photo_row(self):
        rel = "uploads/originals/album/missing-thumb.jpg"
        source = self.uploads / "originals" / "album" / "missing-thumb.jpg"
        source.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 60), color="blue").save(source, format="JPEG")
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            cursor = conn.execute(
                "INSERT INTO photos(rel_path, filename, thumb_name) VALUES(?, ?, NULL)",
                (rel, source.name),
            )
            photo_id = int(cursor.lastrowid)
            conn.commit()
            row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()

        thumb_name = fjordlens._rebuild_thumbnail_for_row(row)

        self.assertTrue((self.thumbs / thumb_name).exists())
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            updated = conn.execute("SELECT thumb_name FROM photos WHERE id=?", (photo_id,)).fetchone()
        self.assertEqual(updated["thumb_name"], thumb_name)


if __name__ == "__main__":
    unittest.main()
