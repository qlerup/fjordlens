import unittest
import sqlite3
from unittest.mock import Mock
from face_retry import FaceRetryGate, is_database_busy
from processing_failures import ServiceUnavailable, FailureTracker


class RetryTests(unittest.TestCase):
    def test_only_sqlite_lock_errors_are_retryable(self):
        self.assertTrue(is_database_busy(sqlite3.OperationalError('database is locked')))
        extended = sqlite3.OperationalError('busy snapshot')
        extended.sqlite_errorcode = sqlite3.SQLITE_BUSY | (2 << 8)
        self.assertTrue(is_database_busy(extended))
        self.assertFalse(is_database_busy(sqlite3.OperationalError('no such table: photos')))
        self.assertFalse(is_database_busy(RuntimeError('database is locked')))
        self.assertFalse(is_database_busy(None))

    def test_outage_retries_same_item_without_consuming_queue(self):
        notify = Mock()
        operation = Mock(side_effect=[ServiceUnavailable('offline'), ServiceUnavailable('offline'), ['face']])
        gate = FaceRetryGate(notify, delay=0)
        self.assertEqual(gate.run(operation, lambda: True), ['face'])
        self.assertEqual(operation.call_count, 3)
        self.assertEqual([c.args for c in notify.call_args_list], [('offline',), ('',)])

    def test_stop_during_outage_does_not_retry(self):
        active = [True]
        def fail():
            active[0] = False
            raise ServiceUnavailable('offline')
        operation = Mock(side_effect=fail)
        with self.assertRaisesRegex(RuntimeError, 'stopped'):
            FaceRetryGate(Mock(), delay=0).run(operation, lambda: active[0])
        operation.assert_called_once()

    def test_bad_image_is_not_retried(self):
        operation = Mock(side_effect=ValueError('invalid image'))
        with self.assertRaises(ValueError):
            FaceRetryGate(Mock(), delay=0).run(operation, lambda: True)
        operation.assert_called_once()

    def test_transient_outage_is_not_persisted_as_file_failure(self):
        tracker = FailureTracker(Mock())
        tracker.fail = Mock()
        @tracker.track('faces', lambda: 'photo.jpg')
        def work():
            raise ServiceUnavailable('offline')
        with self.assertRaises(ServiceUnavailable):
            work()
        tracker.fail.assert_not_called()
