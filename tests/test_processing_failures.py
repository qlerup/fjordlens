import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from processing_failures import FailureTracker


class ProcessingFailureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'data.db'
        def connect():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            return conn
        self.connect = connect
        self.tracker = FailureTracker(connect)

    def tearDown(self):
        self.directory.cleanup()

    def test_failure_persists_without_photo_and_across_restart(self):
        self.tracker.fail('not-indexed.heic', 'conversion', 'out of memory')
        restarted = FailureTracker(self.connect)
        self.assertEqual(restarted.items()[0]['error'], 'out of memory')

    def test_success_clears_only_its_own_stage_and_file(self):
        for rel, stage in [('a.jpg', 'faces'), ('a.jpg', 'embeddings'), ('b.jpg', 'faces')]:
            self.tracker.fail(rel, stage, 'failed')
        work = self.tracker.track('faces', lambda rel: rel)(lambda rel: 0)
        work('a.jpg')  # Zero faces is a valid successful result.
        self.assertEqual({(r['rel_path'], r['stage']) for r in self.tracker.items()},
                         {('a.jpg', 'embeddings'), ('b.jpg', 'faces')})

    def test_success_notifies_log_resolution_only_after_committed_clear(self):
        def resolved(rel, stage):
            self.assertEqual((rel, stage), ('a.jpg', 'faces'))
            self.assertEqual(self.tracker.items(), [])
        callback = Mock(side_effect=resolved)
        self.tracker.on_success = callback
        self.tracker.fail('a.jpg', 'faces', 'locked')
        callback.assert_not_called()
        work = self.tracker.track('faces', lambda rel: rel)(lambda rel: 0)
        work('a.jpg')
        callback.assert_called_once_with('a.jpg', 'faces')

    def test_all_stages_capture_exceptions_and_keep_latest_reason(self):
        for stage in ('metadata', 'conversion', 'faces', 'embeddings', 'descriptions', 'thumbnails'):
            fn = self.tracker.track(stage, lambda rel: rel)(Mock(side_effect=RuntimeError('timeout')))
            with self.assertRaisesRegex(RuntimeError, 'timeout'):
                fn('a.jpg')
        self.assertEqual(len(self.tracker.items()), 6)
        self.tracker.fail('a.jpg', 'metadata', 'new failure')
        row = next(r for r in self.tracker.items() if r['stage'] == 'metadata')
        self.assertEqual(row['attempts'], 2)
        self.assertEqual(row['error'], 'new failure')

    def test_false_result_is_failure_but_unsupported_file_is_skipped(self):
        work = self.tracker.track('embeddings', lambda rel: rel, false_failure=True,
                                 enabled=lambda rel: rel.endswith('.jpg'))(lambda rel: False)
        work('a.mp4')
        self.assertEqual(self.tracker.items(), [])
        work('a.jpg')
        self.assertEqual(len(self.tracker.items()), 1)

    def test_partial_metadata_does_not_clear_error(self):
        work = self.tracker.track('metadata', lambda meta: meta['rel_path'],
            result_error=lambda result, meta: meta.get('thumb_error'))(lambda meta: None)
        work({'rel_path': 'a.jpg', 'thumb_error': 'corrupt image'})
        self.assertEqual(self.tracker.items()[0]['error'], 'corrupt image')

    def test_retry_snapshot_skips_resolved_failures_and_keeps_failed_retry(self):
        for rel in ('a.jpg', 'b.jpg'):
            self.tracker.fail(rel, 'faces', 'timeout')
        items = self.tracker.items()
        self.tracker.clear('a.jpg', 'faces')
        handler = Mock(side_effect=RuntimeError('still broken'))
        self.tracker.progress = {'processed': 0}
        self.tracker.retrying = True
        self.tracker.retry(items, handler)
        handler.assert_called_once_with('b.jpg', 'faces')
        self.assertFalse(self.tracker.retrying)
        self.assertEqual(self.tracker.items()[0]['error'], 'still broken')

    def test_conversion_moves_remaining_flags_to_destination(self):
        self.tracker.fail('a.heic', 'conversion', 'bad')
        self.tracker.fail('a.heic', 'metadata', 'bad')
        self.tracker.relocate('a.heic', 'a.jpg')
        self.assertEqual([(r['rel_path'], r['stage']) for r in self.tracker.items()], [('a.jpg', 'metadata')])

    def test_admin_only_and_no_duplicate_retry(self):
        from flask import Flask
        from flask_login import LoginManager, UserMixin
        app = Flask(__name__)
        app.secret_key = 'test'
        manager = LoginManager(app)
        class User(UserMixin):
            id = '1'
            is_admin = False
        user = User()
        manager.user_loader(lambda uid: user)
        self.tracker.register(app, Mock())
        client = app.test_client()
        self.assertEqual(client.get('/api/processing-failures').status_code, 401)
        with client.session_transaction() as session:
            session['_user_id'] = '1'
            session['_fresh'] = True
        self.assertEqual(client.get('/api/processing-failures').status_code, 403)
        user.is_admin = True
        self.tracker.fail('a.jpg', 'faces', 'error')
        with patch('processing_failures.threading.Thread') as thread:
            self.assertEqual(client.post('/api/processing-failures', json={}).status_code, 200)
            self.assertEqual(client.post('/api/processing-failures', json={}).status_code, 409)
            thread.assert_called_once()


if __name__ == '__main__':
    unittest.main()
