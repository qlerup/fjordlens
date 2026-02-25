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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
