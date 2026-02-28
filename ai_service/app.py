import io
import os
from typing import List

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import torch
import numpy as np
from PIL import Image
import open_clip
import insightface
import numpy as np
try:
    # Enable HEIC/HEIF decoding when the wheel is available
    from pillow_heif import register_heif_opener  # type: ignore
    register_heif_opener()
except Exception:
    pass

MODEL_NAME = os.environ.get("CLIP_MODEL", "ViT-B-32")
MODEL_PRETRAINED = os.environ.get("CLIP_PRETRAINED", "openai")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

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

# Load InsightFace for face detection/recognition (CPU by default)
face_app = insightface.app.FaceAnalysis(name='buffalo_l')
try:
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
except Exception:
    # Fallback without det_size if necessary
    face_app.prepare(ctx_id=-1)


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
    return {"ok": True, "device": DEVICE, "model": MODEL_NAME, "pretrained": MODEL_PRETRAINED}


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
