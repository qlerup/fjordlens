import ast
from collections import deque
import json
from pathlib import Path
import tempfile
import threading
import unittest
from flask import Flask, jsonify, request
from types import SimpleNamespace

from log_retries import resolved_log_ids, unresolved_error_logs


def error(identifier, rel='a.jpg', stage='faces'):
    return dict(id=identifier, event='error', rel_path=rel, stage=stage, error='failed')


def success(identifier, rel='a.jpg', stage='faces'):
    return dict(id=identifier, event='processing_stage_done', rel_path=rel, stage=stage)


class LogResolutionTests(unittest.TestCase):
    def test_success_removes_only_older_errors_for_exact_file_and_stage(self):
        logs = [error(1), error(2, stage='weather'), error(3, rel='b.jpg'),
                error(4), success(5), error(6)]
        self.assertEqual(resolved_log_ids(logs), [1, 4])
        self.assertEqual([item['id'] for item in unresolved_error_logs(logs)], [2, 3, 6])

    def test_success_before_error_cannot_resolve_it(self):
        self.assertEqual(resolved_log_ids([success(1), error(2)]), [])

    def test_retry_failure_tracks_failed_children_not_successful_parent(self):
        summary = dict(id=2, event='log_retry_fail', rel_path='a.jpg', stage='metadata',
                       failed_stages=['faces', 'descriptions'], error='failed')
        logs = [summary, success(3, stage='metadata'), success(4)]
        self.assertEqual(resolved_log_ids(logs), [])
        logs.append(success(5, stage='descriptions'))
        self.assertEqual(resolved_log_ids(logs), [2])

    def test_existing_error_formats_match_success_from_other_retry_buttons(self):
        logs = [dict(id=1, event='error', rel_path='a.jpg', error='postprocess_faces_queue: locked'),
                dict(id=2, event='ai_embed_fail', rel_path='a.jpg'),
                dict(id=3, event='error', rel_path='a.jpg', error='weather_index: timeout'),
                success(4), success(5, stage='embeddings'),
                dict(id=6, event='weather_saved', rel_path='a.jpg')]
        self.assertEqual(resolved_log_ids(logs), [1, 2, 3])

    def test_clear_keeps_unknown_errors_but_drops_success_and_resolved_errors(self):
        logs = [error(1), success(2), dict(id=3, event='error', error='unknown failure'),
                dict(id=4, event='upload_done', errors=0)]
        self.assertEqual([item['id'] for item in unresolved_error_logs(logs)], [3])

    def persistence_fixture(self, directory, logs):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {'_clear_persistent_logs', '_load_persistent_logs'}]
        path = Path(directory) / 'events.jsonl'
        env = dict(LOG_LOCK=threading.RLock(), LOG_BUFFER=deque(logs), LOG_SEQ=10,
                   _event_log_path=lambda: path, json=json, unresolved_error_logs=unresolved_error_logs)
        exec(compile('from __future__ import annotations\n' + ast.unparse(ast.Module(body=functions, type_ignores=[])),
                     str(source), 'exec'), env)
        return env, path

    def test_clear_persists_only_unresolved_errors_and_preserves_ids_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            env, path = self.persistence_fixture(directory, [error(1), success(2), error(3, rel='b.jpg')])
            kept = env['_clear_persistent_logs'](preserve_errors=True)
            self.assertEqual([item['id'] for item in kept], [3])
            env['_load_persistent_logs']()
            self.assertEqual(env['LOG_SEQ'], 10)
            self.assertEqual([item['id'] for item in unresolved_error_logs(list(env['LOG_BUFFER']))], [3])
            self.assertNotIn('processing_stage_done', path.read_text())

    def test_failed_persistent_write_does_not_discard_memory_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            env, path = self.persistence_fixture(directory, [error(1)])
            path.with_suffix('.tmp').mkdir()
            with self.assertRaises(OSError):
                env['_clear_persistent_logs'](preserve_errors=True)
            self.assertEqual(list(env['LOG_BUFFER']), [error(1)])

    def test_factory_reset_can_still_clear_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            env, path = self.persistence_fixture(directory, [error(1)])
            env['_clear_persistent_logs']()
            self.assertEqual(list(env['LOG_BUFFER']), [])
            self.assertEqual(env['LOG_SEQ'], 0)

    def test_log_api_advances_over_hidden_pages_and_reports_resolved_old_rows(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'api_logs')
        node.decorator_list = []
        logs = [error(1)] + [success(i) for i in range(2, 201)] + [error(201, rel='b.jpg')]
        env = dict(_forbid_user_role_for_maintenance=lambda: None, request=request, jsonify=jsonify,
                   LOG_LOCK=threading.RLock(), LOG_BUFFER=logs, resolved_log_ids=resolved_log_ids,
                   log_retries=SimpleNamespace(describe=lambda item: item))
        exec(compile(ast.unparse(node), str(source), 'exec'), env)
        app = Flask(__name__)
        with app.test_request_context('/api/logs?after=0'):
            result = env['api_logs']().get_json()
        self.assertEqual(result['items'], [])
        self.assertEqual(result['next'], 200)
        self.assertEqual(result['resolved_ids'], [1])
        with app.test_request_context('/api/logs?after=200'):
            result = env['api_logs']().get_json()
        self.assertEqual([item['id'] for item in result['items']], [201])
        self.assertEqual(result['resolved_ids'], [1])


if __name__ == '__main__':
    unittest.main()
