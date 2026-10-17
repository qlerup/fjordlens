import sqlite3
import tempfile
import unittest
from pathlib import Path

from media_activity import MediaActivity
from folder_index import _process_start


class MediaActivityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / 'activity.db'
        self.activity = MediaActivity(lambda: sqlite3.connect(path), _process_start)
        self.other_worker = MediaActivity(lambda: sqlite3.connect(path), _process_start)

    def tearDown(self):
        self.directory.cleanup()

    def test_other_worker_sees_active_file_but_can_delete_unrelated_sibling(self):
        with self.activity.processing(['uploads/originals/trip/a.jpg']):
            self.assertIsNone(self.other_worker.acquire('deleting', ['uploads/converted/trip/a.jpg']))
            free = self.other_worker.acquire('deleting', ['uploads/originals/trip/b.jpg'])
            self.assertIsNotNone(free)
            self.other_worker.release(free)
            self.assertIsNone(self.other_worker.acquire('deleting', [], ['uploads/trip']))
            free = self.other_worker.acquire('deleting', [], ['uploads/trip2'])
            self.assertIsNotNone(free)
            self.other_worker.release(free)

    def test_nested_stage_finishing_keeps_outer_flow_protected(self):
        with self.activity.processing(['uploads/originals/a.jpg']):
            with self.activity.processing(['uploads/originals/a.jpg']):
                pass
            self.assertIsNone(self.other_worker.acquire('deleting', ['uploads/originals/a.jpg']))
        token = self.other_worker.acquire('deleting', ['uploads/originals/a.jpg'])
        self.assertIsNotNone(token)
        self.other_worker.release(token)

    def test_queued_file_is_protected_across_worker_and_handoff(self):
        self.activity.queue('uploads/originals/a.jpg')
        self.assertIsNone(self.other_worker.acquire('deleting', ['uploads/originals/a.jpg']))
        with self.activity.processing(['uploads/originals/a.jpg'], consume_queue=True):
            self.assertIsNone(self.other_worker.acquire('deleting', ['uploads/originals/a.jpg']))
        token = self.other_worker.acquire('deleting', ['uploads/originals/a.jpg'])
        self.assertIsNotNone(token)
        self.other_worker.release(token)

    def test_exception_releases_flow(self):
        with self.assertRaises(ValueError):
            with self.activity.processing(['uploads/a.jpg']):
                raise ValueError('stopped')
        token = self.other_worker.acquire('deleting', ['uploads/a.jpg'])
        self.assertIsNotNone(token)
        self.other_worker.release(token)
