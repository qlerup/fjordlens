import threading
import ast
from pathlib import Path
from contextlib import closing
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from flask_login import LoginManager, UserMixin
from log_retries import LogRetries, retry_target, missing_stages, StageRetryError, resolved_log_ids


class User(UserMixin):
    id = 'admin'
    is_admin = True


class LogRetryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test'
        self.user = User()
        login = LoginManager(self.app)
        login.user_loader(lambda _: self.user)
        self.item = dict(id=7, event='error', rel_path='uploads/a.jpg',
                         error='postprocess_faces_queue: database is locked')
        self.tracker = SimpleNamespace(lock=threading.RLock(), retrying=False,
                                       items=Mock(return_value=[]))
        self.handler, self.log, self.busy = Mock(), Mock(), Mock(return_value=False)
        self.retries = LogRetries(self.tracker, lambda i: self.item if i == 7 else None,
                                  self.handler, self.log, self.busy)
        self.retries.register(self.app)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = 'admin'

    def test_permissions_and_unknown_log(self):
        self.assertEqual(self.app.test_client().post('/api/logs/7/retry').status_code, 401)
        self.user.is_admin = False
        self.assertEqual(self.client.post('/api/logs/7/retry').status_code, 403)
        self.user.is_admin = True
        self.assertEqual(self.client.post('/api/logs/99/retry').status_code, 404)

    @patch('log_retries.threading.Thread')
    def test_server_selects_original_file_and_stage_and_prevents_duplicate(self, thread):
        response = self.client.post('/api/logs/7/retry', json={'rel_path': 'other', 'stage': 'conversion'})
        self.assertEqual(response.json['status'], 'running')
        self.assertEqual(thread.call_args.kwargs['args'], (7, 'uploads/a.jpg', 'faces'))
        self.client.post('/api/logs/7/retry')
        thread.assert_called_once()
        self.assertEqual(self.client.get('/api/logs/7/retry').json['status'], 'running')

    @patch('log_retries.threading.Thread')
    def test_busy_pipeline_does_not_start_work(self, thread):
        self.busy.return_value = True
        self.assertEqual(self.client.post('/api/logs/7/retry').status_code, 409)
        thread.assert_not_called()
        self.assertFalse(self.tracker.retrying)

    def test_success_runs_only_selected_stage_and_exposes_result(self):
        self.tracker.retrying = True
        self.retries.run(7, 'uploads/a.jpg', 'faces')
        self.handler.assert_called_once_with('uploads/a.jpg', 'faces')
        self.assertEqual(self.retries.describe(self.item)['retry']['status'], 'succeeded')
        self.assertFalse(self.tracker.retrying)
        self.assertEqual(self.log.call_args.args[0], 'log_retry_done')

    def test_failure_remains_retryable_and_releases_worker(self):
        self.handler.side_effect = RuntimeError('still locked')
        self.retries.run(7, 'uploads/a.jpg', 'faces')
        self.assertEqual(self.retries.states[7], {'status': 'failed', 'error': 'still locked'})
        self.assertFalse(self.tracker.retrying)
        self.assertEqual(self.log.call_args.args[0], 'log_retry_fail')
        with patch('log_retries.threading.Thread') as thread:
            self.assertEqual(self.client.post('/api/logs/7/retry').json['status'], 'running')
            thread.assert_called_once()

    def test_return_without_exception_is_not_success_when_failure_remains(self):
        self.tracker.items.return_value = [dict(rel_path='uploads/a.jpg', stage='faces', error='no result')]
        self.retries.run(7, 'uploads/a.jpg', 'faces')
        self.assertEqual(self.retries.states[7]['status'], 'failed')

    def test_known_stages_and_unrelated_errors(self):
        for prefix, stage in [('weather_index', 'weather'), ('postprocess_index', 'metadata'),
                              ('postprocess_thumb', 'thumbnails'), ('postprocess_ai', 'embeddings'),
                              ('postprocess_ai_desc', 'descriptions')]:
            item = dict(self.item, error=prefix + ': unavailable')
            self.assertEqual(retry_target(item), ('uploads/a.jpg', stage))
        self.assertIsNone(retry_target(dict(self.item, error='login failed')))
        self.assertIsNone(retry_target(dict(self.item, event='weather_index_retry')))

    def test_completed_and_disabled_steps_are_preserved(self):
        row = dict(faces_indexed_at='2026-09-23', people_count=0, embedding_json='[1]',
                   ai_desc_caption='A photo', ai_desc_tags='["photo"]')
        self.assertEqual(missing_stages(row, thumbnail_exists=True, faces=True,
                                       embeddings=True, descriptions=True), [])
        self.assertEqual(missing_stages({}, thumbnail_exists=True, faces=False,
                                       embeddings=False, descriptions=False), [])

    def resume_function(self, handler):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_retry_logged_failure')
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = {}
        # A metadata row exists, but none of its later stages has finished.
        conn.execute.return_value.fetchone.return_value = {'id': 1}
        env = dict(_retry_processing_failure=handler, processing_failures=self.tracker,
                   _upload_extension_needs_conversion=lambda ext: ext.lower() == '.heic',
                   StageRetryError=StageRetryError,
                   log_event=self.log, closing=closing, get_conn=lambda: conn,
                   missing_stages=missing_stages, THUMB_DIR=Path('.'), Path=Path,
                   faces_auto_index_enabled=lambda: True, VIDEO_EXTS={'.mp4'},
                   faces_video_index_enabled=lambda: True, ai_auto_ingest_enabled=lambda: True,
                   _is_ai_embedding_supported_rel=lambda rel: True,
                   ai_desc_auto_ingest_enabled=lambda: True)
        exec(compile(ast.unparse(node), str(source), 'exec'), env)
        return env['_retry_logged_failure']

    def test_metadata_retry_resumes_all_missing_steps_for_same_file(self):
        handler = Mock()
        self.resume_function(handler)('uploads/a.jpg', 'metadata')
        self.assertEqual([c.args for c in handler.call_args_list],
                         [('uploads/a.jpg', stage) for stage in
                          ['metadata', 'thumbnails', 'faces', 'embeddings', 'descriptions']])

    def test_heic_retry_runs_conversion_prerequisite_without_followup_decoders(self):
        handler = Mock(side_effect=StageRetryError('Invalid HEIC', ['conversion']))
        with self.assertRaisesRegex(StageRetryError, 'Invalid HEIC'):
            self.resume_function(handler)('uploads/a.HEIC', 'faces')
        handler.assert_called_once_with('uploads/a.HEIC', 'conversion')

    def test_failure_in_faces_does_not_stop_other_missing_steps(self):
        def work(rel, stage):
            if stage == 'faces':
                raise RuntimeError('locked')
        handler = Mock(side_effect=work)
        with self.assertRaisesRegex(RuntimeError, 'locked'):
            self.resume_function(handler)('uploads/a.jpg', 'faces')
        self.assertEqual([c.args[1] for c in handler.call_args_list],
                         ['thumbnails', 'faces', 'embeddings', 'descriptions'])

    def test_face_retry_repairs_existing_metadata_failure_first(self):
        failures = [dict(rel_path='uploads/a.jpg', stage='metadata', error='failed')]
        self.tracker.items.side_effect = lambda: list(failures)
        def work(rel, stage):
            failures[:] = [item for item in failures if item['stage'] != stage]
        handler = Mock(side_effect=work)
        self.resume_function(handler)('uploads/a.jpg', 'faces')
        self.assertEqual([call.args[1] for call in handler.call_args_list],
                         ['metadata', 'thumbnails', 'faces', 'embeddings', 'descriptions'])

    def test_failed_metadata_retry_does_not_run_dependent_steps(self):
        handler = Mock(side_effect=RuntimeError('metadata unavailable'))
        with self.assertRaisesRegex(RuntimeError, 'metadata unavailable'):
            self.resume_function(handler)('uploads/a.jpg', 'metadata')
        handler.assert_called_once_with('uploads/a.jpg', 'metadata')


if __name__ == '__main__':
    unittest.main()
