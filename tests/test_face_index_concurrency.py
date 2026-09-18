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

    def test_manual_face_indexer_refills_free_slots_without_waiting_for_batch(self):
        rels = [self._make_photo(f"batch_{i}") for i in range(6)]
        fjordlens._set_setting("upload_workflow_face_batch_size", "4")

        first_wave = threading.Barrier(4)
        long_release = threading.Event()
        refill_started = threading.Event()
        active_lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_index(rel):
            nonlocal active, max_active
            idx = int(Path(rel).stem.split("_")[-1])
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                if idx < 4:
                    first_wave.wait(timeout=3)
                    if idx == 0:
                        return 0
                    long_release.wait(timeout=3)
                    return 0
                if idx == 4:
                    # This must start as soon as item 0 frees one of the four slots,
                    # while items 1-3 are still deliberately blocked.
                    refill_started.set()
                    long_release.set()
                    return 0
                return 0
            finally:
                with active_lock:
                    active -= 1

        fjordlens._faces_running.set()
        with (
            patch.object(fjordlens, "index_faces_for_photo", side_effect=fake_index) as index_one,
            patch.object(fjordlens, "faces_index_throttle_enabled_sec", return_value=0.0),
        ):
            fjordlens._index_faces_worker(all_photos=True)

        self.assertTrue(refill_started.is_set(), "A free face slot should be refilled immediately")
        self.assertEqual(max_active, 4)
        self.assertEqual(index_one.call_count, 6)
        self.assertFalse(fjordlens._faces_running.is_set())


if __name__ == "__main__":
    unittest.main()
