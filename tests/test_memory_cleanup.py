import threading
import unittest
from unittest.mock import Mock, patch

from flask import Flask
import memory_cleanup


class HeapCleanupTests(unittest.TestCase):
    def test_requests_start_only_one_worker(self):
        app = Flask(__name__)
        memory_cleanup.install(app)
        app.add_url_rule("/", view_func=lambda: "ok")
        with patch.object(memory_cleanup, "_load_trim", return_value=Mock()), \
                patch.object(memory_cleanup.threading, "Thread") as thread:
            for _ in range(3):
                self.assertEqual(app.test_client().get("/").status_code, 200)
            thread.assert_called_once()
            thread.return_value.start.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])

    def test_trim_repeats_without_requests_or_jobs(self):
        cleanup = memory_cleanup.HeapCleanup(interval=0.001)
        done = threading.Event()
        calls = []

        def trim(padding):
            calls.append(padding)
            if len(calls) == 2:
                cleanup._stop.set()
                done.set()
            return 0  # No releasable memory is a normal result, not an error.

        with patch.object(memory_cleanup, "_load_trim", return_value=trim):
            cleanup.start()
            try:
                self.assertTrue(done.wait(2))
                self.assertEqual(calls, [0, 0])
            finally:
                cleanup._stop.set()

    def test_unsupported_platform_does_not_break_requests(self):
        cleanup = memory_cleanup.HeapCleanup()
        with patch.object(memory_cleanup.ctypes, "CDLL", return_value=object()), \
                patch.object(memory_cleanup.threading, "Thread") as thread:
            cleanup.start()
            cleanup.start()
            thread.assert_not_called()

    def test_windows_loader_rejects_null_library_name(self):
        with patch.object(memory_cleanup.ctypes, "CDLL", side_effect=TypeError("library name required")):
            self.assertIsNone(memory_cleanup._load_trim())

    def test_child_resets_inherited_worker_state(self):
        cleanup = memory_cleanup.HeapCleanup()
        old_lock = cleanup._lock
        cleanup._started = True
        cleanup._stop.set()
        cleanup._reset()
        self.assertIsNot(cleanup._lock, old_lock)
        self.assertFalse(cleanup._stop.is_set())
        with patch.object(memory_cleanup, "_load_trim", return_value=Mock()), \
                patch.object(memory_cleanup.threading, "Thread") as thread:
            cleanup.start()
            thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
