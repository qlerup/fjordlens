import io
import os
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import insightface
import numpy as np
import open_clip
import torch
import uvicorn
from PIL import Image

try:
    import onnxruntime as ort
except Exception:
    ort = None

try:
    # Enable HEIC/HEIF decoding when the wheel is available
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:
    pass

MODEL_NAME = os.environ.get("CLIP_MODEL", "ViT-B-32")
MODEL_PRETRAINED = os.environ.get("CLIP_PRETRAINED", "openai")
DEVICE_PREF = str(os.environ.get("AI_DEVICE", "auto") or "auto").strip().lower()
if DEVICE_PREF not in {"auto", "cpu", "cuda"}:
    DEVICE_PREF = "auto"

TORCH_CUDA_AVAILABLE = bool(torch.cuda.is_available())
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


def _build_face_analysis(preferred_providers: list[str], ctx_id: int):
    """Create and prepare FaceAnalysis with best-effort provider support details."""
    providers_kw_supported = True
    try:
        app_obj = insightface.app.FaceAnalysis(name="buffalo_l", providers=preferred_providers)
    except TypeError:
        # Older insightface versions may not expose providers kwarg.
        providers_kw_supported = False
        app_obj = insightface.app.FaceAnalysis(name="buffalo_l")

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

# Load model at startup
model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=MODEL_PRETRAINED, device=DEVICE)
tokenizer = open_clip.get_tokenizer(MODEL_NAME)
model.eval()

# Load InsightFace for face detection/recognition
face_app = None
face_detection_available = False
face_detection_error = None
face_device = FACE_DEVICE_CONFIGURED
face_providers_kw_supported = None
if FACE_USE_CUDA:
    cuda_init_errors: list[str] = []
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
            cuda_init_errors.append(f"{label}:{exc}")

    if not face_detection_available:
        # Explicit CPU fallback with retained reason for diagnostics.
        try:
            app_obj, kw_supported, _ = _build_face_analysis(["CPUExecutionProvider"], ctx_id=-1)
            face_app = app_obj
            face_detection_available = True
            face_device = "cpu"
            face_providers_kw_supported = bool(kw_supported)
            face_detection_error = "cuda_init_failed: " + " | ".join(cuda_init_errors)
        except Exception as exc2:
            face_detection_error = "cuda_init_failed: " + " | ".join(cuda_init_errors) + f"; cpu_fallback_failed: {exc2}"
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
        "device": DEVICE,
        "device_preference": DEVICE_PREF,
        "torch_version": str(getattr(torch, "__version__", "")),
        "torch_cuda_version": str(getattr(torch.version, "cuda", "")),
        "torch_cuda_available": TORCH_CUDA_AVAILABLE,
        "model": MODEL_NAME,
        "pretrained": MODEL_PRETRAINED,
        "onnx_available_providers": ONNX_AVAILABLE_PROVIDERS,
        "face_device": runtime_face_device,
        "face_device_configured": FACE_DEVICE_CONFIGURED,
        "face_providers_kw_supported": face_providers_kw_supported,
        "face_provider_chain": FACE_PROVIDER_CHAIN,
        "face_runtime_providers": runtime_providers,
        "face_detection_runtime_providers": detection_runtime_providers,
        "face_runtime_warning": runtime_warning,
        "face_ctx_id": FACE_CTX_ID if runtime_face_device == "cuda" else -1,
        "face_detection_available": face_detection_available,
        "face_detection_error": face_detection_error,
    }


@app.post("/embed/text", response_model=EmbedOut)
def embed_text(payload: TextIn):
    with torch.no_grad():
        tokens = tokenizer([payload.text]).to(DEVICE)
        text_features = model.encode_text(tokens)
        return {"embedding": _to_list(text_features)}


@app.post("/embed/image", response_model=EmbedOut)
def embed_image(file: UploadFile = File(...)):
    data = file.file.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = preprocess(img).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        image_features = model.encode_image(img)
        return {"embedding": _to_list(image_features)}


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
