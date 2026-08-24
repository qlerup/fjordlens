import tempfile
import unittest
from pathlib import Path

import app as fjordlens


class PersistentLogTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_data_dir = fjordlens.DATA_DIR
        with fjordlens.LOG_LOCK:
            self.previous_items = list(fjordlens.LOG_BUFFER)
            self.previous_seq = fjordlens.LOG_SEQ
            self.previous_file_entries = fjordlens.LOG_FILE_ENTRIES
            fjordlens.DATA_DIR = Path(self.tempdir.name)
            fjordlens.LOG_BUFFER.clear()
            fjordlens.LOG_SEQ = 0
            fjordlens.LOG_FILE_ENTRIES = 0

    def tearDown(self):
        with fjordlens.LOG_LOCK:
            fjordlens.DATA_DIR = self.previous_data_dir
            fjordlens.LOG_BUFFER.clear()
            fjordlens.LOG_BUFFER.extend(self.previous_items)
            fjordlens.LOG_SEQ = self.previous_seq
            fjordlens.LOG_FILE_ENTRIES = self.previous_file_entries
        self.tempdir.cleanup()

    def test_events_survive_memory_reload(self):
        fjordlens.log_event("upload_done", filename="IMG_0001.mov", saved=1)
        log_path = fjordlens._event_log_path()
        self.assertTrue(log_path.exists())

        with fjordlens.LOG_LOCK:
            fjordlens.LOG_BUFFER.clear()
            fjordlens.LOG_SEQ = 0
            fjordlens.LOG_FILE_ENTRIES = 0
        fjordlens._load_persistent_logs()

        self.assertEqual(len(fjordlens.LOG_BUFFER), 1)
        self.assertEqual(fjordlens.LOG_BUFFER[0]["event"], "upload_done")
        self.assertEqual(fjordlens.LOG_BUFFER[0]["filename"], "IMG_0001.mov")
        self.assertEqual(fjordlens.LOG_SEQ, 1)

    def test_clear_removes_memory_and_file(self):
        fjordlens.log_event("folder_created", path="Ny mappe")
        fjordlens._clear_persistent_logs()

        self.assertEqual(list(fjordlens.LOG_BUFFER), [])
        self.assertEqual(fjordlens.LOG_SEQ, 0)
        self.assertFalse(fjordlens._event_log_path().exists())


if __name__ == "__main__":
    unittest.main()
