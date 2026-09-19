import ast
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
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
                   _extract_video_frame_bytes=Mock(return_value=frames),
                   _ai_detect_faces_bytes=Mock(side_effect=responses),
                   _dedupe_faces_by_embedding=lambda x: x, log_event=Mock())
        return load_function('app.py', '_ai_detect_faces_video_path', env), env

    def test_failed_frame_is_not_empty_success(self):
        fn, env = self.video([[], None])
        with self.assertRaisesRegex(RuntimeError, 'frame at 1.00s'):
            fn(Path('test.mp4'), 'test.mp4')
        self.assertNotIn('faces_video_detect_done', [c.args[0] for c in env['log_event'].call_args_list])

    def test_valid_empty_results_succeed(self):
        fn, _ = self.video([[], []])
        self.assertEqual(fn(Path('test.mp4'), 'test.mp4'), [])

    def test_undecodable_video_is_not_empty_success(self):
        fn, _ = self.video([], frames=None)
        with self.assertRaisesRegex(RuntimeError, 'No video frames'):
            fn(Path('test.mp4'), 'test.mp4')

    def test_model_inference_holds_lifecycle_lock(self):
        lock = threading.RLock()
        def get(image):
            self.assertTrue(lock._is_owned())
            return []
        env = dict(Image=SimpleNamespace(open=lambda x: SimpleNamespace(convert=lambda x: 'image')),
                   io=SimpleNamespace(BytesIO=lambda x: x), np=SimpleNamespace(array=lambda x: x),
                   _face_runtime_lock=lock, face_detection_available=True,
                   face_app=SimpleNamespace(get=get), _serialize_face_result=lambda x: x)
        fn = load_function('ai_service/app.py', '_detect_faces_bytes', env)
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(fn, [b'jpeg'] * 16)), [[]] * 16)

    def test_inference_error_is_service_failure(self):
        class HTTPException(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
        env = dict(HTTPException=HTTPException, File=lambda *a: None,
                   _detect_faces_bytes=Mock(side_effect=RuntimeError('bad allocation')))
        fn = load_function('ai_service/app.py', 'detect_faces', env)
        with self.assertRaises(HTTPException) as caught:
            fn(SimpleNamespace(file=SimpleNamespace(read=lambda: b'jpeg')))
        self.assertEqual(caught.exception.status_code, 503)
        env['_detect_faces_bytes'].side_effect = HTTPException(400, 'invalid image')
        with self.assertRaises(HTTPException) as caught:
            fn(SimpleNamespace(file=SimpleNamespace(read=lambda: b'bad')))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()

