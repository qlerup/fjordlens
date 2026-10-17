import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from upload_notifications import UploadNotifications, summary_event


class UploadNotificationsTests(unittest.TestCase):
    def test_summary_counts_files_and_preserves_failure_categories(self):
        event = summary_event('Owner', ['a.jpg', 'a.jpg', 'b.MOV'],
                              {'indexed': 1, 'face_count': 5, 'faces_done': 1, 'faces_enabled': True,
                               'faces_errors': 1, 'thumb_errors': 2}, {'.mov'}, failed=True)
        self.assertEqual(event['status'], 'failed')
        self.assertEqual(event['stats']['files'], 2)
        self.assertEqual(event['stats']['images'], 1)
        self.assertEqual(event['stats']['videos'], 1)
        self.assertEqual(event['stats']['face_count'], 5)
        self.assertEqual(event['stats']['thumb_errors'], 2)

    def test_retry_survives_restart_and_preserves_event_id(self):
        with tempfile.TemporaryDirectory() as directory:
            api = Mock(return_value={'ok': False})
            sender = UploadNotifications(directory, api, lambda: True, autostart=False)
            event = summary_event('Owner', ['a.jpg'], {}, set())
            sender.enqueue(event)
            sender.flush()
            restarted = UploadNotifications(directory, api, lambda: True, autostart=False)
            api.return_value = {'ok': True}
            restarted.flush()
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args_list[0].args[1]['event_id'], api.call_args_list[1].args[1]['event_id'])
            restarted.flush()
            self.assertEqual(api.call_count, 2)

    def test_unmanaged_app_does_not_create_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            sender = UploadNotifications(directory, Mock(), lambda: False, autostart=False)
            sender.enqueue(summary_event('', ['a.jpg'], {}, set()))
            self.assertFalse(sender.path.exists())


class WorkerSummaryTests(unittest.TestCase):
    def test_normal_worker_notifies_once_after_all_batches(self):
        import inspect
        from contextlib import ExitStack
        from unittest.mock import patch
        import app
        worker = inspect.unwrap(app._upload_postprocess_worker)
        for failed in (False, True):
            with ExitStack() as stack:
                for name, result in [('upload_workflow_mode', 'gentle'), ('faces_auto_index_enabled', False),
                                     ('ai_auto_ingest_enabled', False), ('ai_desc_auto_ingest_enabled', False),
                                     ('_get_upload_postprocess_state', {}), ('_set_upload_postprocess_state', None),
                                     ('log_event', None)]:
                    stack.enter_context(patch.object(app, name, return_value=result))
                stack.enter_context(patch.object(app, 'UPLOAD_POSTPROCESS_STOP_EVENT', __import__('threading').Event()))
                stack.enter_context(patch.object(app, '_pop_uploaded_rels', side_effect=[['b.mov'], []]))
                pipeline = stack.enter_context(patch.object(app, '_run_postprocess_serialized'))
                if failed:
                    pipeline.side_effect = RuntimeError('GPU failure')
                else:
                    pipeline.return_value = {'received': 1, 'indexed': 1, 'face_count': 3, 'thumb_errors': 1}
                notify = stack.enter_context(patch.object(app, '_notify_upload_summary'))
                worker('Owner', ['a.jpg'])
                notify.assert_called_once()
                args, kwargs = notify.call_args
                self.assertEqual(kwargs['failed'], failed)
                self.assertEqual(args[1], ['a.jpg'] if failed else ['a.jpg', 'b.mov'])
                if not failed:
                    self.assertEqual(args[2]['face_count'], 6)
                    self.assertEqual(args[2]['thumb_errors'], 2)
                    self.assertEqual(pipeline.call_count, 2)
