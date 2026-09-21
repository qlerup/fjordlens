import io
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image, ImageOps

from ai_service.face_pipeline import FacePipeline, VramAdmission, InvalidFaceImage, image_info


def encoded_image(fmt='JPEG', orientation=1):
    image = Image.fromarray(np.arange(18*12*3, dtype=np.uint8).reshape(18, 12, 3))
    exif = image.getexif()
    exif[274] = orientation
    output = io.BytesIO()
    image.save(output, format=fmt, exif=exif)
    return output.getvalue()


class FacePipelineTests(unittest.TestCase):
    def test_cpu_fallback_preserves_orientation_and_rgb(self):
        for orientation in range(1, 9):
            data = encoded_image(orientation=orientation)
            memory = SimpleNamespace(slot=Mock(side_effect=lambda *a: nullcontext()))
            model = SimpleNamespace(get=Mock(return_value=['face']))
            pipeline = FacePipeline(model, memory, use_cuda=False)
            self.assertEqual(pipeline.detect(data), ['face'])
            with Image.open(io.BytesIO(data)) as source:
                expected = np.array(ImageOps.exif_transpose(source).convert('RGB'))
            np.testing.assert_array_equal(model.get.call_args.args[0], expected)
            memory.slot.assert_called_once()

    def test_cpu_jobs_use_one_model_and_release_lock_after_failure(self):
        count = 0
        peak = 0
        def get(image):
            nonlocal count, peak
            count += 1
            peak = max(peak, count)
            time.sleep(0.005)
            count -= 1
            return []
        pipeline = FacePipeline(SimpleNamespace(get=get), SimpleNamespace(slot=lambda *a: nullcontext()))
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(pipeline.detect, [encoded_image()]*8)), [[]]*8)
        self.assertEqual(peak, 1)
        pipeline.runtime.get = Mock(side_effect=RuntimeError('failed'))
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            pipeline.detect(encoded_image())
        pipeline.runtime.get = lambda image: []
        self.assertEqual(pipeline.detect(encoded_image()), [])

    def test_invalid_image_rejected_before_model_call(self):
        model = Mock()
        pipeline = FacePipeline(model, SimpleNamespace(slot=lambda *a: nullcontext()))
        with self.assertRaises(InvalidFaceImage):
            pipeline.detect(b'not an image')
        model.get.assert_not_called()

    def test_vram_gate_releases_on_failure_and_rejects_oversize(self):
        cuda = SimpleNamespace(mem_get_info=lambda _: (1000, 1000),
                               memory_reserved=lambda _: 0, memory_allocated=lambda _: 0)
        gate = VramAdmission(SimpleNamespace(cuda=cuda), margin=100)
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            with gate.slot(600):
                self.assertEqual(gate.reserved, 600)
                with self.assertRaisesRegex(RuntimeError, 'GPU-budget'):
                    with gate.slot(400, timeout=0):
                        self.fail('Exceeded reserved VRAM')
                raise RuntimeError('failed')
        self.assertEqual(gate.reserved, 0)
        with self.assertRaisesRegex(RuntimeError, 'GPU-budget'):
            with gate.slot(901, timeout=0):
                self.fail('Exceeded GPU capacity')

    def test_vram_waiter_enters_after_job_finishes(self):
        cuda = SimpleNamespace(mem_get_info=lambda _: (1000, 1000),
                               memory_reserved=lambda _: 0, memory_allocated=lambda _: 0)
        gate = VramAdmission(SimpleNamespace(cuda=cuda), margin=100)
        started = threading.Event()
        entered = threading.Event()
        def work():
            started.set()
            with gate.slot(600, timeout=2):
                entered.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with gate.slot(600):
                pending = pool.submit(work)
                self.assertTrue(started.wait(1))
                self.assertFalse(entered.wait(0.03))
            pending.result(timeout=2)
        self.assertTrue(entered.is_set())
        self.assertEqual(gate.reserved, 0)


if __name__ == '__main__':
    unittest.main()
