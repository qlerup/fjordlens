"""One shared face model, compressed uploads and GPU-resident image preparation.

Only detector outputs/landmarks and embeddings cross back to the CPU. CPU-only
installations and non-JPEG inputs retain a guarded Pillow fallback.
"""
from contextlib import contextmanager
import io
import threading
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageOps

MIB = 1024**2


class InvalidFaceImage(ValueError):
    pass


def image_info(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            orientation = int(image.getexif().get(274, 1))
            if width < 1 or height < 1:
                raise ValueError('Invalid image dimensions')
            return width, height, image.format, orientation
    except Exception as exc:
        raise InvalidFaceImage(str(exc)) from exc


def decode_cpu(data, orient=True):
    try:
        with Image.open(io.BytesIO(data)) as source:
            if orient:
                source = ImageOps.exif_transpose(source)
            return np.array(source.convert('RGB'))
    except (OSError, ValueError) as exc:
        raise InvalidFaceImage(str(exc)) from exc


def orient_tensor(image, orientation):
    """Pillow exif_transpose semantics for a CHW tensor (without host copies)."""
    if orientation == 2:
        return image.flip(-1)
    if orientation == 3:
        return image.flip((-2, -1))
    if orientation == 4:
        return image.flip(-2)
    if orientation == 5:
        return image.transpose(-2, -1)
    if orientation == 6:
        return image.rot90(-1, (-2, -1))
    if orientation == 7:
        return image.transpose(-2, -1).flip((-2, -1))
    if orientation == 8:
        return image.rot90(1, (-2, -1))
    return image


class VramAdmission:
    """Account for in-flight peak allocations before allowing another decode."""
    def __init__(self, torch, margin=512*MIB):
        self.torch = torch
        self.margin = margin
        self.condition = threading.Condition()
        self.reserved = 0
        self.baseline_free = 0

    @contextmanager
    def slot(self, amount, timeout=40):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                free, _ = self.torch.cuda.mem_get_info(0)
                # Idle PyTorch cache can be reused without consuming more VRAM.
                reusable = max(0, self.torch.cuda.memory_reserved(0) - self.torch.cuda.memory_allocated(0))
                free += reusable
                if self.reserved == 0:
                    self.baseline_free = free
                if (amount + self.margin <= free and
                        self.reserved + amount + self.margin <= self.baseline_free):
                    self.reserved += amount
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('GPU-budget: afventer ledig GPU-hukommelse')
                self.condition.wait(timeout=0.25)
        try:
            yield
        finally:
            with self.condition:
                self.reserved -= amount
                self.condition.notify_all()


class FacePipeline:
    def __init__(self, runtime, memory, use_cuda=False):
        self.runtime = runtime
        self.memory = memory
        self.inference_lock = threading.Lock()
        self.cpu_lock = threading.Lock()
        self.torch = None
        self.admission = None
        self.last_backend = 'cpu'
        self.fallback_reason = None
        if use_cuda:
            import torch
            from torchvision.io import decode_jpeg, ImageReadMode
            self.torch = torch
            self.decode_jpeg = decode_jpeg
            self.rgb_mode = ImageReadMode.RGB
            self.admission = VramAdmission(torch)

    def detect(self, data, progress=lambda stage: None):
        width, height, fmt, orientation = image_info(data)
        if self.torch is None:
            # CPU fallback is serialized before allocation, sharing one model.
            with self.cpu_lock, self.memory.slot(width*height*16 + 64*MIB):
                progress('decode_cpu')
                image = decode_cpu(data)
                progress('inference')
                with self.inference_lock:
                    return self.runtime.get(image)
        # RGB uint8 plus decode/rotation/resize/alignment float working buffers.
        # No fixed assumption that eight arbitrary images fit in 6 GiB.
        estimate = width*height*24 + 192*MIB
        progress('waiting_gpu')
        with self.admission.slot(estimate):
            with self.memory.slot(64*MIB + len(data)*2):
                with self.torch.inference_mode():
                    return self._gpu(data, fmt, orientation, width*height, progress)

    def _gpu(self, data, fmt, orientation, pixels, progress):
        torch = self.torch
        image = None
        try:
            if fmt == 'JPEG':
                progress('decode_gpu')
                try:
                    encoded = torch.from_numpy(np.frombuffer(data, dtype=np.uint8).copy())
                    image = self.decode_jpeg(encoded, mode=self.rgb_mode, device='cuda:0')
                    self.last_backend = 'cuda_jpeg'
                    self.fallback_reason = None
                except torch.cuda.OutOfMemoryError:
                    raise
                except RuntimeError as exc:
                    # CMYK/other unsupported JPEGs and wheels without nvJPEG.
                    self.fallback_reason = str(exc)[:240]
                    print(f'faces_decode_fallback reason={self.fallback_reason!r}', flush=True)
            if image is None:
                progress('decode_cpu')
                with self.cpu_lock, self.memory.slot(pixels*16 + 64*MIB):
                    array = decode_cpu(data, orient=False)
                    image = torch.from_numpy(array).permute(2, 0, 1).to('cuda:0')
                    del array
                self.last_backend = 'cpu_decode_cuda_prepare'
            image = orient_tensor(image, orientation)
            progress('prepare_gpu')
            # One shared session runs inference at a time. Other admitted jobs
            # can decode while it runs; no per-job copies of model weights.
            with self.inference_lock:
                progress('inference')
                return self._analyse(image)
        finally:
            # Finish all reads before releasing the admission reservation.
            torch.cuda.synchronize(0)
            del image

    def _run(self, model, tensor):
        tensor = tensor.contiguous()
        # Torch and ORT own different CUDA streams; explicit synchronization
        # prevents ORT from reading an unfinished tensor.
        self.torch.cuda.current_stream(0).synchronize()
        binding = model.session.io_binding()
        binding.bind_input(model.input_name, 'cuda', 0, np.float32,
                           tuple(tensor.shape), tensor.data_ptr())
        for name in model.output_names:
            binding.bind_output(name, 'cpu')
        model.session.run_with_iobinding(binding)
        return binding.copy_outputs_to_cpu()

    def _detect(self, image):
        """SCRFD/RetinaFace output decoding; same thresholds/NMS as InsightFace."""
        torch = self.torch
        model = self.runtime.det_model
        height, width = image.shape[-2:]
        target_w, target_h = model.input_size
        if height / width > target_h / target_w:
            new_h, new_w = target_h, max(1, int(target_h * width / height))
        else:
            new_w, new_h = target_w, max(1, int(target_w * height / width))
        scale = new_h / height
        resized = torch.nn.functional.interpolate(image[None].float(), size=(new_h, new_w),
                                                   mode='bilinear', align_corners=False)
        # Retain historical RGB-input + swapRB semantics for existing vectors.
        blob = torch.zeros((1, 3, target_h, target_w), device=image.device)
        blob[:, :, :new_h, :new_w] = resized.round().clamp_(0, 255)
        blob = (blob[:, [2, 1, 0]] - model.input_mean) / model.input_std
        outputs = self._run(model, blob)
        scores_all, boxes_all, points_all = [], [], []
        for level, stride in enumerate(model._feat_stride_fpn):
            scores = outputs[level].reshape(-1)
            distances = outputs[level + model.fmc].reshape(-1, 4) * stride
            landmarks = outputs[level + 2*model.fmc].reshape(-1, 5, 2) * stride
            y, x = np.mgrid[:target_h//stride, :target_w//stride]
            centers = np.stack((x, y), axis=-1).reshape(-1, 2).astype(np.float32) * stride
            centers = np.repeat(centers, model._num_anchors, axis=0)
            selected = np.flatnonzero(scores >= model.det_thresh)
            center = centers[selected]
            delta = distances[selected]
            boxes_all.append(np.concatenate((center-delta[:, :2], center+delta[:, 2:]), axis=1)/scale)
            points_all.append((landmarks[selected] + center[:, None])/scale)
            scores_all.append(scores[selected])
        scores = np.concatenate(scores_all)
        boxes = np.concatenate(boxes_all)
        points = np.concatenate(points_all)
        order = scores.argsort()[::-1]
        detections = np.column_stack((boxes, scores)).astype(np.float32)[order]
        keep = model.nms(detections)
        return detections[keep], points[order][keep]

    def _align(self, image, landmarks, size):
        from insightface.utils.face_align import estimate_norm
        import cv2
        # Estimate the affine transform from just five points on the CPU.
        inverse = cv2.invertAffineTransform(estimate_norm(landmarks, image_size=size))
        return self._sample_affine(image, inverse, size)

    def _sample_affine(self, image, inverse, size):
        torch = self.torch
        height, width = image.shape[-2:]
        corners = np.array([[0, 0, 1], [size-1, 0, 1], [0, size-1, 1], [size-1, size-1, 1]]) @ inverse.T
        x0, y0 = np.maximum(0, np.floor(corners.min(axis=0)-1)).astype(int)
        x1, y1 = np.minimum([width, height], np.ceil(corners.max(axis=0)+2)).astype(int)
        if x1 <= x0 or y1 <= y0:
            return torch.zeros((1, 3, size, size), device=image.device)
        # Convert only the face region to float, not the entire original image.
        region = image[:, y0:y1, x0:x1][None].float()
        yy, xx = torch.meshgrid(torch.arange(size, device=image.device),
                                torch.arange(size, device=image.device), indexing='ij')
        transform = torch.as_tensor(inverse, device=image.device, dtype=torch.float32)
        sx = transform[0, 0]*xx + transform[0, 1]*yy + transform[0, 2] - x0
        sy = transform[1, 0]*xx + transform[1, 1]*yy + transform[1, 2] - y0
        grid = torch.stack((2*(sx+0.5)/(x1-x0)-1, 2*(sy+0.5)/(y1-y0)-1), dim=-1)[None]
        crop = torch.nn.functional.grid_sample(region, grid, mode='bilinear',
                                               padding_mode='zeros', align_corners=False)
        return crop.round().clamp_(0, 255)

    def _analyse(self, image):
        boxes, landmarks = self._detect(image)
        recognition = self.runtime.models['recognition']
        results = []
        for box, points in zip(boxes, landmarks):
            aligned = self._align(image, points, recognition.input_size[0])
            blob = (aligned[:, [2, 1, 0]] - recognition.input_mean) / recognition.input_std
            embedding = self._run(recognition, blob)[0].reshape(-1)
            results.append(SimpleNamespace(bbox=box[:4], kps=points, embedding=embedding,
                                           det_score=float(box[4])))
        return results
