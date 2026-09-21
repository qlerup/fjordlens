"""Opt-in real CUDA/InsightFace tests: FJORDLENS_GPU_TEST=1 python -m unittest ...

Downloads the standard buffalo_l model into InsightFace's cache on first run.
Uses scikit-image's bundled astronaut photo, never a user's photo library.
"""
import io
import os
import unittest
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageOps

from ai_service.face_pipeline import FacePipeline, orient_tensor


@unittest.skipUnless(os.environ.get('FJORDLENS_GPU_TEST') == '1', 'opt-in CUDA integration')
class FacePipelineGpuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import insightface
        from skimage.data import astronaut
        cls.torch = torch
        assert torch.cuda.is_available(), 'CUDA required for this opt-in test'
        cls.runtime = insightface.app.FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition'],
                                                  providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        cls.runtime.prepare(ctx_id=0, det_size=(640, 640))
        assert cls.runtime.det_model.session.get_providers()[0] == 'CUDAExecutionProvider'
        cls.pipeline = FacePipeline(cls.runtime, SimpleNamespace(slot=lambda *a: nullcontext()), use_cuda=True)
        cls.source = Image.fromarray(astronaut())

    def encoded(self, fmt='JPEG', orientation=1):
        image = self.source
        if orientation == 6:
            image = image.transpose(Image.Transpose.ROTATE_90)
        exif = image.getexif()
        exif[274] = orientation
        buf = io.BytesIO()
        image.save(buf, format=fmt, exif=exif)
        return buf.getvalue()

    def test_tensor_orientation_matches_pillow_all_eight(self):
        for orientation in range(1, 9):
            data = self.encoded(orientation=orientation)
            with Image.open(io.BytesIO(data)) as image:
                raw = np.array(image.convert('RGB'))
                expected = np.array(ImageOps.exif_transpose(image).convert('RGB'))
            tensor = self.torch.from_numpy(raw).permute(2, 0, 1).cuda()
            actual = orient_tensor(tensor, orientation).permute(1, 2, 0).cpu().numpy()
            np.testing.assert_array_equal(actual, expected)

    def test_gpu_results_match_existing_model_jpeg_png_and_orientation(self):
        for fmt, orientation in [('JPEG', 1), ('JPEG', 6), ('PNG', 1)]:
            with self.subTest(fmt=fmt, orientation=orientation):
                data = self.encoded(fmt, orientation)
                with Image.open(io.BytesIO(data)) as source:
                    rgb = np.array(ImageOps.exif_transpose(source).convert('RGB'))
                expected = self.runtime.get(rgb)
                actual = self.pipeline.detect(data)
                self.assertGreater(len(expected), 0)
                self.assertEqual(len(actual), len(expected))
                for old, new in zip(expected, actual):
                    np.testing.assert_allclose(new.bbox, old.bbox, atol=2)
                    a, b = old.embedding, new.embedding
                    similarity = float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b)))
                    self.assertGreater(similarity, 0.97)
                    print(f'gpu_parity format={fmt} orientation={orientation} cosine={similarity:.5f}', flush=True)
                self.assertEqual(self.pipeline.last_backend, 'cuda_jpeg' if fmt == 'JPEG' else 'cpu_decode_cuda_prepare')
                self.assertEqual(self.pipeline.admission.reserved, 0)

    def test_eight_jobs_share_runtime_and_complete(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.pipeline.detect, [self.encoded()]*8))
        self.assertTrue(all(len(faces) > 0 for faces in results))
        self.assertIs(self.pipeline.runtime, self.runtime)
        self.assertEqual(self.pipeline.admission.reserved, 0)

    def test_large_images_with_eight_queue_slots(self):
        buffer = io.BytesIO()
        self.source.resize((6000, 4000)).save(buffer, format='JPEG', quality=90)
        self.torch.cuda.reset_peak_memory_stats()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self.pipeline.detect, [buffer.getvalue()]*8))
        self.assertTrue(all(len(faces) > 0 for faces in results))
        self.assertEqual(self.pipeline.admission.reserved, 0)
        print(f'gpu_large_images jobs=8 pixels=24000000 torch_peak_mib={self.torch.cuda.max_memory_allocated()/1024**2:.1f}', flush=True)

    def test_cpu_only_model_needs_no_cuda_pipeline(self):
        import insightface
        runtime = insightface.app.FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition'],
                                               providers=['CPUExecutionProvider'])
        runtime.prepare(ctx_id=-1, det_size=(640, 640))
        pipeline = FacePipeline(runtime, SimpleNamespace(slot=lambda *a: nullcontext()), use_cuda=False)
        self.assertIsNone(pipeline.torch)
        self.assertGreater(len(pipeline.detect(self.encoded())), 0)


if __name__ == '__main__':
    unittest.main()
