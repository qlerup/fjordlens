import ast
import threading
import json
import time
import unittest
from functools import partial
from face_retry import retry_video_frame
from processing_failures import FaceIndexSkipped, ServiceUnavailable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def load_function(file, name, env):
    tree = ast.parse((ROOT / file).read_text(encoding='utf-8-sig'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile('from __future__ import annotations\n' + ast.unparse(module), file, 'exec'), env)
    return env[name]


class FaceFailureTests(unittest.TestCase):
    def video(self, responses, frames=b'jpeg'):
        env = dict(_video_face_sample_timestamps=lambda *a: (3, [0, 1]),
                   faces_video_index_enabled=lambda: True,
                   FACE_JOB_CONTEXT=threading.local(), FaceIndexSkipped=FaceIndexSkipped,
                   retry_video_frame=partial(retry_video_frame, delay=0),
                   _extract_video_frame_bytes=Mock(return_value=frames),
                   _ai_detect_faces_bytes=Mock(side_effect=responses),
                   _dedupe_faces_by_embedding=lambda x: x, log_event=Mock())
        return load_function('app.py', '_ai_detect_faces_video_path', env), env

    def test_failed_frame_is_skipped_after_retry_when_another_frame_succeeded(self):
        fn, env = self.video([[], None, None])
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])
        done = next(c for c in env['log_event'].call_args_list if c.args[0] == 'faces_video_detect_done')
        self.assertEqual(done.kwargs['decoded_frames'], 1)
        self.assertEqual(done.kwargs['skipped_frames'], 1)
        self.assertEqual(env['_ai_detect_faces_bytes'].call_count, 3)
        retries = [c for c in env['log_event'].call_args_list if c.args[0] == 'faces_video_frame_retry']
        failures = [c for c in env['log_event'].call_args_list if c.args[0] == 'faces_video_frame_fail']
        self.assertEqual(len(retries), 1)
        self.assertEqual(len(failures), 1)
        self.assertNotIn('error', retries[0].kwargs)

    def test_valid_empty_results_succeed(self):
        fn, _ = self.video([[], []])
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])

    def test_undecodable_video_is_not_empty_success(self):
        fn, _ = self.video([], frames=None)
        with self.assertRaisesRegex(RuntimeError, 'No video frames'):
            fn(Path('test.mp4'), 'test.mp4')

    def test_failed_first_frame_does_not_prevent_later_frame_results(self):
        fn, env = self.video([[{'embedding': [1.0]}]])
        env['_extract_video_frame_bytes'].side_effect = [None, None, b'jpeg']
        faces = fn(Path('test.mp4'), 'test.mp4')
        self.assertEqual(faces, [{'embedding': [1.0], 'frame_sec': 1}])
        self.assertEqual([c.args[2] for c in env['_extract_video_frame_bytes'].call_args_list], [0, 0, 1])

    def test_all_ai_frames_failing_does_not_complete_video(self):
        fn, env = self.video([None, None, None, None])
        with self.assertRaisesRegex(RuntimeError, 'No video frames'):
            fn(Path('test.mp4'), 'test.mp4')
        self.assertEqual(env['_ai_detect_faces_bytes'].call_count, 4)
        self.assertFalse(any(c.args[0] == 'faces_video_detect_done' for c in env['log_event'].call_args_list))

    def test_failed_extract_retries_same_timestamp_before_next_frame(self):
        fn, env = self.video([[], []])
        env['_extract_video_frame_bytes'].side_effect = [None, b'jpeg', b'jpeg']
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])
        self.assertEqual([c.args[2] for c in env['_extract_video_frame_bytes'].call_args_list], [0, 0, 1])
        done = next(c for c in env['log_event'].call_args_list if c.args[0] == 'faces_video_detect_done')
        self.assertEqual(done.kwargs['sampled_frames'], done.kwargs['decoded_frames'])
        self.assertFalse(any(c.args[0] == 'faces_video_frame_fail' for c in env['log_event'].call_args_list))

    def test_ai_timeout_reuses_decoded_frame(self):
        fn, env = self.video([ServiceUnavailable('timeout'), [], []])
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])
        self.assertEqual(env['_extract_video_frame_bytes'].call_count, 2)
        names = [c.kwargs['filename'] for c in env['_ai_detect_faces_bytes'].call_args_list]
        self.assertEqual(names, ['test_t0.00.jpg', 'test_t0.00.jpg', 'test_t1.00.jpg'])

    def test_zero_faces_is_success_without_retry(self):
        fn, env = self.video([[], []])
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])
        self.assertEqual(env['_ai_detect_faces_bytes'].call_count, 2)
        self.assertFalse(any(c.args[0] == 'faces_video_frame_retry' for c in env['log_event'].call_args_list))

    def test_stop_during_retry_does_not_advance_or_complete_video(self):
        fn, env = self.video([], frames=None)
        running = threading.Event()
        running.set()
        env['FACE_JOB_CONTEXT'].allowed = running.is_set
        env['log_event'].side_effect = lambda *a, **kw: running.clear()
        with self.assertRaises(FaceIndexSkipped):
            fn(Path('test.mp4'), 'test.mp4')
        self.assertEqual(env['_extract_video_frame_bytes'].call_count, 1)
        self.assertFalse(any(c.args[0] == 'faces_video_detect_done' for c in env['log_event'].call_args_list))

    def runtime(self, factory):
        lock = threading.RLock()
        class Pipeline:
            def __init__(self, runtime, *args, **kwargs):
                self.runtime = runtime
            def detect(self, data, progress):
                return self.runtime.get(data)
        env = dict(Image=SimpleNamespace(open=lambda x: SimpleNamespace(convert=lambda x: 'image')),
                   io=SimpleNamespace(BytesIO=lambda x: x), np=SimpleNamespace(array=lambda x: x),
                   _face_runtime_lock=lock, face_detection_available=True,
                   _face_pipeline=None, FacePipeline=Pipeline, SimpleNamespace=SimpleNamespace, InvalidFaceImage=ValueError,
                   _face_runtime_condition=threading.Condition(lock),
                   _face_runtime_idle=[], _face_runtime_instances=0, _face_runtime_active=0,
                   _face_runtime_peak_active=0, _face_runtime_releasing=False,
                   _face_runtime_ids={}, _face_jobs={}, time=time, json=json,
                   MEMORY=SimpleNamespace(enabled=False),
                   FACE_RUNTIME_MAX_WORKERS=16, FACE_DEVICE_CONFIGURED='cpu',
                   face_app=factory(), _serialize_face_result=lambda x: x,
                   _ensure_face_runtime_loaded=Mock(), _clear_cuda_cache=Mock(), print=Mock(),
                   _face_detection_runtime_providers=lambda: ['CPUExecutionProvider'],
                   _build_face_analysis=Mock(side_effect=lambda *a, **kw: (factory(), True, ['CPUExecutionProvider'])))
        for name in ('_face_status_snapshot', '_log_face_status', '_update_face_job',
                     '_acquire_face_runtime', '_return_face_runtime', '_release_face_runtime'):
            load_function('ai_service/app.py', name, env)
        fn = load_function('ai_service/app.py', '_detect_faces_bytes', env)
        return fn, env

    def test_selected_number_of_jobs_share_one_model(self):
        for workers in (1, 2, 4, 6, 8):
            with self.subTest(workers=workers):
                barrier = threading.Barrier(workers)
                def factory():
                    def get(image):
                        barrier.wait(timeout=5)
                        return []
                    return SimpleNamespace(get=get)
                fn, env = self.runtime(factory)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    self.assertEqual(list(pool.map(fn, [b'jpeg'] * workers * 2)), [[]] * workers * 2)
                self.assertEqual(env['_face_runtime_peak_active'], workers)
                self.assertEqual(env['_face_runtime_instances'], 1)
                self.assertEqual(env['_face_runtime_active'], 0)

    def test_inference_failure_returns_model_slot(self):
        fn, env = self.runtime(lambda: SimpleNamespace(get=Mock(side_effect=RuntimeError('inference failed'))))
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            fn(b'jpeg')
        self.assertEqual(env['_face_runtime_active'], 0)
        self.assertEqual(len(env['_face_runtime_idle']), 0)

    def test_batch_endpoint_runs_eight_model_calls_concurrently(self):
        barrier = threading.Barrier(8)
        def get(image):
            barrier.wait(timeout=5)
            return []
        _, env = self.runtime(lambda: SimpleNamespace(get=get))
        env.update(File=lambda *a: None, ThreadPoolExecutor=ThreadPoolExecutor, as_completed=as_completed)
        batch = load_function('ai_service/app.py', 'detect_faces_batch', env)
        uploads = [SimpleNamespace(filename=f'{i}.jpg', file=SimpleNamespace(read=lambda: b'jpeg')) for i in range(8)]
        result = batch(uploads)
        self.assertEqual(result['batch_size'], 8)
        self.assertTrue(all(item['ok'] for item in result['items']))
        self.assertEqual(env['_face_runtime_peak_active'], 8)

    def test_more_jobs_share_model_without_building_extra_instances(self):
        _, env = self.runtime(lambda: SimpleNamespace(get=lambda image: []))
        first = env['_acquire_face_runtime']()
        second = env['_acquire_face_runtime']()
        self.assertIs(first.pipeline, second.pipeline)
        env['_build_face_analysis'].assert_not_called()
        self.assertEqual(env['_face_runtime_instances'], 1)
        self.assertEqual(env['_face_runtime_active'], 2)
        env['_return_face_runtime'](first)
        env['_return_face_runtime'](second)
        self.assertEqual(env['_face_runtime_active'], 0)

    def test_status_tracks_filename_and_reuses_instance_without_stale_job(self):
        _, env = self.runtime(lambda: SimpleNamespace(get=lambda image: []))
        runtime = env['_acquire_face_runtime']('first.jpg')
        first = env['_face_status_snapshot']()[0]
        self.assertEqual(first['file'], 'first.jpg')
        self.assertEqual(first['stage'], 'queued')
        self.assertIsNone(first['percent'])
        env['_return_face_runtime'](runtime)
        self.assertEqual(env['_face_status_snapshot'](), [])
        again = env['_acquire_face_runtime']('second.jpg')
        second = env['_face_status_snapshot']()[0]
        self.assertEqual(second['instance'], first['instance'])
        self.assertEqual(second['file'], 'second.jpg')
        env['_return_face_runtime'](again)

    def test_logs_escape_filename_and_report_success_only_after_inference(self):
        fn, env = self.runtime(lambda: SimpleNamespace(get=lambda image: []))
        fn(b'jpeg', filename='photo\nforged.jpg')
        lines = [call.args[0] for call in env['print'].call_args_list if call.args[0].startswith('faces_instance instance=')]
        self.assertEqual(len(lines), 3)
        self.assertTrue(all('\n' not in line for line in lines))
        self.assertIn('stage=queued percent=unknown', lines[0])
        self.assertIn('stage=done percent=100', lines[-1])
        self.assertEqual(env['_face_status_snapshot'](), [])
        env['print'].assert_any_call('faces_instance active=0 stage=idle', flush=True)

    def test_release_waits_for_inference_then_clears_all_models(self):
        entered = threading.Event()
        finish = threading.Event()
        def get(image):
            entered.set()
            self.assertTrue(finish.wait(timeout=5))
            return []
        fn, env = self.runtime(lambda: SimpleNamespace(get=get))
        def clear():
            self.assertEqual(env['_face_runtime_active'], 0)
            self.assertEqual(env['_face_runtime_idle'], [])
        env['_clear_cuda_cache'].side_effect = clear
        with ThreadPoolExecutor(max_workers=2) as pool:
            detection = pool.submit(fn, b'jpeg')
            self.assertTrue(entered.wait(timeout=5))
            release = pool.submit(env['_release_face_runtime'])
            try:
                self.assertFalse(release.done())
                self.assertIsNotNone(env['face_app'])
            finally:
                finish.set()
            self.assertEqual(detection.result(timeout=5), [])
            self.assertTrue(release.result(timeout=5))
        self.assertEqual(env['_face_runtime_instances'], 0)
        self.assertIsNone(env['face_app'])
        # The next workflow can lazily load a fresh primary instance.
        def reload():
            env['face_app'] = SimpleNamespace(get=lambda image: [])
            env['face_detection_available'] = True
        env['_ensure_face_runtime_loaded'].side_effect = reload
        self.assertEqual(fn(b'jpeg'), [])
        self.assertEqual(env['_face_runtime_instances'], 1)

    def test_inference_error_is_service_failure(self):
        class HTTPException(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
        env = dict(HTTPException=HTTPException, File=lambda *a: None,
                   _detect_faces_bytes=Mock(side_effect=RuntimeError('bad allocation')))
        fn = load_function('ai_service/app.py', 'detect_faces', env)
        with self.assertRaises(HTTPException) as caught:
            fn(SimpleNamespace(filename='photo.jpg', file=SimpleNamespace(read=lambda: b'jpeg')))
        self.assertEqual(caught.exception.status_code, 503)
        env['_detect_faces_bytes'].side_effect = HTTPException(400, 'invalid image')
        with self.assertRaises(HTTPException) as caught:
            fn(SimpleNamespace(filename='bad.jpg', file=SimpleNamespace(read=lambda: b'bad')))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()

