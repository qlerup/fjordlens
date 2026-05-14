import io
import inspect
import json
import os
import re
import threading
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import uvicorn
from PIL import Image

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
Qwen2_5_VLForConditionalGeneration = None
bnb = None
_BITSANDBYTES_AVAILABLE = False
_QWEN_DEPS_IMPORT_ATTEMPTED = False
_QWEN_DEPS_IMPORT_ERROR = None


def _ensure_qwen_deps_loaded() -> bool:
    global AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
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
QWEN_VL_PROMPT = str(
    os.environ.get(
        "QWEN_VL_PROMPT",
        (
            "Du analyserer et foto. Returner kun JSON med felterne caption og tags. "
            "caption skal være en kort dansk sætning (maks 18 ord). "
            "tags skal være 3-8 korte danske nøgleord i lower-case."
        ),
    )
    or ""
).strip()
try:
    QWEN_VL_MAX_NEW_TOKENS = int(os.environ.get("QWEN_VL_MAX_NEW_TOKENS", "120") or 120)
except Exception:
    QWEN_VL_MAX_NEW_TOKENS = 120
QWEN_VL_MAX_NEW_TOKENS = max(32, min(256, QWEN_VL_MAX_NEW_TOKENS))
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
_qwen_model = None
_qwen_processor = None
_qwen_runtime_device = DEVICE
_qwen_runtime_error = None
_qwen_quantization = "none"

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


def _encode_text_with_fallback(text: str) -> List[float]:
    with _embed_lock:
        try:
            return _run_text_embedding(text)
        except Exception as exc:
            if embed_device_active == "cuda":
                _set_embed_runtime_cpu_fallback(f"cuda_text_runtime_failed: {exc}")
                return _run_text_embedding(text)
            raise


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


def _normalize_caption_and_tags(caption_value: Any, tags_value: Any) -> tuple[str, List[str]]:
    caption = str(caption_value or "").strip()
    tags: List[str] = []
    if isinstance(tags_value, (list, tuple)):
        for v in tags_value:
            t = str(v or "").strip().lower()
            if not t or t in tags:
                continue
            tags.append(t)
            if len(tags) >= 10:
                break
    elif isinstance(tags_value, str):
        for part in re.split(r"[,;|]", tags_value):
            t = str(part or "").strip().lower()
            if not t or t in tags:
                continue
            tags.append(t)
            if len(tags) >= 10:
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
        for token in re.findall(r"[a-zA-Z0-9æøåÆØÅ\-]{3,}", caption.lower()):
            if token in stop or token in tags:
                continue
            tags.append(token)
            if len(tags) >= 8:
                break

    return caption, tags


def _parse_qwen_output_text(text: str) -> tuple[str, List[str]]:
    parsed = _extract_first_json_object(text)
    if parsed is not None:
        return _normalize_caption_and_tags(parsed.get("caption"), parsed.get("tags"))
    return _normalize_caption_and_tags(text, None)


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
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                quantization = "4bit"
            except Exception:
                quantization = "none"

        try:
            model_cls = Qwen2_5_VLForConditionalGeneration or AutoModelForVision2Seq
            model_obj = model_cls.from_pretrained(QWEN_VL_MODEL, **model_kwargs)
            processor_obj = AutoProcessor.from_pretrained(QWEN_VL_MODEL, trust_remote_code=True)
            model_obj.eval()

            _qwen_model = model_obj
            _qwen_processor = processor_obj
            _qwen_runtime_device = _infer_qwen_runtime_device(model_obj)
            _qwen_runtime_error = None
            _qwen_quantization = quantization
            return _qwen_model, _qwen_processor
        except Exception as exc:
            _qwen_runtime_error = str(exc)[:800]
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


def _qwen_describe_image(img: Image.Image) -> Dict[str, Any]:
    model_obj, processor_obj = _ensure_qwen_model_loaded()

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

    with torch.no_grad():
        output_ids = model_obj.generate(
            **inputs,
            max_new_tokens=QWEN_VL_MAX_NEW_TOKENS,
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
        "face_runtime_providers": runtime_providers,
        "face_detection_runtime_providers": detection_runtime_providers,
        "face_runtime_warning": runtime_warning,
        "face_ctx_id": FACE_CTX_ID if runtime_face_device == "cuda" else -1,
        "face_detection_available": face_detection_available,
        "face_cuda_init_errors": face_cuda_init_errors,
        "face_detection_error": face_detection_error,
        "qwen_model": QWEN_VL_MODEL,
        "qwen_loaded": bool(_qwen_model is not None and _qwen_processor is not None),
        "qwen_device": _qwen_runtime_device,
        "qwen_quantization": _qwen_quantization,
        "qwen_4bit_enabled": QWEN_VL_ENABLE_4BIT,
        "qwen_max_new_tokens": QWEN_VL_MAX_NEW_TOKENS,
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


@app.post("/faces/detect")
def detect_faces(file: UploadFile = File(...)):
    if not face_detection_available or face_app is None:
        raise HTTPException(status_code=503, detail="Face detection model unavailable")

    data = file.file.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    # InsightFace expects numpy array in RGB (H,W,C)
    img_np = np.array(img)
    faces = face_app.get(img_np)

    out = []
    for f in faces:
        bbox = [float(x) for x in f.bbox.tolist()] if hasattr(f.bbox, 'tolist') else [float(x) for x in f.bbox]
        kps = f.kps.tolist() if hasattr(f.kps, 'tolist') else [[float(x) for x in p] for p in f.kps]
        emb = f.normed_embedding if hasattr(f, 'normed_embedding') and f.normed_embedding is not None else f.embedding
        if hasattr(emb, 'tolist'):
            emb = emb.tolist()
        # Ensure float32 and unit length
        v = np.asarray(emb, dtype=np.float32).ravel()
        n = float(np.linalg.norm(v)) or 1.0
        v = (v / n).astype(np.float32)
        conf = float(getattr(f, 'det_score', 1.0))
        out.append({
            "bbox": bbox,  # [x1,y1,x2,y2]
            "landmarks": kps,  # 5 keypoints
            "embedding": v.tolist(),
            "confidence": conf,
        })
    return {"ok": True, "count": len(out), "faces": out}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
