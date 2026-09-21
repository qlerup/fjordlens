import io
try:
    from memory_budget import MEMORY, MIB
except ModuleNotFoundError:
    from ai_service.memory_budget import MEMORY, MIB
import inspect
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import uvicorn
from PIL import Image, ImageOps, ImageEnhance

# Import onnxruntime right after torch so CUDA-dependent libs provided by
# torch wheels are loaded before InsightFace initializes ONNX sessions.
try:
    import onnxruntime as ort
except Exception:
    ort = None

import insightface
import numpy as np


def _patch_torch_pytree_for_transformers() -> None:
    """Compatibility shim for transformers expecting torch pytree newer API.

    Some torch builds expose only _register_pytree_node while newer
    transformers calls register_pytree_node with extra kwargs. We provide a
    best-effort adapter before importing modules that may pull transformers.
    """

    try:
        pytree_mod = getattr(torch.utils, "_pytree", None)
        if pytree_mod is None:
            return
        if hasattr(pytree_mod, "register_pytree_node"):
            return
        legacy_register = getattr(pytree_mod, "_register_pytree_node", None)
        if legacy_register is None:
            return

        try:
            legacy_params = set(inspect.signature(legacy_register).parameters.keys())
        except Exception:
            legacy_params = set()

        def _compat_register_pytree_node(node_type, flatten_fn, unflatten_fn, **kwargs):
            filtered_kwargs = {k: v for k, v in kwargs.items() if (not legacy_params) or (k in legacy_params)}
            try:
                return legacy_register(node_type, flatten_fn, unflatten_fn, **filtered_kwargs)
            except TypeError:
                return legacy_register(node_type, flatten_fn, unflatten_fn)

        setattr(pytree_mod, "register_pytree_node", _compat_register_pytree_node)
    except Exception:
        # Never block service startup on compatibility patching.
        pass


_patch_torch_pytree_for_transformers()

import open_clip

AutoModelForVision2Seq = None
AutoProcessor = None
BitsAndBytesConfig = None
Qwen2VLForConditionalGeneration = None
Qwen2_5_VLForConditionalGeneration = None
bnb = None
_BITSANDBYTES_AVAILABLE = False
_QWEN_DEPS_IMPORT_ATTEMPTED = False
_QWEN_DEPS_IMPORT_ERROR = None


def _ensure_qwen_deps_loaded() -> bool:
    global AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig, Qwen2VLForConditionalGeneration, Qwen2_5_VLForConditionalGeneration
    global bnb, _BITSANDBYTES_AVAILABLE, _QWEN_DEPS_IMPORT_ATTEMPTED, _QWEN_DEPS_IMPORT_ERROR
    if _QWEN_DEPS_IMPORT_ATTEMPTED:
        return AutoProcessor is not None and AutoModelForVision2Seq is not None

    _QWEN_DEPS_IMPORT_ATTEMPTED = True
    try:
        from transformers import AutoModelForVision2Seq as _AutoModelForVision2Seq
        from transformers import AutoProcessor as _AutoProcessor
        from transformers import BitsAndBytesConfig as _BitsAndBytesConfig

        AutoModelForVision2Seq = _AutoModelForVision2Seq
        AutoProcessor = _AutoProcessor
        BitsAndBytesConfig = _BitsAndBytesConfig
        try:
            from transformers import Qwen2VLForConditionalGeneration as _Qwen2VLForConditionalGeneration  # type: ignore

            Qwen2VLForConditionalGeneration = _Qwen2VLForConditionalGeneration
        except Exception:
            Qwen2VLForConditionalGeneration = None
        try:
            from transformers import Qwen2_5_VLForConditionalGeneration as _Qwen2_5_VLForConditionalGeneration  # type: ignore

            Qwen2_5_VLForConditionalGeneration = _Qwen2_5_VLForConditionalGeneration
        except Exception:
            Qwen2_5_VLForConditionalGeneration = None
    except Exception as exc:
        _QWEN_DEPS_IMPORT_ERROR = str(exc)[:800]
        return False

    try:
        import bitsandbytes as _bnb  # type: ignore

        bnb = _bnb
        _BITSANDBYTES_AVAILABLE = True
    except Exception:
        bnb = None
        _BITSANDBYTES_AVAILABLE = False

    _QWEN_DEPS_IMPORT_ERROR = None
    return True

try:
    # Enable HEIC/HEIF decoding when the wheel is available
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:
    pass

MODEL_NAME = os.environ.get("CLIP_MODEL", "ViT-B-32")
MODEL_PRETRAINED = os.environ.get("CLIP_PRETRAINED", "openai")
QWEN_VL_MODEL = str(os.environ.get("QWEN_VL_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct") or "Qwen/Qwen2.5-VL-3B-Instruct").strip()
QWEN_VL_ENABLE_4BIT = str(os.environ.get("QWEN_VL_4BIT", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
QWEN_VL_4BIT_QUANT_TYPE = str(os.environ.get("QWEN_VL_4BIT_QUANT_TYPE", "fp4") or "fp4").strip().lower()
if QWEN_VL_4BIT_QUANT_TYPE not in {"fp4", "nf4"}:
    QWEN_VL_4BIT_QUANT_TYPE = "fp4"
QWEN_VL_RESERVE_GPU = str(os.environ.get("QWEN_VL_RESERVE_GPU", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
QWEN_VL_CPU_FALLBACK = str(os.environ.get("QWEN_VL_CPU_FALLBACK", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
QWEN_VL_LOW_CPU_MEM_USAGE = str(os.environ.get("QWEN_VL_LOW_CPU_MEM_USAGE", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
QWEN_VL_PROMPT = str(
    os.environ.get(
        "QWEN_VL_PROMPT",
        (
            "Du analyserer et foto til søgning i et familiealbum. "
            "Skriv ALTID på dansk (aldrig engelsk). Returner KUN gyldig JSON med felterne caption og tags. "
            "caption: én kort sætning (maks 18 ord) der beskriver hovedmotiv, personer (når tydeligt), handling og sted/indendørs/udendørs. "
            "tags: 8-16 korte danske søgeord i lowercase. Medtag synonymer/bøjninger (fx 'gynge','gynger'), personer (barn/pige/dreng/kvinde/mand), handlinger (fx 'vinker','sidder'), objekter (fx 'stol','gynge'), og sted (fx 'indendørs','stue','strand'). "
            "Ingen forklaringer, ingen kodeblokke – kun JSON. "
            "Eksempel: {\"caption\":\"en pige gynger på en legeplads\",\"tags\":[\"pige\",\"barn\",\"gynge\",\"gynger\",\"legeplads\",\"udendørs\"]}."
        ),
    )
    or ""
).strip()
try:
    QWEN_VL_MAX_NEW_TOKENS = int(os.environ.get("QWEN_VL_MAX_NEW_TOKENS", "120") or 120)
except Exception:
    QWEN_VL_MAX_NEW_TOKENS = 120
QWEN_VL_MAX_NEW_TOKENS = max(32, min(256, QWEN_VL_MAX_NEW_TOKENS))
try:
    QWEN_VL_MAX_IMAGE_SIDE = int(os.environ.get("QWEN_VL_MAX_IMAGE_SIDE", "1280") or 1280)
except Exception:
    QWEN_VL_MAX_IMAGE_SIDE = 1280
QWEN_VL_MAX_IMAGE_SIDE = max(0, min(4096, QWEN_VL_MAX_IMAGE_SIDE))
try:
    QWEN_VL_MAX_IMAGE_PIXELS = int(os.environ.get("QWEN_VL_MAX_IMAGE_PIXELS", "1500000") or 1500000)
except Exception:
    QWEN_VL_MAX_IMAGE_PIXELS = 1500000
QWEN_VL_MAX_IMAGE_PIXELS = max(0, min(12000000, QWEN_VL_MAX_IMAGE_PIXELS))
DEVICE_PREF = str(os.environ.get("AI_DEVICE", "auto") or "auto").strip().lower()
if DEVICE_PREF not in {"auto", "cpu", "cuda"}:
    DEVICE_PREF = "auto"
try:
    FACE_ONNX_THREADS = int(os.environ.get("FACE_ONNX_THREADS", "1") or 1)
except Exception:
    FACE_ONNX_THREADS = 1
FACE_ONNX_THREADS = max(1, min(8, FACE_ONNX_THREADS))
FACE_ALLOWED_MODULES = ["detection", "recognition"]

TORCH_CUDA_AVAILABLE = bool(torch.cuda.is_available())
TORCH_CUDA_DEVICE_COUNT = 0
TORCH_CUDA_DEVICE_NAME = None
TORCH_CUDA_PROBE_ERROR = None
try:
    TORCH_CUDA_DEVICE_COUNT = int(torch.cuda.device_count())
    if TORCH_CUDA_AVAILABLE and TORCH_CUDA_DEVICE_COUNT > 0:
        TORCH_CUDA_DEVICE_NAME = str(torch.cuda.get_device_name(0))
except Exception as exc:
    TORCH_CUDA_PROBE_ERROR = str(exc)[:800]
if DEVICE_PREF == "cpu":
    DEVICE = "cpu"
elif DEVICE_PREF == "cuda":
    DEVICE = "cuda" if TORCH_CUDA_AVAILABLE else "cpu"
else:
    DEVICE = "cuda" if TORCH_CUDA_AVAILABLE else "cpu"

ONNX_AVAILABLE_PROVIDERS: list[str] = []
if ort is not None:
    try:
        ONNX_AVAILABLE_PROVIDERS = [str(p) for p in ort.get_available_providers()]
    except Exception:
        ONNX_AVAILABLE_PROVIDERS = []

FACE_USE_CUDA = DEVICE == "cuda" and "CUDAExecutionProvider" in ONNX_AVAILABLE_PROVIDERS
FACE_CTX_ID = 0 if FACE_USE_CUDA else -1
FACE_PROVIDER_CHAIN = (
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if FACE_USE_CUDA
    else ["CPUExecutionProvider"]
)
FACE_DEVICE_CONFIGURED = "cuda" if FACE_USE_CUDA else "cpu"


def _face_detection_runtime_providers_for(app_obj) -> list[str]:
    """Providers bound to detection model session for a specific FaceAnalysis instance."""
    try:
        if app_obj is None:
            return []
        det_model = getattr(app_obj, "det_model", None)
        sess = getattr(det_model, "session", None)
        if sess is not None and hasattr(sess, "get_providers"):
            return [str(p) for p in (sess.get_providers() or [])]
    except Exception:
        pass
    return []


def _face_provider_options(providers: list[str]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for provider in providers:
        if provider == "CUDAExecutionProvider":
            options.append({"device_id": 0})
        else:
            options.append({})
    return options


def _face_session_options():
    if ort is None:
        return None
    try:
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = FACE_ONNX_THREADS
        opts.inter_op_num_threads = 1
        return opts
    except Exception:
        return None


@MEMORY.guard(768*MIB)
def _build_face_analysis(preferred_providers: list[str], ctx_id: int):
    """Create and prepare FaceAnalysis with best-effort provider support details."""
    providers_kw_supported = True
    kwargs: dict[str, Any] = {
        "providers": preferred_providers,
        "provider_options": _face_provider_options(preferred_providers),
    }
    sess_options = _face_session_options()
    if sess_options is not None:
        kwargs["sess_options"] = sess_options
    try:
        app_obj = insightface.app.FaceAnalysis(
            name="buffalo_l",
            allowed_modules=FACE_ALLOWED_MODULES,
            **kwargs,
        )
    except TypeError:
        # Older insightface versions may not expose providers kwarg.
        providers_kw_supported = False
        app_obj = insightface.app.FaceAnalysis(name="buffalo_l", allowed_modules=FACE_ALLOWED_MODULES)

    try:
        app_obj.prepare(ctx_id=ctx_id, det_size=(640, 640))
    except Exception:
        app_obj.prepare(ctx_id=ctx_id)

    det_runtime_providers = _face_detection_runtime_providers_for(app_obj)
    return app_obj, providers_kw_supported, det_runtime_providers

app = FastAPI(title="FjordLens AI Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _start_qwen_idle_unloader():
    if QWEN_VL_AUTO_UNLOAD_IDLE_SEC <= 0:
        return

    def _loop():
        import time as _t
        while True:
            try:
                _t.sleep(60)
                # Only consider unloading when model is loaded
                if _qwen_model is None and _qwen_processor is None:
                    continue
                last = float(globals().get("_qwen_last_used_ts", 0.0) or 0.0)
                if last <= 0:
                    # Never used since load — start grace timer now
                    globals()["_qwen_last_used_ts"] = float(_t.time())
                    continue
                idle = float(_t.time()) - last
                if idle >= float(QWEN_VL_AUTO_UNLOAD_IDLE_SEC):
                    _unload_qwen_model()
            except Exception:
                # Never crash loop; keep trying
                continue

    try:
        t = threading.Thread(target=_loop, name="qwen-idle-unloader", daemon=True)
        t.start()
    except Exception:
        pass


@MEMORY.guard(768*MIB)
def _create_clip_model(device: str):
    mdl, _, prep = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=MODEL_PRETRAINED, device=device)
    mdl.eval()
    return mdl, prep


# Load CLIP with preferred runtime; fallback behavior is handled below.
model, preprocess = _create_clip_model(DEVICE)
tokenizer = open_clip.get_tokenizer(MODEL_NAME)
_embed_lock = threading.RLock()
embed_device_configured = DEVICE
embed_device_active = DEVICE
embed_runtime_warning = None
_embed_cpu_model = None
_embed_cpu_preprocess = None
_qwen_lock = threading.RLock()


def _qwen_job(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not MEMORY.enabled:
            return fn(*args, **kwargs)
        with _qwen_lock:
            return fn(*args, **kwargs)
    return wrapped
_qwen_model = None
_qwen_processor = None
_qwen_runtime_device = DEVICE
_qwen_runtime_error = None
_qwen_quantization = "none"
_qwen_abort_event = threading.Event()
_qwen_last_used_ts = 0.0
try:
    QWEN_VL_AUTO_UNLOAD_IDLE_SEC = int(os.environ.get("QWEN_VL_AUTO_UNLOAD_IDLE_SEC", "600") or 600)
except Exception:
    QWEN_VL_AUTO_UNLOAD_IDLE_SEC = 600
QWEN_VL_AUTO_UNLOAD_IDLE_SEC = max(0, min(86400, QWEN_VL_AUTO_UNLOAD_IDLE_SEC))

_start_qwen_idle_unloader()

# Load InsightFace for face detection/recognition
face_app = None
face_detection_available = False
face_detection_error = None
face_device = FACE_DEVICE_CONFIGURED
face_providers_kw_supported = None
face_cuda_init_errors: list[str] = []
if FACE_USE_CUDA:
    # Try normal chain first, then strict CUDA-only to force explicit failure if CUDA binding fails.
    for providers, label in ((FACE_PROVIDER_CHAIN, "chain"), (["CUDAExecutionProvider"], "cuda_only")):
        try:
            app_obj, kw_supported, det_runtime_providers = _build_face_analysis(providers, ctx_id=0)
            if "CUDAExecutionProvider" not in det_runtime_providers:
                raise RuntimeError(
                    f"{label}_runtime_providers={det_runtime_providers or ['none']}, providers_kw_supported={kw_supported}"
                )
            face_app = app_obj
            face_detection_available = True
            face_device = "cuda"
            face_providers_kw_supported = bool(kw_supported)
            break
        except Exception as exc:
            face_cuda_init_errors.append(f"{label}:{exc}")

    if not face_detection_available:
        # Explicit CPU fallback with retained reason for diagnostics.
        try:
            app_obj, kw_supported, _ = _build_face_analysis(["CPUExecutionProvider"], ctx_id=-1)
            face_app = app_obj
            face_detection_available = True
            face_device = "cpu"
            face_providers_kw_supported = bool(kw_supported)
            face_detection_error = "cuda_init_failed: " + " | ".join(face_cuda_init_errors)
        except Exception as exc2:
            face_detection_error = "cuda_init_failed: " + " | ".join(face_cuda_init_errors) + f"; cpu_fallback_failed: {exc2}"
else:
    try:
        app_obj, kw_supported, _ = _build_face_analysis(["CPUExecutionProvider"], ctx_id=-1)
        face_app = app_obj
        face_detection_available = True
        face_device = "cpu"
        face_providers_kw_supported = bool(kw_supported)
    except Exception as exc:
        face_detection_error = str(exc)


def _face_runtime_providers() -> list[str]:
    """Best-effort read of ONNX providers across loaded face sessions."""
    try:
        if face_app is None:
            return []

        ordered: list[str] = []
        seen: set[str] = set()

        def _append_all(providers: list[str]) -> None:
            for p in providers:
                sp = str(p)
                if sp in seen:
                    continue
                seen.add(sp)
                ordered.append(sp)

        # Detection session is most relevant for face indexing throughput.
        det_model = getattr(face_app, "det_model", None)
        det_sess = getattr(det_model, "session", None)
        if det_sess is not None and hasattr(det_sess, "get_providers"):
            _append_all([str(p) for p in (det_sess.get_providers() or [])])

        models = getattr(face_app, "models", None)
        if isinstance(models, dict):
            for model in models.values():
                sess = getattr(model, "session", None)
                if sess is not None and hasattr(sess, "get_providers"):
                    _append_all([str(p) for p in (sess.get_providers() or [])])
        return ordered
    except Exception:
        pass
    return []


def _face_detection_runtime_providers() -> list[str]:
    """Providers bound to detection model session specifically."""
    try:
        if face_app is None:
            return []
        det_model = getattr(face_app, "det_model", None)
        sess = getattr(det_model, "session", None)
        if sess is not None and hasattr(sess, "get_providers"):
            return [str(p) for p in (sess.get_providers() or [])]
    except Exception:
        pass
    return []


def _face_runtime_device() -> str:
    providers = _face_detection_runtime_providers() or _face_runtime_providers()
    if any(str(p) == "CUDAExecutionProvider" for p in providers):
        return "cuda"
    if providers:
        return "cpu"
    return face_device


_face_runtime_lock = threading.RLock()
_face_runtime_condition = threading.Condition(_face_runtime_lock)
_face_runtime_idle: list[Any] = []
_face_runtime_instances = 0
_face_runtime_active = 0
_face_runtime_peak_active = 0
_face_runtime_releasing = False
FACE_RUNTIME_MAX_WORKERS = 16
_face_runtime_ids: dict[int, int] = {}
_face_jobs: dict[int, dict[str, Any]] = {}


def _face_status_snapshot() -> list[dict[str, Any]]:
    with _face_runtime_lock:
        now = time.monotonic()
        return [
            {"instance": instance, "file": job["file"], "stage": job["stage"],
             "percent": job["percent"], "elapsed_sec": round(now - job["started"], 1)}
            for instance, job in sorted(_face_jobs.items())
        ]


@app.get("/faces/status")
def face_status():
    # Loading a model may wait on admission while holding the pool lock. The
    # monitor must still respond, and must not perform another network request.
    if not _face_runtime_lock.acquire(blocking=False):
        return {'instances': [], 'waiting': 'Klargør ansigtsmodel eller afventer RAM',
                'memory': dict(MEMORY.last)}
    try:
        return {'instances': _face_status_snapshot(), 'waiting': '', 'memory': dict(MEMORY.last)}
    finally:
        _face_runtime_lock.release()


def _log_face_status(row: dict[str, Any]) -> None:
    percent = "unknown" if row["percent"] is None else str(row["percent"])
    # JSON quoting keeps untrusted filenames (including newlines) on one log line.
    print(f'faces_instance instance={row["instance"]} file={json.dumps(row["file"], ensure_ascii=True)} '
          f'stage={row["stage"]} percent={percent} elapsed_sec={row["elapsed_sec"]}', flush=True)


def _update_face_job(runtime, stage: str, percent: Optional[int] = None) -> None:
    with _face_runtime_lock:
        instance = _face_runtime_ids[id(runtime)]
        job = _face_jobs[instance]
        job.update(stage=stage, percent=percent)
        _log_face_status({"instance": instance, "file": job["file"], "stage": stage,
                          "percent": percent, "elapsed_sec": round(time.monotonic() - job["started"], 1)})


def _acquire_face_runtime(filename: str = "unknown"):
    """Lease an exclusive model instance; inference runs outside the pool lock."""
    global _face_runtime_instances, _face_runtime_active, _face_runtime_peak_active
    with _face_runtime_condition:
        deadline = time.monotonic() + 45
        while True:
            blocked = _face_runtime_releasing or (not _face_runtime_idle and _face_runtime_instances >= FACE_RUNTIME_MAX_WORKERS)
            needs_model = not _face_runtime_idle and not (_face_runtime_instances == 0 and face_app is not None)
            if not blocked and needs_model and MEMORY.enabled:
                with MEMORY.lock:
                    blocked = MEMORY.available(MEMORY.status()) < 768*MIB
            if not blocked:
                break
            if MEMORY.enabled and time.monotonic() >= deadline:
                raise RuntimeError("RAM-budget: afventer en ledig ansigtsplads")
            _face_runtime_condition.wait(timeout=0.5)
        if _face_runtime_idle:
            runtime = _face_runtime_idle.pop()
        elif _face_runtime_instances == 0:
            _ensure_face_runtime_loaded()
            runtime = face_app
            _face_runtime_instances += 1
        else:
            providers = _face_detection_runtime_providers()
            runtime, _, actual_providers = _build_face_analysis(
                providers, ctx_id=0 if "CUDAExecutionProvider" in providers else -1
            )
            if "CUDAExecutionProvider" in providers and "CUDAExecutionProvider" not in actual_providers:
                raise RuntimeError("Concurrent face model failed to initialize CUDA")
            _face_runtime_instances += 1
        _face_runtime_active += 1
        _face_runtime_peak_active = max(_face_runtime_peak_active, _face_runtime_active)
        if id(runtime) not in _face_runtime_ids:
            _face_runtime_ids[id(runtime)] = next(i for i in range(1, FACE_RUNTIME_MAX_WORKERS + 1) if i not in _face_runtime_ids.values())
        instance = _face_runtime_ids[id(runtime)]
        _face_jobs[instance] = {"file": str(filename or "unknown"), "stage": "inference",
                                "percent": None, "started": time.monotonic()}
        _update_face_job(runtime, "inference")
        print(f"faces_inference_start active={_face_runtime_active} instances={_face_runtime_instances}", flush=True)
        return runtime


def _return_face_runtime(runtime) -> None:
    global _face_runtime_active
    with _face_runtime_condition:
        _face_jobs.pop(_face_runtime_ids[id(runtime)], None)
        _face_runtime_idle.append(runtime)
        _face_runtime_active -= 1
        print(f"faces_inference_done active={_face_runtime_active} instances={_face_runtime_instances}", flush=True)
        if _face_runtime_active == 0:
            print("faces_instance active=0 stage=idle", flush=True)
        _face_runtime_condition.notify_all()


def _ensure_face_runtime_loaded() -> bool:
    """Load InsightFace again after an idle release. Returns True when reloaded."""
    global face_app, face_detection_available, face_detection_error, face_device, face_providers_kw_supported
    with _face_runtime_lock:
        if face_detection_available and face_app is not None:
            return False

        errors: list[str] = []
        if FACE_USE_CUDA:
            for providers, label in ((FACE_PROVIDER_CHAIN, "chain"), (["CUDAExecutionProvider"], "cuda_only")):
                try:
                    app_obj, kw_supported, det_runtime_providers = _build_face_analysis(providers, ctx_id=0)
                    if "CUDAExecutionProvider" not in det_runtime_providers:
                        raise RuntimeError(
                            f"{label}_runtime_providers={det_runtime_providers or ['none']}, providers_kw_supported={kw_supported}"
                        )
                    face_app = app_obj
                    face_detection_available = True
                    face_device = "cuda"
                    face_providers_kw_supported = bool(kw_supported)
                    face_detection_error = None
                    face_cuda_init_errors[:] = errors
                    return True
                except Exception as exc:
                    errors.append(f"{label}:{exc}")

        try:
            app_obj, kw_supported, _ = _build_face_analysis(["CPUExecutionProvider"], ctx_id=-1)
            face_app = app_obj
            face_detection_available = True
            face_device = "cpu"
            face_providers_kw_supported = bool(kw_supported)
            face_cuda_init_errors[:] = errors
            face_detection_error = ("cuda_init_failed: " + " | ".join(errors)) if errors else None
            return True
        except Exception as exc:
            face_app = None
            face_detection_available = False
            face_device = "cpu"
            face_providers_kw_supported = None
            face_cuda_init_errors[:] = errors
            if errors:
                face_detection_error = "cuda_init_failed: " + " | ".join(errors) + f"; cpu_fallback_failed: {exc}"
            else:
                face_detection_error = str(exc)
            raise RuntimeError(face_detection_error)


def _release_face_runtime() -> bool:
    """Drop ONNX/InsightFace sessions so their CUDA allocations are returned."""
    global face_app, face_detection_available, face_detection_error, face_device, face_providers_kw_supported
    global _face_runtime_instances, _face_runtime_releasing
    with _face_runtime_condition:
        while _face_runtime_releasing:
            _face_runtime_condition.wait()
        _face_runtime_releasing = True
        try:
            while _face_runtime_active:
                _face_runtime_condition.wait()
            changed = face_app is not None or face_detection_available
            _face_runtime_idle.clear()
            _face_runtime_ids.clear()
            _face_jobs.clear()
            _face_runtime_instances = 0
            face_app = None
            face_detection_available = False
            face_device = FACE_DEVICE_CONFIGURED
            face_providers_kw_supported = None
            face_detection_error = "released_after_workflow"
            _clear_cuda_cache()
        finally:
            _face_runtime_releasing = False
            _face_runtime_condition.notify_all()
    return bool(changed)


def _to_list(t: torch.Tensor) -> List[float]:
    v = t.detach().cpu().numpy().astype("float32").ravel()
    # Normalize (unit length)
    n = float(np.linalg.norm(v)) or 1.0
    return (v / n).tolist()


def _ensure_cpu_clip_model():
    global _embed_cpu_model, _embed_cpu_preprocess
    if (_embed_cpu_model is None) or (_embed_cpu_preprocess is None):
        _embed_cpu_model, _embed_cpu_preprocess = _create_clip_model("cpu")
    return _embed_cpu_model, _embed_cpu_preprocess


def _set_embed_runtime_cpu_fallback(reason: str) -> None:
    global model, preprocess, embed_device_active, embed_runtime_warning
    cpu_model, cpu_preprocess = _ensure_cpu_clip_model()
    model = cpu_model
    preprocess = cpu_preprocess
    embed_device_active = "cpu"
    embed_runtime_warning = str(reason or "cuda_runtime_fallback")[:600]


def _run_text_embedding(text: str) -> List[float]:
    with torch.no_grad():
        tokens = tokenizer([text]).to(embed_device_active)
        text_features = model.encode_text(tokens)
        return _to_list(text_features)


def _run_image_embedding(img: Image.Image) -> List[float]:
    img_t = preprocess(img).unsqueeze(0).to(embed_device_active)
    with torch.no_grad():
        image_features = model.encode_image(img_t)
        return _to_list(image_features)


@MEMORY.guard(128*MIB)
def _encode_text_with_fallback(text: str) -> List[float]:
    with _embed_lock:
        try:
            return _run_text_embedding(text)
        except Exception as exc:
            if embed_device_active == "cuda":
                _set_embed_runtime_cpu_fallback(f"cuda_text_runtime_failed: {exc}")
                return _run_text_embedding(text)
            raise


@MEMORY.guard(256*MIB)
def _encode_image_with_fallback(img: Image.Image) -> List[float]:
    with _embed_lock:
        try:
            return _run_image_embedding(img)
        except Exception as exc:
            if embed_device_active == "cuda":
                _set_embed_runtime_cpu_fallback(f"cuda_image_runtime_failed: {exc}")
                return _run_image_embedding(img)
            raise


def _warmup_embed_runtime() -> None:
    if embed_device_active != "cuda":
        return
    with _embed_lock:
        try:
            _ = _run_text_embedding("fjordlens warmup")
        except Exception as exc:
            _set_embed_runtime_cpu_fallback(f"cuda_startup_warmup_failed: {exc}")


_warmup_embed_runtime()


def _clear_cuda_cache() -> None:
    try:
        gc.collect()
    except Exception:
        pass
    if MEMORY.enabled:
        try:
            import ctypes
            ctypes.CDLL(None).malloc_trim(0)
        except (AttributeError, OSError):
            pass
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _reserve_gpu_memory_for_qwen() -> None:
    """Move other optional GPU runtimes to CPU before Qwen claims VRAM."""

    global face_app, face_device, face_detection_available, face_detection_error, face_providers_kw_supported

    if not (QWEN_VL_RESERVE_GPU and torch.cuda.is_available()):
        return

    if embed_device_active == "cuda":
        with _embed_lock:
            if embed_device_active == "cuda":
                _set_embed_runtime_cpu_fallback("cuda_reserved_for_qwen")

    if _face_runtime_device() == "cuda":
        if MEMORY.enabled:
            _release_face_runtime()
        else:
            try:
                app_obj, kw_supported, _ = _build_face_analysis(["CPUExecutionProvider"], ctx_id=-1)
                face_app = app_obj
                face_detection_available = True
                face_device = "cpu"
                face_providers_kw_supported = bool(kw_supported)
                msg = "cuda_reserved_for_qwen"
                face_detection_error = f"{face_detection_error}; {msg}" if face_detection_error else msg
            except Exception as exc:
                msg = f"qwen_gpu_reserve_cpu_face_failed: {exc}"
                face_detection_error = f"{face_detection_error}; {msg}" if face_detection_error else msg

    _clear_cuda_cache()


def _infer_qwen_runtime_device(model_obj: Any) -> str:
    try:
        device_map = getattr(model_obj, "hf_device_map", None)
        if isinstance(device_map, dict):
            vals = [str(v).lower() for v in device_map.values()]
            if any("cuda" in v for v in vals):
                return "cuda"
            if any("cpu" in v for v in vals):
                return "cpu"
        p = next(model_obj.parameters())
        dev = str(getattr(p, "device", "") or "").lower()
        if "cuda" in dev:
            return "cuda"
        if "cpu" in dev:
            return "cpu"
    except Exception:
        pass
    return "cuda" if torch.cuda.is_available() else "cpu"


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = raw[start : end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _repair_mojibake(text: str) -> str:
    raw = str(text or "")
    if "\u00c3" not in raw and "\u00c2" not in raw:
        return raw
    try:
        fixed = raw.encode("latin1").decode("utf-8")
        if fixed:
            return fixed
    except Exception:
        pass
    return raw


def _clean_qwen_text(value: Any) -> str:
    text = _repair_mojibake(str(value or "")).strip().lower()
    text = text.strip(" \t\r\n\"'`[]{}()")
    text = re.sub(r"\s+", " ", text)
    return text


_EN_DA_TAG_MAP = {
    # personer
    "child": "barn",
    "kid": "barn",
    "girl": "pige",
    "boy": "dreng",
    "woman": "kvinde",
    "man": "mand",
    "people": "personer",
    "person": "person",
    "baby": "baby",
    "little": "lille",
    "small": "lille",
    "happy": "glad",
    "activity": "aktivitet",
    "family album": "familiealbum",
    "photo": "foto",
    "picture": "foto",
    "image": "billede",
    "january": "januar",
    "lady": "dame",
    # handlinger
    "wave": "vinker",
    "waving": "vinker",
    "sit": "sidder",
    "sitting": "sidder",
    "smile": "smiler",
    "smiling": "smiler",
    # objekter/steder
    "chair": "stol",
    "swing": "gynge",
    "playground": "legeplads",
    "stairs": "trappe",
    "indoor": "indendørs",
    "indoors": "indendørs",
    "outdoor": "udendørs",
    "outdoors": "udendørs",
    "beach": "strand",
    "sea": "hav",
    "ocean": "hav",
    "water": "vand",
    "living room": "stue",
    "kitchen": "køkken",
}


_QWEN_TAG_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "at være",
    "det",
    "der",
    "en",
    "er",
    "et",
    "for",
    "i",
    "jeg",
    "med",
    "of",
    "og",
    "on",
    "på",
    "som",
    "the",
    "til",
    "to",
    "være",
    "with",
}


def _to_danish_tag(tag: str) -> str:
    t = _clean_qwen_text(tag)
    return _EN_DA_TAG_MAP.get(t, t)


def _qwen_tag_parts(value: Any) -> list[str]:
    return [p for p in re.split(r"[,;|]|\s+[–—-]\s+", str(value or "")) if p]


def _append_clean_tag(tags: List[str], value: Any, max_tags: int = 16) -> None:
    tag = _to_danish_tag(value)
    if (
        not tag
        or len(tag) > 40
        or tag in tags
        or any(ch in tag for ch in "\n\r\t")
        or tag in _QWEN_TAG_STOPWORDS
        or tag in {"caption", "tags", "json", "null", "none"}
    ):
        return
    tags.append(tag)


def _normalize_caption_and_tags(caption_value: Any, tags_value: Any) -> tuple[str, List[str]]:
    caption = _repair_mojibake(str(caption_value or "")).strip()
    tags: List[str] = []
    if isinstance(tags_value, (list, tuple)):
        for v in tags_value:
            for part in _qwen_tag_parts(v):
                _append_clean_tag(tags, part)
                if len(tags) >= 16:
                    break
            if len(tags) >= 16:
                break
    elif isinstance(tags_value, str):
        for part in _qwen_tag_parts(tags_value):
            _append_clean_tag(tags, part)
            if len(tags) >= 16:
                break

    if not tags and caption:
        stop = {
            "og",
            "det",
            "der",
            "som",
            "med",
            "for",
            "the",
            "and",
            "with",
            "this",
            "that",
            "photo",
            "image",
            "billede",
        }
        for token in re.findall(r"[a-zA-Z0-9æøåÆØÅ\-]{3,}", _repair_mojibake(caption).lower()):
            if token in stop or token in tags:
                continue
            tags.append(token)
            if len(tags) >= 16:
                break

    # Fallback: hvis caption er for tynd, byg en lille dansk sætning fra tags
    try:
        wc = len([w for w in re.findall(r"[\wæøåÆØÅ]+", caption) if w])
    except Exception:
        wc = 0
    if wc < 3 and tags:
        place = next((t for t in tags if t in {"indendørs", "udendørs", "strand", "stue", "køkken"}), None)
        person = next((t for t in tags if t in {"barn", "pige", "dreng", "kvinde", "mand", "baby"}), None)
        obj = next((t for t in tags if t in {"stol", "gynge", "trappe"}), None)
        if person and obj and place:
            caption = f"{person} på {obj} {place}"
        elif person and place:
            caption = f"{person} {place}"
        elif person and obj:
            caption = f"{person} med {obj}"
        else:
            caption = ", ".join(tags[:3])

    return caption, tags


def _parse_qwen_output_text(text: str) -> tuple[str, List[str]]:
    parsed = _extract_first_json_object(text)
    if parsed is not None:
        return _normalize_caption_and_tags(parsed.get("caption"), parsed.get("tags"))
    return _normalize_caption_and_tags(text, None)


def _select_qwen_model_class():
    model_key = QWEN_VL_MODEL.lower().replace("_", "-")
    if "qwen2-vl" in model_key and "qwen2.5-vl" not in model_key and "qwen2-5-vl" not in model_key:
        return Qwen2VLForConditionalGeneration or AutoModelForVision2Seq
    if "qwen2.5-vl" in model_key or "qwen2-5-vl" in model_key:
        return Qwen2_5_VLForConditionalGeneration or AutoModelForVision2Seq
    return AutoModelForVision2Seq


def _ensure_qwen_model_loaded():
    global _qwen_model, _qwen_processor, _qwen_runtime_device, _qwen_runtime_error, _qwen_quantization
    with _qwen_lock:
        if _qwen_model is not None and _qwen_processor is not None:
            return _qwen_model, _qwen_processor

        if not _ensure_qwen_deps_loaded():
            _qwen_runtime_error = _QWEN_DEPS_IMPORT_ERROR or "transformers_not_installed"
            raise RuntimeError(_qwen_runtime_error)

        model_kwargs: Dict[str, Any] = {
            "device_map": "auto",
            "trust_remote_code": True,
        }
        if QWEN_VL_LOW_CPU_MEM_USAGE:
            model_kwargs["low_cpu_mem_usage"] = True
        if torch.cuda.is_available():
            model_kwargs["torch_dtype"] = torch.float16
        else:
            model_kwargs["torch_dtype"] = torch.float32

        quantization = "none"
        if (
            torch.cuda.is_available()
            and QWEN_VL_ENABLE_4BIT
            and BitsAndBytesConfig is not None
            and _BITSANDBYTES_AVAILABLE
        ):
            try:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type=QWEN_VL_4BIT_QUANT_TYPE,
                    bnb_4bit_use_double_quant=True,
                )
                quantization = f"4bit-{QWEN_VL_4BIT_QUANT_TYPE}"
            except Exception:
                quantization = "none"

        model_cls = _select_qwen_model_class()
        try:
            _reserve_gpu_memory_for_qwen()
            model_obj = model_cls.from_pretrained(QWEN_VL_MODEL, **model_kwargs)
            processor_obj = AutoProcessor.from_pretrained(QWEN_VL_MODEL, trust_remote_code=True)
            model_obj.eval()

            _qwen_model = model_obj
            _qwen_processor = processor_obj
            _qwen_runtime_device = _infer_qwen_runtime_device(model_obj)
            _qwen_runtime_error = None
            _qwen_quantization = quantization
            try:
                import time as _t
                globals()["_qwen_last_used_ts"] = float(_t.time())
            except Exception:
                pass
            return _qwen_model, _qwen_processor
        except Exception as exc:
            primary_error = str(exc)[:800]
            _clear_cuda_cache()

            if torch.cuda.is_available() and QWEN_VL_CPU_FALLBACK:
                try:
                    cpu_kwargs: Dict[str, Any] = {
                        "device_map": {"": "cpu"},
                        "trust_remote_code": True,
                        "torch_dtype": torch.float32,
                    }
                    if QWEN_VL_LOW_CPU_MEM_USAGE:
                        cpu_kwargs["low_cpu_mem_usage"] = True
                    model_obj = model_cls.from_pretrained(QWEN_VL_MODEL, **cpu_kwargs)
                    processor_obj = AutoProcessor.from_pretrained(QWEN_VL_MODEL, trust_remote_code=True)
                    model_obj.eval()

                    _qwen_model = model_obj
                    _qwen_processor = processor_obj
                    _qwen_runtime_device = "cpu"
                    _qwen_runtime_error = f"cuda_load_failed_cpu_fallback: {primary_error}"[:800]
                    _qwen_quantization = "none"
                    try:
                        import time as _t
                        globals()["_qwen_last_used_ts"] = float(_t.time())
                    except Exception:
                        pass
                    return _qwen_model, _qwen_processor
                except Exception as cpu_exc:
                    _qwen_runtime_error = f"{primary_error} | cpu_fallback_failed: {cpu_exc}"[:800]
            else:
                _qwen_runtime_error = primary_error

            _qwen_runtime_device = "error"
            _qwen_model = None
            _qwen_processor = None
            _qwen_quantization = "none"
            raise


def _qwen_input_device(model_obj: Any) -> str:
    try:
        device_map = getattr(model_obj, "hf_device_map", None)
        if isinstance(device_map, dict):
            vals = [str(v).lower() for v in device_map.values()]
            if any("cuda" in v for v in vals):
                return "cuda"
            if any("cpu" in v for v in vals):
                return "cpu"
    except Exception:
        pass
    try:
        p = next(model_obj.parameters())
        dev = str(getattr(p, "device", "") or "").strip()
        if dev:
            return dev
    except Exception:
        pass
    return "cuda" if torch.cuda.is_available() else "cpu"


def _mark_qwen_used() -> None:
    try:
        import time as _t
        globals()["_qwen_last_used_ts"] = float(_t.time())
    except Exception:
        pass


def _unload_qwen_model() -> bool:
    global _qwen_model, _qwen_processor
    changed = False
    try:
        if _qwen_model is not None or _qwen_processor is not None:
            _qwen_model = None
            _qwen_processor = None
            changed = True
    except Exception:
        pass
    try:
        gc.collect()
    except Exception:
        pass
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return changed


def _prepare_qwen_image(img: Image.Image) -> Image.Image:
    width, height = img.size
    if width <= 0 or height <= 0:
        return img

    scale = 1.0
    if QWEN_VL_MAX_IMAGE_SIDE > 0:
        scale = min(scale, float(QWEN_VL_MAX_IMAGE_SIDE) / float(max(width, height)))
    if QWEN_VL_MAX_IMAGE_PIXELS > 0:
        pixels = width * height
        if pixels > QWEN_VL_MAX_IMAGE_PIXELS:
            scale = min(scale, (float(QWEN_VL_MAX_IMAGE_PIXELS) / float(pixels)) ** 0.5)

    # Resize if needed first
    if scale < 1.0:
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        img = img.resize(new_size, resample)

    # Light auto-enhance for meget mørke billeder for bedre synlighed
    try:
        lum = img.convert("L")
        mean_val = float(np.asarray(lum, dtype=np.uint8).mean())
        if mean_val < 78.0:  # mørkt billede
            img = ImageOps.autocontrast(img, cutoff=2)
            try:
                img = ImageEnhance.Brightness(img).enhance(1.25)
                img = ImageEnhance.Contrast(img).enhance(1.12)
            except Exception:
                pass
    except Exception:
        pass

    return img


@MEMORY.guard(lambda: 768*MIB if _qwen_model is not None else 4*1024*MIB)
@_qwen_job
def _qwen_describe_image(img: Image.Image) -> Dict[str, Any]:
    _qwen_abort_event.clear()
    model_obj, processor_obj = _ensure_qwen_model_loaded()
    _mark_qwen_used()
    img = _prepare_qwen_image(img)

    prompt_text = QWEN_VL_PROMPT
    fallback_prompt_text = f"<|vision_start|><|image_pad|><|vision_end|>\n{QWEN_VL_PROMPT}"
    if hasattr(processor_obj, "apply_chat_template"):
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ]
            prompt_text = processor_obj.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt_text = fallback_prompt_text

    try:
        inputs = processor_obj(
            text=[prompt_text],
            images=[img],
            return_tensors="pt",
        )
    except Exception:
        inputs = processor_obj(
            text=[fallback_prompt_text],
            images=[img],
            return_tensors="pt",
        )

    device = _qwen_input_device(model_obj)
    for key, value in list(inputs.items()):
        if hasattr(value, "to"):
            try:
                inputs[key] = value.to(device)
            except Exception:
                pass

    generate_kwargs: Dict[str, Any] = {
        **inputs,
        "max_new_tokens": QWEN_VL_MAX_NEW_TOKENS,
        "do_sample": False,
    }
    try:
        from transformers import StoppingCriteria, StoppingCriteriaList

        class _QwenAbortCriteria(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):  # type: ignore[no-untyped-def]
                return _qwen_abort_event.is_set()

        generate_kwargs["stopping_criteria"] = StoppingCriteriaList([_QwenAbortCriteria()])
    except Exception:
        pass

    with torch.no_grad():
        output_ids = model_obj.generate(**generate_kwargs)

    if _qwen_abort_event.is_set():
        raise RuntimeError("qwen_describe_aborted")

    prompt_len = 0
    try:
        in_ids = inputs.get("input_ids")
        if in_ids is not None and hasattr(in_ids, "shape"):
            prompt_len = int(in_ids.shape[-1])
    except Exception:
        prompt_len = 0

    decode_ids = output_ids
    try:
        if prompt_len > 0 and hasattr(output_ids, "shape") and int(output_ids.shape[-1]) > prompt_len:
            decode_ids = output_ids[:, prompt_len:]
    except Exception:
        decode_ids = output_ids

    raw_text = ""
    try:
        decoded = processor_obj.batch_decode(decode_ids, skip_special_tokens=True)
        if decoded:
            raw_text = str(decoded[0] or "").strip()
    except Exception:
        raw_text = ""

    caption, tags = _parse_qwen_output_text(raw_text)
    return {
        "caption": caption,
        "tags": tags,
        "raw": raw_text,
    }


class TextIn(BaseModel):
    text: str


class EmbedOut(BaseModel):
    embedding: List[float]


@app.get("/health")
def health():
    runtime_providers = _face_runtime_providers()
    detection_runtime_providers = _face_detection_runtime_providers()
    runtime_face_device = _face_runtime_device()
    runtime_warning = None
    if FACE_DEVICE_CONFIGURED == "cuda" and runtime_face_device != "cuda":
        runtime_warning = "configured_cuda_but_runtime_cpu"
    return {
        "ok": True,
        "device": embed_device_active,
        "device_configured": embed_device_configured,
        "device_preference": DEVICE_PREF,
        "torch_version": str(getattr(torch, "__version__", "")),
        "torch_cuda_version": str(getattr(torch.version, "cuda", "")),
        "torch_cuda_available": TORCH_CUDA_AVAILABLE,
        "torch_cuda_device_count": TORCH_CUDA_DEVICE_COUNT,
        "torch_cuda_device_name": TORCH_CUDA_DEVICE_NAME,
        "torch_cuda_probe_error": TORCH_CUDA_PROBE_ERROR,
        "model": MODEL_NAME,
        "pretrained": MODEL_PRETRAINED,
        "embed_runtime_warning": embed_runtime_warning,
        "onnxruntime_version": str(getattr(ort, "__version__", "")) if ort is not None else None,
        "onnx_available_providers": ONNX_AVAILABLE_PROVIDERS,
        "face_device": runtime_face_device,
        "face_device_configured": FACE_DEVICE_CONFIGURED,
        "face_providers_kw_supported": face_providers_kw_supported,
        "face_provider_chain": FACE_PROVIDER_CHAIN,
        "face_provider_options": _face_provider_options(FACE_PROVIDER_CHAIN),
        "face_allowed_modules": FACE_ALLOWED_MODULES,
        "face_onnx_threads": FACE_ONNX_THREADS,
        # Compatibility/status field: concurrency follows the request batch size.
        # The endpoint itself accepts at most 16 files; the UI currently offers up to 8.
        "face_batch_max_workers": FACE_RUNTIME_MAX_WORKERS,
        "face_inference_active": _face_runtime_active,
        "face_inference_peak_active": _face_runtime_peak_active,
        "face_model_instances": _face_runtime_instances,
        "face_batch_endpoint": True,
        "face_runtime_providers": runtime_providers,
        "face_detection_runtime_providers": detection_runtime_providers,
        "face_runtime_warning": runtime_warning,
        "face_ctx_id": FACE_CTX_ID if runtime_face_device == "cuda" else -1,
        "face_detection_available": face_detection_available,
        "face_cuda_init_errors": face_cuda_init_errors,
        "face_detection_error": face_detection_error,
        "qwen_model": QWEN_VL_MODEL,
        "qwen_model_class": getattr(_select_qwen_model_class(), "__name__", None) if _QWEN_DEPS_IMPORT_ATTEMPTED else None,
        "qwen_loaded": bool(_qwen_model is not None and _qwen_processor is not None),
        "qwen_device": _qwen_runtime_device,
        "qwen_quantization": _qwen_quantization,
        "qwen_4bit_enabled": QWEN_VL_ENABLE_4BIT,
        "qwen_4bit_quant_type": QWEN_VL_4BIT_QUANT_TYPE,
        "qwen_reserve_gpu": QWEN_VL_RESERVE_GPU,
        "qwen_cpu_fallback": QWEN_VL_CPU_FALLBACK,
        "qwen_low_cpu_mem_usage": QWEN_VL_LOW_CPU_MEM_USAGE,
        "qwen_max_new_tokens": QWEN_VL_MAX_NEW_TOKENS,
        "qwen_max_image_side": QWEN_VL_MAX_IMAGE_SIDE,
        "qwen_max_image_pixels": QWEN_VL_MAX_IMAGE_PIXELS,
        "qwen_deps_loaded": _QWEN_DEPS_IMPORT_ATTEMPTED and AutoProcessor is not None and AutoModelForVision2Seq is not None,
        "qwen_deps_import_error": _QWEN_DEPS_IMPORT_ERROR,
        "qwen_runtime_error": _qwen_runtime_error,
    }


@app.post("/embed/text", response_model=EmbedOut)
def embed_text(payload: TextIn):
    try:
        return {"embedding": _encode_text_with_fallback(payload.text)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"embed_text_failed: {exc}")


@app.post("/embed/image", response_model=EmbedOut)
def embed_image(file: UploadFile = File(...)):
    data = file.file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid_image: {exc}")
    try:
        return {"embedding": _encode_image_with_fallback(img)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"embed_image_failed: {exc}")


@app.post("/describe/stop")
def stop_describe(hard: bool = False):
    _qwen_abort_event.set()
    if hard:
        def _exit_soon() -> None:
            time.sleep(0.2)
            os._exit(0)

        threading.Thread(target=_exit_soon, daemon=True).start()
    return {"ok": True, "hard": bool(hard)}


class QueryIn(BaseModel):
    text: str
    language: Optional[str] = None  # e.g. "da" or "en"


@MEMORY.guard(lambda: 512*MIB if _qwen_model is not None else 4*1024*MIB)
@_qwen_job
def _qwen_expand_query(text: str, language: Optional[str] = None) -> Dict[str, Any]:
    """Use Qwen-VL as a text-only LLM to expand a freeform query into Danish search tags.

    Returns a dict with keys: tags (List[str]), raw (str).
    """
    _qwen_abort_event.clear()
    model_obj, processor_obj = _ensure_qwen_model_loaded()

    lang = (str(language or "da").strip().lower() or "da")
    if lang not in {"da", "en"}:
        lang = "da"
    if lang == "da":
        sys_prompt = (
            "Du udvider en søgetekst til billedsøgning i et familiealbum. "
            "Returner KUN gyldig JSON med feltet 'tags' som en liste af 8-16 korte danske søgeord i lowercase. "
            "Brug almindelige synonymer og bøjningsvarianter (fx 'gynge','gynger'), konkrete objekter, handlinger, steder og personer når relevant. "
            "Ingen forklaringer, kun JSON. Eksempel: {\"tags\":[\"pige\",\"barn\",\"gynge\",\"gynger\",\"legeplads\"]}."
        )
    else:
        sys_prompt = (
            "Expand a freeform photo search into 8-16 short lowercase tags in English. "
            "Return ONLY valid JSON with field 'tags'. Include synonyms, inflections, objects, actions, places, people when relevant. "
            "Example: {\"tags\":[\"girl\",\"child\",\"swing\",\"playground\"]}."
        )

    # Build prompt using chat template when available to keep compatibility with Qwen processors
    prompt_text = sys_prompt + "\n\nSøgetekst: " + str(text or "").strip()
    if hasattr(processor_obj, "apply_chat_template"):
        try:
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": str(text or "").strip()},
            ]
            prompt_text = processor_obj.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            # Fallback to concatenated text
            prompt_text = sys_prompt + "\n\n" + str(text or "").strip()

    inputs = processor_obj(
        text=[prompt_text],
        return_tensors="pt",
    )
    device = _qwen_input_device(model_obj)
    for key, value in list(inputs.items()):
        if hasattr(value, "to"):
            try:
                inputs[key] = value.to(device)
            except Exception:
                pass

    with torch.no_grad():
        output_ids = model_obj.generate(
            **inputs,
            max_new_tokens=min(max(96, QWEN_VL_MAX_NEW_TOKENS // 2), 192),
            do_sample=False,
        )

    prompt_len = 0
    try:
        in_ids = inputs.get("input_ids")
        if in_ids is not None and hasattr(in_ids, "shape"):
            prompt_len = int(in_ids.shape[-1])
    except Exception:
        prompt_len = 0

    decode_ids = output_ids
    try:
        if prompt_len > 0 and hasattr(output_ids, "shape") and int(output_ids.shape[-1]) > prompt_len:
            decode_ids = output_ids[:, prompt_len:]
    except Exception:
        decode_ids = output_ids

    raw_text = ""
    try:
        decoded = processor_obj.batch_decode(decode_ids, skip_special_tokens=True)
        if decoded:
            raw_text = str(decoded[0] or "").strip()
    except Exception:
        raw_text = ""

    # Parse output similarly to image description, but keep only tags
    _, tags = _parse_qwen_output_text(raw_text)
    return {"tags": tags, "raw": raw_text}


@app.post("/query/expand")
def expand_query(payload: QueryIn):
    try:
        out = _qwen_expand_query(payload.text, payload.language)
        return {
            "ok": True,
            "tags": out.get("tags") or [],
            "raw": out.get("raw") or "",
            "model": QWEN_VL_MODEL,
            "device": _qwen_runtime_device,
            "quantization": _qwen_quantization,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"expand_query_failed: {exc}")


class MomentEntryIn(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    place: Optional[str] = None
    caption: Optional[str] = None
    tags: Optional[List[str]] = None
    favorite: Optional[bool] = None


class MomentNarrateIn(BaseModel):
    kind: Optional[str] = None
    title_hint: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    primary_place: Optional[str] = None
    language: Optional[str] = None
    entries: List[MomentEntryIn] = []


@MEMORY.guard(lambda: 768*MIB if _qwen_model is not None else 4*1024*MIB)
@_qwen_job
def _qwen_narrate_moment(payload: "MomentNarrateIn") -> Dict[str, Any]:
    """Text-only Qwen call: reads already-stored per-photo metadata (dates, places, AI
    captions/tags) and writes a short title + a handful of narrative slideshow lines.
    No image tensors involved — this is a cheap, pure-text prompt.
    """
    _qwen_abort_event.clear()
    model_obj, processor_obj = _ensure_qwen_model_loaded()

    lang = (str(payload.language or "da").strip().lower() or "da")
    if lang not in {"da", "en"}:
        lang = "da"

    lines = []
    for e in (payload.entries or [])[:40]:
        bits = [b for b in [e.date, e.time, e.place] if b]
        head = ", ".join(bits) if bits else "(ukendt tidspunkt)"
        desc_bits = []
        if e.caption:
            desc_bits.append(f'"{e.caption}"')
        if e.tags:
            desc_bits.append("tags: " + ", ".join(e.tags[:8]))
        if e.favorite:
            desc_bits.append("favorit")
        line = head + (": " + " | ".join(desc_bits) if desc_bits else "")
        lines.append(line)
    entries_text = "\n".join(lines) if lines else "(ingen detaljer)"

    kind_label = "et årsoverblik" if payload.kind == "year_review" else "en rejse/begivenhed"
    context_bits = [f"Type: {kind_label}"]
    if payload.start_date or payload.end_date:
        context_bits.append(f"Periode: {payload.start_date or '?'} til {payload.end_date or '?'}")
    if payload.primary_place:
        context_bits.append(f"Sted: {payload.primary_place}")
    context_text = "\n".join(context_bits)

    if lang == "da":
        sys_prompt = (
            "Du skriver korte, varme mindebogs-tekster til et diasshow af familiebilleder, ud fra "
            "metadata (datoer, steder, korte billedbeskrivelser) — du ser IKKE selve billederne. "
            "Returner KUN gyldig JSON med felterne 'title' (kort titel, maks 6 ord), "
            "'subtitle' (én kort introlinje) og 'cards' (liste af 4-8 meget korte danske sætninger, "
            "hver maks ca. 8 ord, i kronologisk rækkefølge, som kan vises som tekstplancher mellem billederne). "
            "Skriv i nutid eller datid, personligt og varmt, ingen klichéer, ingen forklaringer uden om JSON'en. "
            'Eksempel: {"title":"Sommer ved havet","subtitle":"En uge i juli 2014",'
            '"cards":["Første morgen med sand mellem tæerne","Isen smeltede hurtigere end vi kunne spise"]}'
        )
    else:
        sys_prompt = (
            "You write short, warm memory-book text for a family photo slideshow, based on metadata "
            "(dates, places, short image captions) — you do NOT see the images themselves. "
            "Return ONLY valid JSON with fields 'title' (short, max 6 words), 'subtitle' (one short intro line), "
            "and 'cards' (a list of 4-8 very short sentences, max ~8 words each, in chronological order, "
            "to be shown as text cards between the photos). Warm and personal tone, no clichés, JSON only."
        )

    user_text = f"{context_text}\nForslag til titel: {payload.title_hint or ''}\n\nBilleder:\n{entries_text}"

    prompt_text = sys_prompt + "\n\n" + user_text
    if hasattr(processor_obj, "apply_chat_template"):
        try:
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_text},
            ]
            prompt_text = processor_obj.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt_text = sys_prompt + "\n\n" + user_text

    inputs = processor_obj(text=[prompt_text], return_tensors="pt")
    device = _qwen_input_device(model_obj)
    for key, value in list(inputs.items()):
        if hasattr(value, "to"):
            try:
                inputs[key] = value.to(device)
            except Exception:
                pass

    with torch.no_grad():
        output_ids = model_obj.generate(
            **inputs,
            max_new_tokens=min(max(160, QWEN_VL_MAX_NEW_TOKENS), 384),
            do_sample=False,
        )

    prompt_len = 0
    try:
        in_ids = inputs.get("input_ids")
        if in_ids is not None and hasattr(in_ids, "shape"):
            prompt_len = int(in_ids.shape[-1])
    except Exception:
        prompt_len = 0

    decode_ids = output_ids
    try:
        if prompt_len > 0 and hasattr(output_ids, "shape") and int(output_ids.shape[-1]) > prompt_len:
            decode_ids = output_ids[:, prompt_len:]
    except Exception:
        decode_ids = output_ids

    raw_text = ""
    try:
        decoded = processor_obj.batch_decode(decode_ids, skip_special_tokens=True)
        if decoded:
            raw_text = str(decoded[0] or "").strip()
    except Exception:
        raw_text = ""

    parsed = _extract_first_json_object(raw_text) or {}
    title = _clean_qwen_text(parsed.get("title") or "")
    subtitle = _clean_qwen_text(parsed.get("subtitle") or "")
    cards_raw = parsed.get("cards") or []
    cards = [_clean_qwen_text(c) for c in cards_raw if _clean_qwen_text(c)] if isinstance(cards_raw, list) else []
    return {"title": title, "subtitle": subtitle, "cards": cards, "raw": raw_text}


@app.post("/moments/narrate")
def moments_narrate(payload: MomentNarrateIn):
    try:
        out = _qwen_narrate_moment(payload)
        return {
            "ok": True,
            "title": out.get("title") or "",
            "subtitle": out.get("subtitle") or "",
            "cards": out.get("cards") or [],
            "model": QWEN_VL_MODEL,
            "device": _qwen_runtime_device,
            "quantization": _qwen_quantization,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"moments_narrate_failed: {exc}")


@app.post("/qwen/unload")
def qwen_unload():
    changed = _unload_qwen_model()
    return {"ok": True, "unloaded": bool(changed)}


@app.post("/describe/image")
def describe_image(file: UploadFile = File(...)):
    data = file.file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid_image: {exc}")

    try:
        out = _qwen_describe_image(img)
        return {
            "ok": True,
            "caption": out.get("caption") or None,
            "tags": out.get("tags") or [],
            "model": QWEN_VL_MODEL,
            "device": _qwen_runtime_device,
            "quantization": _qwen_quantization,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"describe_image_failed: {exc}")


def _serialize_face_result(face) -> Dict[str, Any]:
    bbox = [float(x) for x in face.bbox.tolist()] if hasattr(face.bbox, "tolist") else [float(x) for x in face.bbox]
    kps = face.kps.tolist() if hasattr(face.kps, "tolist") else [[float(x) for x in p] for p in face.kps]
    emb = face.normed_embedding if hasattr(face, "normed_embedding") and face.normed_embedding is not None else face.embedding
    if hasattr(emb, "tolist"):
        emb = emb.tolist()
    v = np.asarray(emb, dtype=np.float32).ravel()
    n = float(np.linalg.norm(v)) or 1.0
    v = (v / n).astype(np.float32)
    return {
        "bbox": bbox,
        "landmarks": kps,
        "embedding": v.tolist(),
        "confidence": float(getattr(face, "det_score", 1.0)),
    }


@MEMORY.guard(128*MIB)
def _detect_faces_bytes(data: bytes, filename: str = "unknown") -> List[Dict[str, Any]]:
    runtime = _acquire_face_runtime(filename)
    try:
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img_np = np.array(img)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid_image: {exc}") from exc
        faces = runtime.get(img_np)
        _update_face_job(runtime, "serialize")
        result = [_serialize_face_result(face) for face in faces]
        _update_face_job(runtime, "done", 100)
        return result
    except Exception:
        _update_face_job(runtime, "error")
        raise
    finally:
        _return_face_runtime(runtime)


@app.post("/faces/detect")
def detect_faces(file: UploadFile = File(...)):
    try:
        out = _detect_faces_bytes(file.file.read(), filename=file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"face_detect_failed: {exc}") from exc
    return {"ok": True, "count": len(out), "faces": out}


@app.post("/faces/detect-batch")
def detect_faces_batch(files: List[UploadFile] = File(...)):
    uploads = list(files or [])
    if not uploads:
        raise HTTPException(status_code=400, detail="No files supplied")
    if len(uploads) > 16:
        raise HTTPException(status_code=400, detail="Maximum 16 files per face batch")

    payloads = []
    for index, upload in enumerate(uploads):
        payloads.append((index, str(upload.filename or f"image-{index}.jpg"), upload.file.read()))

    # Each active request leases its own model, including during inference.
    workers = len(payloads)
    results: List[Optional[Dict[str, Any]]] = [None] * len(payloads)

    def run_one(item):
        index, filename, data = item
        faces = _detect_faces_bytes(data, filename=filename)
        return index, {
            "filename": filename,
            "ok": True,
            "count": len(faces),
            "faces": faces,
        }

    failed: List[tuple[int, str, bytes, Exception]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fjordlens-face-batch") as pool:
        future_map = {pool.submit(run_one, item): item for item in payloads}
        for future in as_completed(future_map):
            index, filename, data = future_map[future]
            try:
                result_index, result = future.result()
                results[result_index] = result
            except Exception as exc:
                failed.append((index, filename, data, exc))

    # Keep the existing one-shot retry after all initial batch attempts finish.
    for index, filename, data, first_exc in failed:
        try:
            faces = _detect_faces_bytes(data, filename=filename)
            results[index] = {
                "filename": filename,
                "ok": True,
                "count": len(faces),
                "faces": faces,
                "retried_serially": True,
            }
        except Exception as retry_exc:
            results[index] = {
                "filename": filename,
                "ok": False,
                "count": 0,
                "faces": [],
                "error": str(retry_exc or first_exc),
            }

    items = [item or {"ok": False, "count": 0, "faces": [], "error": "missing_result"} for item in results]
    _clear_cuda_cache()
    return {
        "ok": True,
        "batch_size": len(items),
        "workers": workers,
        "items": items,
    }


@app.post("/faces/warmup")
def faces_warmup():
    try:
        reloaded = _ensure_face_runtime_loaded()
        return {
            "ok": True,
            "reloaded": bool(reloaded),
            "available": bool(face_detection_available and face_app is not None),
            "device": _face_runtime_device(),
            "providers": _face_detection_runtime_providers(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"face_warmup_failed: {exc}")


@app.post("/faces/release")
def faces_release():
    try:
        released = _release_face_runtime()
        return {"ok": True, "released": bool(released)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"face_release_failed: {exc}")


def _memory_pressure_loop():
    global _face_runtime_instances
    while True:
        try:
            status = MEMORY.status()
            with MEMORY.lock:
                pressure = MEMORY.available(status) < 512*MIB
            if pressure:
                with _face_runtime_condition:
                    if _face_runtime_active == 0:
                        _release_face_runtime()
                    else:
                        for runtime in list(_face_runtime_idle):
                            if runtime is face_app:
                                continue
                            _face_runtime_idle.remove(runtime)
                            _face_runtime_ids.pop(id(runtime), None)
                            _face_runtime_instances -= 1
                        runtime = None
                        _face_runtime_condition.notify_all()
                if _qwen_lock.acquire(blocking=False):
                    try:
                        _unload_qwen_model()
                    finally:
                        _qwen_lock.release()
                _clear_cuda_cache()
        except Exception as exc:
            print(f"memory_trim error={exc}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    if MEMORY.enabled:
        threading.Thread(target=_memory_pressure_loop, name="memory-trim", daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
