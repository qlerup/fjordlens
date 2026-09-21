import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app as fjordlens


class _CountingLock:
    """Wraps a real lock and records the max number of simultaneous holders,
    so tests can prove a code path is actually serialized rather than just
    hoping timing happens to expose a race."""

    def __init__(self):
        self._lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._current = 0
        self.max_concurrent = 0

    def __enter__(self):
        self._lock.acquire()
        with self._count_lock:
            self._current += 1
            self.max_concurrent = max(self.max_concurrent, self._current)
        return self

    def __exit__(self, exc_type, exc, tb):
        with self._count_lock:
            self._current -= 1
        self._lock.release()
        return False


class FaceIndexConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.uploads = root / "uploads"
        (self.uploads / "originals").mkdir(parents=True)
        self.previous = {
            "DATA_DIR": fjordlens.DATA_DIR,
            "DB_PATH": fjordlens.DB_PATH,
            "UPLOAD_DIR": fjordlens.UPLOAD_DIR,
            "INSTALL_STATE_PATH": fjordlens.INSTALL_STATE_PATH,
            "DB_BOOTSTRAP_READY": fjordlens.DB_BOOTSTRAP_READY,
            "FACE_DB_WRITE_LOCK": fjordlens.FACE_DB_WRITE_LOCK,
        }
        fjordlens.DATA_DIR = root
        fjordlens.DB_PATH = root / "fjordlens.db"
        fjordlens.UPLOAD_DIR = self.uploads
        fjordlens.INSTALL_STATE_PATH = root / "fjordlens.install.json"
        fjordlens.DB_BOOTSTRAP_READY = False
        fjordlens.init_db()
        self.counting_lock = _CountingLock()
        fjordlens.FACE_DB_WRITE_LOCK = self.counting_lock

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(fjordlens, name, value)
        self.tempdir.cleanup()

    def _make_photo(self, name: str) -> str:
        rel = f"uploads/originals/{name}.jpg"
        (self.uploads / "originals" / f"{name}.jpg").write_bytes(b"fake")
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute(
                """INSERT INTO photos(rel_path, filename, ext, file_size, width, height, created_fs, modified_fs, captured_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (rel, f"{name}.jpg", "jpg", 10, 100, 100, fjordlens.now_iso(), fjordlens.now_iso(), fjordlens.now_iso()),
            )
            conn.commit()
        return rel

    def test_disabled_videos_are_excluded_from_coverage_and_preserve_results(self):
        image = self._make_photo('image')
        video_old = self._make_photo('video')
        video = video_old.replace('.jpg', '.mp4')
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute("UPDATE photos SET rel_path=?, people_count=3 WHERE rel_path=?", (video, video_old))
            conn.commit()
        fjordlens._set_setting('faces_video_index', '0')
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 1)
        with patch.object(fjordlens, '_ai_detect_faces_path', return_value=[]), \
             patch.object(fjordlens, '_ai_detect_faces_video_path') as detect_video:
            stats = fjordlens._run_face_slot_queue([image, video], 2)
        detect_video.assert_not_called()
        self.assertEqual(stats['skipped'], 1)
        self.assertEqual(stats['errors'], 0)
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            row = conn.execute('SELECT people_count, faces_indexed_at FROM photos WHERE rel_path=?', (video,)).fetchone()
            self.assertEqual(row['people_count'], 3)
            self.assertFalse(row['faces_indexed_at'])
            self.assertEqual(conn.execute('SELECT count(*) FROM processing_failures WHERE rel_path=?', (video,)).fetchone()[0], 0)
        fjordlens._set_setting('faces_video_index', '1')
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 1)
        self.assertTrue(fjordlens._is_faces_index_supported_rel(video))

    def test_switching_video_off_stops_at_next_frame(self):
        fjordlens._set_setting('faces_video_index', '1')
        def first_frame(*args, **kwargs):
            fjordlens._set_setting('faces_video_index', '0')
            return []
        with patch.object(fjordlens, '_video_face_sample_timestamps', return_value=(5, [0, 1, 2])), \
             patch.object(fjordlens, '_extract_video_frame_bytes', return_value=b'jpeg') as extract, \
             patch.object(fjordlens, '_ai_detect_faces_bytes', side_effect=first_frame):
            with self.assertRaises(fjordlens.FaceIndexSkipped):
                fjordlens._ai_detect_faces_video_path(Path('movie.mp4'), 'movie.mp4')
        self.assertEqual(extract.call_count, 1)

    def test_retry_missing_matches_coverage_and_skips_completed_files(self):
        missing = self._make_photo('missing')
        completed = self._make_photo('completed_without_faces')
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            conn.execute('UPDATE photos SET faces_indexed_at=? WHERE rel_path=?', (fjordlens.now_iso(), completed))
            conn.commit()
        self.assertEqual(fjordlens._faces_index_coverage()['missing'], 1)
        with patch.object(fjordlens, '_run_face_slot_queue', return_value={'errors': 0}) as queue, patch.object(fjordlens, '_ai_face_runtime_warmup'), patch.object(fjordlens, '_ai_face_runtime_release'):
            fjordlens._index_faces_worker(all_photos=False)
        self.assertEqual(queue.call_args.args[0], [missing])

    def test_concurrent_batch_serializes_db_writes_and_indexes_every_photo(self):
        rels = [self._make_photo(f"concurrent_{i}") for i in range(8)]
        fake_face = {"embedding": [1.0, 0.0, 0.0, 0.0], "bbox": [1, 2, 11, 22], "confidence": 0.9}

        # Real AI detection is out of scope here; only the concurrency/locking
        # behavior of the DB-write phase that follows it is under test.
        with patch.object(fjordlens, "_ai_detect_faces_path", return_value=[fake_face]):
            start = threading.Barrier(len(rels))
            errors = []

            def run(rel):
                try:
                    start.wait(timeout=5)
                    fjordlens.index_faces_for_photo(rel)
                except Exception as e:
                    errors.append((rel, e))

            threads = [threading.Thread(target=run, args=(rel,)) for rel in rels]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(self.counting_lock.max_concurrent, 1, "DB-write phase must never run on more than one thread at a time")

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            for rel in rels:
                photo = conn.execute("SELECT id, people_count FROM photos WHERE rel_path=?", (rel,)).fetchone()
                self.assertEqual(photo["people_count"], 1)
                faces = conn.execute("SELECT COUNT(*) AS c FROM faces WHERE photo_id=?", (photo["id"],)).fetchone()
                self.assertEqual(faces["c"], 1)

    def test_upload_face_batch_setting_is_persisted_and_bounded(self):
        fjordlens._set_setting("upload_workflow_face_batch_size", "8")
        payload = fjordlens._upload_workflow_settings_payload()
        self.assertEqual(payload["batch_size"], 8)
        self.assertEqual(payload["face_batch_mode"], "slot_queue")

        fjordlens._set_setting("upload_workflow_face_batch_size", "999")
        self.assertEqual(fjordlens._upload_workflow_settings_payload()["batch_size"], 8)

        fjordlens._set_setting("upload_workflow_face_batch_size", "0")
        self.assertEqual(fjordlens._upload_workflow_settings_payload()["batch_size"], 1)

    def test_manual_face_indexer_refills_gpu_slot_before_db_store_finishes(self):
        rels = [self._make_photo(f"batch_{i}") for i in range(6)]
        fjordlens._set_setting("upload_workflow_face_batch_size", "4")

        first_wave = threading.Barrier(4)
        long_detection_release = threading.Event()
        refill_started = threading.Event()
        active_lock = threading.Lock()
        active_detection = 0
        max_active_detection = 0

        def fake_detect(rel):
            nonlocal active_detection, max_active_detection
            idx = int(Path(rel).stem.split("_")[-1])
            with active_lock:
                active_detection += 1
                max_active_detection = max(max_active_detection, active_detection)
            try:
                if idx < 4:
                    first_wave.wait(timeout=3)
                    if idx == 0:
                        # Detection 0 completes immediately. The queue must refill
                        # its GPU slot before persisting this result to SQLite.
                        return []
                    long_detection_release.wait(timeout=3)
                    return []
                if idx == 4:
                    refill_started.set()
                    long_detection_release.set()
                    return []
                return []
            finally:
                with active_lock:
                    active_detection -= 1

        stored = []

        def fake_store_batch(items, *, match_cache, touched_person_ids):
            batch_results = []
            for rel, _faces in items:
                idx = int(Path(rel).stem.split("_")[-1])
                if idx == 0:
                    # Persistence is a separate consumer. GPU slot 0 must be
                    # refilled while this DB writer is still waiting.
                    self.assertTrue(
                        refill_started.wait(timeout=2),
                        "GPU detection slot was not refilled before DB persistence",
                    )
                stored.append(rel)
                batch_results.append((rel, 0, None))
            return batch_results, match_cache

        fjordlens._faces_running.set()
        with (
            patch.object(fjordlens, "_detect_faces_for_photo", side_effect=fake_detect) as detect,
            patch.object(fjordlens, "_store_face_results_batch", side_effect=fake_store_batch) as store_batch,
            patch.object(fjordlens, "_recompute_person_centroids_bulk", return_value=None),
            patch.object(fjordlens, "faces_index_throttle_enabled_sec", return_value=0.0),
        ):
            fjordlens._index_faces_worker(all_photos=True)

        self.assertTrue(refill_started.is_set(), "A free GPU face slot should be refilled immediately")
        self.assertEqual(max_active_detection, 4)
        self.assertEqual(detect.call_count, 6)
        self.assertGreaterEqual(store_batch.call_count, 1)
        self.assertEqual(set(stored), set(rels))
        self.assertFalse(fjordlens._faces_running.is_set())


if __name__ == "__main__":
    unittest.main()
