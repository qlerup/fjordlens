import hashlib
import shutil
import subprocess
import tempfile
import re
import hmac
import secrets
import io
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_from_directory, redirect, url_for, make_response, session
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import threading
from PIL import Image, ExifTags, ImageOps
import piexif
import exifread
import requests
import reverse_geocoder as rg
import pycountry
import pyotp
import qrcode
import base64
import queue
try:
    # Enable HEIC/HEIF support via pillow-heif if available
    from pillow_heif import register_heif_opener, HeifFile  # type: ignore
    register_heif_opener()
except Exception:
    pass
from urllib.parse import quote, urlparse, urlunparse
from werkzeug.utils import secure_filename

APP_PORT = 8080
# Define DATA_DIR first so PHOTO_DIR can default inside it for uploads-only setups
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
# If PHOTO_DIR is not set, default to a library folder inside DATA_DIR so no external mount is required
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", str(DATA_DIR / "library"))).resolve()
THUMB_DIR = DATA_DIR / "thumbs"
CONVERT_DIR = DATA_DIR / "converted"
UPLOAD_DIR = DATA_DIR / "uploads"
TUS_TMP_DIR = DATA_DIR / "tus_uploads"
DB_PATH = DATA_DIR / "fjordlens.db"
AI_URL = os.environ.get("AI_URL", "http://localhost:8001").rstrip("/")
SHARE_DUCKDNS_BASE_URL = str(os.environ.get("SHARE_DUCKDNS_BASE_URL", "")).strip()
AI_ENV_ENABLED_DEFAULT = (os.environ.get("AI_ENABLED", "1") not in {"0", "false", "False"})
AI_ENV_AUTO_INGEST_DEFAULT = (os.environ.get("AI_AUTO_INGEST", "0") in {"1", "true", "True"})
AI_DESC_ENV_AUTO_INGEST_DEFAULT = (os.environ.get("AI_DESC_AUTO_INGEST", "0") in {"1", "true", "True"})
FACES_ENV_AUTO_INDEX_DEFAULT = (os.environ.get("FACES_AUTO_INDEX", "0") in {"1", "true", "True"})
HEIC_CONVERT_ON_UPLOAD_DEFAULT = (os.environ.get("HEIC_CONVERT_ON_UPLOAD", "0") in {"1", "true", "True"})
UPLOAD_DEST_UPLOADS = "uploads"
UPLOAD_DEST_LIBRARY = "library"
UPLOAD_DEST_DEFAULT = UPLOAD_DEST_UPLOADS
UPLOAD_DEST_CHOICES = {UPLOAD_DEST_UPLOADS, UPLOAD_DEST_LIBRARY}
LANG_DA = "da"
LANG_EN = "en"
LANG_CHOICES = {LANG_DA, LANG_EN}
DEFAULT_UI_LANGUAGE = LANG_DA
DEFAULT_SEARCH_LANGUAGE = LANG_DA
TEMPLATE_I18N: Dict[str, Dict[str, str]] = {
    LANG_DA: {
        "login_invalid_credentials": "Forkert brugernavn eller adgangskode",
        "setup_invalid_token": "Forkert setup-token",
        "setup_fill_fields": "Udfyld felterne",
        "setup_password_mismatch": "Adgangskoder matcher ikke",
        "invalid_code": "Ugyldig kode",
        "share_invalid_or_expired": "Share link er ugyldigt eller udløbet.",
        "admin_user_created": "Bruger oprettet",
        "admin_cannot_delete_self": "Du kan ikke slette din egen bruger",
        "admin_user_not_found": "Bruger findes ikke",
        "admin_cannot_delete_last_admin": "Kan ikke slette den sidste admin",
        "admin_user_deleted": "Bruger slettet",
        "error_prefix": "Fejl:",
    },
    LANG_EN: {
        "login_invalid_credentials": "Invalid username or password",
        "setup_invalid_token": "Invalid setup token",
        "setup_fill_fields": "Please fill in all required fields",
        "setup_password_mismatch": "Passwords do not match",
        "invalid_code": "Invalid code",
        "share_invalid_or_expired": "Share link is invalid or expired.",
        "admin_user_created": "User created",
        "admin_cannot_delete_self": "You cannot delete your own user",
        "admin_user_not_found": "User not found",
        "admin_cannot_delete_last_admin": "Cannot delete the last admin",
        "admin_user_deleted": "User deleted",
        "error_prefix": "Error:",
    },
}
UPLOAD_DEFAULT_SUBDIR_BY_DEST = {
    UPLOAD_DEST_UPLOADS: "",
    UPLOAD_DEST_LIBRARY: "Photos",
}
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.5"))
VIDEO_FACE_SAMPLE_INTERVAL_SEC = float(os.environ.get("VIDEO_FACE_SAMPLE_INTERVAL_SEC", "3.0"))
VIDEO_FACE_SAMPLE_MAX_FRAMES = int(os.environ.get("VIDEO_FACE_SAMPLE_MAX_FRAMES", "24"))
VIDEO_FACE_SAMPLE_START_SEC = float(os.environ.get("VIDEO_FACE_SAMPLE_START_SEC", "0.5"))
VIDEO_FACE_DEDUPE_THRESHOLD = float(os.environ.get("VIDEO_FACE_DEDUPE_THRESHOLD", "0.92"))
AI_INGEST_THROTTLE_SEC = max(0.0, float(os.environ.get("AI_INGEST_THROTTLE_SEC", "0.04")))
FACES_INDEX_THROTTLE_SEC = max(0.0, float(os.environ.get("FACES_INDEX_THROTTLE_SEC", "0.06")))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
THUMB_SIZE = (600, 600)
PHASH_MATCH_THRESHOLD = int(os.environ.get("PHASH_MATCH_THRESHOLD", "8"))
GEOCODE_ENABLE = os.environ.get("GEOCODE_ENABLE", "1") not in {"0", "false", "False"}
GEOCODE_EMAIL = os.environ.get("GEOCODE_EMAIL", "fjordlens@example.com")
GEOCODE_TIMEOUT = int(os.environ.get("GEOCODE_TIMEOUT", "12"))
GEOCODE_RETRIES = int(os.environ.get("GEOCODE_RETRIES", "3"))
GEOCODE_DELAY = float(os.environ.get("GEOCODE_DELAY", "1.0"))  # courteous delay per request
GEOCODE_PROVIDER = os.environ.get("GEOCODE_PROVIDER", "rg").strip().lower()
GEOCODE_LANG = os.environ.get("GEOCODE_LANG", "da").strip().lower()


app = Flask(__name__)
APP_BUILD_ID = int(time.time())


def _normalize_lang(value: Optional[str], default: str = LANG_DA) -> str:
    v = str(value or "").strip().lower()
    return v if v in LANG_CHOICES else default


def _request_ui_language() -> str:
    try:
        if getattr(current_user, "is_authenticated", False):
            return _normalize_lang(getattr(current_user, "ui_language", None), LANG_DA)
    except Exception:
        pass
    raw = str(request.headers.get("Accept-Language") or "")
    for part in raw.split(","):
        code = part.split(";", 1)[0].strip().lower()
        if code.startswith("en"):
            return LANG_EN
        if code.startswith("da"):
            return LANG_DA
    return LANG_DA


def _ui_text(key: str, lang: Optional[str] = None) -> str:
    chosen = _normalize_lang(lang or _request_ui_language(), LANG_DA)
    return TEMPLATE_I18N.get(chosen, TEMPLATE_I18N[LANG_DA]).get(key, TEMPLATE_I18N[LANG_DA].get(key, key))


@app.context_processor
def inject_template_i18n():
    lang = _request_ui_language()
    return {
        "ui_lang": lang,
        "tt": lambda key: _ui_text(str(key), lang),
        "app_build": APP_BUILD_ID,
    }

# --- Console color support (for Windows terminals and Docker logs) ---
ANSI_RESET = "\033[0m"
ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RED = "\033[91m"
ANSI_DIM = "\033[90m"

def _enable_windows_ansi() -> None:
    try:
        if os.name == "nt":
            import ctypes  # type: ignore
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        # Best-effort only; ignore if not a real console
        pass

_enable_windows_ansi()

def _classify_log_level(event: str, data: Dict[str, Any]) -> str:
    ev = (event or "").lower()
    if data.get("error") or ev == "error" or ev.endswith("_error") or ev.endswith("_fail") or ev == "ai_http_error":
        return "err"
    if ev in {"skip_unchanged", "no_new", "missing"} or ev.endswith("_check") or ("retry" in ev) or ("skip" in ev):
        return "warn"
    if ev.endswith("_done") or ev.endswith("_saved") or ev.endswith("_ok") or ev in {"indexed", "faces_detect", "faces_index_done", "face_saved", "upload_indexed", "rethumb_ok"}:
        return "ok"
    return "info"


def _get_secret_key() -> bytes:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        try:
            return env_key.encode("utf-8")
        except Exception:
            pass
    key_file = DATA_DIR / "secret.key"
    try:
        if key_file.exists():
            return key_file.read_bytes().strip()
        # First run: create a persistent key so multiple workers share it
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key = os.urandom(32)
        key_file.write_bytes(key)
        return key
    except Exception:
        # Last-resort deterministic fallback to avoid per-process randomness
        return b"fjordlens-dev-secret-key"


app.secret_key = _get_secret_key()

login_manager = LoginManager(app)
login_manager.login_view = "login"

# Global scan control
scan_stop_event = threading.Event()

# Simple in-memory log buffer for UI polling
from collections import deque
LOG_BUFFER: deque[Dict[str, Any]] = deque(maxlen=1000)
LOG_SEQ: int = 0
UPLOAD_PENDING_BY_USER: Dict[str, list[str]] = {}
UPLOAD_PENDING_LOCK = threading.Lock()
UPLOAD_POSTPROCESS_BY_USER: Dict[str, Dict[str, Any]] = {}
UPLOAD_POSTPROCESS_LOCK = threading.Lock()


def log_event(event: str, **data: Any) -> None:
    global LOG_SEQ
    LOG_SEQ += 1
    t = now_iso()
    LOG_BUFFER.append({"id": LOG_SEQ, "t": t, "event": event, **data})
    # Console output with colors and proper newlines
    try:
        lvl = _classify_log_level(event, data)
        color = ANSI_DIM
        if lvl == "ok":
            color = ANSI_GREEN
        elif lvl == "warn":
            color = ANSI_YELLOW
        elif lvl == "err":
            color = ANSI_RED
        # Compact key=value payload
        parts = []
        for k, v in data.items():
            if v is None:
                continue
            try:
                if isinstance(v, (dict, list)):
                    sv = json.dumps(v, ensure_ascii=False)
                else:
                    sv = str(v)
            except Exception:
                sv = str(v)
            # keep lines readable
            if len(sv) > 300:
                sv = sv[:297] + "..."
            parts.append(f"{k}={sv}")
        extra = (" " + " ".join(parts)) if parts else ""
        print(f"{color}[{t}] {event}{extra}{ANSI_RESET}")
    except Exception:
        # Never let console formatting break logging
        pass


# --- AI helpers (CLIP service) ---
def _ai_health() -> dict:
    try:
        r = requests.get(f"{AI_URL}/health", timeout=5)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {"ok": False}


def _ai_embed_text(text: str) -> Optional[list[float]]:
    try:
        r = requests.post(f"{AI_URL}/embed/text", json={"text": text}, timeout=20)
        if r.ok:
            return r.json().get("embedding")
    except Exception:
        pass
    return None


def _ai_embed_image_path(path: Path) -> Optional[list[float]]:
    try:
        # Use a browser/AI-friendly copy for HEIC/HEIF
        rel_guess = None
        try:
            rel_guess = str(path.relative_to(PHOTO_DIR)).replace("\\", "/")
        except Exception:
            rel_guess = path.name
        ai_src = ensure_viewable_copy(path, rel_guess)
        with ai_src.open("rb") as f:
            # Use generic content-type to avoid server rejections
            files = {"file": (ai_src.name, f, "application/octet-stream")}
            r = requests.post(f"{AI_URL}/embed/image", files=files, timeout=60)
        if r.ok:
            try:
                return r.json().get("embedding")
            except Exception as e:
                log_event("ai_http_error", rel_path=str(path), error=f"json:{e}")
        else:
            log_event("ai_http_error", rel_path=str(path), error=f"status:{r.status_code}")
    except Exception as e:
        log_event("ai_http_error", rel_path=str(path), error=str(e))
    return None


def _ai_detect_faces_path(path: Path) -> Optional[list[Dict[str, Any]]]:
    """Send a viewable copy of the image to AI service for face detection/embeddings."""
    try:
        rel_guess = None
        try:
            rel_guess = str(path.relative_to(PHOTO_DIR)).replace("\\", "/")
        except Exception:
            rel_guess = path.name
        ai_src = ensure_viewable_copy(path, rel_guess)
        with ai_src.open("rb") as f:
            files = {"file": (ai_src.name, f, "application/octet-stream")}
            r = requests.post(f"{AI_URL}/faces/detect", files=files, timeout=90)
        if r.ok:
            js = r.json() or {}
            if js.get("ok") and isinstance(js.get("faces"), list):
                return js.get("faces")
    except Exception as e:
        log_event("error", rel_path=str(path), error=f"ai_faces: {e}")
    return None


def _ai_detect_faces_bytes(data: bytes, filename: str = "frame.jpg") -> Optional[list[Dict[str, Any]]]:
    """Send image bytes to AI service for face detection/embeddings."""
    try:
        files = {"file": (filename, data, "application/octet-stream")}
        r = requests.post(f"{AI_URL}/faces/detect", files=files, timeout=90)
        if r.ok:
            js = r.json() or {}
            if js.get("ok") and isinstance(js.get("faces"), list):
                return js.get("faces")
        else:
            log_event("ai_http_error", file=filename, error=f"status:{r.status_code}")
    except Exception as e:
        log_event("error", file=filename, error=f"ai_faces_bytes: {e}")
    return None


def _video_duration_seconds(path: Path) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        r = subprocess.run(cmd, check=True, capture_output=True, text=True)
        val = float((r.stdout or "").strip())
        return val if val > 0 else None
    except Exception:
        return None


def _video_face_sample_timestamps(path: Path, rel_path: str) -> tuple[Optional[float], list[float]]:
    """Build sampling timestamps for video face detection."""
    duration = _video_duration_seconds(path)
    start = max(0.0, VIDEO_FACE_SAMPLE_START_SEC)
    interval = max(0.5, VIDEO_FACE_SAMPLE_INTERVAL_SEC)
    max_frames = max(1, VIDEO_FACE_SAMPLE_MAX_FRAMES)

    if not duration:
        ts = [start]
        log_event("faces_video_sampling", rel_path=rel_path, duration=None, samples=ts)
        return None, ts

    ts: list[float] = []
    t = start
    while t < duration and len(ts) < max_frames:
        ts.append(round(t, 3))
        t += interval

    if not ts:
        fallback = max(0.0, min(start, duration * 0.5))
        ts = [round(fallback, 3)]

    tail = max(0.0, duration - 0.2)
    if len(ts) < max_frames and tail > ts[-1] + (interval * 0.5):
        ts.append(round(tail, 3))

    log_event("faces_video_sampling", rel_path=rel_path, duration=round(duration, 2), sample_count=len(ts), samples=ts)
    return duration, ts


def _extract_video_frame_bytes(path: Path, rel_path: str, at_sec: float) -> Optional[bytes]:
    """Extract one JPEG frame from video at a timestamp."""
    try:
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "face_frame.jpg"
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", f"{at_sec:.3f}", "-i", str(path),
                "-frames:v", "1",
                "-q:v", "3",
                str(out_path),
            ]
            subprocess.run(cmd, check=True)
            if out_path.exists():
                return out_path.read_bytes()
    except Exception as e:
        log_event("faces_video_frame_fail", rel_path=rel_path, at_sec=round(at_sec, 2), error=str(e))
    return None


def _dedupe_faces_by_embedding(faces: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Remove repeated detections of the same person across nearby video frames."""
    if not faces:
        return []
    thr = max(0.0, min(1.0, VIDEO_FACE_DEDUPE_THRESHOLD))
    ranked = sorted(faces, key=lambda f: float(f.get("confidence") or 0.0), reverse=True)
    kept: list[Dict[str, Any]] = []
    kept_embs: list[list[float]] = []
    for fc in ranked:
        emb = fc.get("embedding") or []
        if not emb:
            kept.append(fc)
            continue
        duplicate = False
        for ref in kept_embs:
            if _cosine(emb, ref) >= thr:
                duplicate = True
                break
        if duplicate:
            continue
        kept.append(fc)
        kept_embs.append(emb)
    return kept


def _ai_detect_faces_video_path(path: Path, rel_path: str) -> list[Dict[str, Any]]:
    """Detect faces from sampled video frames and return deduplicated detections."""
    _, timestamps = _video_face_sample_timestamps(path, rel_path)
    all_faces: list[Dict[str, Any]] = []
    frames_ok = 0
    for sec in timestamps:
        frame_bytes = _extract_video_frame_bytes(path, rel_path, sec)
        if not frame_bytes:
            continue
        frames_ok += 1
        faces = _ai_detect_faces_bytes(frame_bytes, filename=f"{path.stem}_t{sec:.2f}.jpg") or []
        log_event("faces_video_frame_detect", rel_path=rel_path, at_sec=round(sec, 2), count=len(faces))
        for fc in faces:
            if isinstance(fc, dict):
                fc["frame_sec"] = sec
                all_faces.append(fc)
    unique_faces = _dedupe_faces_by_embedding(all_faces)
    log_event(
        "faces_video_detect_done",
        rel_path=rel_path,
        sampled_frames=len(timestamps),
        decoded_frames=frames_ok,
        faces_total=len(all_faces),
        faces_unique=len(unique_faces),
    )
    return unique_faces


def _find_or_create_person_id(conn: sqlite3.Connection, emb: list[float]) -> tuple[int, bool, float]:
    """Return (person_id, created_new, score). Find best match by cosine; create 'Ukendt-#' if below threshold."""
    best_pid: Optional[int] = None
    best_score = -1.0
    try:
        rows = conn.execute("SELECT id, embedding_json, person_id FROM faces WHERE embedding_json IS NOT NULL").fetchall()
        for row in rows:
            try:
                vec = json.loads(row["embedding_json"]) if row["embedding_json"] else None
            except Exception:
                vec = None
            if not vec:
                continue
            sc = _cosine(emb, vec)
            if sc > best_score:
                best_score = sc
                best_pid = row["person_id"]
    except Exception:
        best_pid = None
        best_score = -1.0

    if best_pid is not None and best_score >= FACE_MATCH_THRESHOLD:
        return int(best_pid), False, float(best_score)

    # Create a new 'unknown' person with unique name
    base = "Ukendt"
    i = 1
    while True:
        name = f"{base}-{i}"
        try:
            cur = conn.execute("INSERT INTO people(name, created_at) VALUES(?,?)", (name, now_iso()))
            conn.commit()
            lr = getattr(cur, "lastrowid", None)
            pid_new = int(lr) if lr is not None else int(conn.execute("SELECT id FROM people WHERE name=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()["id"])
            return pid_new, True, float(best_score)
        except Exception:
            i += 1


def index_faces_for_photo(rel_path: str) -> int:
    """Detect faces for a photo/video and store into DB; updates people_count."""
    try:
        disk_path = _disk_path_from_rel_path(rel_path)
        if not disk_path.exists():
            return 0
        log_event("faces_index_start", rel_path=rel_path)
        is_video = disk_path.suffix.lower() in VIDEO_EXTS
        if is_video:
            faces = _ai_detect_faces_video_path(disk_path, rel_path)
            log_event("faces_detect", rel_path=rel_path, media="video", count=len(faces))
        else:
            faces = _ai_detect_faces_path(disk_path) or []
            log_event("faces_detect", rel_path=rel_path, media="image", count=len(faces))
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id, metadata_json FROM photos WHERE rel_path=?", (rel_path,)).fetchone()
            if not row:
                return 0
            photo_id = int(row["id"])
            # Clear previous faces for this photo (re-index)
            try:
                conn.execute("DELETE FROM faces WHERE photo_id=?", (photo_id,))
                conn.commit()
            except Exception:
                pass
            count = 0
            created_new = 0
            matched_existing = 0
            for fc in faces:
                emb = fc.get("embedding") or []
                bbox = fc.get("bbox") or [0, 0, 0, 0]
                try:
                    x1, y1, x2, y2 = [int(round(float(v))) for v in bbox]
                    bx, by = max(0, x1), max(0, y1)
                    bw, bh = max(0, x2 - x1), max(0, y2 - y1)
                except Exception:
                    bx = by = bw = bh = 0
                try:
                    if emb:
                        pid, created, score = _find_or_create_person_id(conn, emb)
                        if created:
                            created_new += 1
                        else:
                            matched_existing += 1
                    else:
                        pid, created, score = (None, False, -1.0)
                except Exception:
                    pid, created, score = (None, False, -1.0)
                try:
                    conn.execute(
                        """
                        INSERT INTO faces(photo_id, person_id, bbox_x, bbox_y, bbox_w, bbox_h, embedding_json, confidence, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            photo_id,
                            pid,
                            bx, by, bw, bh,
                            json.dumps(emb, ensure_ascii=False),
                            float(fc.get("confidence") or 1.0),
                            now_iso(),
                        ),
                    )
                    count += 1
                    log_event(
                        "face_saved",
                        rel_path=rel_path,
                        photo_id=photo_id,
                        person_id=pid,
                        bbox=[bx, by, bw, bh],
                        score=score,
                        frame_sec=fc.get("frame_sec"),
                    )
                except Exception as e:
                    log_event("error", rel_path=rel_path, error=f"face_insert: {e}")
            try:
                conn.execute("UPDATE photos SET people_count=? WHERE id=?", (count, photo_id))
                conn.commit()
            except Exception:
                pass
            log_event("faces_index_done", rel_path=rel_path, faces=count, matched=matched_existing, created=created_new)
            return int(count)
    except Exception as e:
        log_event("error", rel_path=rel_path, error=f"index_faces_for_photo: {e}")
        return 0


# Zero-shot labels (initial simple vocabulary; can expand/customize later)
AI_LABELS: list[str] = [
    "person", "man", "woman", "child", "baby",
    "dog", "cat", "bird", "horse",
    "car", "bicycle", "motorcycle", "bus", "train", "boat", "airplane",
    "tree", "flower", "sky", "clouds", "sunset", "beach", "sea", "mountain", "snow", "forest", "city", "building", "house", "road", "street", "lake", "river",
    "food", "cake", "pizza", "drink", "coffee", "beer", "wine",
    "phone", "laptop", "computer", "keyboard", "book", "document",
    "lamp", "chair", "table", "bed", "sofa",
]
_LABEL_VECS: Optional[list[list[float]]] = None


def _ensure_label_vecs() -> list[list[float]]:
    global _LABEL_VECS
    if _LABEL_VECS is not None:
        return _LABEL_VECS
    vecs: list[list[float]] = []
    for t in AI_LABELS:
        v = _ai_embed_text(t)
        if v:
            vecs.append(v)
        else:
            vecs.append([0.0])
    _LABEL_VECS = vecs
    return vecs


def _classify_labels(img_vec: list[float], top_k: int = 5, thr: float = 0.24) -> list[str]:
    try:
        label_vecs = _ensure_label_vecs()
        scores = []
        for idx, lv in enumerate(label_vecs):
            sc = _cosine(img_vec, lv)
            scores.append((sc, idx))
        scores.sort(key=lambda x: x[0], reverse=True)
        out: list[str] = []
        for sc, idx in scores[: top_k * 2]:  # check a bit wider then filter by thr
            if sc >= thr:
                out.append(AI_LABELS[idx])
            if len(out) >= top_k:
                break
        return out
    except Exception:
        return []


AI_DESC_PROMPTS: list[Dict[str, Any]] = [
    {"prompt": "people swimming in water", "tags": ["personer", "svømning", "vand"]},
    {"prompt": "a person swimming at the beach", "tags": ["personer", "svømning", "strand"]},
    {"prompt": "a person running outdoors", "tags": ["personer", "løb", "udendørs"]},
    {"prompt": "a person riding a bicycle", "tags": ["personer", "cykling"]},
    {"prompt": "people hiking in nature", "tags": ["personer", "natur", "vandring"]},
    {"prompt": "a family having dinner", "tags": ["familie", "mad"]},
    {"prompt": "people on a beach", "tags": ["personer", "strand"]},
    {"prompt": "a person in the sea", "tags": ["personer", "hav", "vand"]},
    {"prompt": "an indoor photo", "tags": ["indendørs"]},
    {"prompt": "an outdoor photo", "tags": ["udendørs"]},
]
_DESC_PROMPT_VECS: Optional[list[Tuple[str, list[str], list[float]]]] = None


def _ensure_desc_prompt_vecs() -> list[Tuple[str, list[str], list[float]]]:
    global _DESC_PROMPT_VECS
    if _DESC_PROMPT_VECS is not None:
        return _DESC_PROMPT_VECS
    vecs: list[Tuple[str, list[str], list[float]]] = []
    for item in AI_DESC_PROMPTS:
        prompt = str(item.get("prompt") or "").strip()
        tags = [str(t).strip().lower() for t in (item.get("tags") or []) if str(t).strip()]
        if not prompt or not tags:
            continue
        v = _ai_embed_text(prompt)
        if v:
            vecs.append((prompt, tags, v))
    _DESC_PROMPT_VECS = vecs
    return vecs


def _classify_descriptive_tags(img_vec: list[float], top_k: int = 6, thr: float = 0.235) -> list[str]:
    try:
        prompt_vecs = _ensure_desc_prompt_vecs()
        if not prompt_vecs:
            return []
        scored: list[Tuple[float, list[str]]] = []
        for _, tags, vec in prompt_vecs:
            scored.append((_cosine(img_vec, vec), tags))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[str] = []
        seen: set[str] = set()
        for score, tags in scored:
            if score < thr:
                continue
            for tag in tags:
                t = str(tag or "").strip().lower()
                if not t or t in seen:
                    continue
                seen.add(t)
                out.append(t)
                if len(out) >= top_k:
                    return out
        return out
    except Exception:
        return []


def _build_desc_caption(tags: list[str]) -> Optional[str]:
    vals = [str(t or "").strip().lower() for t in (tags or []) if str(t or "").strip()]
    if not vals:
        return None
    s = set(vals)
    if "personer" in s and "svømning" in s:
        if "strand" in s:
            return "personer der svømmer på stranden"
        if "hav" in s:
            return "personer der svømmer i havet"
        return "personer der svømmer"
    return ", ".join(vals[:4])


# --- 2FA trust helpers ---
def _ua_fingerprint() -> str:
    ua = (request.headers.get("User-Agent") or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(ua).hexdigest()[:16]


def _sign_token(raw: str) -> str:
    key = app.secret_key if isinstance(app.secret_key, (bytes, bytearray)) else str(app.secret_key).encode()
    return hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_trust_cookie(user_id: int, days: int) -> tuple[str, int]:
    if days <= 0:
        return ("", 0)
    now = int(time.time())
    exp = now + days * 86400
    fp = _ua_fingerprint()
    payload = f"{user_id}.{exp}.{fp}"
    sig = _sign_token(payload)
    token = f"{payload}.{sig}"
    return (token, exp - now)


def _parse_trust_cookie(val: str) -> Optional[dict]:
    try:
        user_s, exp_s, fp, sig = val.split(".", 3)
        raw = f"{user_s}.{exp_s}.{fp}"
        if _sign_token(raw) != sig:
            return None
        exp = int(exp_s)
        if exp < int(time.time()):
            return None
        return {"user_id": int(user_s), "exp": exp, "fp": fp}
    except Exception:
        return None


def _trust_cookie_valid_for(user_id: int) -> bool:
    val = request.cookies.get("fl_trust")
    if not val:
        return False
    data = _parse_trust_cookie(val)
    if not data:
        return False
    if data["user_id"] != int(user_id):
        return False
    if data.get("fp") != _ua_fingerprint():
        return False
    return True


class User(UserMixin):
    def __init__(
        self,
        id: int,
        username: str,
        role: Optional[str] = None,
        is_admin_fallback: Optional[bool] = None,
        ui_language: Optional[str] = None,
        search_language: Optional[str] = None,
    ):
        self.id = str(id)
        self.username = username
        role_norm = (role or ("admin" if is_admin_fallback else "user") or "user").strip().lower()
        if role_norm not in {"admin", "manager", "user"}:
            role_norm = "user"
        self.role = role_norm
        self.ui_language = _normalize_language(ui_language, DEFAULT_UI_LANGUAGE)
        self.search_language = _normalize_language(search_language, DEFAULT_SEARCH_LANGUAGE)

    @property
    def is_admin(self) -> bool:
        return (getattr(self, "role", "user") == "admin")

    @property
    def is_manager(self) -> bool:
        return (getattr(self, "role", "user") == "manager")

    def can_manage_users(self) -> bool:
        return self.is_admin

    def can_maintain(self) -> bool:
        return self.is_admin or self.is_manager


def _row_to_user(row: sqlite3.Row) -> Optional[User]:
    if not row:
        return None
    qr_url = None
    secret_out = None
    # if not enabled:  # (Uncomment and implement if needed)
    try:
        role = row["role"] if "role" in row.keys() else None
    except Exception:
        role = None
    try:
        ui_language = row["ui_language"] if "ui_language" in row.keys() else None
    except Exception:
        ui_language = None
    try:
        search_language = row["search_language"] if "search_language" in row.keys() else None
    except Exception:
        search_language = None
    is_admin_fallback = False
    try:
        is_admin_fallback = bool(row["is_admin"]) if "is_admin" in row.keys() else False
    except Exception:
        is_admin_fallback = False
    return User(int(row["id"]), row["username"], role, is_admin_fallback, ui_language, search_language)


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute(
                "SELECT id, username, is_admin, role, ui_language, search_language FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return _row_to_user(row)
    except Exception:
        return None


def users_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(row["c"]) if row else 0


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    CONVERT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TUS_TMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Canonical upload subfolders used by the app
        (UPLOAD_DIR / "originals").mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / "converted").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


# Note: We intentionally avoid creating folders on startup.
# Startup initialization is deferred to usage sites (e.g., first upload).


def _queue_uploaded_rel(uploaded_by: str, rel_path: str) -> None:
    user = str(uploaded_by or "").strip() or "__unknown__"
    rel = str(rel_path or "").strip()
    if not rel:
        return
    with UPLOAD_PENDING_LOCK:
        bucket = UPLOAD_PENDING_BY_USER.setdefault(user, [])
        bucket.append(rel)


def _is_upload_postprocess_running(uploaded_by: str) -> bool:
    user = str(uploaded_by or "").strip() or "__unknown__"
    with UPLOAD_POSTPROCESS_LOCK:
        st = UPLOAD_POSTPROCESS_BY_USER.get(user) or {}
        return bool(st.get("running"))


def _ensure_upload_postprocess_running(uploaded_by: str) -> bool:
    """Start per-user upload postprocess worker if it is not already running."""
    user = str(uploaded_by or "").strip() or "__unknown__"
    with UPLOAD_POSTPROCESS_LOCK:
        st = dict(UPLOAD_POSTPROCESS_BY_USER.get(user) or {})
        if bool(st.get("running")):
            return False
        st.update(
            {
                "running": True,
                "started_at": now_iso(),
                "finished_at": None,
                "error": None,
                "result": None,
                "phase": "starting",
                "current_rel": None,
                "stage_processed": 0,
                "stage_total": 0,
            }
        )
        UPLOAD_POSTPROCESS_BY_USER[user] = st

    rels = _pop_uploaded_rels(user)
    if not rels:
        _set_upload_postprocess_state(
            user,
            {
                "running": False,
                "phase": "idle",
                "finished_at": now_iso(),
            },
        )
        return False

    try:
        threading.Thread(target=_upload_postprocess_worker, args=(user, rels), daemon=True).start()
        return True
    except Exception as e:
        _set_upload_postprocess_state(
            user,
            {
                "running": False,
                "phase": "error",
                "error": f"Unable to start postprocess worker: {e}",
                "finished_at": now_iso(),
            },
        )
        return False


def _set_upload_postprocess_state(uploaded_by: str, patch: Dict[str, Any]) -> None:
    user = str(uploaded_by or "").strip() or "__unknown__"
    with UPLOAD_POSTPROCESS_LOCK:
        cur = dict(UPLOAD_POSTPROCESS_BY_USER.get(user) or {})
        cur.update(patch)
        UPLOAD_POSTPROCESS_BY_USER[user] = cur


def _get_upload_postprocess_state(uploaded_by: str) -> Dict[str, Any]:
    user = str(uploaded_by or "").strip() or "__unknown__"
    with UPLOAD_POSTPROCESS_LOCK:
        return dict(UPLOAD_POSTPROCESS_BY_USER.get(user) or {})


def _request_client_ip() -> str:
    try:
        cf = str(request.headers.get("CF-Connecting-IP") or "").strip()
        if cf:
            return cf
        xff = str(request.headers.get("X-Forwarded-For") or "").strip()
        if xff:
            return xff.split(",", 1)[0].strip()
    except Exception:
        pass
    try:
        return str(request.remote_addr or "").strip()
    except Exception:
        return ""


def _request_client_country() -> Optional[str]:
    code = str(request.headers.get("CF-IPCountry") or "").strip().upper()
    if not code or code in {"XX", "T1"}:
        return None
    try:
        obj = pycountry.countries.get(alpha_2=code)
        return str(getattr(obj, "name", None) or code)
    except Exception:
        return code


def _describe_device(user_agent: str) -> str:
    ua = str(user_agent or "").strip()
    if not ua:
        return "Unknown"
    s = ua.lower()
    if "iphone" in s:
        platform = "iPhone"
    elif "ipad" in s:
        platform = "iPad"
    elif "android" in s:
        platform = "Android"
    elif "windows" in s:
        platform = "Windows"
    elif "mac os" in s or "macintosh" in s:
        platform = "macOS"
    elif "linux" in s:
        platform = "Linux"
    else:
        platform = "Unknown OS"

    if "edg/" in s:
        browser = "Edge"
    elif "chrome/" in s and "edg/" not in s:
        browser = "Chrome"
    elif "firefox/" in s:
        browser = "Firefox"
    elif "safari/" in s and "chrome/" not in s:
        browser = "Safari"
    else:
        browser = "Unknown browser"

    return f"{browser} on {platform}"


def _log_login_attempt(
    username_input: str,
    user_id: Optional[int],
    username_resolved: Optional[str],
    success: bool,
    event_type: str,
    reason: str,
) -> None:
    try:
        ip = _request_client_ip()[:80]
        ua = str(request.headers.get("User-Agent") or "").strip()[:500]
        device = _describe_device(ua)[:120]
        country = _request_client_country()
        with closing(get_conn()) as conn:
            conn.execute(
                """
                INSERT INTO login_audit(
                    at, username_input, user_id, username, success,
                    event_type, reason, ip, country, device, user_agent
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    now_iso(),
                    str(username_input or "")[:120],
                    int(user_id) if user_id is not None else None,
                    str(username_resolved or "")[:120] or None,
                    1 if success else 0,
                    str(event_type or "")[:50],
                    str(reason or "")[:120],
                    ip or None,
                    (str(country)[:120] if country else None),
                    device,
                    ua or None,
                ),
            )
            conn.commit()
    except Exception:
        pass


def _pop_uploaded_rels(uploaded_by: str) -> list[str]:
    user = str(uploaded_by or "").strip() or "__unknown__"
    with UPLOAD_PENDING_LOCK:
        rels = list(UPLOAD_PENDING_BY_USER.pop(user, []))
    out: list[str] = []
    seen: set[str] = set()
    for rel in rels:
        key = str(rel or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _postprocess_uploaded_rels(
    uploaded_by: str,
    rel_paths: list[str],
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    user = str(uploaded_by or "").strip()
    rels = []
    seen: set[str] = set()
    for rel in (rel_paths or []):
        key = str(rel or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        rels.append(key)

    faces_enabled = faces_auto_index_enabled()
    ai_enabled = ai_auto_ingest_enabled()
    ai_desc_enabled = ai_desc_auto_ingest_enabled()

    def _emit_progress(payload: Dict[str, Any]) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(payload)
        except Exception:
            pass

    _emit_progress({
        "phase": "metadata",
        "current_rel": None,
        "stage_processed": 0,
        "stage_total": len(rels),
    })

    indexed_ok: list[str] = []
    heic_converted_count = 0
    index_errors = 0
    for i, rel in enumerate(rels, start=1):
        _emit_progress({
            "phase": "metadata",
            "current_rel": rel,
            "stage_processed": i,
            "stage_total": len(rels),
        })
        disk_path = _disk_path_from_rel_path(rel)
        orig_rel_for_convert = rel
        # Optional: convert HEIC/HEIF to JPEG in-place (preserve EXIF when possible)
        try:
            if heic_convert_on_upload_enabled() and disk_path.suffix.lower() in {".heic", ".heif"} and disk_path.exists():
                new_rel = None
                new_path = None
                try:
                    with Image.open(disk_path) as himg:
                        try:
                            himg = ImageOps.exif_transpose(himg)
                        except Exception:
                            pass
                        rgb = himg.convert("RGB")
                        exif_bytes = None
                        try:
                            exif_bytes = himg.info.get("exif") or himg.getexif().tobytes()
                        except Exception:
                            exif_bytes = None
                        # Save converted copy under uploads/converted/<subdir>/
                        sub_rel = ""
                        try:
                            # rel is 'uploads/originals/<sub>/<file>' at this point
                            parts = str(orig_rel_for_convert).split("/", 2)
                            if len(parts) >= 3:
                                sub_rel = parts[2]  # '<sub>/<file>'
                            else:
                                sub_rel = Path(orig_rel_for_convert).name
                        except Exception:
                            sub_rel = Path(orig_rel_for_convert).name
                        subdir_only = str(Path(sub_rel).parent).replace("\\", "/").strip("./")
                        leaf_jpg = f"{Path(sub_rel).stem}.jpg"
                        conv_dir = UPLOAD_DIR / "converted" / (subdir_only if subdir_only != '.' else '')
                        conv_dir.mkdir(parents=True, exist_ok=True)
                        new_path = conv_dir / leaf_jpg
                        # Avoid clobbering existing .jpg — add numeric suffix
                        if new_path.exists():
                            stem = new_path.stem
                            parent = new_path.parent
                            i = 1
                            while True:
                                cand = parent / f"{stem}_{i}.jpg"
                                if not cand.exists():
                                    new_path = cand
                                    break
                                i += 1
                        save_kwargs = {"format": "JPEG", "quality": 92, "optimize": True}
                        if exif_bytes:
                            save_kwargs["exif"] = exif_bytes
                        rgb.save(new_path, **save_kwargs)
                    # Preserve timestamps
                    try:
                        st = disk_path.stat()
                        os.utime(new_path, (st.st_atime, st.st_mtime))
                    except Exception:
                        pass
                    # Switch rel/disk_path to the converted copy (optionally keep the original under 'originals')
                    if rel.startswith("uploads/originals/"):
                        # mirror to /uploads/converted/<...>.jpg
                        try:
                            tail = str(Path(sub_rel).with_suffix(".jpg")).replace("\\", "/")
                        except Exception:
                            tail = f"{Path(sub_rel).stem}.jpg"
                        new_rel = f"uploads/converted/{tail}"
                    else:
                        # Library fallback
                        try:
                            new_rel = str(Path(rel).with_suffix(".jpg")).replace("\\", "/")
                        except Exception:
                            new_rel = rel + ".jpg"
                    rel = new_rel
                    disk_path = new_path
                    try:
                        log_event("heic_converted", rel_path=rel)
                    except Exception:
                        pass
                    heic_converted_count += 1
                    # Remove any stub row created under the original HEIC rel (originals path)
                    try:
                        with closing(get_conn()) as conn:
                            conn.execute("DELETE FROM photos WHERE rel_path=?", (orig_rel_for_convert,))
                            conn.commit()
                    except Exception:
                        pass
                    # Optionally delete the physical original to save space
                    try:
                        if not heic_keep_originals_enabled():
                            orig_path = _disk_path_from_rel_path(orig_rel_for_convert)
                            orig_path.unlink(missing_ok=True)
                            log_event("heic_original_deleted", rel_path=orig_rel_for_convert)
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        log_event("error", rel_path=str(rel), error=f"heic_convert: {e}")
                    except Exception:
                        pass
        except Exception:
            pass
        if not disk_path.exists():
            index_errors += 1
            try:
                log_event("error", rel_path=rel, error="Upload file missing before post-process")
            except Exception:
                pass
            continue
        try:
            meta = extract_metadata(disk_path, rel, generate_thumb=False)
            meta["uploaded_by"] = user
            upsert_photo(meta)
            indexed_ok.append(rel)
            try:
                log_event("upload_indexed", rel_path=rel, width=meta.get("width"), height=meta.get("height"), has_gps=bool(meta.get("gps_lat") and meta.get("gps_lon")))
            except Exception:
                pass
        except Exception as e:
            index_errors += 1
            try:
                log_event("error", rel_path=rel, error=f"postprocess_index: {e}")
            except Exception:
                pass

    thumb_errors = 0
    _emit_progress({
        "phase": "thumbnails",
        "current_rel": None,
        "stage_processed": 0,
        "stage_total": len(indexed_ok),
    })
    for i, rel in enumerate(indexed_ok, start=1):
        _emit_progress({
            "phase": "thumbnails",
            "current_rel": rel,
            "stage_processed": i,
            "stage_total": len(indexed_ok),
        })
        try:
            disk_path = _disk_path_from_rel_path(rel)
            if not disk_path.exists():
                thumb_errors += 1
                continue
            stat = disk_path.stat()
            thumb_name: Optional[str] = None
            if disk_path.suffix.lower() in VIDEO_EXTS:
                thumb_name = _make_video_thumb(disk_path, rel, stat.st_mtime, stat.st_size)
            else:
                with Image.open(disk_path) as img:
                    try:
                        img = ImageOps.exif_transpose(img)
                    except Exception:
                        pass
                    thumb_name = make_thumb(img, rel, stat.st_mtime, stat.st_size)
            if thumb_name:
                with closing(get_conn()) as conn:
                    conn.execute("UPDATE photos SET thumb_name=?, last_scanned_at=? WHERE rel_path=?", (thumb_name, now_iso(), rel))
                    conn.commit()
            else:
                thumb_errors += 1
        except Exception as e:
            thumb_errors += 1
            try:
                log_event("error", rel_path=rel, error=f"postprocess_thumb: {e}")
            except Exception:
                pass

    faces_done = 0
    faces_found = 0
    faces_errors = 0
    if faces_enabled:
        _emit_progress({
            "phase": "faces",
            "current_rel": None,
            "stage_processed": 0,
            "stage_total": len(indexed_ok),
        })
        for i, rel in enumerate(indexed_ok, start=1):
            _emit_progress({
                "phase": "faces",
                "current_rel": rel,
                "stage_processed": i,
                "stage_total": len(indexed_ok),
            })
            try:
                fc = index_faces_for_photo(rel)
                faces_done += 1
                try:
                    if int(fc or 0) > 0:
                        faces_found += 1
                except Exception:
                    pass
            except Exception as e:
                faces_errors += 1
                try:
                    log_event("error", rel_path=rel, error=f"postprocess_faces: {e}")
                except Exception:
                    pass

    ai_done = 0
    ai_errors = 0
    if ai_enabled:
        _emit_progress({
            "phase": "embeddings",
            "current_rel": None,
            "stage_processed": 0,
            "stage_total": len(indexed_ok),
        })
        for i, rel in enumerate(indexed_ok, start=1):
            _emit_progress({
                "phase": "embeddings",
                "current_rel": rel,
                "stage_processed": i,
                "stage_total": len(indexed_ok),
            })
            try:
                _embed_uploaded_photo_if_needed(rel)
                ai_done += 1
            except Exception as e:
                ai_errors += 1
                try:
                    log_event("error", rel_path=rel, error=f"postprocess_ai: {e}")
                except Exception:
                    pass

    ai_desc_done = 0
    ai_desc_errors = 0
    if ai_desc_enabled:
        desc_total = len(indexed_ok)
        _emit_progress({
            "phase": "descriptions",
            "current_rel": None,
            "stage_processed": 0,
            "stage_total": desc_total,
        })
        for i, rel in enumerate(indexed_ok, start=1):
            _emit_progress({
                "phase": "descriptions",
                "current_rel": rel,
                "stage_processed": i,
                "stage_total": desc_total,
            })
            try:
                _describe_uploaded_photo_if_needed(rel)
                ai_desc_done += 1
            except Exception as e:
                ai_desc_errors += 1
                try:
                    log_event("error", rel_path=rel, error=f"postprocess_ai_desc: {e}")
                except Exception:
                    pass

    _emit_progress({
        "phase": "done",
        "current_rel": None,
        "stage_processed": len(rels),
        "stage_total": len(rels),
    })

    return {
        "ok": True,
        "received": len(rels),
        "indexed": len(indexed_ok),
        "index_errors": index_errors,
        "thumb_errors": thumb_errors,
        "heic_converted": heic_converted_count,
        "faces_enabled": faces_enabled,
        "faces_done": faces_done,
        "faces_found": faces_found,
        "faces_errors": faces_errors,
        "ai_enabled": ai_enabled,
        "ai_done": ai_done,
        "ai_errors": ai_errors,
        "ai_desc_enabled": ai_desc_enabled,
        "ai_desc_done": ai_desc_done,
        "ai_desc_errors": ai_desc_errors,
    }


def _upload_postprocess_worker(uploaded_by: str, initial_rels: list[str]) -> None:
    user = str(uploaded_by or "").strip() or "__unknown__"
    _set_upload_postprocess_state(
        user,
        {
            "running": True,
            "started_at": now_iso(),
            "finished_at": None,
            "error": None,
            "result": None,
            "phase": "starting",
            "current_rel": None,
            "stage_processed": 0,
            "stage_total": 0,
        },
    )

    aggregate: Dict[str, Any] = {
        "ok": True,
        "received": 0,
        "indexed": 0,
        "index_errors": 0,
        "heic_converted": 0,
        "faces_enabled": faces_auto_index_enabled(),
        "faces_done": 0,
        "faces_found": 0,
        "faces_errors": 0,
        "ai_enabled": ai_auto_ingest_enabled(),
        "ai_done": 0,
        "ai_errors": 0,
        "ai_desc_enabled": ai_desc_auto_ingest_enabled(),
        "ai_desc_done": 0,
        "ai_desc_errors": 0,
    }

    batch = list(initial_rels or [])
    try:
        while batch:
            try:
                log_event("upload_postprocess_start", user=user, files=len(batch))
            except Exception:
                pass

            result = _postprocess_uploaded_rels(
                user,
                batch,
                progress_cb=lambda p: _set_upload_postprocess_state(user, p),
            )
            aggregate["received"] += int(result.get("received") or 0)
            aggregate["indexed"] += int(result.get("indexed") or 0)
            aggregate["index_errors"] += int(result.get("index_errors") or 0)
            aggregate["heic_converted"] += int(result.get("heic_converted") or 0)
            aggregate["faces_done"] += int(result.get("faces_done") or 0)
            aggregate["faces_found"] += int(result.get("faces_found") or 0)
            aggregate["faces_errors"] += int(result.get("faces_errors") or 0)
            aggregate["ai_done"] += int(result.get("ai_done") or 0)
            aggregate["ai_errors"] += int(result.get("ai_errors") or 0)
            aggregate["ai_desc_done"] += int(result.get("ai_desc_done") or 0)
            aggregate["ai_desc_errors"] += int(result.get("ai_desc_errors") or 0)
            aggregate["faces_enabled"] = bool(result.get("faces_enabled"))
            aggregate["ai_enabled"] = bool(result.get("ai_enabled"))
            aggregate["ai_desc_enabled"] = bool(result.get("ai_desc_enabled"))

            try:
                log_event(
                    "upload_postprocess_done",
                    user=user,
                    files=result.get("received"),
                    indexed=result.get("indexed"),
                    heic_converted=result.get("heic_converted"),
                    faces_scanned=result.get("faces_done"),
                    faces_found=result.get("faces_found"),
                    index_errors=result.get("index_errors"),
                    faces_done=result.get("faces_done"),
                    faces_errors=result.get("faces_errors"),
                    ai_done=result.get("ai_done"),
                    ai_errors=result.get("ai_errors"),
                    ai_desc_done=result.get("ai_desc_done"),
                    ai_desc_errors=result.get("ai_desc_errors"),
                )
            except Exception:
                pass

            batch = _pop_uploaded_rels(user)

        _set_upload_postprocess_state(
            user,
            {
                "running": False,
                "finished_at": now_iso(),
                "result": aggregate,
                "error": None,
                "phase": "done",
                "current_rel": None,
                "stage_processed": int(aggregate.get("received") or 0),
                "stage_total": int(aggregate.get("received") or 0),
            },
        )
        try:
            log_event(
                "upload_postprocess_summary_done",
                user=user,
                files=aggregate.get("received"),
                indexed=aggregate.get("indexed"),
                heic_converted=aggregate.get("heic_converted"),
                faces_scanned=aggregate.get("faces_done"),
                faces_found=aggregate.get("faces_found"),
                index_errors=aggregate.get("index_errors"),
                faces_errors=aggregate.get("faces_errors"),
                ai_done=aggregate.get("ai_done"),
                ai_errors=aggregate.get("ai_errors"),
                ai_desc_done=aggregate.get("ai_desc_done"),
                ai_desc_errors=aggregate.get("ai_desc_errors"),
            )
        except Exception:
            pass
    except Exception as e:
        _set_upload_postprocess_state(
            user,
            {
                "running": False,
                "finished_at": now_iso(),
                "error": str(e),
                "result": aggregate,
                "phase": "error",
            },
        )


def _tus_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Tus-Resumable": "1.0.0",
        "Tus-Version": "1.0.0",
        "Tus-Extension": "creation",
    }
    if extra:
        headers.update(extra)
    return headers


def _tus_require_version() -> Optional[Tuple[dict, int]]:
    ver = str(request.headers.get("Tus-Resumable") or "").strip()
    if ver != "1.0.0":
        return ({"ok": False, "error": "Missing or invalid Tus-Resumable"}, 412)
    return None


def _parse_tus_metadata(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not raw:
        return out
    for pair in raw.split(","):
        part = str(pair or "").strip()
        if not part:
            continue
        chunks = part.split(" ", 1)
        if len(chunks) != 2:
            continue
        key = chunks[0].strip()
        value = chunks[1].strip()
        if not key:
            continue
        try:
            decoded = base64.b64decode(value).decode("utf-8") if value else ""
        except Exception:
            decoded = ""
        out[key] = decoded
    return out


def _tus_upload_paths(upload_id: str) -> Tuple[Path, Path]:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", upload_id or "")
    if not safe_id:
        raise ValueError("Invalid upload id")
    return (TUS_TMP_DIR / f"{safe_id}.bin", TUS_TMP_DIR / f"{safe_id}.json")


def _tus_load_meta(upload_id: str) -> Optional[Dict[str, Any]]:
    try:
        _, meta_path = _tus_upload_paths(upload_id)
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tus_store_meta(upload_id: str, meta: Dict[str, Any]) -> None:
    _, meta_path = _tus_upload_paths(upload_id)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _upsert_uploaded_stub(rel_path: str, disk_path: Path, uploaded_by: str) -> None:
    """Create/update a lightweight photo row right after upload commit.

    This lets the UI show newly uploaded files immediately (often as
    'Ingen thumbnail') while background postprocess fills metadata/thumb.
    """
    rel = str(rel_path or "").strip()
    if not rel:
        return
    try:
        st = disk_path.stat()
    except Exception:
        return

    ts_iso = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    payload = {
        "rel_path": rel,
        "filename": disk_path.name,
        "ext": disk_path.suffix.lower(),
        "file_size": int(st.st_size),
        "created_fs": ts_iso,
        "modified_fs": ts_iso,
        "captured_at": ts_iso,
        "ai_tags": json.dumps([], ensure_ascii=False),
        "metadata_json": json.dumps({}, ensure_ascii=False),
        "exif_json": json.dumps({}, ensure_ascii=False),
        "uploaded_by": _sanitize_share_visitor_name(uploaded_by or "") or None,
        "imported_at": now_iso(),
        "last_scanned_at": now_iso(),
    }

    try:
        with closing(get_conn()) as conn:
            conn.execute(
                """
                INSERT INTO photos (
                    rel_path, filename, ext, file_size,
                    created_fs, modified_fs, captured_at,
                    ai_tags, metadata_json, exif_json,
                    uploaded_by, imported_at, last_scanned_at
                ) VALUES (
                    :rel_path, :filename, :ext, :file_size,
                    :created_fs, :modified_fs, :captured_at,
                    :ai_tags, :metadata_json, :exif_json,
                    :uploaded_by, :imported_at, :last_scanned_at
                )
                ON CONFLICT(rel_path) DO UPDATE SET
                    filename=excluded.filename,
                    ext=excluded.ext,
                    file_size=excluded.file_size,
                    modified_fs=excluded.modified_fs,
                    created_fs=COALESCE(photos.created_fs, excluded.created_fs),
                    captured_at=COALESCE(photos.captured_at, excluded.captured_at),
                    uploaded_by=COALESCE(photos.uploaded_by, excluded.uploaded_by),
                    last_scanned_at=excluded.last_scanned_at
                """,
                payload,
            )
            conn.commit()
    except Exception as e:
        try:
            log_event("error", rel_path=rel, error=f"upload_stub_upsert: {e}")
        except Exception:
            pass


def _commit_uploaded_file(target_dir: Path, rel_prefix: str, subdir: str, source_path: Path, original_name: str, last_modified_ms: Optional[int], uploaded_by: str) -> Tuple[bool, str, Optional[str]]:
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return (False, "", "Cannot create target directory")
    name = secure_filename(original_name or "")
    if not name:
        return (False, "", "Invalid filename")
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        return (False, "", f"Unsupported: {name}")

    target = target_dir / name
    stem = Path(name).stem
    suffix = Path(name).suffix
    i = 1
    while target.exists():
        target = target_dir / f"{stem}_{i}{suffix}"
        i += 1

    shutil.move(str(source_path), str(target))
    try:
        if last_modified_ms:
            ts = float(last_modified_ms) / 1000.0
            os.utime(target, (ts, ts))
    except Exception:
        pass

    rel_leaf = f"{subdir}/{target.name}" if subdir else target.name
    rel = f"{rel_prefix}{rel_leaf}" if rel_prefix else rel_leaf
    try:
        _queue_uploaded_rel(uploaded_by, rel)
    except Exception as e:
        return (False, target.name, f"Queue fail: {target.name}: {e}")

    # Ensure postprocess runs in the container even if the browser refreshes/closes.
    try:
        _ensure_upload_postprocess_running(uploaded_by)
    except Exception as e:
        try:
            log_event("error", rel_path=rel, error=f"postprocess_autostart: {e}")
        except Exception:
            pass

    # Make file visible in UI immediately; full metadata/thumb comes from postprocess.
    _upsert_uploaded_stub(rel, target, uploaded_by)
    return (True, target.name, None)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                ext TEXT,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                created_fs TEXT,
                modified_fs TEXT,
                captured_at TEXT,
                camera_make TEXT,
                camera_model TEXT,
                lens_model TEXT,
                iso INTEGER,
                focal_length REAL,
                f_number REAL,
                exposure_time TEXT,
                gps_lat REAL,
                gps_lon REAL,
                gps_name TEXT,
                checksum_sha256 TEXT,
                phash TEXT,
                thumb_name TEXT,
                favorite INTEGER DEFAULT 0,
                people_count INTEGER DEFAULT 0,
                ai_tags TEXT,
                ai_desc_tags TEXT,
                ai_desc_caption TEXT,
                embedding_json TEXT,
                metadata_json TEXT,
                exif_json TEXT,
                uploaded_by TEXT,
                imported_at TEXT,
                last_scanned_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_photos_captured_at ON photos(captured_at);
            CREATE INDEX IF NOT EXISTS idx_photos_filename ON photos(filename);
                CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(phash);

                CREATE TABLE IF NOT EXISTS geo_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat_rounded INTEGER NOT NULL,
                    lon_rounded INTEGER NOT NULL,
                    country TEXT,
                    city TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_geo_cache ON geo_cache(lat_rounded, lon_rounded);
            CREATE INDEX IF NOT EXISTS idx_photos_favorite ON photos(favorite);
            CREATE INDEX IF NOT EXISTS idx_photos_gps ON photos(gps_lat, gps_lon);
            CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(phash);

            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                person_id INTEGER,
                bbox_x INTEGER,
                bbox_y INTEGER,
                bbox_w INTEGER,
                bbox_h INTEGER,
                embedding_json TEXT,
                confidence REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(photo_id) REFERENCES photos(id),
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 1,
                role TEXT,
                ui_language TEXT DEFAULT 'da',
                search_language TEXT DEFAULT 'da',
                totp_secret TEXT,
                totp_enabled INTEGER DEFAULT 0,
                totp_setup_done INTEGER DEFAULT 0,
                totp_remember_days INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                username_input TEXT,
                user_id INTEGER,
                username TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                event_type TEXT,
                reason TEXT,
                ip TEXT,
                country TEXT,
                device TEXT,
                user_agent TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_login_audit_at ON login_audit(at);
            CREATE INDEX IF NOT EXISTS idx_login_audit_user_id ON login_audit(user_id);
            CREATE INDEX IF NOT EXISTS idx_login_audit_success ON login_audit(success);

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS user_folder_access (
                user_id INTEGER NOT NULL,
                folder_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(user_id, folder_path),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_user_folder_access_user ON user_folder_access(user_id);

            CREATE TABLE IF NOT EXISTS share_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT UNIQUE NOT NULL,
                token_plain TEXT,
                share_name TEXT,
                folder_path TEXT NOT NULL,
                can_upload INTEGER DEFAULT 0,
                can_delete INTEGER DEFAULT 0,
                require_visitor_name INTEGER DEFAULT 0,
                link_use_duckdns INTEGER DEFAULT 0,
                password_hash TEXT,
                expires_at TEXT,
                revoked INTEGER DEFAULT 0,
                created_by_user_id INTEGER,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY(created_by_user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS share_link_folders (
                share_id INTEGER NOT NULL,
                folder_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(share_id, folder_path),
                FOREIGN KEY(share_id) REFERENCES share_links(id)
            );
            CREATE INDEX IF NOT EXISTS idx_share_links_folder ON share_links(folder_path);
            CREATE INDEX IF NOT EXISTS idx_share_links_expires ON share_links(expires_at);
            CREATE INDEX IF NOT EXISTS idx_share_link_folders_share ON share_link_folders(share_id);
            """
        )
        conn.commit()
        # Simple migration for old DBs
        # Add people.hidden if missing
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(people)").fetchall()]  # type: ignore[index]
            if "hidden" not in cols:
                conn.execute("ALTER TABLE people ADD COLUMN hidden INTEGER DEFAULT 0")
                conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_enabled INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_setup_done INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN totp_remember_days INTEGER DEFAULT 0")
        except Exception:
            pass
        # Add role column if missing and backfill values from is_admin
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN ui_language TEXT DEFAULT 'da'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN search_language TEXT DEFAULT 'da'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE share_links ADD COLUMN password_hash TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE share_links ADD COLUMN token_plain TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE share_links ADD COLUMN link_use_duckdns INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE share_links ADD COLUMN share_name TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE photos ADD COLUMN uploaded_by TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE photos ADD COLUMN ai_desc_tags TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE photos ADD COLUMN ai_desc_caption TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE share_links ADD COLUMN require_visitor_name INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE login_audit ADD COLUMN country TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE login_audit ADD COLUMN device TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE login_audit ADD COLUMN user_agent TEXT")
        except Exception:
            pass
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS share_link_folders (
                    share_id INTEGER NOT NULL,
                    folder_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(share_id, folder_path),
                    FOREIGN KEY(share_id) REFERENCES share_links(id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_share_link_folders_share ON share_link_folders(share_id)")
            conn.commit()
        except Exception:
            pass
        try:
            share_cols = [r[1] for r in conn.execute("PRAGMA table_info(share_links)").fetchall()]  # type: ignore[index]
            has_token_plain = "token_plain" in share_cols
            has_token_hash = "token_hash" in share_cols
            has_legacy_token = "token" in share_cols
            if has_token_plain and has_legacy_token:
                conn.execute(
                    """
                    UPDATE share_links
                    SET token_plain = token
                    WHERE (token_plain IS NULL OR TRIM(token_plain)='')
                      AND token IS NOT NULL
                      AND TRIM(token)<>''
                    """
                )
            if has_token_hash and has_legacy_token:
                legacy_rows = conn.execute(
                    """
                    SELECT id, token FROM share_links
                    WHERE (token_hash IS NULL OR TRIM(token_hash)='')
                      AND token IS NOT NULL
                      AND TRIM(token)<>''
                    """
                ).fetchall()
                for lr in legacy_rows:
                    token_raw = str(lr["token"] or "").strip()
                    token_hash = _share_token_digest(token_raw)
                    if not token_hash:
                        continue
                    try:
                        conn.execute("UPDATE share_links SET token_hash=? WHERE id=?", (token_hash, int(lr["id"])))
                    except Exception:
                        continue
            conn.execute(
                """
                INSERT OR IGNORE INTO share_link_folders(share_id, folder_path, created_at)
                SELECT id, folder_path, COALESCE(created_at, ?)
                FROM share_links
                WHERE folder_path IS NOT NULL AND TRIM(folder_path)<>''
                """,
                (now_iso(),),
            )
            conn.execute(
                """
                UPDATE share_links
                SET share_name = ('uploads/' || folder_path)
                WHERE (share_name IS NULL OR TRIM(share_name)='')
                  AND folder_path IS NOT NULL
                  AND TRIM(folder_path)<>''
                """
            )
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("UPDATE users SET role='admin' WHERE (role IS NULL OR role='') AND is_admin=1")
            conn.execute("UPDATE users SET role='user' WHERE (role IS NULL OR role='') AND is_admin=0")
            conn.execute("UPDATE users SET ui_language='da' WHERE ui_language IS NULL OR TRIM(ui_language)='' OR LOWER(ui_language) NOT IN ('da','en')")
            conn.execute("UPDATE users SET search_language='da' WHERE search_language IS NULL OR TRIM(search_language)='' OR LOWER(search_language) NOT IN ('da','en')")
            conn.commit()
        except Exception:
            pass

        # Seed defaults for AI settings if not present
        try:
            row = conn.execute("SELECT value FROM settings WHERE key='ai_enabled'").fetchone()
            if not row:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("ai_enabled", "1" if AI_ENV_ENABLED_DEFAULT else "0"))
            row2 = conn.execute("SELECT value FROM settings WHERE key='ai_auto_ingest'").fetchone()
            if not row2:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("ai_auto_ingest", "1" if AI_ENV_AUTO_INGEST_DEFAULT else "0"))
            row2a = conn.execute("SELECT value FROM settings WHERE key='ai_desc_auto_ingest'").fetchone()
            if not row2a:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("ai_desc_auto_ingest", "1" if AI_DESC_ENV_AUTO_INGEST_DEFAULT else "0"))
            row2b = conn.execute("SELECT value FROM settings WHERE key='faces_auto_index'").fetchone()
            if not row2b:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("faces_auto_index", "1" if FACES_ENV_AUTO_INDEX_DEFAULT else "0"))
            row2c = conn.execute("SELECT value FROM settings WHERE key='ai_ingest_throttle_sec'").fetchone()
            if not row2c:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("ai_ingest_throttle_sec", str(AI_INGEST_THROTTLE_SEC)))
            row2d = conn.execute("SELECT value FROM settings WHERE key='faces_index_throttle_sec'").fetchone()
            if not row2d:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("faces_index_throttle_sec", str(FACES_INDEX_THROTTLE_SEC)))
            row3 = conn.execute("SELECT value FROM settings WHERE key='upload_destination'").fetchone()
            if not row3:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("upload_destination", UPLOAD_DEST_DEFAULT))
            row4 = conn.execute("SELECT value FROM settings WHERE key='upload_subdir'").fetchone()
            if not row4:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("upload_subdir", ""))
            row5 = conn.execute("SELECT value FROM settings WHERE key='upload_subdir_uploads'").fetchone()
            if not row5:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("upload_subdir_uploads", ""))
            row6 = conn.execute("SELECT value FROM settings WHERE key='upload_subdir_library'").fetchone()
            if not row6:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", ("upload_subdir_library", ""))
            conn.commit()
        except Exception:
            pass


def _normalize_folder_acl_path(value: Optional[str]) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.lstrip("/").rstrip("/")
    if raw in {"", "."}:
        return ""
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    if any(p == ".." for p in parts):
        raise ValueError("invalid_folder")
    return "/".join(parts)


def _normalize_rel_path_for_acl(value: Optional[str]) -> str:
    rel = str(value or "").replace("\\", "/")
    while "//" in rel:
        rel = rel.replace("//", "/")
    return rel.lstrip("/")


def _list_all_photo_folders(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT rel_path FROM photos").fetchall()
    folders: set[str] = set()

    # Include real upload folders from disk so admins can assign access
    # even before images are indexed in those folders.
    try:
        upload_dirs = _list_upload_subdirs(UPLOAD_DIR, limit=2000)
        for sub in upload_dirs:
            clean = _normalize_folder_acl_path(sub)
            if clean:
                folders.add(f"uploads/{clean}")
    except Exception:
        pass

    for r in rows:
        rel = _normalize_rel_path_for_acl(r["rel_path"])
        if not rel:
            continue
        # Canonicalize uploads paths so converted/originals are shown under the user folder
        rel_for_folder = rel
        if rel.startswith("uploads/originals/"):
            parts = rel.split("/", 2)
            if len(parts) >= 3:
                rel_for_folder = f"uploads/{parts[2]}"
            else:
                rel_for_folder = "uploads"
        elif rel.startswith("uploads/converted/"):
            parts = rel.split("/", 2)
            if len(parts) >= 3:
                rel_for_folder = f"uploads/{parts[2]}"
            else:
                rel_for_folder = "uploads"
        parent = rel_for_folder.rsplit("/", 1)[0] if "/" in rel_for_folder else ""
        if not parent:
            continue
        parts = [p for p in parent.split("/") if p]
        acc = ""
        for part in parts:
            acc = f"{acc}/{part}" if acc else part
            if acc == "uploads":
                continue
            folders.add(acc)
    return sorted(folders, key=lambda x: x.lower())


def _set_user_allowed_folders(conn: sqlite3.Connection, user_id: int, folders: list[str]) -> list[str]:
    cleaned = []
    for path in folders:
        try:
            p = _normalize_folder_acl_path(path)
        except Exception:
            continue
        if p:
            cleaned.append(p)
    cleaned = sorted(set(cleaned), key=lambda x: (-x.count("/"), x.lower()))
    reduced: list[str] = []
    for path in cleaned:
        # Keep the deepest selections only.
        # If a deeper descendant is selected, parent is ignored to allow narrowing access.
        if any((child == path) or child.startswith(path + "/") for child in reduced):
            continue
        reduced.append(path)
    reduced = sorted(reduced, key=lambda x: x.lower())

    conn.execute("DELETE FROM user_folder_access WHERE user_id=?", (user_id,))
    if reduced:
        now = now_iso()
        conn.executemany(
            "INSERT INTO user_folder_access(user_id, folder_path, created_at) VALUES(?,?,?)",
            [(user_id, p, now) for p in reduced],
        )
    return reduced


def _get_user_allowed_folders(conn: sqlite3.Connection, user_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT folder_path FROM user_folder_access WHERE user_id=? ORDER BY folder_path COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    out: list[str] = []
    for r in rows:
        try:
            p = _normalize_folder_acl_path(r["folder_path"])
        except Exception:
            continue
        if p:
            out.append(p)
    return out


def _current_user_acl_prefixes(conn: Optional[sqlite3.Connection] = None) -> Optional[list[str]]:
    try:
        if getattr(current_user, "is_admin", False):
            return None
        uid = int(getattr(current_user, "id", 0) or 0)
        if uid <= 0:
            return None
    except Exception:
        return None

    def _load(c: sqlite3.Connection) -> list[str]:
        return _get_user_allowed_folders(c, uid)

    if conn is not None:
        rows = _load(conn)
    else:
        with closing(get_conn()) as conn2:
            rows = _load(conn2)
    if not rows:
        return None
    return rows


def _is_rel_path_allowed_for_current_user(rel_path: Optional[str], conn: Optional[sqlite3.Connection] = None) -> bool:
    rel = _normalize_rel_path_for_acl(rel_path)
    if not rel:
        return False
    prefixes = _current_user_acl_prefixes(conn)
    if prefixes is None:
        return True
    for p in prefixes:
        if rel == p or rel.startswith(p + "/"):
            return True
    return False


def _filter_public_items_by_current_user_acl(items: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not items:
        return items
    prefixes = _current_user_acl_prefixes()
    if prefixes is None:
        return items
    out: list[Dict[str, Any]] = []
    for item in items:
        rel = _normalize_rel_path_for_acl(item.get("rel_path"))
        if not rel:
            continue
        if any(rel == p or rel.startswith(p + "/") for p in prefixes):
            out.append(item)
    return out


def _filter_folders_by_current_user_acl(folders: list[str], conn: Optional[sqlite3.Connection] = None) -> list[str]:
    prefixes = _current_user_acl_prefixes(conn)
    if prefixes is None:
        return folders
    out: list[str] = []
    for raw in folders:
        try:
            folder = _normalize_folder_acl_path(raw)
        except Exception:
            continue
        if not folder:
            out.append("")
            continue
        if any(
            folder == p
            or folder.startswith(p + "/")
            or p.startswith(folder + "/")
            for p in prefixes
        ):
            out.append(folder)
    if "" not in out:
        out.insert(0, "")
    seen: set[str] = set()
    deduped: list[str] = []
    for f in out:
        if f in seen:
            continue
        seen.add(f)
        deduped.append(f)
    return deduped


@app.before_request
def enforce_login_for_app():
    # Allow static files and login endpoints without auth
    open_endpoints = {
        "login",
        "verify_2fa",
        "static",
        "setup",
        "api_health",
        "shared_folder_view",
        "api_share_info",
        "api_share_photos",
        "api_share_thumb",
        "api_share_viewable",
        "api_share_original",
        "api_share_auth",
        "api_share_upload",
        "api_share_delete",
    }
    if request.endpoint in open_endpoints or (request.endpoint or "").startswith("static"):
        return None
    # Bootstrap: if no users exist, redirect to setup
    try:
        if users_count() == 0 and request.endpoint != "setup":
            return redirect(url_for("setup"))
    except Exception:
        pass
    # Everything else (index + /api/* + file routes) requires auth
    if not current_user.is_authenticated:
        # For API calls, return 401 to avoid HTML in fetch
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return redirect(url_for("login", next=request.path))
    # Enforce initial 2FA setup only when 2FA is enabled but not completed
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT totp_enabled, totp_setup_done FROM users WHERE id= ?", (current_user.id,)).fetchone()
        if row and int(row["totp_enabled"] or 0) == 1 and int(row["totp_setup_done"] or 0) == 0 and request.endpoint not in {"setup_2fa", "logout", "static"}:
            return redirect(url_for("setup_2fa"))
    except Exception:
        pass


def _forbid_user_role_for_maintenance() -> Optional[Tuple[dict, int]]:
    """Return (resp, code) when current user is basic 'user' and tries to access maint/log features."""
    try:
        role = getattr(current_user, "role", "user")
    except Exception:
        role = "user"
    if role == "user":
        return ({"ok": False, "error": "Forbidden"}, 403)
    return None


def _normalize_language(value: Optional[str], default: str = DEFAULT_UI_LANGUAGE) -> str:
    lang = str(value or "").strip().lower()
    if lang in LANG_CHOICES:
        return lang
    return default


def _current_user_pref_languages() -> tuple[str, str]:
    ui_lang = _normalize_language(getattr(current_user, "ui_language", None), DEFAULT_UI_LANGUAGE)
    search_lang = _normalize_language(getattr(current_user, "search_language", None), DEFAULT_SEARCH_LANGUAGE)
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT ui_language, search_language FROM users WHERE id=?", (current_user.id,)).fetchone()
        if row:
            ui_lang = _normalize_language(row["ui_language"], ui_lang)
            search_lang = _normalize_language(row["search_language"], search_lang)
    except Exception:
        pass
    return (ui_lang, search_lang)


# --- App settings helpers ---
def _get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            if not row:
                return default
            try:
                return row["value"]  # sqlite3.Row
            except Exception:
                return row[0]
    except Exception:
        return default


def _set_setting(key: str, value: str) -> None:
    try:
        with closing(get_conn()) as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()
    except Exception:
        pass


def _get_setting_bool(key: str, default: bool = False) -> bool:
    v = _get_setting(key, None)
    if v is None:
        return default
    return str(v).strip() not in {"0", "false", "False", "no", "off", ""}


def _parse_throttle_value(value: Any, default: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    if v < 0:
        v = 0.0
    if v > 2.0:
        v = 2.0
    return round(v, 3)


def _get_setting_throttle(key: str, default: float) -> float:
    return _parse_throttle_value(_get_setting(key, str(default)), default)


def ai_feature_enabled() -> bool:
    return _get_setting_bool("ai_enabled", AI_ENV_ENABLED_DEFAULT)


def ai_auto_ingest_enabled() -> bool:
    return _get_setting_bool("ai_auto_ingest", AI_ENV_AUTO_INGEST_DEFAULT)


def heic_convert_on_upload_enabled() -> bool:
    return _get_setting_bool("heic_convert_on_upload", HEIC_CONVERT_ON_UPLOAD_DEFAULT)


def heic_keep_originals_enabled() -> bool:
    # default True to keep safety unless explicitly disabled
    return _get_setting_bool("heic_keep_originals", True)


def ai_desc_auto_ingest_enabled() -> bool:
    return _get_setting_bool("ai_desc_auto_ingest", AI_DESC_ENV_AUTO_INGEST_DEFAULT)


def faces_auto_index_enabled() -> bool:
    return _get_setting_bool("faces_auto_index", FACES_ENV_AUTO_INDEX_DEFAULT)


def ai_ingest_throttle_enabled_sec() -> float:
    return _get_setting_throttle("ai_ingest_throttle_sec", AI_INGEST_THROTTLE_SEC)


def faces_index_throttle_enabled_sec() -> float:
    return _get_setting_throttle("faces_index_throttle_sec", FACES_INDEX_THROTTLE_SEC)


def _disk_path_from_rel_path(rel_path: str) -> Path:
    rel = str(rel_path or "")
    if rel.startswith("uploads/"):
        leaf = rel.split("/", 1)[1] if "/" in rel else ""
        return UPLOAD_DIR / leaf
    return PHOTO_DIR / rel


def get_upload_destination() -> str:
    v = (_get_setting("upload_destination", UPLOAD_DEST_DEFAULT) or "").strip().lower()
    if v not in UPLOAD_DEST_CHOICES:
        return UPLOAD_DEST_DEFAULT
    return v


def _normalize_upload_subdir(raw: Optional[str]) -> str:
    value = (raw or "").strip().replace("\\", "/")
    value = value.strip("/")
    if not value:
        return ""
    safe_parts: list[str] = []
    for part in value.split("/"):
        p = part.strip()
        if not p or p in {".", ".."}:
            raise ValueError("Ugyldig mappe")
        safe = secure_filename(p)
        if not safe:
            raise ValueError("Ugyldig mappe")
        safe_parts.append(safe)
    return "/".join(safe_parts)


def _upload_subdir_setting_key(destination: str) -> str:
    if destination == UPLOAD_DEST_LIBRARY:
        return "upload_subdir_library"
    return "upload_subdir_uploads"


def get_upload_subdir(destination: Optional[str] = None) -> str:
    dest = destination or get_upload_destination()
    try:
        by_dest = _get_setting(_upload_subdir_setting_key(dest), "")
        legacy = _get_setting("upload_subdir", "")
        raw = by_dest if (by_dest or "").strip() else legacy
        subdir = _normalize_upload_subdir(raw)
        # Migration: old default for uploads created nested /data/uploads/uploads.
        if dest == UPLOAD_DEST_UPLOADS and subdir.lower() == "uploads":
            try:
                _set_upload_subdir(dest, "")
            except Exception:
                pass
            return ""
        return subdir
    except Exception:
        return ""


def _set_upload_subdir(destination: str, subdir: str) -> None:
    safe = _normalize_upload_subdir(subdir)
    _set_setting(_upload_subdir_setting_key(destination), safe)
    # Keep legacy key in sync for backward compatibility
    _set_setting("upload_subdir", safe)


def _ensure_default_upload_subdir(destination: str, target_root: Path, current_subdir: str) -> str:
    if current_subdir:
        return current_subdir
    default_name = UPLOAD_DEFAULT_SUBDIR_BY_DEST.get(destination, "")
    if not default_name:
        return ""
    try:
        safe = _normalize_upload_subdir(default_name)
    except Exception:
        return ""
    try:
        target = target_root / safe
        target.mkdir(parents=True, exist_ok=True)
        _set_upload_subdir(destination, safe)
        return safe
    except Exception:
        return ""


def _list_upload_subdirs(base_dir: Path, limit: int = 400) -> list[str]:
    out: list[str] = [""]
    try:
        base = base_dir.resolve()
    except Exception:
        return out
    if not base.exists() or not base.is_dir():
        return out
    try:
        for root, dirs, _files in os.walk(base):
            dirs[:] = sorted([d for d in dirs if not d.startswith(".")])
            for d in dirs:
                p = Path(root) / d
                try:
                    rel = str(p.relative_to(base)).replace("\\", "/")
                except Exception:
                    continue
                # Hide framework folders from folder pickers ('originals' and 'converted')
                parts = [seg for seg in rel.split("/") if seg]
                if parts and parts[0] in {"originals", "converted"}:
                    # Do not surface internal storage roots as user folders
                    continue
                if rel and rel not in out:
                    out.append(rel)
                    if len(out) >= limit:
                        return out
    except Exception:
        return out
    return out


def _upload_settings_payload(destination: str) -> dict:
    saved_destination = get_upload_destination()
    subdir = get_upload_subdir(destination)
    target_root, _ = _upload_target_for_destination(destination)
    subdir = _ensure_default_upload_subdir(destination, target_root, subdir)
    folders = _list_upload_subdirs(target_root)
    folders = _filter_folders_by_current_user_acl(folders)
    if destination == UPLOAD_DEST_UPLOADS and "uploads" in folders:
        folders = [f for f in folders if f != "uploads"]
    if subdir and subdir not in folders:
        # Stored folder no longer exists on disk: remove stale reference
        _set_upload_subdir(destination, "")
        subdir = ""
    return {
        "ok": True,
        "destination": destination,
        "saved_destination": saved_destination,
        "subdir": subdir,
        "folders": folders,
        "photo_dir": str(PHOTO_DIR),
        "upload_dir": str(UPLOAD_DIR),
        "note": "Scan bruger filer direkte fra biblioteket og kopierer ikke.",
        "options": [
            {"value": UPLOAD_DEST_UPLOADS, "label": "Kopiér til uploads-mappen"},
            {"value": UPLOAD_DEST_LIBRARY, "label": "Kopiér til fotobiblioteket"},
        ],
    }


def _delete_indexed_photos_for_prefixes(rel_prefixes: Iterable[str]) -> dict:
    prefixes = [str(p or "").strip("/") for p in (rel_prefixes or []) if str(p or "").strip("/")]
    if not prefixes:
        return {"photos": 0, "faces": 0, "thumbs": 0}

    where_parts: list[str] = []
    params: list[Any] = []
    for pref in prefixes:
        where_parts.append("(rel_path = ? OR rel_path LIKE ?)")
        params.extend([pref, pref + "/%"])

    q = "SELECT id, thumb_name FROM photos WHERE " + " OR ".join(where_parts)
    with closing(get_conn()) as conn:
        rows = conn.execute(q, params).fetchall()
        if not rows:
            return {"photos": 0, "faces": 0, "thumbs": 0}

        photo_ids = [int(r["id"]) for r in rows]
        thumbs = [str(r["thumb_name"]) for r in rows if r["thumb_name"]]

        ph = ",".join(["?"] * len(photo_ids))
        faces_removed = int(conn.execute(f"SELECT COUNT(*) AS c FROM faces WHERE photo_id IN ({ph})", photo_ids).fetchone()["c"] or 0)
        conn.execute(f"DELETE FROM faces WHERE photo_id IN ({ph})", photo_ids)
        conn.execute(f"DELETE FROM photos WHERE id IN ({ph})", photo_ids)
        conn.commit()

    thumbs_removed = 0
    for tn in thumbs:
        try:
            p = THUMB_DIR / tn
            if p.exists():
                p.unlink()
                thumbs_removed += 1
        except Exception:
            continue

    return {"photos": len(photo_ids), "faces": faces_removed, "thumbs": thumbs_removed}


def _delete_indexed_photos_by_ids(photo_ids: Iterable[int]) -> dict:
    ids = sorted({int(pid) for pid in (photo_ids or []) if str(pid).isdigit()})
    if not ids:
        return {"photos": 0, "faces": 0, "thumbs": 0, "files": 0}

    with closing(get_conn()) as conn:
        ph = ",".join(["?"] * len(ids))
        rows = conn.execute(
            f"SELECT id, rel_path, thumb_name FROM photos WHERE id IN ({ph})",
            ids,
        ).fetchall()
        if not rows:
            return {"photos": 0, "faces": 0, "thumbs": 0, "files": 0}

        resolved_ids = [int(r["id"]) for r in rows]
        thumbs = [str(r["thumb_name"]) for r in rows if r["thumb_name"]]
        rel_paths = [str(r["rel_path"]) for r in rows if r["rel_path"]]

        ph2 = ",".join(["?"] * len(resolved_ids))
        faces_removed = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM faces WHERE photo_id IN ({ph2})",
                resolved_ids,
            ).fetchone()["c"]
            or 0
        )
        conn.execute(f"DELETE FROM faces WHERE photo_id IN ({ph2})", resolved_ids)
        conn.execute(f"DELETE FROM photos WHERE id IN ({ph2})", resolved_ids)
        conn.commit()

    thumbs_removed = 0
    for tn in thumbs:
        try:
            p = THUMB_DIR / tn
            if p.exists():
                p.unlink()
                thumbs_removed += 1
        except Exception:
            continue

    files_removed = 0
    for rel in rel_paths:
        try:
            fp = _disk_path_from_rel_path(rel)
            if fp.exists() and fp.is_file():
                fp.unlink()
                files_removed += 1
        except Exception:
            continue

    return {
        "photos": len(resolved_ids),
        "faces": faces_removed,
        "thumbs": thumbs_removed,
        "files": files_removed,
    }


def _share_token_digest(token: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""
    key = app.secret_key
    if isinstance(key, str):
        key_bytes = key.encode("utf-8", errors="ignore")
    elif isinstance(key, bytes):
        key_bytes = key
    else:
        key_bytes = str(key).encode("utf-8", errors="ignore")
    return hmac.new(key_bytes, raw.encode("utf-8", errors="ignore"), hashlib.sha256).hexdigest()


def _share_is_expired(expires_at: Optional[str]) -> bool:
    exp = str(expires_at or "").strip()
    if not exp:
        return False
    return exp <= now_iso()


def _share_folder_rel_prefix(folder_path: str) -> str:
    folder = _normalize_upload_subdir(folder_path)
    return f"uploads/{folder}" if folder else "uploads"


def _share_folder_paths(conn: sqlite3.Connection, share_row: sqlite3.Row) -> list[str]:
    share_id = int(share_row["id"] or 0)
    rows = conn.execute(
        "SELECT folder_path FROM share_link_folders WHERE share_id=? ORDER BY folder_path COLLATE NOCASE",
        (share_id,),
    ).fetchall()
    values: list[str] = []
    for r in rows:
        fp = _normalize_upload_subdir(str(r["folder_path"] or ""))
        if fp and fp not in values:
            values.append(fp)
    if values:
        return values
    fallback = _normalize_upload_subdir(str(share_row["folder_path"] or ""))
    return [fallback] if fallback else []


def _share_rel_prefixes(folder_paths: list[str]) -> list[str]:
    prefixes: list[str] = []
    for fp in folder_paths:
        rel_prefix = _share_folder_rel_prefix(fp)
        if rel_prefix and rel_prefix not in prefixes:
            prefixes.append(rel_prefix)
    return prefixes


def _share_scope_sql(prefixes: list[str]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for rel_prefix in prefixes:
        clauses.append("(rel_path=? OR rel_path LIKE ?)")
        params.extend([rel_prefix, rel_prefix + "/%"])
    return " OR ".join(clauses), params


def _load_share_from_token(token: str, touch: bool = False) -> Optional[sqlite3.Row]:
    token_hash = _share_token_digest(token)
    if not token_hash:
        return None
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE token_hash=? LIMIT 1",
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        if int(row["revoked"] or 0) == 1:
            return None
        if _share_is_expired(row["expires_at"]):
            return None
        if touch:
            try:
                conn.execute("UPDATE share_links SET last_used_at=? WHERE id=?", (now_iso(), int(row["id"])))
                conn.commit()
            except Exception:
                pass
    return row


def _share_session_key(share_row: sqlite3.Row) -> str:
    return f"share_auth_{int(share_row['id'])}"


def _share_name_session_key(share_row: sqlite3.Row) -> str:
    return f"share_name_{int(share_row['id'])}"


def _sanitize_share_visitor_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(name) > 80:
        name = name[:80].strip()
    return name


def _share_is_password_protected(share_row: sqlite3.Row) -> bool:
    return bool(str(share_row["password_hash"] or "").strip())


def _share_requires_visitor_name(share_row: sqlite3.Row) -> bool:
    try:
        return bool(int(share_row["require_visitor_name"] or 0))
    except Exception:
        return False


def _share_get_visitor_name(share_row: sqlite3.Row) -> str:
    return _sanitize_share_visitor_name(session.get(_share_name_session_key(share_row)) or "")


def _share_is_authorized(share_row: sqlite3.Row) -> bool:
    if _share_is_password_protected(share_row) and not bool(session.get(_share_session_key(share_row))):
        return False
    if _share_requires_visitor_name(share_row) and not _share_get_visitor_name(share_row):
        return False
    return True


def _normalize_share_base_url(raw: str) -> Optional[str]:
    value = str(raw or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def _build_share_link(token: str, use_duckdns: bool) -> Tuple[Optional[str], Optional[str]]:
    share_path = url_for("shared_folder_view", token=token, _external=False)
    if use_duckdns:
        configured = _get_setting("share_duckdns_base_url", SHARE_DUCKDNS_BASE_URL) or SHARE_DUCKDNS_BASE_URL
        base = _normalize_share_base_url(configured)
        if not base:
            return None, "DuckDNS-base URL mangler. Sæt SHARE_DUCKDNS_BASE_URL i miljøvariabler."
        return f"{base}{share_path}", None
    return url_for("shared_folder_view", token=token, _external=True), None


def _share_link_for_admin_row(row: sqlite3.Row) -> Optional[str]:
    token_plain = str(row["token_plain"] or "").strip()
    if not token_plain:
        return None
    use_duckdns = bool(int(row["link_use_duckdns"] or 0))
    link, err = _build_share_link(token_plain, use_duckdns)
    if link and not err:
        return link
    fallback, _ = _build_share_link(token_plain, False)
    return fallback


def _get_share_scoped_photo_row(conn: sqlite3.Connection, share_row: sqlite3.Row, photo_id: int) -> Optional[sqlite3.Row]:
    folder_paths = _share_folder_paths(conn, share_row)
    prefixes = _share_rel_prefixes(folder_paths)
    if not prefixes:
        return None
    where_sql, where_params = _share_scope_sql(prefixes)
    sql = f"SELECT * FROM photos WHERE id=? AND ({where_sql}) LIMIT 1"
    return conn.execute(sql, (int(photo_id), *where_params)).fetchone()


def _upload_target_for_destination(destination: str) -> Tuple[Path, str]:
    if destination == UPLOAD_DEST_LIBRARY:
        return PHOTO_DIR, ""
    # Place uploads under 'uploads/originals' so HEIC originals are kept separate from converted copies
    return (UPLOAD_DIR / "originals"), "uploads/originals/"


def _read_secret(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    f = os.environ.get(f"{name}_FILE")
    if f and os.path.exists(f):
        try:
            return Path(f).read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None


@app.route("/setup", methods=["GET", "POST"])
def setup():
    # If a user already exists, send to login
    if users_count() > 0:
        return redirect(url_for("login"))
    require_token = bool(_read_secret("SETUP_TOKEN"))
    if request.method == "POST":
        token = (request.form.get("token") or "").strip()
        if require_token and token != _read_secret("SETUP_TOKEN"):
            return render_template("setup.html", error=_ui_text("setup_invalid_token"), require_token=True)
        u = (request.form.get("username") or "").strip()
        p = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if not u or not p:
            return render_template("setup.html", error=_ui_text("setup_fill_fields"), require_token=require_token)
        if p != p2:
            return render_template("setup.html", error=_ui_text("setup_password_mismatch"), require_token=require_token)
        try:
            with closing(get_conn()) as conn:
                conn.execute(
                    "INSERT INTO users(username, password_hash, is_admin, created_at) VALUES (?,?,?,?)",
                    (u, generate_password_hash(p), 1, now_iso()),
                )
                conn.commit()
            # Redirect directly to login after successful creation
            return redirect(url_for("login", created=1))
        except Exception as e:
            return render_template("setup.html", error=str(e), require_token=require_token)
    return render_template("setup.html", require_token=require_token)


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def average_hash(img: Image.Image, hash_size: int = 8) -> str:
    gray = img.convert("L").resize((hash_size, hash_size))
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    # binary -> hex string
    return f"{int(bits, 2):0{hash_size*hash_size//4}x}"


def _rational_to_float(v: Any) -> Optional[float]:
    try:
        # EXIF kan returnere tuple (numerator, denominator)
        if isinstance(v, tuple) and len(v) == 2 and v[1] != 0:
            return float(v[0]) / float(v[1])
        # Nogle EXIF-objekter har numerator/denominator attributter
        if hasattr(v, "numerator") and hasattr(v, "denominator"):
            denom = getattr(v, "denominator", None)
            if denom:
                return float(getattr(v, "numerator", 0)) / float(denom)
        # Hvis det bare er et tal
        if isinstance(v, (int, float)):
            return float(v)
        # Hvis det er en string, prøv at konvertere
        if isinstance(v, str):
            return float(v)
    except Exception:
        return None
    return None


def _gps_to_deg(value: Any) -> Optional[float]:
    try:
        if not value or len(value) != 3:
            return None
        d = _rational_to_float(value[0])
        m = _rational_to_float(value[1])
        s = _rational_to_float(value[2])
        if d is None or m is None or s is None:
            return None
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None


def parse_exif(img: Image.Image) -> Dict[str, Any]:
    exif_map: Dict[str, Any] = {}
    try:
        exif = img.getexif()
    except Exception:
        exif = None
    if not exif:
        # last resort: try GPS IFD if available in Pillow
        try:
            if hasattr(img, "getexif") and hasattr(ExifTags, "IFD"):
                gps_ifd = img.getexif().get_ifd(getattr(ExifTags, "IFD").GPS)  # type: ignore[attr-defined]
                if gps_ifd:
                    exif_map["GPSInfo"] = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
                    # derive lat/lon
                    lat = _gps_to_deg(exif_map["GPSInfo"].get("GPSLatitude"))
                    lon = _gps_to_deg(exif_map["GPSInfo"].get("GPSLongitude"))
                    if lat is not None and exif_map["GPSInfo"].get("GPSLatitudeRef") in ("S", b"S"):
                        lat = -lat
                    if lon is not None and exif_map["GPSInfo"].get("GPSLongitudeRef") in ("W", b"W"):
                        lon = -lon
                    if lat is not None:
                        exif_map["_gps_lat"] = lat
                    if lon is not None:
                        exif_map["_gps_lon"] = lon
        except Exception:
            pass
        return exif_map

    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        try:
            if tag_name == "GPSInfo" and isinstance(value, dict):
                gps = {}
                for k, v in value.items():
                    gps_name = ExifTags.GPSTAGS.get(k, str(k))
                    gps[gps_name] = v
                exif_map["GPSInfo"] = gps
            elif isinstance(value, bytes):
                exif_map[tag_name] = f"<bytes:{len(value)}>"
            else:
                exif_map[tag_name] = value
        except Exception:
            exif_map[tag_name] = str(value)

    # If GPSInfo not present, try direct GPS IFD
    if "GPSInfo" not in exif_map:
        try:
            if hasattr(ExifTags, "IFD"):
                gps_ifd = exif.get_ifd(getattr(ExifTags, "IFD").GPS)  # type: ignore[attr-defined]
                if gps_ifd:
                    exif_map["GPSInfo"] = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
        except Exception:
            pass

    # Pillow sometimes stores GPSInfo values without expanding GPSTAGS
    if "GPSInfo" in exif_map and isinstance(exif_map["GPSInfo"], dict):
        gps = exif_map["GPSInfo"]
        lat = _gps_to_deg(gps.get("GPSLatitude"))
        lon = _gps_to_deg(gps.get("GPSLongitude"))
        if lat is not None and gps.get("GPSLatitudeRef") in ("S", b"S"):
            lat = -lat
        if lon is not None and gps.get("GPSLongitudeRef") in ("W", b"W"):
            lon = -lon
        if lat is not None:
            exif_map["_gps_lat"] = lat
        if lon is not None:
            exif_map["_gps_lon"] = lon

    return exif_map


def _merge_if_missing(meta: Dict[str, Any], key: str, val: Any):
    if val is None:
        return
    if meta.get(key) is None or meta.get(key) == "":
        meta[key] = val


def _piexif_get_first(exif_dict: dict, ifd: str, tag: int) -> Optional[Any]:
    try:
        return exif_dict.get(ifd, {}).get(tag)
    except Exception:
        return None


def extract_exif_via_heif(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        # If pillow_heif is unavailable, skip gracefully
        try:
            hf = HeifFile(path)  # type: ignore[name-defined]
        except NameError:
            return out
        exif_bytes = hf.info.get("exif") if isinstance(hf.info, dict) else None
        if not exif_bytes:
            return out
        exif_dict = piexif.load(exif_bytes)
        # DateTimeOriginal
        dto = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.DateTimeOriginal)
        if dto:
            try:
                out["captured_at"] = parse_captured_at({"DateTimeOriginal": dto.decode() if isinstance(dto, bytes) else str(dto)}, path.stat().st_mtime)
            except Exception:
                pass
        # Camera/Lens
        mke = _piexif_get_first(exif_dict, "0th", piexif.ImageIFD.Make)
        mdl = _piexif_get_first(exif_dict, "0th", piexif.ImageIFD.Model)
        lmd = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.LensModel)
        out["camera_make"] = mke.decode() if isinstance(mke, bytes) else mke
        out["camera_model"] = mdl.decode() if isinstance(mdl, bytes) else mdl
        out["lens_model"] = lmd.decode() if isinstance(lmd, bytes) else lmd
        # Exposure
        out["iso"] = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.ISOSpeedRatings) or _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.PhotographicSensitivity)
        out["f_number"] = _rational_to_float(_piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.FNumber))
        out["focal_length"] = _rational_to_float(_piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.FocalLength))
        et = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.ExposureTime)
        out["exposure_time"] = str(et) if et is not None else None
        # GPS
        gps = exif_dict.get("GPS", {})
        glat = gps.get(piexif.GPSIFD.GPSLatitude)
        glat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        glon = gps.get(piexif.GPSIFD.GPSLongitude)
        glon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)
        def conv_triplet(t):
            if not t:
                return None
            try:
                d = _rational_to_float(t[0])
                m = _rational_to_float(t[1])
                s = _rational_to_float(t[2])
                if d is None or m is None or s is None:
                    return None
                return d + (m / 60.0) + (s / 3600.0)
            except Exception:
                return None
        lat = conv_triplet(glat)
        lon = conv_triplet(glon)
        if lat is not None and (glat_ref in (b"S", "S")):
            lat = -lat
        if lon is not None and (glon_ref in (b"W", "W")):
            lon = -lon
        out["gps_lat"] = lat
        out["gps_lon"] = lon
    except Exception as e:
        log_event("error", rel_path=str(path), error=f"heif_exif: {e}")
    return out


def extract_exif_via_exifread(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        with path.open("rb") as f:
            tags = exifread.process_file(f, details=False)
        # DateTimeOriginal
        for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            if key in tags:
                dto = str(tags[key])
                out["captured_at"] = parse_captured_at({"DateTimeOriginal": dto.replace("/", ":")}, path.stat().st_mtime)
                break
        # Camera / Lens
        out["camera_make"] = str(tags.get("Image Make", "")) or None
        out["camera_model"] = str(tags.get("Image Model", "")) or None
        out["lens_model"] = str(tags.get("EXIF LensModel", "")) or None
        # GPS
        lat = tags.get("GPS GPSLatitude")
        lat_ref = str(tags.get("GPS GPSLatitudeRef", ""))
        lon = tags.get("GPS GPSLongitude")
        lon_ref = str(tags.get("GPS GPSLongitudeRef", ""))
        def to_float_gps(tag):
            try:
                vals = [float(v.num) / float(v.den) for v in tag.values]
                return vals[0] + vals[1] / 60.0 + vals[2] / 3600.0
            except Exception:
                return None
        if lat and lon:
            la = to_float_gps(lat)
            lo = to_float_gps(lon)
            if la is not None:
                if lat_ref.strip().upper().startswith("S"):
                    la = -la
                out["gps_lat"] = la
            if lo is not None:
                if lon_ref.strip().upper().startswith("W"):
                    lo = -lo
                out["gps_lon"] = lo
    except Exception as e:
        log_event("error", rel_path=str(path), error=f"exifread: {e}")
    return out


def extract_exif_via_piexif_file(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        exif_dict = piexif.load(str(path))
        dto = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.DateTimeOriginal)
        if dto:
            out["captured_at"] = parse_captured_at({"DateTimeOriginal": dto.decode() if isinstance(dto, bytes) else str(dto)}, path.stat().st_mtime)
        mke = _piexif_get_first(exif_dict, "0th", piexif.ImageIFD.Make)
        mdl = _piexif_get_first(exif_dict, "0th", piexif.ImageIFD.Model)
        lmd = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.LensModel)
        out["camera_make"] = mke.decode() if isinstance(mke, bytes) else mke
        out["camera_model"] = mdl.decode() if isinstance(mdl, bytes) else mdl
        out["lens_model"] = lmd.decode() if isinstance(lmd, bytes) else lmd
        out["iso"] = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.ISOSpeedRatings) or _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.PhotographicSensitivity)
        out["f_number"] = _rational_to_float(_piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.FNumber))
        out["focal_length"] = _rational_to_float(_piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.FocalLength))
        et = _piexif_get_first(exif_dict, "Exif", piexif.ExifIFD.ExposureTime)
        out["exposure_time"] = str(et) if et is not None else None
        gps = exif_dict.get("GPS", {})
        glat = gps.get(piexif.GPSIFD.GPSLatitude)
        glat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        glon = gps.get(piexif.GPSIFD.GPSLongitude)
        glon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)
        def conv_triplet(t):
            if not t:
                return None
            try:
                d = _rational_to_float(t[0])
                m = _rational_to_float(t[1])
                s = _rational_to_float(t[2])
                if d is None or m is None or s is None:
                    return None
                return d + (m / 60.0) + (s / 3600.0)
            except Exception:
                return None
        lat = conv_triplet(glat)
        lon = conv_triplet(glon)
        if lat is not None and (glat_ref in (b"S", "S")):
            lat = -lat
        if lon is not None and (glon_ref in (b"W", "W")):
            lon = -lon
        out["gps_lat"] = lat
        out["gps_lon"] = lon
    except Exception as e:
        log_event("error", rel_path=str(path), error=f"piexif_file: {e}")
    return out


def parse_captured_at(exif_map: Dict[str, Any], file_mtime: float) -> str:
    for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        raw = exif_map.get(key)
        if not raw:
            continue
        # EXIF often uses "YYYY:MM:DD HH:MM:SS"
        if isinstance(raw, bytes):
            raw = raw.decode(errors="ignore")
        raw = str(raw)
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.isoformat(timespec="seconds")
            except ValueError:
                pass
    return datetime.fromtimestamp(file_mtime).isoformat(timespec="seconds")


def build_ai_tags(filename: str, exif_map: Dict[str, Any], gps_lat: Optional[float], gps_lon: Optional[float]) -> list[str]:
    # Placeholder tags until real ONNX/CLIP/vision pipeline is added
    tags: set[str] = set()
    name = filename.lower()

    # Danish-friendly keyword hints
    keyword_groups = {
        "strand": {"strand", "beach", "kyst", "hav", "sea"},
        "solnedgang": {"solnedgang", "sunset", "aftenhimmel"},
        "skov": {"skov", "forest", "woods"},
        "bil": {"bil", "car", "tesla"},
        "familie": {"familie", "family", "middag", "jul"},
        "barn": {"barn", "kid", "baby", "child"},
    }
    for tag, words in keyword_groups.items():
        if any(w in name for w in words):
            tags.add(tag)

    if gps_lat is not None and gps_lon is not None:
        tags.update({"sted", "gps"})
    if exif_map.get("Model"):
        tags.add("kamera")
    if exif_map.get("LensModel"):
        tags.add("linse")

    return sorted(tags)


def make_thumb(img: Image.Image, rel_path: str, file_mtime: float, file_size: int, *, force: bool = False) -> str:
    key = hashlib.md5(f"{rel_path}|{file_mtime}|{file_size}".encode("utf-8")).hexdigest()
    thumb_name = f"{key}.jpg"
    thumb_path = THUMB_DIR / thumb_name
    try:
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if thumb_path.exists() and not force:
        return thumb_name

    # For animated GIFs we use the first frame for a deterministic thumbnail.
    try:
        if getattr(img, "is_animated", False):
            img.seek(0)
    except Exception:
        pass

    thumb = img.convert("RGB").copy()
    try:
        thumb = ImageOps.exif_transpose(thumb)
    except Exception:
        pass
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(thumb_path, format="JPEG", quality=85, optimize=True)
    return thumb_name


def _make_video_thumb(path: Path, rel_path: str, file_mtime: float, file_size: int) -> Optional[str]:
    """Extract a representative frame via ffmpeg and save as JPEG thumbnail.
    Returns the thumbnail file name or None on failure.
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "frame.jpg"
            # Grab a frame at 0.5s; fall back to first frame if video is shorter
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", "0.5", "-i", str(path),
                "-frames:v", "1",
                str(out_path),
            ]
            subprocess.run(cmd, check=True)
            with Image.open(out_path) as img:
                return make_thumb(img, rel_path, file_mtime, file_size)
    except Exception as e:
        try:
            log_event("error", rel_path=rel_path, error=f"video_thumb: {e}")
        except Exception:
            pass
        return None


def ensure_viewable_copy(path: Path, rel_path: str) -> Path:
    """Return a path that browsers and AI can read.
    For HEIC/HEIF originals (which browsers can't display and some libs can't stream),
    create a cached JPEG copy under CONVERT_DIR mirroring the folder structure,
    with suffix `_HEIC.jpg`. Reuse if up-to-date.
    """
    ext = path.suffix.lower()
    if ext not in {".heic", ".heif"}:
        return path
    try:
        dest_rel = Path(rel_path).with_suffix("")
        dest_rel = Path(str(dest_rel) + "_HEIC.jpg")
        dest = CONVERT_DIR / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Rebuild if missing or source newer
        if (not dest.exists()) or (path.stat().st_mtime > dest.stat().st_mtime):
            with Image.open(path) as im:
                try:
                    im = ImageOps.exif_transpose(im)
                except Exception:
                    pass
                rgb = im.convert("RGB")
                rgb.save(dest, format="JPEG", quality=92, optimize=True)
        return dest
    except Exception:
        return path


def extract_metadata(path: Path, rel_path: str, *, generate_thumb: bool = True) -> Dict[str, Any]:
    stat = path.stat()
    metadata: Dict[str, Any] = {
        "rel_path": rel_path,
        "filename": path.name,
        "ext": path.suffix.lower(),
        "file_size": stat.st_size,
        "created_fs": datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
        "modified_fs": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }

    # Prepare common fields used by the DB layer; always provide placeholders
    exif_map: Dict[str, Any] = {}
    thumb_name = None
    phash = None
    # Ensure all DB-bound fields exist (videos may not populate them)
    for k in (
        "width", "height", "camera_make", "camera_model", "lens_model",
        "iso", "focal_length", "f_number", "exposure_time",
        "gps_lat", "gps_lon", "gps_name",
    ):
        metadata[k] = None
    # Determine if file is a video (no EXIF parsing via Pillow)
    is_video = metadata["ext"] in VIDEO_EXTS
    if is_video:
        # Minimal fields for videos
        metadata.setdefault("captured_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"))
        # Attempt to make a thumbnail from first frame
        if generate_thumb:
            tn = _make_video_thumb(path, rel_path, stat.st_mtime, stat.st_size)
            if tn:
                thumb_name = tn
    
    if not is_video:
        # Images: read via Pillow to populate EXIF-derived fields
        try:
            with Image.open(path) as img:
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                metadata["width"], metadata["height"] = img.size
                exif_map = parse_exif(img)
                metadata["captured_at"] = parse_captured_at(exif_map, stat.st_mtime)
                metadata["camera_make"] = exif_map.get("Make")
                metadata["camera_model"] = exif_map.get("Model")
                metadata["lens_model"] = exif_map.get("LensModel")
                metadata["iso"] = exif_map.get("ISOSpeedRatings") or exif_map.get("PhotographicSensitivity")
                metadata["focal_length"] = _rational_to_float(exif_map.get("FocalLength"))
                metadata["f_number"] = _rational_to_float(exif_map.get("FNumber"))
                metadata["exposure_time"] = str(exif_map.get("ExposureTime")) if exif_map.get("ExposureTime") is not None else None
                metadata["gps_lat"] = exif_map.get("_gps_lat")
                metadata["gps_lon"] = exif_map.get("_gps_lon")
                metadata["gps_name"] = None  # placeholder for future reverse geocoding
                thumb_name = make_thumb(img, rel_path, stat.st_mtime, stat.st_size) if generate_thumb else None
                try:
                    phash = average_hash(img)
                except Exception:
                    phash = None
        except Exception as e:
            # Unsupported or damaged image: still index file-level info
            metadata.setdefault("captured_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"))
            metadata["thumb_error"] = str(e)

    # Fallbacks to enrich missing EXIF (camera, lens, GPS, date)
    try:
        ext = path.suffix.lower()
        if ext in {".heic", ".heif"}:
            extra = extract_exif_via_heif(path)
        elif ext in {".jpg", ".jpeg", ".tif", ".tiff"}:
            # prefer piexif on file (robust GPS), then exifread as backup
            extra = extract_exif_via_piexif_file(path)
            if not extra.get("gps_lat") and not extra.get("gps_lon"):
                more = extract_exif_via_exifread(path)
                extra.update({k: v for k, v in more.items() if v is not None})
        else:
            extra = extract_exif_via_exifread(path)
        for k in ("captured_at", "camera_make", "camera_model", "lens_model", "iso", "f_number", "focal_length", "exposure_time", "gps_lat", "gps_lon"):
            if metadata.get(k) in (None, "") and extra.get(k) is not None:
                metadata[k] = extra[k]
                if k in ("gps_lat", "gps_lon"):
                    log_event("exif_fallback", rel_path=rel_path, field=k, value=str(extra[k]))
    except Exception as e:
        log_event("error", rel_path=rel_path, error=f"exif_fallback: {e}")

    # Reverse geocoding (country, city) if GPS present
    try:
        lat_raw = metadata.get("gps_lat")
        lon_raw = metadata.get("gps_lon")
        if GEOCODE_ENABLE and (lat_raw is not None) and (lon_raw is not None):
            lat = float(lat_raw)
            lon = float(lon_raw)
            country, city = reverse_geocode_with_cache(lat, lon)
            # Save into metadata_json and gps_name for quick display
            if country or city:
                mj = metadata.get("metadata_json") or {}
                geo = mj.get("geo", {})
                if country and not geo.get("country"):
                    geo["country"] = country
                if city and not geo.get("city"):
                    geo["city"] = city
                mj["geo"] = geo
                metadata["metadata_json"] = mj
                if not metadata.get("gps_name"):
                    metadata["gps_name"] = ", ".join([x for x in [city, country] if x])
    except Exception as e:
        log_event("error", rel_path=rel_path, error=f"geocode_outer: {e}")

    # If critical EXIF is missing (common when HEIC was re-encoded as JPG without metadata),
    # try to enrich from a sibling HEIC/HEIF with same basename — but ONLY if the images
    # are visually the same (verified via perceptual hash distance threshold).
    try:
        if (not metadata.get("gps_lat") and not metadata.get("gps_lon")) or (not metadata.get("lens_model")):
            # Consider any sibling with the same basename but different extension (supported types)
            cur_phash = phash
            if cur_phash is None:
                try:
                    with Image.open(path) as _img_tmp:
                        try:
                            _img_tmp = ImageOps.exif_transpose(_img_tmp)
                        except Exception:
                            pass
                        cur_phash = average_hash(_img_tmp)
                except Exception:
                    cur_phash = None

            if cur_phash is not None:
                exts_to_try = set()
                for ext in SUPPORTED_EXTS:
                    if ext.lower() != metadata.get("ext", path.suffix.lower()):
                        exts_to_try.add(ext.lower())
                        exts_to_try.add(ext.upper())
                for ext in exts_to_try:
                    cand = path.with_suffix(ext)
                    if not cand.exists():
                        continue
                    try:
                        with Image.open(cand) as himg:
                            try:
                                himg = ImageOps.exif_transpose(himg)
                            except Exception:
                                pass
                            h_exif = parse_exif(himg)
                            try:
                                cand_phash = average_hash(himg)
                            except Exception:
                                cand_phash = None
                            if not cand_phash:
                                continue
                            dist = _hamdist_hex(cur_phash, cand_phash)
                            if dist <= PHASH_MATCH_THRESHOLD:  # visual match threshold
                                log_event("enrich", rel_path=rel_path, from_path=str(cand), distance=dist)
                                if not metadata.get("captured_at"):
                                    metadata["captured_at"] = parse_captured_at(h_exif, stat.st_mtime)
                                if not metadata.get("camera_make"):
                                    metadata["camera_make"] = h_exif.get("Make")
                                if not metadata.get("camera_model"):
                                    metadata["camera_model"] = h_exif.get("Model")
                                if not metadata.get("lens_model"):
                                    metadata["lens_model"] = h_exif.get("LensModel")
                                if not metadata.get("iso"):
                                    metadata["iso"] = h_exif.get("ISOSpeedRatings") or h_exif.get("PhotographicSensitivity")
                                if not metadata.get("focal_length"):
                                    metadata["focal_length"] = _rational_to_float(h_exif.get("FocalLength"))
                                if not metadata.get("f_number"):
                                    metadata["f_number"] = _rational_to_float(h_exif.get("FNumber"))
                                if metadata.get("gps_lat") is None and h_exif.get("_gps_lat") is not None:
                                    metadata["gps_lat"] = h_exif.get("_gps_lat")
                                if metadata.get("gps_lon") is None and h_exif.get("_gps_lon") is not None:
                                    metadata["gps_lon"] = h_exif.get("_gps_lon")
                                break  # stop at first valid visual match
                    except Exception:
                        continue
    except Exception:
        pass

    metadata["checksum_sha256"] = sha256_file(path)
    metadata["phash"] = phash
    metadata["thumb_name"] = thumb_name
    metadata["ai_tags"] = build_ai_tags(metadata["filename"], exif_map, metadata.get("gps_lat"), metadata.get("gps_lon"))
    metadata["exif_json"] = exif_map
    # Preserve any previously-added fields in metadata_json (e.g. geo from reverse geocoding)
    prev_mj = metadata.get("metadata_json") or {}
    mj: Dict[str, Any] = {**prev_mj}
    mj["file"] = {
        "rel_path": rel_path,
        "filename": path.name,
        "ext": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "created_fs": metadata["created_fs"],
        "modified_fs": metadata["modified_fs"],
    }
    mj["image"] = {"width": metadata.get("width"), "height": metadata.get("height")}
    mj["exif"] = exif_map
    # Add AI description tags and caption if present
    ai_desc_tags = metadata.get("ai_desc_tags")
    ai_desc_caption = metadata.get("ai_desc_caption")
    mj["ai"] = {
        "tags": metadata["ai_tags"],
        "desc_tags": ai_desc_tags if ai_desc_tags is not None else [],
        "desc_caption": ai_desc_caption if ai_desc_caption is not None else None,
        "embedding": None,
        "faces": []
    }
    metadata["metadata_json"] = mj
    return metadata


def reverse_geocode_with_cache(lat: float, lon: float) -> tuple[Optional[str], Optional[str]]:
    """Return (country, city) using cache and provider fallbacks."""
    lat_r = int(round(lat * 10000))
    lon_r = int(round(lon * 10000))
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT country, city FROM geo_cache WHERE lat_rounded=? AND lon_rounded=?",
            (lat_r, lon_r),
        ).fetchone()
    if row and (row["country"] or row["city"]):
        return row["country"], row["city"]

    country, city = reverse_geocode_providers(lat, lon)
    if country or city:
        with closing(get_conn()) as conn:
            conn.execute(
                "INSERT INTO geo_cache(lat_rounded, lon_rounded, country, city, created_at) VALUES (?,?,?,?,?)",
                (lat_r, lon_r, country, city, now_iso()),
            )
            conn.commit()
    return country, city


def reverse_geocode_providers(lat: float, lon: float) -> tuple[Optional[str], Optional[str]]:
    """Try configured provider first, then fallbacks (Offline RG → Nominatim → BigDataCloud → Photon)."""
    order: list[str] = []
    pref = GEOCODE_PROVIDER or "rg"
    if pref not in ("rg", "nominatim", "bigdatacloud", "photon"):
        pref = "rg"
    order.append(pref)
    for p in ("rg", "nominatim", "bigdatacloud", "photon"):
        if p not in order:
            order.append(p)

    last_err = None
    ua = {"User-Agent": f"FjordLens/1.0 ({GEOCODE_EMAIL})"}
    for prov in order:
        try:
            time.sleep(max(0.0, GEOCODE_DELAY))
            if prov == "rg":
                # Offline reverse geocoder (city-level, no network)
                try:
                    out = rg.search((lat, lon), mode=1, verbose=False)
                except TypeError:
                    # older versions don't support verbose arg
                    out = rg.search((lat, lon), mode=1)
                if out:
                    rec = out[0]
                    city = rec.get("name") or rec.get("admin1") or rec.get("admin2")
                    cc = rec.get("cc")
                    country = None
                    if cc:
                        try:
                            c = pycountry.countries.get(alpha_2=cc.upper())
                            country = getattr(c, "name", None)
                        except Exception:
                            country = cc
                    if country or city:
                        return country, city
            elif prov == "nominatim":
                r = requests.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1},
                    headers=ua,
                    timeout=GEOCODE_TIMEOUT,
                )
                if r.status_code == 429:
                    last_err = "nominatim 429"
                    continue
                if r.ok:
                    js = r.json()
                    addr = js.get("address", {})
                    country = addr.get("country")
                    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet")
                    if country or city:
                        return country, city
            elif prov == "bigdatacloud":
                r = requests.get(
                    "https://api.bigdatacloud.net/data/reverse-geocode-client",
                    params={"latitude": lat, "longitude": lon, "localityLanguage": GEOCODE_LANG or "en"},
                    headers=ua,
                    timeout=GEOCODE_TIMEOUT,
                )
                if r.ok:
                    js = r.json()
                    country = js.get("countryName")
                    city = js.get("city") or js.get("locality") or js.get("principalSubdivision")
                    if country or city:
                        return country, city
            elif prov == "photon":
                r = requests.get(
                    "https://photon.komoot.io/reverse",
                    params={"lat": lat, "lon": lon, "lang": GEOCODE_LANG or "en"},
                    headers=ua,
                    timeout=GEOCODE_TIMEOUT,
                )
                if r.ok:
                    js = r.json()
                    feats = js.get("features") or []
                    if feats:
                        props = feats[0].get("properties", {})
                        country = props.get("country")
                        city = props.get("city") or props.get("town") or props.get("village") or props.get("state") or props.get("name")
                        if country or city:
                            return country, city
        except Exception as e:
            last_err = str(e)
            continue
    if last_err:
        log_event("error", rel_path="geocode", error=f"providers_failed: {last_err}")
    return None, None


def rescan_metadata(stop_event=None) -> Dict[str, Any]:
    init_db()
    log_event("rescan_start")
    scanned = 0
    updated = 0
    errors = 0
    missing = 0
    samples: list[str] = []

    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT id, rel_path, thumb_name,
                   gps_lat, gps_lon, lens_model, camera_make, camera_model,
                   captured_at, iso, focal_length, f_number,
                   gps_name, metadata_json
            FROM photos
            """
        ).fetchall()

    for row in rows:
        if stop_event and stop_event.is_set():
            break
        rel_path = row["rel_path"]
        disk_path = PHOTO_DIR / rel_path
        scanned += 1
        log_event("rescan_check", rel_path=rel_path)
        if not disk_path.exists():
            missing += 1
            log_event("missing", rel_path=rel_path)
            continue
        try:
            meta = extract_metadata(disk_path, rel_path, generate_thumb=False)
            # Preserve existing thumbnail name if we didn't regenerate
            if not meta.get("thumb_name"):
                meta["thumb_name"] = row["thumb_name"]
            # Determine if anything actually changes (subset of important fields)
            changed = False
            keys = [
                "gps_lat", "gps_lon", "lens_model", "camera_make", "camera_model",
                "captured_at", "iso", "focal_length", "f_number"
            ]
            for k in keys:
                old = row[k]
                new = meta.get(k)
                if old != new:
                    changed = True
                    break
            # If not changed yet, see if reverse-geocoded geo/city/country was added
            if not changed:
                try:
                    old_mj = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                except Exception:
                    old_mj = {}
                old_geo = (old_mj.get("geo") or {})
                new_mj = meta.get("metadata_json") or {}
                new_geo = (new_mj.get("geo") or {})
                old_city = old_geo.get("city")
                old_country = old_geo.get("country")
                new_city = new_geo.get("city")
                new_country = new_geo.get("country")
                if (new_city and new_city != old_city) or (new_country and new_country != old_country):
                    changed = True
                elif (meta.get("gps_name") or None) != (row["gps_name"] or None):
                    changed = True
            if changed:
                upsert_photo(meta)
                updated += 1
                log_event("rescan_updated", rel_path=rel_path)
            else:
                log_event("no_new", rel_path=rel_path)
        except Exception as e:
            errors += 1
            log_event("error", rel_path=rel_path, error=str(e))
            if len(samples) < 5:
                samples.append(f"{rel_path}: {e}")

    result = {
        "ok": True,
        "scanned": scanned,
        "updated": updated,
        "errors": errors,
        "missing": missing,
        "error_samples": samples,
    }
    log_event("rescan_done", scanned=scanned, updated=updated, errors=errors, missing=missing)
    return result


# --- Face indexing API ---
_faces_running = threading.Event()
faces_counts: Dict[str, int] = {"processed": 0, "total": 0}
last_faces_result: Optional[Dict[str, Any]] = None


def _index_faces_worker(all_photos: bool = False):
    global faces_counts, last_faces_result
    try:
        with closing(get_conn()) as conn:
            if all_photos:
                rows = conn.execute("SELECT rel_path FROM photos").fetchall()
            else:
                rows = conn.execute("SELECT rel_path FROM photos WHERE people_count=0").fetchall()
        total = len(rows)
        faces_counts = {"processed": 0, "total": total}
        for row in rows:
            if not _faces_running.is_set():
                break
            rel = row["rel_path"]
            log_event("faces_index", rel_path=rel)
            index_faces_for_photo(rel)
            faces_counts["processed"] += 1
            face_delay = faces_index_throttle_enabled_sec()
            if face_delay > 0:
                time.sleep(face_delay)
        last_faces_result = {"ok": True, **faces_counts}
    finally:
        _faces_running.clear()


@app.route("/api/faces/index", methods=["POST"])
def api_faces_index():
    global faces_counts
    if _faces_running.is_set():
        return jsonify({"ok": False, "error": "Faces indexing already running"}), 409
    scope = (request.args.get("scope") or "").strip().lower()
    _set_setting("faces_auto_index", "1")
    if scope == "new":
        return jsonify({"ok": True, "running": False, "auto_index": True, "scope": "new"})

    _faces_running.set()
    faces_counts = {"processed": 0, "total": 0}
    all_photos = True if scope == "all" else (request.args.get("all") in {"1", "true", "True"})
    threading.Thread(target=_index_faces_worker, args=(all_photos,), daemon=True).start()
    return jsonify({"ok": True, "running": True, "auto_index": True, "scope": (scope or ("all" if all_photos else "missing"))})


@app.route("/api/faces/stop", methods=["POST"])
def api_faces_stop():
    _set_setting("faces_auto_index", "0")
    if _faces_running.is_set():
        _faces_running.clear()
        return jsonify({"ok": True, "running": True, "stopping": True, "auto_index": False})
    return jsonify({"ok": True, "running": False, "auto_index": False})


@app.route("/api/faces/status")
def api_faces_status():
    resp: Dict[str, Any] = {"ok": True, "running": _faces_running.is_set(), "auto_index": faces_auto_index_enabled(), **faces_counts}
    if not _faces_running.is_set() and last_faces_result:
        resp["last"] = last_faces_result
    return jsonify(resp)


def upsert_photo(meta: Dict[str, Any]) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            INSERT INTO photos (
                rel_path, filename, ext, file_size, width, height, created_fs, modified_fs,
                captured_at, camera_make, camera_model, lens_model, iso, focal_length, f_number,
                exposure_time, gps_lat, gps_lon, gps_name, checksum_sha256, phash, thumb_name,
                favorite, people_count, ai_tags, embedding_json, metadata_json, exif_json,
                uploaded_by, imported_at, last_scanned_at
            ) VALUES (
                :rel_path, :filename, :ext, :file_size, :width, :height, :created_fs, :modified_fs,
                :captured_at, :camera_make, :camera_model, :lens_model, :iso, :focal_length, :f_number,
                :exposure_time, :gps_lat, :gps_lon, :gps_name, :checksum_sha256, :phash, :thumb_name,
                COALESCE((SELECT favorite FROM photos WHERE rel_path=:rel_path), 0),
                COALESCE((SELECT people_count FROM photos WHERE rel_path=:rel_path), 0),
                :ai_tags, COALESCE((SELECT embedding_json FROM photos WHERE rel_path=:rel_path), NULL),
                :metadata_json, :exif_json,
                COALESCE((SELECT uploaded_by FROM photos WHERE rel_path=:rel_path), :uploaded_by),
                COALESCE((SELECT imported_at FROM photos WHERE rel_path=:rel_path), :imported_at),
                :last_scanned_at
            )
            ON CONFLICT(rel_path) DO UPDATE SET
                filename=excluded.filename,
                ext=excluded.ext,
                file_size=excluded.file_size,
                width=excluded.width,
                height=excluded.height,
                created_fs=excluded.created_fs,
                modified_fs=excluded.modified_fs,
                captured_at=excluded.captured_at,
                camera_make=excluded.camera_make,
                camera_model=excluded.camera_model,
                lens_model=excluded.lens_model,
                iso=excluded.iso,
                focal_length=excluded.focal_length,
                f_number=excluded.f_number,
                exposure_time=excluded.exposure_time,
                gps_lat=excluded.gps_lat,
                gps_lon=excluded.gps_lon,
                gps_name=excluded.gps_name,
                checksum_sha256=excluded.checksum_sha256,
                phash=excluded.phash,
                thumb_name=excluded.thumb_name,
                ai_tags=excluded.ai_tags,
                metadata_json=excluded.metadata_json,
                exif_json=excluded.exif_json,
                uploaded_by=COALESCE(excluded.uploaded_by, uploaded_by),
                last_scanned_at=excluded.last_scanned_at
            """,
            {
                **meta,
                "ai_tags": json.dumps(meta.get("ai_tags", []), ensure_ascii=False),
                "metadata_json": json.dumps(meta.get("metadata_json", {}), ensure_ascii=False, default=str),
                "exif_json": json.dumps(meta.get("exif_json", {}), ensure_ascii=False, default=str),
                "uploaded_by": _sanitize_share_visitor_name(meta.get("uploaded_by") or "") or None,
                "imported_at": now_iso(),
                "last_scanned_at": now_iso(),
            },
        )
        conn.commit()


def iter_photo_files(root: Path, prefix: str = "") -> Iterable[Tuple[Path, str]]:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        # Skip Synology generated thumbnails and special folders
        name_upper = p.name.upper()
        if any(part == "@eaDir" for part in p.parts):
            continue
        if name_upper.startswith("SYNOPHOTO_THUMB_") or name_upper.startswith("SYNOPHOTO_CACHE_"):
            continue
        if p.name.startswith("._"):  # macOS resource forks
            continue
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except Exception:
            rel = p.name
        if prefix:
            rel = f"{prefix.rstrip('/')}/{rel}"
        yield p, rel


def scan_library(stop_event=None) -> Dict[str, Any]:
    init_db()
    log_event("scan_start")

    if not PHOTO_DIR.exists():
        return {
            "ok": False,
            "error": f"Photo folder not found: {PHOTO_DIR}",
            "scanned": 0,
            "updated": 0,
            "errors": 0,
        }

    scanned = 0
    updated = 0
    errors = 0
    error_samples: list[str] = []

    with closing(get_conn()) as conn:
        existing = {
            row["rel_path"]: row
            for row in conn.execute(
                "SELECT rel_path, modified_fs, file_size, gps_lat, gps_lon, lens_model FROM photos"
            )
        }


    # Scan primary photo directory
    for path, rel_path in iter_photo_files(PHOTO_DIR):
        if stop_event and stop_event.is_set():
            break
        scanned += 1
        try:
            log_event("scan_check", rel_path=rel_path)
            stat = path.stat()
            modified_fs = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_size = stat.st_size
            prev = existing.get(rel_path)
            if prev:
                unchanged = (prev["modified_fs"] == modified_fs and prev["file_size"] == file_size)
                missing_meta = (prev["lens_model"] in (None, "")) or (prev["gps_lat"] is None and prev["gps_lon"] is None)
                if unchanged and not missing_meta:
                    log_event("skip_unchanged", rel_path=rel_path)
                    log_event("no_new", rel_path=rel_path)
                    continue

            meta = extract_metadata(path, rel_path)
            upsert_photo(meta)
            updated += 1
            log_event("indexed", rel_path=rel_path)
        except Exception as e:
            errors += 1
            log_event("error", rel_path=rel_path, error=str(e))
            if len(error_samples) < 5:
                error_samples.append(f"{rel_path}: {e}")

    # Also scan uploaded files stored under DATA_DIR/uploads (prefixed as 'uploads/...')
    for path, rel_path in iter_photo_files(UPLOAD_DIR, prefix="uploads"):
        if stop_event and stop_event.is_set():
            break
        scanned += 1
        try:
            log_event("scan_check", rel_path=rel_path)
            stat = path.stat()
            modified_fs = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_size = stat.st_size
            prev = existing.get(rel_path)
            if prev:
                unchanged = (prev["modified_fs"] == modified_fs and prev["file_size"] == file_size)
                missing_meta = (prev["lens_model"] in (None, "")) or (prev["gps_lat"] is None and prev["gps_lon"] is None)
                if unchanged and not missing_meta:
                    log_event("skip_unchanged", rel_path=rel_path)
                    log_event("no_new", rel_path=rel_path)
                    continue

            meta = extract_metadata(path, rel_path)
            upsert_photo(meta)
            updated += 1
            log_event("indexed", rel_path=rel_path)
        except Exception as e:
            errors += 1
            log_event("error", rel_path=rel_path, error=str(e))
            if len(error_samples) < 5:
                error_samples.append(f"{rel_path}: {e}")

    result = {
        "ok": True,
        "photo_dir": str(PHOTO_DIR),
        "scanned": scanned,
        "updated": updated,
        "errors": errors,
        "error_samples": error_samples,
        "stopped": bool(stop_event.is_set()) if stop_event else False,
    }
    log_event("scan_done", scanned=scanned, updated=updated, errors=errors)
    return result


def row_to_public(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for key in ("ai_tags", "ai_desc_tags", "embedding_json", "metadata_json", "exif_json"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
        else:
            d[key] = [] if key in {"ai_tags", "ai_desc_tags"} else None
    if d.get("ai_desc_caption"):
        d["ai_desc_caption"] = str(d.get("ai_desc_caption") or "").strip()
    else:
        d["ai_desc_caption"] = None
    d["favorite"] = bool(d.get("favorite", 0))
    if d.get("thumb_name"):
        d["thumb_url"] = f"/api/thumbs/{d['thumb_name']}"
    else:
        d["thumb_url"] = None
    # Public URL to original (for viewer)
    rel = d.get("rel_path") or d.get("filename")
    if rel:
        try:
            # Serve a browser-friendly copy when needed
            d["original_url"] = f"/api/viewable/{quote(rel)}"
            d["download_url"] = f"/api/original/{quote(rel)}"
        except Exception:
            d["original_url"] = None
            d["download_url"] = None
    else:
        d["original_url"] = None
        d["download_url"] = None
    # Annotate media type
    try:
        ext = (d.get("ext") or "").lower()
        d["is_video"] = ext in VIDEO_EXTS
    except Exception:
        d["is_video"] = False
    # Friendly device and lens labels
    try:
        make = (d.get("camera_make") or "").strip()
        model = (d.get("camera_model") or "").strip()
        dev_label = " ".join([x for x in [make, model] if x]).strip()
        d["device_label"] = dev_label if dev_label else None
        lens = (d.get("lens_model") or "").strip()
        if lens and dev_label:
            # remove occurrences of device make/model in lens text (case-insensitive)
            lm = lens
            for s in {make, model, dev_label}:
                if s:
                    try:
                        lm = re.sub(re.escape(s), "", lm, flags=re.IGNORECASE)
                    except re.error:
                        pass
            lm = re.sub(r"\s{2,}", " ", lm).strip(" -,")
            d["lens_label"] = lm if lm else lens
        else:
            d["lens_label"] = lens or None
    except Exception:
        d["device_label"] = (d.get("camera_model") or d.get("camera_make"))
        d["lens_label"] = d.get("lens_model")
    return d


def _row_to_share_public(row: sqlite3.Row, token: str) -> Dict[str, Any]:
    d = row_to_public(row)
    pid = int(d.get("id") or 0)
    if pid > 0:
        d["thumb_url"] = url_for("api_share_thumb", token=token, photo_id=pid)
        d["original_url"] = url_for("api_share_viewable", token=token, photo_id=pid)
        d["download_url"] = url_for("api_share_original", token=token, photo_id=pid)
    return d


@app.route("/api/people")
def api_people_list():
    """List people with face counts and a sample thumbnail."""
    include_hidden = request.args.get("include_hidden") in {"1", "true", "True"}
    with closing(get_conn()) as conn:
        acl_prefixes = _current_user_acl_prefixes(conn)
        where = "" if include_hidden else "WHERE COALESCE(p.hidden,0)=0"
        rows = conn.execute(
            f"""
            SELECT p.id, p.name, COALESCE(p.hidden,0) AS hidden
            FROM people p
            {where}
            ORDER BY p.name COLLATE NOCASE ASC
            """
        ).fetchall()
        people = []
        for r in rows:
            pid = int(r["id"])
            name = r["name"]
            hidden = bool(int(r["hidden"] or 0))

            if acl_prefixes is None:
                cnt_row = conn.execute("SELECT COUNT(*) AS c FROM faces WHERE person_id=?", (pid,)).fetchone()
                cnt = int(cnt_row["c"] or 0) if cnt_row else 0
                face_row = conn.execute("SELECT id FROM faces WHERE person_id=? ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
            else:
                clauses = []
                params: list[Any] = [pid]
                for pref in acl_prefixes:
                    clauses.append("(ph.rel_path=? OR ph.rel_path LIKE ?)")
                    params.extend([pref, pref + "/%"])
                where_acl = " OR ".join(clauses) if clauses else "0=1"
                cnt_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM faces f
                    INNER JOIN photos ph ON ph.id = f.photo_id
                    WHERE f.person_id=? AND ({where_acl})
                    """,
                    params,
                ).fetchone()
                cnt = int(cnt_row["c"] or 0) if cnt_row else 0
                face_row = conn.execute(
                    f"""
                    SELECT f.id
                    FROM faces f
                    INNER JOIN photos ph ON ph.id = f.photo_id
                    WHERE f.person_id=? AND ({where_acl})
                    ORDER BY f.id DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()

            thumb_url = f"/api/face-thumb/{int(face_row['id'])}" if face_row else None
            if cnt > 0:
                people.append({"id": pid, "name": name, "count": cnt, "thumb_url": thumb_url, "hidden": hidden})

        if acl_prefixes is None:
            unk = conn.execute(
                "SELECT COUNT(DISTINCT photo_id) AS c FROM faces WHERE person_id IS NULL"
            ).fetchone()
            unk_count = int(unk["c"] or 0) if unk else 0
            frow = conn.execute(
                "SELECT id FROM faces WHERE person_id IS NULL ORDER BY id DESC LIMIT 1"
            ).fetchone()
        else:
            clauses = []
            params2: list[Any] = []
            for pref in acl_prefixes:
                clauses.append("(ph.rel_path=? OR ph.rel_path LIKE ?)")
                params2.extend([pref, pref + "/%"])
            where_acl = " OR ".join(clauses) if clauses else "0=1"
            unk = conn.execute(
                f"""
                SELECT COUNT(DISTINCT f.photo_id) AS c
                FROM faces f
                INNER JOIN photos ph ON ph.id = f.photo_id
                WHERE f.person_id IS NULL AND ({where_acl})
                """,
                params2,
            ).fetchone()
            unk_count = int(unk["c"] or 0) if unk else 0
            frow = conn.execute(
                f"""
                SELECT f.id
                FROM faces f
                INNER JOIN photos ph ON ph.id = f.photo_id
                WHERE f.person_id IS NULL AND ({where_acl})
                ORDER BY f.id DESC
                LIMIT 1
                """,
                params2,
            ).fetchone()

        if unk_count > 0:
            thumb_url = f"/api/face-thumb/{int(frow['id'])}" if frow else None
            people.insert(0, {"id": "unknown", "name": "Ukendte", "count": unk_count, "thumb_url": thumb_url})
    return jsonify({"ok": True, "items": people})


@app.route("/api/people/<int:pid>/hide", methods=["POST"])
def api_people_hide(pid: int):
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    try:
        data = request.get_json(silent=True) or {}
        val = data.get("hidden")
        hidden = 1 if (val in (1, True, "1", "true", "True", None)) else 0
        with closing(get_conn()) as conn:
            conn.execute("UPDATE people SET hidden=? WHERE id=?", (hidden, pid))
            conn.commit()
        return jsonify({"ok": True, "id": pid, "hidden": bool(hidden)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/people/<int:pid>/photos")
def api_people_photos(pid: int):
    """List photos that include a given person id."""
    items: list[Dict[str, Any]] = []
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT p.*
            FROM photos p
            INNER JOIN faces f ON f.photo_id = p.id
            WHERE f.person_id = ?
            ORDER BY COALESCE(p.captured_at, p.modified_fs, p.created_fs) DESC
            """,
            (pid,),
        ).fetchall()
        for r in rows:
            if _is_rel_path_allowed_for_current_user(r["rel_path"], conn):
                items.append(row_to_public(r))
    return jsonify({"ok": True, "items": items})


@app.route("/api/people/unknown/photos-faces")
def api_people_unknown_photos_faces():
    items: list[Dict[str, Any]] = []
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT p.*, f.id as face_id, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h
            FROM photos p
            INNER JOIN faces f ON f.photo_id = p.id
            WHERE f.person_id IS NULL
            ORDER BY COALESCE(p.captured_at, p.modified_fs, p.created_fs) DESC, f.id DESC
            """
        ).fetchall()
        # Group faces per photo
        by_photo: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            if not _is_rel_path_allowed_for_current_user(r["rel_path"], conn):
                continue
            pid_ = int(r["id"])  # photo id
            if pid_ not in by_photo:
                by_photo[pid_] = row_to_public(r)
                by_photo[pid_]["faces"] = []
            try:
                w = float(r["width"] or 0) or 1.0
                h = float(r["height"] or 0) or 1.0
            except Exception:
                w, h = 1.0, 1.0
            x = max(0.0, float(r["bbox_x"] or 0) / w)
            y = max(0.0, float(r["bbox_y"] or 0) / h)
            bw = max(0.0, float(r["bbox_w"] or 0) / w)
            bh = max(0.0, float(r["bbox_h"] or 0) / h)
            by_photo[pid_]["faces"].append({"x": x, "y": y, "w": bw, "h": bh, "id": int(r["face_id"])})
    items = list(by_photo.values())
    return jsonify({"ok": True, "items": items})


@app.route("/api/face-thumb/<int:face_id>")
def api_face_thumb(face_id: int):
    # Serve cached face thumbnail; if missing/stale, queue background generation and return fallback quickly.
    try:
        with closing(get_conn()) as conn:
            r = conn.execute(
                "SELECT f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, p.rel_path, p.thumb_name FROM faces f INNER JOIN photos p ON p.id = f.photo_id WHERE f.id=?",
                (face_id,),
            ).fetchone()
        if not r:
            return ("Not found", 404)
        src_rel = r["rel_path"]
        if not _is_rel_path_allowed_for_current_user(src_rel):
            return ("Forbidden", 403)

        out_name = f"face_{face_id}.jpg"
        out_path = THUMB_DIR / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)

        src_path = (UPLOAD_DIR / src_rel.split("/", 1)[1]) if src_rel.startswith("uploads/") else (PHOTO_DIR / src_rel)
        view_path = ensure_viewable_copy(src_path, src_rel)
        source_mtime = 0.0
        try:
            source_mtime = float(view_path.stat().st_mtime)
        except Exception:
            source_mtime = 0.0

        is_ready = False
        try:
            is_ready = out_path.exists() and (out_path.stat().st_mtime >= source_mtime)
        except Exception:
            is_ready = False

        if is_ready:
            resp = send_from_directory(str(THUMB_DIR), out_name)
            resp.headers["Cache-Control"] = "no-store"
            return resp

        _enqueue_face_thumb_generation(face_id)

        fallback_name = str(r["thumb_name"] or "").strip()
        if fallback_name and (THUMB_DIR / fallback_name).exists():
            resp = send_from_directory(str(THUMB_DIR), fallback_name)
            resp.headers["Cache-Control"] = "no-store"
            return resp

        # Never build synchronously here: many concurrent requests can spike memory/CPU.
        # Background worker will create the face thumb; until then return a tiny placeholder.
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'>"
            "<rect width='64' height='64' fill='#1a2233'/>"
            "<circle cx='32' cy='24' r='12' fill='#8aa0c8'/>"
            "<rect x='14' y='40' width='36' height='16' rx='8' fill='#8aa0c8'/>"
            "</svg>"
        )
        resp = make_response(svg, 200)
        resp.headers["Content-Type"] = "image/svg+xml"
        resp.headers["Cache-Control"] = "no-store"
        return resp
    except Exception as e:
        return (str(e), 500)


_face_thumb_queue: "queue.Queue[int]" = queue.Queue()
_face_thumb_worker_started = False
_face_thumb_lock = threading.Lock()
_face_thumb_queued: set[int] = set()

# HEIC bulk conversion worker
heic_convert_thread = None
last_heic_convert_result: Optional[Dict[str, Any]] = None


def _build_face_thumb(face_id: int) -> bool:
    try:
        with closing(get_conn()) as conn:
            r = conn.execute(
                "SELECT f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, p.rel_path FROM faces f INNER JOIN photos p ON p.id = f.photo_id WHERE f.id=?",
                (face_id,),
            ).fetchone()
        if not r:
            return False
        src_rel = r["rel_path"]
        src_path = (UPLOAD_DIR / src_rel.split("/", 1)[1]) if src_rel.startswith("uploads/") else (PHOTO_DIR / src_rel)
        view_path = ensure_viewable_copy(src_path, src_rel)

        out_name = f"face_{face_id}.jpg"
        out_path = THUMB_DIR / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)

        needs_build = True
        try:
            needs_build = (not out_path.exists()) or (view_path.stat().st_mtime > out_path.stat().st_mtime)
        except Exception:
            needs_build = True

        if not needs_build:
            return True

        with Image.open(view_path) as im:
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            x = max(0, int(r["bbox_x"] or 0))
            y = max(0, int(r["bbox_y"] or 0))
            w = max(1, int(r["bbox_w"] or 1))
            h = max(1, int(r["bbox_h"] or 1))
            pad = int(max(w, h) * 0.25)
            cx1 = max(0, x - pad)
            cy1 = max(0, y - pad)
            cx2 = min(im.width, x + w + pad)
            cy2 = min(im.height, y + h + pad)
            crop = im.crop((cx1, cy1, cx2, cy2)).convert("RGB")
            crop.thumbnail((300, 300))
            crop.save(out_path, format="JPEG", quality=90, optimize=True)
        return True
    except Exception as e:
        try:
            log_event("error", error=f"face_thumb_bg: {e}", face_id=face_id)
        except Exception:
            pass
        return False


def _face_thumb_worker_loop() -> None:
    while True:
        try:
            face_id = int(_face_thumb_queue.get())
        except Exception:
            continue
        try:
            _build_face_thumb(face_id)
        finally:
            with _face_thumb_lock:
                _face_thumb_queued.discard(face_id)
            _face_thumb_queue.task_done()


def _ensure_face_thumb_worker() -> None:
    global _face_thumb_worker_started
    if _face_thumb_worker_started:
        return
    with _face_thumb_lock:
        if _face_thumb_worker_started:
            return
        threading.Thread(target=_face_thumb_worker_loop, daemon=True).start()
        _face_thumb_worker_started = True


def _enqueue_face_thumb_generation(face_id: int) -> None:
    _ensure_face_thumb_worker()
    with _face_thumb_lock:
        if face_id in _face_thumb_queued:
            return
        _face_thumb_queued.add(face_id)
    _face_thumb_queue.put(face_id)


@app.route("/api/face-thumb/status/<int:face_id>")
def api_face_thumb_status(face_id: int):
    """Lightweight readiness check for a face thumbnail.
    Returns {ready: bool, url: str, v: int} where url contains a cache-busting
    version param based on mtime when ready.
    """
    try:
        with closing(get_conn()) as conn:
            r = conn.execute(
                "SELECT f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, p.rel_path, p.thumb_name FROM faces f INNER JOIN photos p ON p.id = f.photo_id WHERE f.id=?",
                (face_id,),
            ).fetchone()
        if not r:
            return jsonify({"ok": False, "ready": False, "error": "not_found"}), 404
        src_rel = r["rel_path"]
        if not _is_rel_path_allowed_for_current_user(src_rel):
            return jsonify({"ok": False, "ready": False, "error": "forbidden"}), 403

        out_name = f"face_{face_id}.jpg"
        out_path = THUMB_DIR / out_name
        src_path = (UPLOAD_DIR / src_rel.split("/", 1)[1]) if src_rel.startswith("uploads/") else (PHOTO_DIR / src_rel)
        view_path = ensure_viewable_copy(src_path, src_rel)
        try:
            source_mtime = float(view_path.stat().st_mtime)
        except Exception:
            source_mtime = 0.0
        ready = False
        ver = 0
        try:
            ready = out_path.exists() and (out_path.stat().st_mtime >= source_mtime)
            if ready:
                ver = int(out_path.stat().st_mtime)
        except Exception:
            ready = False
        if not ready:
            _enqueue_face_thumb_generation(face_id)
        url = f"/api/face-thumb/{face_id}" + (f"?v={ver}" if ver else "")
        return jsonify({"ok": True, "ready": bool(ready), "url": url, "v": ver})
    except Exception as e:
        return jsonify({"ok": False, "ready": False, "error": str(e)}), 500


@app.route("/api/people/unknown/photos")
def api_people_unknown_photos():
    items: list[Dict[str, Any]] = []
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.*
            FROM photos p
            INNER JOIN faces f ON f.photo_id = p.id
            WHERE f.person_id IS NULL
            ORDER BY COALESCE(p.captured_at, p.modified_fs, p.created_fs) DESC
            """
        ).fetchall()
        for r in rows:
            if _is_rel_path_allowed_for_current_user(r["rel_path"], conn):
                items.append(row_to_public(r))
    return jsonify({"ok": True, "items": items})


@app.route("/api/people/<int:pid>/rename", methods=["POST"])
def api_people_rename(pid: int):
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"ok": False, "error": "Missing name"}), 400
    try:
        with closing(get_conn()) as conn:
            src = conn.execute("SELECT id, name FROM people WHERE id=?", (pid,)).fetchone()
            if not src:
                return jsonify({"ok": False, "error": "Person not found"}), 404

            existing = conn.execute("SELECT id, name FROM people WHERE LOWER(name)=LOWER(?)", (new_name,)).fetchone()
            if existing and int(existing["id"]) != int(pid):
                target_id = int(existing["id"])
                conn.execute("UPDATE faces SET person_id=? WHERE person_id=?", (target_id, pid))
                conn.execute("DELETE FROM people WHERE id=?", (pid,))
                conn.commit()
                return jsonify({
                    "ok": True,
                    "merged": True,
                    "from_id": pid,
                    "to_id": target_id,
                    "name": str(existing["name"] or new_name),
                })

            conn.execute("UPDATE people SET name=? WHERE id=?", (new_name, pid))
            conn.commit()
        return jsonify({"ok": True, "id": pid, "name": new_name, "merged": False})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Name already exists"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _cosine(a: list[float], b: list[float]) -> float:
    try:
        import math
        if not a or not b:
            return -1.0
        s = sum(x*y for x, y in zip(a, b))
        na = math.sqrt(sum(x*x for x in a)) or 1.0
        nb = math.sqrt(sum(y*y for y in b)) or 1.0
        return s / (na * nb)
    except Exception:
        return -1.0


QUERY_STOPWORDS_DA = {
    "der", "som", "og", "i", "på", "ved", "til", "af", "for", "med",
    "en", "et", "den", "det", "de", "er", "at", "om",
}

QUERY_STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "by",
    "is", "are", "was", "were", "be", "being", "been", "that", "this", "these", "those",
}


DANISH_SYNONYM_GROUPS = [
    {"person", "personer", "menneske", "mennesker", "people", "man", "woman", "child", "barn"},
    {"strand", "beach", "hav", "kyst"},
    {"hav", "sea", "ocean", "strand", "kyst"},
    {"skov", "forest", "woods"},
    {"bil", "car", "auto", "tesla"},
    {"solnedgang", "sunset", "aftenhimmel"},
    {"kamera", "camera"},
    {"familie", "family", "jul", "middag"},
    {"løber", "løb", "loeb", "running", "runner", "jogging"},
    {"cykler", "cykle", "cykel", "cycling", "bicycle", "bike"},
    {
        "svømmer", "svøm", "svømme", "svømning", "bader", "bade", "badning",
        "svommer", "svoemmer", "swim", "swimming", "bathing",
    },
]


def _fold_danish(text: str) -> str:
    return (
        (text or "")
        .lower()
        .replace("æ", "ae")
        .replace("ø", "oe")
        .replace("å", "aa")
    )


SYNONYM_LOOKUP: Dict[str, set[str]] = {}
for _group in DANISH_SYNONYM_GROUPS:
    expanded = set(_group)
    for _term in list(_group):
        expanded.add(_fold_danish(_term))
    for _term in expanded:
        SYNONYM_LOOKUP[_term] = expanded


def _query_term_groups(q: str, search_language: str = DEFAULT_SEARCH_LANGUAGE) -> list[set[str]]:
    q = (q or "").strip().lower()
    if not q:
        return []
    lang = _normalize_language(search_language, DEFAULT_SEARCH_LANGUAGE)
    stopwords = QUERY_STOPWORDS_DA if lang == LANG_DA else QUERY_STOPWORDS_EN
    raw_words = [w for w in re.findall(r"[0-9a-zA-ZæøåÆØÅ]+", q) if w]
    words = [w.lower() for w in raw_words if w.lower() not in stopwords]
    groups: list[set[str]] = []
    for w in words:
        key = _fold_danish(w)
        group = SYNONYM_LOOKUP.get(key)
        if group:
            groups.append(group)
        else:
            groups.append({w, key})
    return groups


def matches_search(photo: Dict[str, Any], q: str, search_language: str = DEFAULT_SEARCH_LANGUAGE) -> bool:
    term_groups = _query_term_groups(q, search_language)
    if not term_groups:
        return True

    fields = [
        str(photo.get("filename") or "").lower(),
        str(photo.get("rel_path") or "").lower(),
        str(photo.get("camera_make") or "").lower(),
        str(photo.get("camera_model") or "").lower(),
        str(photo.get("lens_model") or "").lower(),
        str(photo.get("gps_name") or "").lower(),
        " ".join((photo.get("ai_tags") or [])).lower(),
        " ".join((photo.get("ai_desc_tags") or [])).lower(),
        str(photo.get("ai_desc_caption") or "").lower(),
        str(photo.get("people_names") or "").lower(),
        str(photo.get("captured_at") or "").lower(),
        str(photo.get("metadata_json") or "").lower(),
    ]
    blob = " ".join(fields)
    blob_folded = _fold_danish(blob)

    for group in term_groups:
        if not any(((term in blob) or (_fold_danish(term) in blob_folded)) for term in group):
            return False
    return True


def query_photos(view: str, sort: str, folder: Optional[str] = None) -> list[Dict[str, Any]]:
    sort_map = {
        "date_desc": "COALESCE(captured_at, modified_fs, created_fs) DESC",
        "date_asc": "COALESCE(captured_at, modified_fs, created_fs) ASC",
        "name_asc": "filename ASC",
        "name_desc": "filename DESC",
        "size_desc": "file_size DESC",
        "size_asc": "file_size ASC",
    }
    order_by = sort_map.get(sort, sort_map["date_desc"])

    where = []
    params: list[Any] = []
    # Always exclude Synology auto-thumbs and @eaDir content from results
    where.append("(UPPER(filename) NOT LIKE 'SYNOPHOTO_THUMB_%' AND UPPER(filename) NOT LIKE 'SYNOPHOTO_CACHE_%')")
    where.append("(rel_path NOT LIKE '%/@eaDir/%')")
    if view == "favorites":
        where.append("favorite = 1")
    elif view == "steder":
        # Only include photos with explicit coordinates so the map can plot them
        where.append("(gps_lat IS NOT NULL AND gps_lon IS NOT NULL)")
    elif view == "kameraer":
        where.append("(camera_model IS NOT NULL AND camera_model != '')")
    elif view == "personer":
        where.append("people_count > 0")  # future face-service
    elif view == "recent":
        where.append("1=1")

    # Optional folder filter: all files under folder (prefix match)
    if folder:
        folder_norm = _normalize_upload_subdir(str(folder))
        folder_with_uploads = folder_norm if folder_norm.startswith("uploads/") else f"uploads/{folder_norm}"
        where.append("(rel_path LIKE ? || '/%' OR rel_path LIKE ? || '/%')")
        params.extend([folder_norm, folder_with_uploads])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT
            photos.*,
            COALESCE((
                SELECT GROUP_CONCAT(name, ' ')
                FROM (
                    SELECT DISTINCT p2.name AS name
                    FROM faces f2
                    INNER JOIN people p2 ON p2.id = f2.person_id
                    WHERE f2.photo_id = photos.id
                      AND COALESCE(p2.hidden, 0) = 0
                )
            ), '') AS people_names
        FROM photos
        {where_sql}
        ORDER BY {order_by}
    """

    with closing(get_conn()) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_public(r) for r in rows]


def _hamdist_hex(a: str, b: str) -> int:
    try:
        va = int(a, 16)
        vb = int(b, 16)
        return (va ^ vb).bit_count()
    except Exception:
        return 64  # max for 64-bit pHash


@app.route("/api/duplicates")
def api_duplicates():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    try:
        dist_thr = int(request.args.get("distance", "5"))
    except ValueError:
        dist_thr = 5
    min_group = max(2, int(request.args.get("min", "2")))

    with closing(get_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, filename, rel_path, file_size, phash, checksum_sha256, thumb_name, captured_at FROM photos WHERE phash IS NOT NULL"
        ).fetchall()]

    # Exact duplicates by checksum
    by_checksum: dict[str, list[dict]] = {}
    for r in rows:
        c = r.get("checksum_sha256")
        if c:
            by_checksum.setdefault(c, []).append(r)
    checksum_groups = [v for v in by_checksum.values() if len(v) >= min_group]

    # Exact duplicates by equal phash
    by_phash: dict[str, list[dict]] = {}
    for r in rows:
        p = r.get("phash")
        if p:
            by_phash.setdefault(p, []).append(r)
    phash_exact_groups = [v for v in by_phash.values() if len(v) >= min_group]

    # Near duplicates by small Hamming distance of pHash
    # Bucket by first 4 hex chars to avoid O(n^2)
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        p = r.get("phash")
        if not p:
            continue
        key = p[:4]
        buckets.setdefault(key, []).append(r)

    visited: set[int] = set()
    # exclude items already in exact groups
    for g in checksum_groups + phash_exact_groups:
        for it in g:
            visited.add(int(it["id"]))

    near_groups: list[list[dict]] = []
    for arr in buckets.values():
        n = len(arr)
        if n < 2:
            continue
        # Build adjacency by threshold
        comp_map: dict[int, set[int]] = {}
        ids = [int(x["id"]) for x in arr]
        for i in range(n):
            for j in range(i + 1, n):
                a, b = arr[i], arr[j]
                if int(a["id"]) in visited and int(b["id"]) in visited:
                    continue
                d = _hamdist_hex(a["phash"], b["phash"])
                if d <= dist_thr:
                    comp_map.setdefault(int(a["id"]), set()).add(int(b["id"]))
                    comp_map.setdefault(int(b["id"]), set()).add(int(a["id"]))
        # Connected components
        seen: set[int] = set()
        for root in ids:
            if root in seen or root not in comp_map:
                continue
            stack = [root]
            comp_ids: set[int] = set()
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                comp_ids.add(cur)
                for nb in comp_map.get(cur, set()):
                    if nb not in seen:
                        stack.append(nb)
            if len(comp_ids) >= min_group:
                group_items = [next(x for x in arr if int(x["id"]) == cid) for cid in comp_ids]
                near_groups.append(group_items)

    # Prepare payload (limit size in thumbs only)
    def _pub(it: dict) -> dict:
        out = {
            "id": it["id"],
            "filename": it["filename"],
            "rel_path": it["rel_path"],
            "file_size": it["file_size"],
            "phash": it["phash"],
            "checksum": it["checksum_sha256"],
            "captured_at": it.get("captured_at"),
        }
        if it.get("thumb_name"):
            out["thumb_url"] = f"/api/thumbs/{it['thumb_name']}"
        else:
            out["thumb_url"] = None
        return out

    resp = {
        "ok": True,
        "distance": dist_thr,
        "groups": [
            {"reason": "checksum", "items": [[_pub(it) for it in g] for g in checksum_groups]},
            {"reason": "phash_equal", "items": [[_pub(it) for it in g] for g in phash_exact_groups]},
            {"reason": "phash_near", "items": [[_pub(it) for it in g] for g in near_groups]},
        ],
        "counts": {
            "checksum": len(checksum_groups),
            "phash_equal": len(phash_exact_groups),
            "phash_near": len(near_groups),
        },
    }
    return jsonify(resp)


@app.route("/")
def index():
    try:
        with closing(get_conn()) as conn:
            row = conn.execute(
                "SELECT id, username, role, ui_language, search_language FROM users WHERE id=?",
                (current_user.id,),
            ).fetchone()
        role = row["role"] if row and row["role"] else getattr(current_user, "role", None)
        profile = {
            "id": int(row["id"]) if row else int(current_user.id),
            "username": (row["username"] if row else getattr(current_user, "username", "")),
            "role": (role or "user"),
            "ui_language": _normalize_language((row["ui_language"] if row else None), DEFAULT_UI_LANGUAGE),
            "search_language": _normalize_language((row["search_language"] if row else None), DEFAULT_SEARCH_LANGUAGE),
        }
    except Exception:
        role = None
        profile = {
            "id": int(getattr(current_user, "id", 0) or 0),
            "username": getattr(current_user, "username", ""),
            "role": (getattr(current_user, "role", None) or "user"),
            "ui_language": _normalize_language(getattr(current_user, "ui_language", None), DEFAULT_UI_LANGUAGE),
            "search_language": _normalize_language(getattr(current_user, "search_language", None), DEFAULT_SEARCH_LANGUAGE),
        }
    return render_template("index.html", user_role=(role or "user"), user_profile=profile)


@app.route("/s/<token>")
def shared_folder_view(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return render_template("login.html", error=_ui_text("share_invalid_or_expired")), 404
    return render_template("shared_folder.html", share_token=token)


@app.route("/api/share/<token>/auth", methods=["POST"])
def api_share_auth(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return jsonify({"ok": False, "error": "Share ugyldig eller udløbet"}), 404
    body = request.get_json(silent=True) or {}
    visitor_name = _sanitize_share_visitor_name(body.get("visitor_name") or "")
    if _share_requires_visitor_name(share) and not visitor_name:
        return jsonify({"ok": False, "error": "Navn er påkrævet"}), 400

    if not _share_is_password_protected(share):
        session[_share_session_key(share)] = 1
        if _share_requires_visitor_name(share):
            session[_share_name_session_key(share)] = visitor_name
        return jsonify({"ok": True, "visitor_name": _share_get_visitor_name(share)})

    password = str(body.get("password") or "")
    if not password:
        return jsonify({"ok": False, "error": "Mangler adgangskode"}), 400

    stored = str(share["password_hash"] or "")
    if not stored or not check_password_hash(stored, password):
        return jsonify({"ok": False, "error": "Forkert adgangskode"}), 401

    session[_share_session_key(share)] = 1
    if _share_requires_visitor_name(share):
        session[_share_name_session_key(share)] = visitor_name
    return jsonify({"ok": True, "visitor_name": _share_get_visitor_name(share)})


@app.route("/api/shares", methods=["POST"])
def api_create_share():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    body = request.get_json(silent=True) or {}
    raw_folder_paths = body.get("folder_paths")
    folder_paths_raw: list[str]
    if isinstance(raw_folder_paths, list):
        folder_paths_raw = [str(v or "") for v in raw_folder_paths]
    else:
        folder_paths_raw = [str(body.get("folder_path") or "")]

    folder_paths: list[str] = []
    for raw in folder_paths_raw:
        try:
            fp = _normalize_upload_subdir(raw)
        except Exception:
            fp = ""
        if fp and fp not in folder_paths:
            folder_paths.append(fp)
    if not folder_paths:
        return jsonify({"ok": False, "error": "Vælg mindst én mappe"}), 400

    base = UPLOAD_DIR.resolve()
    for folder_path in folder_paths:
        try:
            target = (UPLOAD_DIR / folder_path).resolve()
            target.relative_to(base)
        except Exception:
            return jsonify({"ok": False, "error": "Ugyldig mappe"}), 400
        if not target.exists() or not target.is_dir():
            return jsonify({"ok": False, "error": f"Mappen findes ikke: {folder_path}"}), 404

    share_name = str(body.get("share_name") or "").strip()
    if len(share_name) > 120:
        share_name = share_name[:120].strip()
    if not share_name:
        if len(folder_paths) == 1:
            share_name = f"uploads/{folder_paths[0]}"
        else:
            share_name = f"{len(folder_paths)} mapper"

    perm = str(body.get("permission") or "view").strip().lower()
    can_upload = 0
    can_delete = 0
    if perm == "upload":
        can_upload = 1
    elif perm in {"manage", "delete"}:
        can_upload = 1
        can_delete = 1
    elif perm != "view":
        return jsonify({"ok": False, "error": "Ugyldig rettighed"}), 400

    try:
        expires_value = int(body.get("expires_value") or 7)
    except Exception:
        expires_value = 7
    expires_unit = str(body.get("expires_unit") or "days").strip().lower()
    if expires_value < 1:
        expires_value = 1
    if expires_unit not in {"hours", "days"}:
        expires_unit = "days"
    expires_hours = expires_value if expires_unit == "hours" else (expires_value * 24)
    expires_hours = max(1, min(expires_hours, 24 * 365))
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(timespec="seconds") + "Z"

    password_enabled = bool(body.get("password_enabled"))
    require_visitor_name = bool(body.get("require_visitor_name"))
    use_duckdns = bool(body.get("use_duckdns"))
    password_raw = str(body.get("password") or "")
    password_hash = None
    if password_enabled:
        if len(password_raw) < 4:
            return jsonify({"ok": False, "error": "Adgangskode skal være mindst 4 tegn"}), 400
        password_hash = generate_password_hash(password_raw)

    token = secrets.token_urlsafe(24)
    token_hash = _share_token_digest(token)
    created_at = now_iso()
    primary_folder_path = folder_paths[0]
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO share_links(token_hash, token_plain, share_name, folder_path, can_upload, can_delete, require_visitor_name, link_use_duckdns, password_hash, expires_at, revoked, created_by_user_id, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token_hash,
                token,
                share_name,
                primary_folder_path,
                int(can_upload),
                int(can_delete),
                1 if require_visitor_name else 0,
                1 if use_duckdns else 0,
                password_hash,
                expires_at,
                0,
                int(getattr(current_user, "id", 0) or 0),
                created_at,
            ),
        )
        share_id = int(cur.lastrowid or 0)
        for fp in folder_paths:
            conn.execute(
                "INSERT OR IGNORE INTO share_link_folders(share_id, folder_path, created_at) VALUES(?,?,?)",
                (share_id, fp, created_at),
            )
        conn.commit()

    link, link_error = _build_share_link(token, use_duckdns)
    if link_error or not link:
        return jsonify({"ok": False, "error": link_error or "Kunne ikke oprette share-link"}), 400
    return jsonify(
        {
            "ok": True,
            "link": link,
            "share_name": share_name,
            "folder_path": primary_folder_path,
            "folder_paths": folder_paths,
            "permission": perm,
            "can_upload": bool(can_upload),
            "can_delete": bool(can_delete),
            "require_visitor_name": bool(require_visitor_name),
            "password_enabled": bool(password_hash),
            "expires_at": expires_at,
        }
    )


@app.route("/api/share/<token>/info")
def api_share_info(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return jsonify({"ok": False, "error": "Share ugyldig eller udløbet"}), 404
    if not _share_is_authorized(share):
        return jsonify({
            "ok": False,
            "password_required": _share_is_password_protected(share),
            "name_required": _share_requires_visitor_name(share),
            "error": "Adgang kræves",
        }), 401
    with closing(get_conn()) as conn:
        folder_paths = _share_folder_paths(conn, share)
    folder_label = f"uploads/{folder_paths[0]}" if len(folder_paths) == 1 else f"{len(folder_paths)} mapper"
    share_name = str(share["share_name"] or "").strip() if "share_name" in share.keys() else ""
    if not share_name:
        share_name = folder_label
    visitor_name = _share_get_visitor_name(share)
    return jsonify(
        {
            "ok": True,
            "share_name": share_name,
            "folder_path": folder_paths[0] if folder_paths else "",
            "folder_paths": folder_paths,
            "folder_count": len(folder_paths),
            "folder_labels": [f"uploads/{fp}" for fp in folder_paths],
            "folder_label": folder_label,
            "can_upload": bool(int(share["can_upload"] or 0)),
            "can_delete": bool(int(share["can_delete"] or 0)),
            "require_visitor_name": _share_requires_visitor_name(share),
            "visitor_name": visitor_name,
            "password_enabled": _share_is_password_protected(share),
            "expires_at": share["expires_at"],
        }
    )


@app.route("/api/share/<token>/photos")
def api_share_photos(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return jsonify({"ok": False, "error": "Share ugyldig eller udløbet"}), 404
    if not _share_is_authorized(share):
        return jsonify({
            "ok": False,
            "password_required": _share_is_password_protected(share),
            "name_required": _share_requires_visitor_name(share),
            "error": "Adgang kræves",
        }), 401

    with closing(get_conn()) as conn:
        folder_paths = _share_folder_paths(conn, share)
    prefixes = _share_rel_prefixes(folder_paths)
    if not prefixes:
        return jsonify({"ok": False, "error": "Ugyldig share-mappe"}), 400
    where_sql, where_params = _share_scope_sql(prefixes)

    with closing(get_conn()) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM photos
            WHERE ({where_sql})
            ORDER BY COALESCE(captured_at, modified_fs, created_fs) DESC, id DESC
            """,
            tuple(where_params),
        ).fetchall()

    items = [_row_to_share_public(r, token) for r in rows]
    return jsonify({"ok": True, "items": items})


@app.route("/api/share/<token>/thumb/<int:photo_id>")
def api_share_thumb(token: str, photo_id: int):
    share = _load_share_from_token(token)
    if not share or not _share_is_authorized(share):
        return ("Forbidden", 403)
    with closing(get_conn()) as conn:
        row = _get_share_scoped_photo_row(conn, share, photo_id)
    if not row or not row["thumb_name"]:
        return ("Not found", 404)
    return send_from_directory(THUMB_DIR, str(row["thumb_name"]))


@app.route("/api/share/<token>/original/<int:photo_id>")
def api_share_original(token: str, photo_id: int):
    share = _load_share_from_token(token)
    if not share or not _share_is_authorized(share):
        return ("Forbidden", 403)
    with closing(get_conn()) as conn:
        row = _get_share_scoped_photo_row(conn, share, photo_id)
    if not row:
        return ("Not found", 404)

    safe_rel = str(row["rel_path"] or "").replace("..", "").lstrip("/")
    if safe_rel.startswith("uploads/"):
        return send_from_directory(str(UPLOAD_DIR), safe_rel[len("uploads/"):])
    return ("Forbidden", 403)


@app.route("/api/share/<token>/view/<int:photo_id>")
def api_share_viewable(token: str, photo_id: int):
    share = _load_share_from_token(token)
    if not share or not _share_is_authorized(share):
        return ("Forbidden", 403)
    with closing(get_conn()) as conn:
        row = _get_share_scoped_photo_row(conn, share, photo_id)
    if not row:
        return ("Not found", 404)

    safe_rel = str(row["rel_path"] or "").replace("..", "").lstrip("/")
    if not safe_rel.startswith("uploads/"):
        return ("Forbidden", 403)
    src = UPLOAD_DIR / safe_rel[len("uploads/"):]
    if not src.exists():
        return ("Not found", 404)

    view_path = ensure_viewable_copy(src, safe_rel)
    try:
        vp = str(view_path)
        if vp.startswith(str(CONVERT_DIR)):
            rel_conv = str(view_path.relative_to(CONVERT_DIR)).replace("\\", "/")
            return send_from_directory(CONVERT_DIR, rel_conv)
        return send_from_directory(UPLOAD_DIR, safe_rel[len("uploads/"):])
    except Exception as e:
        return (str(e), 500)


@app.route("/api/share/<token>/upload", methods=["POST"])
def api_share_upload(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return jsonify({"ok": False, "error": "Share ugyldig eller udløbet"}), 404
    if not _share_is_authorized(share):
        return jsonify({
            "ok": False,
            "password_required": _share_is_password_protected(share),
            "name_required": _share_requires_visitor_name(share),
            "error": "Adgang kræves",
        }), 401
    if int(share["can_upload"] or 0) != 1:
        return jsonify({"ok": False, "error": "Upload ikke tilladt"}), 403

    with closing(get_conn()) as conn:
        folder_paths = _share_folder_paths(conn, share)
    folder_path = folder_paths[0] if folder_paths else ""
    if not folder_path:
        return jsonify({"ok": False, "error": "Ugyldig share-mappe"}), 400
    uploader_name = _share_get_visitor_name(share)
    if _share_requires_visitor_name(share) and not uploader_name:
        return jsonify({"ok": False, "name_required": True, "error": "Navn er påkrævet"}), 401
    uploader_label = uploader_name or "Share-bruger"

    target_dir = (UPLOAD_DIR / folder_path)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Kan ikke oprette upload-destination: {e}"}), 500

    files = request.files.getlist("files") or []
    if not files:
        return jsonify({"ok": False, "error": "No files"}), 400

    saved = []
    errors: list[str] = []
    for f in files:
        try:
            name = secure_filename(f.filename or "")
            if not name:
                continue
            ext = Path(name).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                errors.append(f"Unsupported: {name}")
                continue

            target = target_dir / name
            stem = Path(name).stem
            suffix = Path(name).suffix
            i = 1
            while target.exists():
                target = target_dir / f"{stem}_{i}{suffix}"
                i += 1
            f.save(str(target))

            rel_leaf = f"{folder_path}/{target.name}" if folder_path else target.name
            rel = f"uploads/{rel_leaf}" if rel_leaf else "uploads"
            try:
                meta = extract_metadata(target, rel)
                meta["uploaded_by"] = uploader_label
                upsert_photo(meta)
            except Exception as e:
                errors.append(f"Index fail: {target.name}: {e}")
            saved.append(target.name)
        except Exception as e:
            errors.append(str(e))

    return jsonify({"ok": True, "saved": saved, "errors": errors})


@app.route("/api/share/<token>/delete", methods=["POST"])
def api_share_delete(token: str):
    share = _load_share_from_token(token, touch=True)
    if not share:
        return jsonify({"ok": False, "error": "Share ugyldig eller udløbet"}), 404
    if not _share_is_authorized(share):
        return jsonify({
            "ok": False,
            "password_required": _share_is_password_protected(share),
            "name_required": _share_requires_visitor_name(share),
            "error": "Adgang kræves",
        }), 401
    if int(share["can_delete"] or 0) != 1:
        return jsonify({"ok": False, "error": "Sletning ikke tilladt"}), 403

    body = request.get_json(silent=True) or {}
    raw_ids = body.get("photo_ids")
    if not isinstance(raw_ids, list):
        return jsonify({"ok": False, "error": "Angiv photo_ids"}), 400
    ids = [int(pid) for pid in raw_ids if str(pid).isdigit()]
    if not ids:
        return jsonify({"ok": False, "error": "Ingen billeder valgt"}), 400

    with closing(get_conn()) as conn:
        allowed_ids: list[int] = []
        for pid in ids:
            row = _get_share_scoped_photo_row(conn, share, pid)
            if row:
                allowed_ids.append(int(row["id"]))

    if not allowed_ids:
        return jsonify({"ok": False, "error": "Ingen gyldige billeder valgt"}), 400

    removed = _delete_indexed_photos_by_ids(allowed_ids)
    return jsonify({"ok": True, "removed": removed, "deleted_ids": allowed_ids})


@app.route("/api/health")
def api_health():
    return jsonify({
        "ok": True,
        "photo_dir": str(PHOTO_DIR),
        "photo_dir_exists": PHOTO_DIR.exists(),
        "data_dir": str(DATA_DIR),
        "db_path": str(DB_PATH),
        "ai": _ai_health(),
    })



# Start scan in thread
scan_thread = None
rescan_thread = None
last_rescan_result: Optional[Dict[str, Any]] = None
rethumb_thread = None
last_rethumb_result: Optional[Dict[str, Any]] = None

@app.route("/api/scan", methods=["POST"])
def api_scan():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global scan_thread
    if scan_thread and scan_thread.is_alive():
        return jsonify({"ok": False, "error": "Scan already running"}), 409
    scan_stop_event.clear()
    def run_scan():
        scan_library(stop_event=scan_stop_event)
    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()
    return jsonify({"ok": True, "started": True})

# Stop scan
@app.route("/api/scan/stop", methods=["POST"])
def api_scan_stop():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    scan_stop_event.set()
    return jsonify({"ok": True, "stopped": True})

# Scan status
@app.route("/api/scan/status")
def api_scan_status():
    running = bool(scan_thread and scan_thread.is_alive())
    return jsonify({"ok": True, "running": running})


@app.route("/api/rescan", methods=["POST"])
def api_rescan():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global rescan_thread, last_rescan_result
    if rescan_thread and rescan_thread.is_alive():
        return jsonify({"ok": False, "error": "Rescan already running"}), 409
    scan_stop_event.clear()
    last_rescan_result = None

    def run_rescan():
        global last_rescan_result
        last_rescan_result = rescan_metadata(stop_event=scan_stop_event)

    rescan_thread = threading.Thread(target=run_rescan, daemon=True)
    rescan_thread.start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/rescan/status")
def api_rescan_status():
    running = bool(rescan_thread and rescan_thread.is_alive())
    resp: Dict[str, Any] = {"ok": True, "running": running}
    if not running and last_rescan_result is not None:
        resp["result"] = last_rescan_result
    return jsonify(resp)


def rethumb_all(stop_event=None) -> Dict[str, Any]:
    init_db()
    log_event("rethumb_start")
    total = 0
    errors = 0
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT rel_path FROM photos").fetchall()
    for row in rows:
        if stop_event and stop_event.is_set():
            break
        rel_path = row["rel_path"]
        p = PHOTO_DIR / rel_path
        if not p.exists():
            continue
        try:
            stat = p.stat()
            with Image.open(p) as img:
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                make_thumb(img, rel_path, stat.st_mtime, stat.st_size, force=True)
            total += 1
            log_event("rethumb_ok", rel_path=rel_path)
        except Exception as e:
            errors += 1
            log_event("error", rel_path=rel_path, error=str(e))
    res = {"ok": True, "processed": total, "errors": errors}
    log_event("rethumb_done", processed=total, errors=errors)
    return res


@app.route("/api/rethumb", methods=["POST"])
def api_rethumb():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global rethumb_thread, last_rethumb_result
    if rethumb_thread and rethumb_thread.is_alive():
        return jsonify({"ok": False, "error": "Rethumb already running"}), 409
    scan_stop_event.clear()
    last_rethumb_result = None

    def run_rethumb():
        global last_rethumb_result
        last_rethumb_result = rethumb_all(stop_event=scan_stop_event)

    rethumb_thread = threading.Thread(target=run_rethumb, daemon=True)
    rethumb_thread.start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/rethumb/status")
def api_rethumb_status():
    running = bool(rethumb_thread and rethumb_thread.is_alive())
    resp: Dict[str, Any] = {"ok": True, "running": running}
    if not running and last_rethumb_result is not None:
        resp["result"] = last_rethumb_result
    return jsonify(resp)


def rethumb_missing(stop_event=None) -> Dict[str, Any]:
    init_db()
    log_event("rethumb_missing_start")
    total = 0
    errors = 0
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT rel_path, thumb_name FROM photos"
        ).fetchall()
    for row in rows:
        if stop_event and stop_event.is_set():
            break
        rel_path = row["rel_path"]
        try:
            p = PHOTO_DIR / rel_path if not rel_path.startswith("uploads/") else UPLOAD_DIR / rel_path[len("uploads/"):]
            if not p.exists():
                continue
            stat = p.stat()
            expected_ok = False
            prev = str(row["thumb_name"] or "").strip()
            if prev:
                tp = THUMB_DIR / prev
                try:
                    expected_ok = tp.exists() and (tp.stat().st_mtime >= stat.st_mtime)
                except Exception:
                    expected_ok = False
            if expected_ok:
                continue
            # Need (re)thumb
            tn: Optional[str] = None
            if p.suffix.lower() in VIDEO_EXTS:
                tn = _make_video_thumb(p, rel_path, stat.st_mtime, stat.st_size)
            else:
                with Image.open(p) as img:
                    try:
                        img = ImageOps.exif_transpose(img)
                    except Exception:
                        pass
                    tn = make_thumb(img, rel_path, stat.st_mtime, stat.st_size)
            if tn:
                with closing(get_conn()) as conn:
                    conn.execute("UPDATE photos SET thumb_name=?, last_scanned_at=? WHERE rel_path=?", (tn, now_iso(), rel_path))
                    conn.commit()
                total += 1
                log_event("rethumb_missing_ok", rel_path=rel_path)
            else:
                errors += 1
        except Exception as e:
            errors += 1
            log_event("error", rel_path=rel_path, error=f"rethumb_missing: {e}")
    res = {"ok": True, "processed": total, "errors": errors}
    log_event("rethumb_missing_done", processed=total, errors=errors)
    return res


@app.route("/api/rethumb/missing", methods=["POST"])
def api_rethumb_missing():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global rethumb_thread, last_rethumb_result
    if rethumb_thread and rethumb_thread.is_alive():
        return jsonify({"ok": False, "error": "Rethumb already running"}), 409
    scan_stop_event.clear()
    last_rethumb_result = None

    def run_rethumb_missing():
        global last_rethumb_result
        last_rethumb_result = rethumb_missing(stop_event=scan_stop_event)

    rethumb_thread = threading.Thread(target=run_rethumb_missing, daemon=True)
    rethumb_thread.start()
    return jsonify({"ok": True, "started": True})


# --- AI: embeddings + search ---
ai_thread = None
ai_running = False
ai_counts: Dict[str, int] = {"embedded": 0, "failed": 0, "total": 0}
last_ai_result: Optional[Dict[str, Any]] = None
ai_desc_thread = None
ai_desc_running = False
ai_desc_counts: Dict[str, int] = {"described": 0, "failed": 0, "total": 0}
last_ai_desc_result: Optional[Dict[str, Any]] = None


def _embed_one_photo(photo_id: int, rel_path: str) -> bool:
    disk_path = _disk_path_from_rel_path(rel_path)
    if not disk_path.exists():
        return False
    emb = _ai_embed_image_path(disk_path)
    if not emb:
        return False

    with closing(get_conn()) as conn:
        conn.execute("UPDATE photos SET embedding_json=? WHERE id=?", (json.dumps(emb), photo_id))
        conn.commit()

    try:
        tags = _classify_labels(emb)
    except Exception:
        tags = []

    if tags:
        try:
            with closing(get_conn()) as conn:
                cur = conn.execute("SELECT ai_tags FROM photos WHERE id=?", (photo_id,)).fetchone()
                prev = []
                if cur and cur["ai_tags"]:
                    try:
                        prev = json.loads(cur["ai_tags"]) or []
                    except Exception:
                        prev = []
                merged = sorted({*(prev or []), *tags})
                conn.execute("UPDATE photos SET ai_tags=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), photo_id))
                conn.commit()
        except Exception:
            pass

    return True


def _embed_missing_photos(stop_event=None) -> Dict[str, Any]:
    global ai_running, ai_counts, last_ai_result
    ai_running = True
    ai_counts = {"embedded": 0, "failed": 0, "total": 0}
    log_event("ai_embed_start")
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT id, rel_path FROM photos WHERE (embedding_json IS NULL OR embedding_json = '')").fetchall()
    for row in rows:
        if stop_event and stop_event.is_set():
            break
        pid = int(row["id"])
        rel = row["rel_path"]
        ai_counts["total"] += 1
        try:
            if _embed_one_photo(pid, rel):
                ai_counts["embedded"] += 1
                log_event("ai_embed_ok", rel_path=rel)
            else:
                ai_counts["failed"] += 1
                log_event("ai_embed_fail", rel_path=rel)
        except Exception:
            ai_counts["failed"] += 1
            log_event("ai_embed_fail", rel_path=rel)
        ai_delay = ai_ingest_throttle_enabled_sec()
        if ai_delay > 0:
            time.sleep(ai_delay)
    ai_running = False
    last_ai_result = {"ok": True, **ai_counts}
    log_event("ai_embed_done", **ai_counts)
    return last_ai_result


def _embed_uploaded_photo_if_needed(rel_path: str) -> None:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id, embedding_json FROM photos WHERE rel_path=?", (rel_path,)).fetchone()
        if not row:
            return
        if row["embedding_json"]:
            return
        pid = int(row["id"])
        if _embed_one_photo(pid, rel_path):
            log_event("ai_embed_ok", rel_path=rel_path, source="upload")
        else:
            log_event("ai_embed_fail", rel_path=rel_path, source="upload")
    except Exception as e:
        log_event("ai_embed_fail", rel_path=rel_path, source="upload", error=str(e))


def _describe_one_photo(photo_id: int, rel_path: str) -> bool:
    emb = None
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT embedding_json FROM photos WHERE id=?", (photo_id,)).fetchone()
    if row and row["embedding_json"]:
        try:
            emb = json.loads(row["embedding_json"])
        except Exception:
            emb = None

    if not emb:
        if not _embed_one_photo(photo_id, rel_path):
            return False
        with closing(get_conn()) as conn:
            row2 = conn.execute("SELECT embedding_json FROM photos WHERE id=?", (photo_id,)).fetchone()
        if row2 and row2["embedding_json"]:
            try:
                emb = json.loads(row2["embedding_json"])
            except Exception:
                emb = None
    if not emb:
        return False

    tags = _classify_descriptive_tags(emb)
    caption = _build_desc_caption(tags)
    with closing(get_conn()) as conn:
        conn.execute(
            "UPDATE photos SET ai_desc_tags=?, ai_desc_caption=? WHERE id=?",
            (json.dumps(tags or [], ensure_ascii=False), caption, photo_id),
        )
        conn.commit()
    return True


def _describe_missing_photos(stop_event=None) -> Dict[str, Any]:
    global ai_desc_running, ai_desc_counts, last_ai_desc_result
    ai_desc_running = True
    ai_desc_counts = {"described": 0, "failed": 0, "total": 0}
    log_event("ai_desc_start")
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT id, rel_path FROM photos WHERE (ai_desc_tags IS NULL OR ai_desc_tags = '')"
        ).fetchall()
    for row in rows:
        if stop_event and stop_event.is_set():
            break
        pid = int(row["id"])
        rel = row["rel_path"]
        ai_desc_counts["total"] += 1
        try:
            if _describe_one_photo(pid, rel):
                ai_desc_counts["described"] += 1
                log_event("ai_desc_ok", rel_path=rel)
            else:
                ai_desc_counts["failed"] += 1
                log_event("ai_desc_fail", rel_path=rel)
        except Exception:
            ai_desc_counts["failed"] += 1
            log_event("ai_desc_fail", rel_path=rel)
        ai_delay = ai_ingest_throttle_enabled_sec()
        if ai_delay > 0:
            time.sleep(ai_delay)
    ai_desc_running = False
    last_ai_desc_result = {"ok": True, **ai_desc_counts}
    log_event("ai_desc_done", **ai_desc_counts)
    return last_ai_desc_result


def _describe_uploaded_photo_if_needed(rel_path: str) -> None:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id, ai_desc_tags FROM photos WHERE rel_path=?", (rel_path,)).fetchone()
        if not row:
            return
        if row["ai_desc_tags"] is not None and str(row["ai_desc_tags"]).strip() != "":
            return
        pid = int(row["id"])
        if _describe_one_photo(pid, rel_path):
            log_event("ai_desc_ok", rel_path=rel_path, source="upload")
        else:
            log_event("ai_desc_fail", rel_path=rel_path, source="upload")
    except Exception as e:
        log_event("ai_desc_fail", rel_path=rel_path, source="upload", error=str(e))


@app.route("/api/ai/ingest", methods=["POST"])
def api_ai_ingest():
    global ai_thread
    if ai_thread and ai_thread.is_alive():
        return jsonify({"ok": False, "error": "AI ingest already running"}), 409
    scope = (request.args.get("scope") or "").strip().lower()
    _set_setting("ai_auto_ingest", "1")
    if scope == "new":
        return jsonify({"ok": True, "started": False, "running": False, "auto_ingest": True, "scope": "new"})
    scan_stop_event.clear()
    def run():
        _embed_missing_photos(stop_event=scan_stop_event)
    ai_thread = threading.Thread(target=run, daemon=True)
    ai_thread.start()
    return jsonify({"ok": True, "started": True, "auto_ingest": True, "scope": (scope or "all")})


@app.route("/api/ai/stop", methods=["POST"])
def api_ai_stop():
    _set_setting("ai_auto_ingest", "0")
    if not ai_running:
        return jsonify({"ok": True, "running": False, "auto_ingest": False})
    scan_stop_event.set()
    return jsonify({"ok": True, "running": True, "stopping": True, "auto_ingest": False})


@app.route("/api/ai/status")
def api_ai_status():
    resp: Dict[str, Any] = {"ok": True, "running": ai_running, "auto_ingest": ai_auto_ingest_enabled(), **ai_counts}
    if not ai_running and last_ai_result:
        resp["last"] = last_ai_result
    return jsonify(resp)


@app.route("/api/ai/describe/ingest", methods=["POST"])
def api_ai_describe_ingest():
    global ai_desc_thread
    if ai_desc_thread and ai_desc_thread.is_alive():
        return jsonify({"ok": False, "error": "AI description ingest already running"}), 409
    scope = (request.args.get("scope") or "").strip().lower()
    _set_setting("ai_desc_auto_ingest", "1")
    if scope == "new":
        return jsonify({"ok": True, "started": False, "running": False, "auto_ingest": True, "scope": "new"})
    scan_stop_event.clear()

    def run():
        _describe_missing_photos(stop_event=scan_stop_event)

    ai_desc_thread = threading.Thread(target=run, daemon=True)
    ai_desc_thread.start()
    return jsonify({"ok": True, "started": True, "auto_ingest": True, "scope": (scope or "all")})


@app.route("/api/ai/describe/stop", methods=["POST"])
def api_ai_describe_stop():
    _set_setting("ai_desc_auto_ingest", "0")
    if not ai_desc_running:
        return jsonify({"ok": True, "running": False, "auto_ingest": False})
    scan_stop_event.set()
    return jsonify({"ok": True, "running": True, "stopping": True, "auto_ingest": False})


@app.route("/api/ai/describe/status")
def api_ai_describe_status():
    resp: Dict[str, Any] = {
        "ok": True,
        "running": ai_desc_running,
        "auto_ingest": ai_desc_auto_ingest_enabled(),
        **ai_desc_counts,
    }
    if not ai_desc_running and last_ai_desc_result:
        resp["last"] = last_ai_desc_result
    return jsonify(resp)


@app.route("/api/ai/search")
def api_ai_search():
    q = (request.args.get("q") or "").strip()
    limit = max(1, min(200, int(request.args.get("limit", "60"))))
    if not q:
        return jsonify({"items": [], "count": 0})
    vec = _ai_embed_text(q)
    if not vec:
        return jsonify({"items": [], "count": 0, "error": "embed_failed"})
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM photos WHERE embedding_json IS NOT NULL AND embedding_json != ''").fetchall()
    scored = []
    for r in rows:
        try:
            emb = json.loads(r["embedding_json"]) if r["embedding_json"] else None
            sc = _cosine(vec, emb) if emb else -1.0
            scored.append((sc, r))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    items = [row_to_public(r) for (s, r) in scored[:limit] if s > -0.5]
    items = _filter_public_items_by_current_user_acl(items)
    return jsonify({"items": items, "count": len(items), "q": q})


@app.route("/api/photos/<int:photo_id>/similar")
def api_similar(photo_id: int):
    limit = max(1, min(200, int(request.args.get("limit", "60"))))
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if not _is_rel_path_allowed_for_current_user(row["rel_path"]):
        return jsonify({"ok": False, "error": "not_found"}), 404
    emb = None
    try:
        emb = json.loads(row["embedding_json"]) if row["embedding_json"] else None
    except Exception:
        emb = None
    if not emb:
        # compute on the fly
        p = PHOTO_DIR / row["rel_path"]
        emb = _ai_embed_image_path(p)
        if not emb:
            return jsonify({"ok": False, "error": "embed_failed"}), 500
        with closing(get_conn()) as conn:
            conn.execute("UPDATE photos SET embedding_json=? WHERE id=?", (json.dumps(emb), photo_id))
            conn.commit()
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM photos WHERE embedding_json IS NOT NULL AND embedding_json != '' AND id<>?", (photo_id,)).fetchall()
    scored = []
    for r in rows:
        try:
            e2 = json.loads(r["embedding_json"]) if r["embedding_json"] else None
            s = _cosine(emb, e2) if e2 else -1.0
            scored.append((s, r))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    items = [row_to_public(r) for (s, r) in scored[:limit] if s > -0.5]
    items = _filter_public_items_by_current_user_acl(items)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/photos/<int:photo_id>/ai-tags", methods=["POST"])
def api_ai_tags(photo_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id, rel_path, embedding_json, ai_tags FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if not _is_rel_path_allowed_for_current_user(row["rel_path"]):
        return jsonify({"ok": False, "error": "not_found"}), 404
    try:
        emb = json.loads(row["embedding_json"]) if row["embedding_json"] else None
        if not emb:
            p = PHOTO_DIR / row["rel_path"]
            emb = _ai_embed_image_path(p)
            if not emb:
                return jsonify({"ok": False, "error": "embed_failed"}), 500
            with closing(get_conn()) as conn:
                conn.execute("UPDATE photos SET embedding_json=? WHERE id=?", (json.dumps(emb), photo_id))
                conn.commit()
        tags = _classify_labels(emb)
        with closing(get_conn()) as conn:
            prev = []
            if row["ai_tags"]:
                try:
                    prev = json.loads(row["ai_tags"]) or []
                except Exception:
                    prev = []
            merged = sorted({*(prev or []), *(tags or [])})
            conn.execute("UPDATE photos SET ai_tags=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), photo_id))
            conn.commit()
        return jsonify({"ok": True, "tags": merged})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def clear_index() -> Dict[str, Any]:
    init_db()
    log_event("clear_start")
    thumbs_deleted = 0
    converted_deleted = 0
    # Delete thumbs safely inside THUMB_DIR only
    for p in THUMB_DIR.glob("*"):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
                thumbs_deleted += 1
        except Exception as e:
            log_event("error", rel_path=str(p), error=str(e))

    # Delete converted cache safely inside CONVERT_DIR (may contain subfolders)
    try:
        for p in CONVERT_DIR.rglob("*"):
            try:
                if p.is_file():
                    p.unlink(missing_ok=True)
                    converted_deleted += 1
            except Exception as e:
                log_event("error", rel_path=str(p), error=str(e))
        # Optionally clean up empty directories
        for d in sorted([x for x in CONVERT_DIR.rglob("*") if x.is_dir()], key=lambda x: len(str(x)), reverse=True):
            try:
                d.rmdir()
            except Exception:
                pass
    except Exception as e:
        log_event("error", rel_path="converted_clear", error=str(e))

    try:
        with closing(get_conn()) as conn:
            photos = conn.execute("SELECT COUNT(*) AS c FROM photos").fetchone()["c"]
            faces = conn.execute("SELECT COUNT(*) AS c FROM faces").fetchone()["c"]
            people = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
            conn.execute("DELETE FROM faces")
            conn.execute("DELETE FROM people")
            conn.execute("DELETE FROM photos")
            # Commit deletes before VACUUM (cannot VACUUM inside a transaction)
            conn.commit()
            conn.execute("VACUUM")
            conn.commit()
    except Exception as e:
        log_event("error", rel_path="db_clear", error=str(e))
        return {"ok": False, "error": str(e)}

    res = {"ok": True, "removed": {"photos": photos, "faces": faces, "people": people, "thumbs": thumbs_deleted, "converted": converted_deleted}}
    log_event("clear_done", **res["removed"])  # type: ignore[arg-type]
    return res


@app.route("/api/clear", methods=["POST"])
def api_clear():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    # Do not touch PHOTO_DIR; only DB + thumbs in DATA_DIR
    result = clear_index()
    return jsonify(result), 200


def _safe_rmtree_contents(root: Path) -> dict:
    """Delete all contents inside 'root' without removing the root directory itself.
    Returns counts of removed files and directories.
    """
    removed_files = 0
    removed_dirs = 0
    try:
        if not root.exists():
            return {"files": 0, "dirs": 0}
        # Remove files first
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    p.unlink(missing_ok=True)
                    removed_files += 1
            except Exception:
                pass
        # Then attempt to remove empty directories deepest-first
        for d in sorted([x for x in root.rglob("*") if x.is_dir()], key=lambda x: len(str(x)), reverse=True):
            try:
                d.rmdir()
                removed_dirs += 1
            except Exception:
                pass
    except Exception:
        pass
    return {"files": removed_files, "dirs": removed_dirs}


@app.route("/api/factory-reset", methods=["POST"])
def api_factory_reset():
    # Admin-only: full wipe of app-generated data and DB
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    try:
        # Stop any background processing
        try:
            scan_stop_event.set()
        except Exception:
            pass

        # Clear runtime upload queues
        try:
            with UPLOAD_PENDING_LOCK:
                UPLOAD_PENDING_BY_USER.clear()
        except Exception:
            pass

        # No eager directory creation; proceed directly to clearing
        # Step 1: Clear index (DB photos/faces/people) and thumbs using existing helper
        clear_res = clear_index()

        # Step 2: Remove additional caches and uploads
        converted = _safe_rmtree_contents(CONVERT_DIR)
        uploads = _safe_rmtree_contents(UPLOAD_DIR)
        tus_tmp = _safe_rmtree_contents(TUS_TMP_DIR)

        # Step 3: Clear non-user content tables (shares, geo cache)
        geo_deleted = 0
        share_deleted = 0
        share_folders_deleted = 0
        login_audit_deleted = 0
        try:
            with closing(get_conn()) as conn:
                try:
                    row = conn.execute("SELECT COUNT(*) AS c FROM geo_cache").fetchone()
                    geo_deleted = int(row["c"]) if row else 0
                    conn.execute("DELETE FROM geo_cache")
                except Exception:
                    pass
                try:
                    row = conn.execute("SELECT COUNT(*) AS c FROM share_link_folders").fetchone()
                    share_folders_deleted = int(row["c"]) if row else 0
                    conn.execute("DELETE FROM share_link_folders")
                except Exception:
                    pass
                try:
                    row = conn.execute("SELECT COUNT(*) AS c FROM share_links").fetchone()
                    share_deleted = int(row["c"]) if row else 0
                    conn.execute("DELETE FROM share_links")
                except Exception:
                    pass
                # Optional: clear login audit to reduce DB size on reset (keeps users)
                try:
                    row = conn.execute("SELECT COUNT(*) AS c FROM login_audit").fetchone()
                    login_audit_deleted = int(row["c"]) if row else 0
                    conn.execute("DELETE FROM login_audit")
                except Exception:
                    pass
                conn.commit()
                try:
                    conn.execute("VACUUM")
                    conn.commit()
                except Exception:
                    pass
        except Exception:
            pass

        # Reset in-memory logs
        try:
            global LOG_SEQ
            LOG_BUFFER.clear()
            LOG_SEQ = 0
        except Exception:
            pass

        # Do not recreate directories here; they will be created lazily on use (e.g., first upload)

        payload = {
            "ok": True,
            "removed": {
                "photos": (clear_res.get("removed", {}) or {}).get("photos", 0),
                "faces": (clear_res.get("removed", {}) or {}).get("faces", 0),
                "people": (clear_res.get("removed", {}) or {}).get("people", 0),
                "thumbs": (clear_res.get("removed", {}) or {}).get("thumbs", 0),
                "converted_files": converted.get("files", 0),
                "converted_dirs": converted.get("dirs", 0),
                "uploads_files": uploads.get("files", 0),
                "uploads_dirs": uploads.get("dirs", 0),
                "tus_tmp_files": tus_tmp.get("files", 0),
                "tus_tmp_dirs": tus_tmp.get("dirs", 0),
                "geo_rows": geo_deleted,
                "share_links": share_deleted,
                "share_link_folders": share_folders_deleted,
                "login_audit": login_audit_deleted,
            },
            # No redirect to setup; users are preserved
        }
        log_event("factory_reset_done", **payload["removed"])  # type: ignore[arg-type]
        return jsonify(payload), 200
    except Exception as e:
        log_event("error", rel_path="factory_reset", error=str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/photos")
def api_photos():
    q = request.args.get("q", "").strip()
    view = request.args.get("view", "library")
    sort = request.args.get("sort", "date_desc")
    folder = request.args.get("folder")
    requested_lang = request.args.get("search_lang")
    _, user_lang = _current_user_pref_languages()
    search_language = _normalize_language(requested_lang, user_lang)

    items = query_photos(view, sort, folder=folder)
    if q:
        items = [p for p in items if matches_search(p, q, search_language=search_language)]
    items = _filter_public_items_by_current_user_acl(items)

    return jsonify({
        "items": items,
        "count": len(items),
        "query": q,
        "view": view,
        "sort": sort,
        "folder": folder,
        "search_lang": search_language,
    })


@app.route("/api/photos/<int:photo_id>")
def api_photo_detail(photo_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    if not _is_rel_path_allowed_for_current_user(row["rel_path"]):
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "item": row_to_public(row)})


@app.route("/api/photos/<int:photo_id>/captured-at", methods=["POST"])
@login_required
def api_update_captured_at(photo_id: int):
    try:
        data = request.get_json(silent=True) or {}
        raw = str(data.get("captured_at") or "").strip()
        if not raw:
            return jsonify({"ok": False, "error": "Missing date"}), 400
        # Accept 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DDTHH:MM:SS' (local)
        if len(raw) == 16:
            raw = raw + ":00"
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid date format"}), 400
        iso = dt.isoformat(timespec="seconds")
        with closing(get_conn()) as conn:
            # Update DB
            conn.execute("UPDATE photos SET captured_at=? WHERE id=?", (iso, photo_id))
            row = conn.execute("SELECT rel_path FROM photos WHERE id=?", (photo_id,)).fetchone()
            conn.commit()
        # Update file mtime to help sorting when EXIF is absent
        try:
            rel = row["rel_path"] if row else None
            if rel:
                safe_rel = rel.replace("..", "").lstrip("/")
                if safe_rel.startswith("uploads/"):
                    fpath = UPLOAD_DIR / safe_rel[len("uploads/"):]
                else:
                    fpath = PHOTO_DIR / safe_rel
                if fpath.exists():
                    ts = dt.timestamp()
                    os.utime(fpath, (ts, ts))
        except Exception:
            pass
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
        return jsonify({"ok": True, "item": row_to_public(row)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/photos/<int:photo_id>/gps", methods=["POST"])
@login_required
def api_update_gps(photo_id: int):
    try:
        data = request.get_json(silent=True) or {}
        lat = data.get("lat")
        lon = data.get("lon")
        if lat is None or lon is None:
            return jsonify({"ok": False, "error": "Missing coordinates"}), 400
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid coordinates"}), 400
        country, city = reverse_geocode_with_cache(lat_f, lon_f)
        name = ", ".join([x for x in [city, country] if x]) if (country or city) else None
        with closing(get_conn()) as conn:
            # Update columns + metadata_json.geo
            row0 = conn.execute("SELECT metadata_json FROM photos WHERE id=?", (photo_id,)).fetchone()
            mj = {}
            try:
                mj = json.loads(row0["metadata_json"]) if row0 and row0["metadata_json"] else {}
            except Exception:
                mj = {}
            geo = mj.get("geo", {})
            if country: geo["country"] = country
            if city: geo["city"] = city
            mj["geo"] = geo
            conn.execute(
                "UPDATE photos SET gps_lat=?, gps_lon=?, gps_name=?, metadata_json=? WHERE id=?",
                (lat_f, lon_f, name, json.dumps(mj, ensure_ascii=False), photo_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
        return jsonify({"ok": True, "item": row_to_public(row)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/photos/<int:photo_id>/favorite", methods=["POST"])
def api_toggle_favorite(photo_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT favorite FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Not found"}), 404
        new_val = 0 if int(row["favorite"] or 0) else 1
        conn.execute("UPDATE photos SET favorite = ? WHERE id = ?", (new_val, photo_id))
        conn.commit()
    return jsonify({"ok": True, "favorite": bool(new_val)})


@app.route("/api/filters")
def api_filters():
    with closing(get_conn()) as conn:
        acl_prefixes = _current_user_acl_prefixes(conn)
        if acl_prefixes is None:
            total = conn.execute("SELECT COUNT(*) AS c FROM photos").fetchone()["c"]
            favorites = conn.execute("SELECT COUNT(*) AS c FROM photos WHERE favorite = 1").fetchone()["c"]
            places = conn.execute("SELECT COUNT(*) AS c FROM photos WHERE gps_lat IS NOT NULL OR gps_name IS NOT NULL").fetchone()["c"]
            cameras = [r["camera_model"] for r in conn.execute(
                "SELECT DISTINCT camera_model FROM photos WHERE camera_model IS NOT NULL AND camera_model != '' ORDER BY camera_model"
            ).fetchall()]
        else:
            conds = []
            params: list[Any] = []
            for pref in acl_prefixes:
                conds.append("(rel_path=? OR rel_path LIKE ?)")
                params.extend([pref, pref + "/%"])
            acl_where = " OR ".join(conds) if conds else "0=1"
            total = conn.execute(f"SELECT COUNT(*) AS c FROM photos WHERE ({acl_where})", params).fetchone()["c"]
            favorites = conn.execute(f"SELECT COUNT(*) AS c FROM photos WHERE favorite = 1 AND ({acl_where})", params).fetchone()["c"]
            places = conn.execute(f"SELECT COUNT(*) AS c FROM photos WHERE (gps_lat IS NOT NULL OR gps_name IS NOT NULL) AND ({acl_where})", params).fetchone()["c"]
            cameras = [r["camera_model"] for r in conn.execute(
                f"SELECT DISTINCT camera_model FROM photos WHERE camera_model IS NOT NULL AND camera_model != '' AND ({acl_where}) ORDER BY camera_model",
                params,
            ).fetchall()]
    return jsonify({
        "total": total,
        "favorites": favorites,
        "places": places,
        "cameras": cameras,
        "ai_search_ready": False,
        "ai_note": "AI søgning/ansigter er klargjort i data-modellen, men ONNX/CLIP service er næste trin.",
    })


@app.route("/api/thumbs/<path:thumb_name>")
def api_thumbs(thumb_name: str):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT rel_path FROM photos WHERE thumb_name=? LIMIT 1", (thumb_name,)).fetchone()
    if row and not _is_rel_path_allowed_for_current_user(row["rel_path"]):
        return ("Forbidden", 403)
    return send_from_directory(THUMB_DIR, thumb_name)


@app.route("/api/original/<path:rel_path>")
def api_original(rel_path: str):
    # Serve original file safely from PHOTO_DIR
    # Prevent path escape
    safe_rel = rel_path.replace("..", "").lstrip("/")
    if not _is_rel_path_allowed_for_current_user(safe_rel):
        return ("Forbidden", 403)
    # If uploaded file (prefixed with 'uploads/'), serve from UPLOAD_DIR
    if safe_rel.startswith("uploads/"):
        up_rel = safe_rel[len("uploads/"):]
        return send_from_directory(str(UPLOAD_DIR), up_rel)
    directory = str(PHOTO_DIR)
    return send_from_directory(directory, safe_rel)


@app.route("/api/viewable/<path:rel_path>")
def api_viewable(rel_path: str):
    # Return a browser/AI-friendly version; convert HEIC→JPEG into CONVERT_DIR when needed
    safe_rel = rel_path.replace("..", "").lstrip("/")
    if not _is_rel_path_allowed_for_current_user(safe_rel):
        return ("Forbidden", 403)
    if safe_rel.startswith("uploads/"):
        src = UPLOAD_DIR / safe_rel[len("uploads/"):]
    else:
        src = PHOTO_DIR / safe_rel
    if not src.exists():
        # Fallback: maybe already a converted file reference
        cand = CONVERT_DIR / safe_rel
        if cand.exists():
            return send_from_directory(CONVERT_DIR, safe_rel)
        return ("Not found", 404)
    view_path = ensure_viewable_copy(src, safe_rel)
    # Serve from the appropriate root
    try:
        vp = str(view_path)
        if vp.startswith(str(CONVERT_DIR)):
            rel_conv = str(view_path.relative_to(CONVERT_DIR)).replace("\\", "/")
            resp = send_from_directory(CONVERT_DIR, rel_conv)
            try: resp.headers["Cache-Control"] = "public, max-age=86400"  # 1 day
            except Exception: pass
            return resp
        # No conversion: serve from the original location
        if safe_rel.startswith("uploads/"):
            resp = send_from_directory(UPLOAD_DIR, safe_rel[len("uploads/"):])
            try: resp.headers["Cache-Control"] = "public, max-age=86400"
            except Exception: pass
            return resp
        resp = send_from_directory(PHOTO_DIR, safe_rel)
        try: resp.headers["Cache-Control"] = "public, max-age=86400"
        except Exception: pass
        return resp
    except Exception as e:
        return (str(e), 500)


@app.route("/api/debug/sample")
def api_debug_sample():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify(row_to_public(row) if row else {"empty": True})


@app.route("/api/logs")
def api_logs():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    try:
        after = int(request.args.get("after", "0"))
    except ValueError:
        after = 0
    items = [itm for itm in list(LOG_BUFFER) if int(itm.get("id", 0)) > after]
    next_id = (items[-1]["id"] if items else (LOG_BUFFER[-1]["id"] if LOG_BUFFER else after))
    return jsonify({"items": items[:200], "next": next_id})


@app.route("/api/settings/upload-destination", methods=["GET", "POST"])
def api_settings_upload_destination():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        destination_raw = body.get("destination")
        destination = get_upload_destination() if destination_raw is None else str(destination_raw).strip().lower()
        if destination not in UPLOAD_DEST_CHOICES:
            return jsonify({"ok": False, "error": "Ugyldigt upload-destination-valg"}), 400
        if "subdir" in body:
            try:
                subdir = _normalize_upload_subdir(str(body.get("subdir") or ""))
            except Exception:
                return jsonify({"ok": False, "error": "Ugyldig undermappe"}), 400
            _set_upload_subdir(destination, subdir)
        _set_setting("upload_destination", destination)
        return jsonify(_upload_settings_payload(destination))

    requested = str(request.args.get("destination") or "").strip().lower()
    current = requested if requested in UPLOAD_DEST_CHOICES else get_upload_destination()
    return jsonify(_upload_settings_payload(current))


@app.route("/api/settings/upload-folder", methods=["POST"])
def api_settings_upload_folder():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    body = request.get_json(silent=True) or {}
    destination_raw = body.get("destination")
    destination = get_upload_destination() if destination_raw is None else str(destination_raw).strip().lower()
    if destination not in UPLOAD_DEST_CHOICES:
        return jsonify({"ok": False, "error": "Ugyldigt upload-destination-valg"}), 400

    try:
        parent_subdir = _normalize_upload_subdir(str(body.get("parent") or ""))
    except Exception:
        return jsonify({"ok": False, "error": "Ugyldig overmappe"}), 400

    try:
        new_subdir_input = _normalize_upload_subdir(str(body.get("path") or ""))
    except Exception:
        return jsonify({"ok": False, "error": "Ugyldigt mappenavn"}), 400
    if not new_subdir_input:
        return jsonify({"ok": False, "error": "Angiv en mappe"}), 400

    # Create path relative to selected parent folder when parent is provided
    new_subdir = f"{parent_subdir}/{new_subdir_input}" if parent_subdir else new_subdir_input
    try:
        new_subdir = _normalize_upload_subdir(new_subdir)
    except Exception:
        return jsonify({"ok": False, "error": "Ugyldig mappe-sti"}), 400

    target_root, _ = _upload_target_for_destination(destination)
    try:
        target_root.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        base = target_root.resolve()
        target = (target_root / new_subdir).resolve()
        target.relative_to(base)
    except Exception:
        return jsonify({"ok": False, "error": "Ugyldig mappe-sti"}), 400

    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Kunne ikke oprette mappe: {e}"}), 400

    _set_upload_subdir(destination, new_subdir)
    payload = _upload_settings_payload(destination)
    payload["created"] = new_subdir
    return jsonify(payload)


@app.route("/api/settings/upload-folder-delete", methods=["POST"])
def api_settings_upload_folder_delete():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    body = request.get_json(silent=True) or {}
    destination = str(body.get("destination") or "uploads").strip().lower()
    if destination != UPLOAD_DEST_UPLOADS:
        return jsonify({"ok": False, "error": "Sletning understøttes kun i uploads-mappen"}), 400

    raw_paths = body.get("paths")
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    if not isinstance(raw_paths, list):
        return jsonify({"ok": False, "error": "Angiv liste af mapper"}), 400

    normalized: list[str] = []
    for rp in raw_paths:
        try:
            safe = _normalize_upload_subdir(str(rp or ""))
        except Exception:
            return jsonify({"ok": False, "error": "Ugyldig mappe-sti"}), 400
        if safe:
            normalized.append(safe)
    if not normalized:
        return jsonify({"ok": False, "error": "Vælg mindst én mappe"}), 400

    # Keep top-most selected folders only (children of selected parents are redundant)
    normalized = sorted(set(normalized), key=lambda x: (x.count("/"), x.lower()))
    selected: list[str] = []
    for path in normalized:
        if any(path == p or path.startswith(p + "/") for p in selected):
            continue
        selected.append(path)

    target_root, rel_prefix = _upload_target_for_destination(destination)
    try:
        base = target_root.resolve()
    except Exception:
        return jsonify({"ok": False, "error": "Upload-rodmappe kunne ikke læses"}), 500

    deleted: list[str] = []
    missing: list[str] = []
    for subdir in selected:
        try:
            target = (target_root / subdir).resolve()
            target.relative_to(base)
        except Exception:
            return jsonify({"ok": False, "error": "Ugyldig mappe-sti"}), 400

        if not target.exists() or not target.is_dir():
            missing.append(subdir)
            continue
        try:
            shutil.rmtree(target)
            deleted.append(subdir)
        except Exception as e:
            return jsonify({"ok": False, "error": f"Kunne ikke slette mappe '{subdir}': {e}"}), 400

    # Clean stale selected subdir setting if deleted
    current_subdir = get_upload_subdir(destination)
    if current_subdir and any(current_subdir == d or current_subdir.startswith(d + "/") for d in deleted):
        _set_upload_subdir(destination, "")

    rel_prefixes = [f"{rel_prefix}{d}" if rel_prefix else d for d in deleted]
    removed = _delete_indexed_photos_for_prefixes(rel_prefixes)

    payload = _upload_settings_payload(destination)
    payload["deleted"] = deleted
    payload["missing"] = missing
    payload["removed_photos"] = removed.get("photos", 0)
    payload["removed_faces"] = removed.get("faces", 0)
    payload["removed_thumbs"] = removed.get("thumbs", 0)
    return jsonify(payload)


@app.route("/api/settings/dns", methods=["GET", "POST"])
def api_settings_dns():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        raw = str(body.get("duckdns_base_url") or "").strip()
        if raw:
            normalized = _normalize_share_base_url(raw)
            if not normalized:
                return jsonify({"ok": False, "error": "Ugyldig URL. Brug fx https://mitnavn.duckdns.org"}), 400
            _set_setting("share_duckdns_base_url", normalized)
        else:
            _set_setting("share_duckdns_base_url", "")

    saved = str(_get_setting("share_duckdns_base_url", "") or "").strip()
    env_default = str(SHARE_DUCKDNS_BASE_URL or "").strip()
    effective = saved or env_default
    return jsonify(
        {
            "ok": True,
            "duckdns_base_url": saved,
            "effective_duckdns_base_url": effective,
            "using_env_default": bool(env_default and not saved),
        }
    )


@app.route("/api/settings/dns/effective", methods=["GET"])
def api_settings_dns_effective():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    saved = str(_get_setting("share_duckdns_base_url", "") or "").strip()
    env_default = str(SHARE_DUCKDNS_BASE_URL or "").strip()
    effective = saved or env_default
    normalized = _normalize_share_base_url(effective)
    return jsonify(
        {
            "ok": True,
            "effective_duckdns_base_url": normalized or "",
            "duckdns_configured": bool(normalized),
            "using_env_default": bool(env_default and not saved and normalized),
        }
    )


@app.route("/api/settings/heic", methods=["GET", "POST"])
def api_settings_heic():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        conv = body.get("convert_on_upload")
        keep = body.get("keep_originals")
        if conv is not None:
            _set_setting("heic_convert_on_upload", "1" if bool(conv) else "0")
        if keep is not None:
            _set_setting("heic_keep_originals", "1" if bool(keep) else "0")

    return jsonify(
        {
            "ok": True,
            "convert_on_upload": heic_convert_on_upload_enabled(),
            "keep_originals": heic_keep_originals_enabled(),
            "env_default_convert": HEIC_CONVERT_ON_UPLOAD_DEFAULT,
        }
    )


def _convert_existing_heic(stop_event=None) -> Dict[str, Any]:
    init_db()
    log_event("heic_bulk_start")
    processed = 0
    errors = 0
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT rel_path FROM photos WHERE LOWER(rel_path) LIKE '%.heic' OR LOWER(rel_path) LIKE '%.heif'").fetchall()
    for r in rows:
        if stop_event and stop_event.is_set():
            break
        try:
            orig_rel = r["rel_path"]
            src = _disk_path_from_rel_path(orig_rel)
            if not src.exists():
                continue

            new_rel = str(Path(orig_rel).with_suffix(".jpg")).replace("\\", "/")
            dst: Path

            if orig_rel.startswith("uploads/"):
                try:
                    if orig_rel.startswith("uploads/originals/"):
                        parts = orig_rel.split("/", 2)
                        sub_rel = parts[2] if len(parts) >= 3 else Path(orig_rel).name
                    else:
                        parts = orig_rel.split("/", 1)
                        sub_rel = parts[1] if len(parts) >= 2 else Path(orig_rel).name
                except Exception:
                    sub_rel = Path(orig_rel).name

                subdir_only = str(Path(sub_rel).parent).replace("\\", "/").strip("./")
                leaf_jpg = f"{Path(sub_rel).stem}.jpg"
                conv_dir = UPLOAD_DIR / "converted" / (subdir_only if subdir_only not in {"", "."} else "")
                conv_dir.mkdir(parents=True, exist_ok=True)
                dst = conv_dir / leaf_jpg
                if dst.exists():
                    i = 1
                    stem = Path(leaf_jpg).stem
                    while True:
                        cand = conv_dir / f"{stem}_{i}.jpg"
                        if not cand.exists():
                            dst = cand
                            break
                        i += 1
                tail = (
                    Path(sub_rel).with_suffix(".jpg").name
                    if subdir_only in {"", "."}
                    else (Path(subdir_only) / Path(sub_rel).with_suffix(".jpg").name).as_posix()
                )
                new_rel = f"uploads/converted/{tail}"
            else:
                dst = src.with_suffix(".jpg")
                dst.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(src) as himg:
                try:
                    himg = ImageOps.exif_transpose(himg)
                except Exception:
                    pass
                rgb = himg.convert("RGB")
                exif_bytes = None
                try:
                    exif_bytes = himg.info.get("exif") or himg.getexif().tobytes()
                except Exception:
                    exif_bytes = None
                save_kwargs = {"format": "JPEG", "quality": 92, "optimize": True}
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
                rgb.save(dst, **save_kwargs)

            try:
                st = src.stat()
                os.utime(dst, (st.st_atime, st.st_mtime))
            except Exception:
                pass

            meta = extract_metadata(dst, new_rel, generate_thumb=True)
            upsert_photo(meta)
            try:
                with closing(get_conn()) as conn2:
                    conn2.execute("DELETE FROM photos WHERE rel_path=?", (orig_rel,))
                    conn2.commit()
            except Exception:
                pass
            try:
                if not heic_keep_originals_enabled():
                    src.unlink(missing_ok=True)
            except Exception:
                pass
            processed += 1
            log_event("heic_converted", rel_path=new_rel)
        except Exception as e:
            errors += 1
            log_event("error", rel_path=str(r["rel_path"]), error=f"heic_bulk: {e}")
    res = {"ok": True, "processed": processed, "errors": errors}
    log_event("heic_bulk_done", **res)
    return res


@app.route("/api/heic/convert-existing", methods=["POST"])
def api_heic_convert_existing():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global heic_convert_thread, last_heic_convert_result
    if heic_convert_thread and heic_convert_thread.is_alive():
        return jsonify({"ok": False, "error": "HEIC-konvertering kører allerede"}), 409
    scan_stop_event.clear()
    last_heic_convert_result = None

    def run_bulk():
        global last_heic_convert_result
        last_heic_convert_result = _convert_existing_heic(stop_event=scan_stop_event)

    heic_convert_thread = threading.Thread(target=run_bulk, daemon=True)
    heic_convert_thread.start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/heic/convert-existing/status")
def api_heic_convert_existing_status():
    running = bool(heic_convert_thread and heic_convert_thread.is_alive())
    return jsonify({
        "ok": True,
        "running": running,
        "result": (last_heic_convert_result if not running else None),
    })


@app.route("/api/settings/ai-performance", methods=["GET", "POST"])
def api_settings_ai_performance():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        ai_throttle = _parse_throttle_value(body.get("ai_ingest_throttle_sec"), AI_INGEST_THROTTLE_SEC)
        faces_throttle = _parse_throttle_value(body.get("faces_index_throttle_sec"), FACES_INDEX_THROTTLE_SEC)
        _set_setting("ai_ingest_throttle_sec", str(ai_throttle))
        _set_setting("faces_index_throttle_sec", str(faces_throttle))

    return jsonify(
        {
            "ok": True,
            "ai_ingest_throttle_sec": ai_ingest_throttle_enabled_sec(),
            "faces_index_throttle_sec": faces_index_throttle_enabled_sec(),
            "runtime_applies_without_restart": True,
        }
    )


# --- Upload endpoint (drag & drop) ---
@app.route("/api/upload/tus", methods=["OPTIONS"])
@app.route("/api/upload/tus/<upload_id>", methods=["OPTIONS"])
@login_required
def api_upload_tus_options(upload_id: Optional[str] = None):
    resp = make_response("", 204)
    for k, v in _tus_headers().items():
        resp.headers[k] = v
    resp.headers["Access-Control-Allow-Methods"] = "OPTIONS, POST, HEAD, PATCH"
    resp.headers["Access-Control-Allow-Headers"] = "Tus-Resumable, Upload-Length, Upload-Offset, Upload-Metadata, Content-Type"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/upload/tus", methods=["POST"])
@login_required
def api_upload_tus_create():
    fb = _tus_require_version()
    if fb:
        return jsonify(fb[0]), fb[1], _tus_headers()

    try:
        TUS_TMP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Will fail later when writing if path is unusable
        pass
    try:
        upload_length = int(str(request.headers.get("Upload-Length") or "0").strip())
    except Exception:
        upload_length = -1
    if upload_length < 0:
        return jsonify({"ok": False, "error": "Invalid Upload-Length"}), 400, _tus_headers()

    meta = _parse_tus_metadata(str(request.headers.get("Upload-Metadata") or ""))
    filename = str(meta.get("filename") or "").strip()
    if not filename:
        return jsonify({"ok": False, "error": "Missing filename"}), 400, _tus_headers()

    destination = get_upload_destination()
    destination_override = str(meta.get("destination") or "").strip().lower()
    if destination_override:
        if destination_override not in UPLOAD_DEST_CHOICES:
            return jsonify({"ok": False, "error": "Ugyldig upload-destination"}), 400, _tus_headers()
        destination = destination_override

    subdir = get_upload_subdir(destination)
    subdir_override_raw = meta.get("subdir")
    if subdir_override_raw is not None:
        try:
            subdir = _normalize_upload_subdir(str(subdir_override_raw or ""))
        except Exception:
            return jsonify({"ok": False, "error": "Ugyldig upload-undermappe"}), 400, _tus_headers()

    target_root, rel_prefix = _upload_target_for_destination(destination)
    subdir = _ensure_default_upload_subdir(destination, target_root, subdir)
    target_dir = (target_root / subdir) if subdir else target_root
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Kan ikke oprette upload-destination: {e}"}), 500, _tus_headers()

    upload_id = secrets.token_urlsafe(18)
    data_path, _ = _tus_upload_paths(upload_id)
    try:
        with data_path.open("wb"):
            pass
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unable to create upload: {e}"}), 500, _tus_headers()

    try:
        last_modified_ms = int(str(meta.get("lastModified") or "0").strip() or "0")
    except Exception:
        last_modified_ms = 0

    upload_meta: Dict[str, Any] = {
        "id": upload_id,
        "filename": filename,
        "destination": destination,
        "subdir": subdir,
        "upload_length": upload_length,
        "upload_offset": 0,
        "target_dir": str(target_dir),
        "rel_prefix": rel_prefix,
        "last_modified_ms": last_modified_ms,
        "uploaded_by": str(getattr(current_user, "username", "") or ""),
        "created_at": now_iso(),
    }
    _tus_store_meta(upload_id, upload_meta)

    try:
        log_event("upload_tus_created", upload_id=upload_id, filename=filename, destination=destination, subdir=subdir, upload_length=upload_length)
    except Exception:
        pass

    resp = make_response("", 201)
    for k, v in _tus_headers().items():
        resp.headers[k] = v
    resp.headers["Location"] = url_for("api_upload_tus_file", upload_id=upload_id)
    resp.headers["Upload-Offset"] = "0"
    return resp


@app.route("/api/upload/tus/<upload_id>", methods=["HEAD"])
@login_required
def api_upload_tus_head(upload_id: str):
    fb = _tus_require_version()
    if fb:
        return jsonify(fb[0]), fb[1], _tus_headers()

    meta = _tus_load_meta(upload_id)
    if not meta:
        return jsonify({"ok": False, "error": "Upload not found"}), 404, _tus_headers()

    data_path, _ = _tus_upload_paths(upload_id)
    offset = int(meta.get("upload_offset") or 0)
    try:
        if data_path.exists():
            offset = int(data_path.stat().st_size)
    except Exception:
        pass

    resp = make_response("", 204)
    for k, v in _tus_headers().items():
        resp.headers[k] = v
    resp.headers["Upload-Offset"] = str(max(0, offset))
    resp.headers["Upload-Length"] = str(int(meta.get("upload_length") or 0))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/upload/tus/<upload_id>", methods=["PATCH"])
@login_required
def api_upload_tus_file(upload_id: str):
    fb = _tus_require_version()
    if fb:
        return jsonify(fb[0]), fb[1], _tus_headers()
    if str(request.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() != "application/offset+octet-stream":
        return jsonify({"ok": False, "error": "Invalid Content-Type"}), 415, _tus_headers()

    meta = _tus_load_meta(upload_id)
    if not meta:
        return jsonify({"ok": False, "error": "Upload not found"}), 404, _tus_headers()

    data_path, meta_path = _tus_upload_paths(upload_id)
    if not data_path.exists():
        return jsonify({"ok": False, "error": "Upload data missing"}), 410, _tus_headers()

    try:
        req_offset = int(str(request.headers.get("Upload-Offset") or "0").strip())
    except Exception:
        return jsonify({"ok": False, "error": "Invalid Upload-Offset"}), 400, _tus_headers()

    current_size = int(data_path.stat().st_size)
    if req_offset != current_size:
        resp = make_response("", 409)
        for k, v in _tus_headers().items():
            resp.headers[k] = v
        resp.headers["Upload-Offset"] = str(current_size)
        return resp

    body = request.get_data(cache=False, as_text=False) or b""
    try:
        with data_path.open("ab") as fh:
            if body:
                fh.write(body)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unable to write upload chunk: {e}"}), 500, _tus_headers()

    new_offset = int(data_path.stat().st_size)
    total_length = int(meta.get("upload_length") or 0)
    meta["upload_offset"] = new_offset
    _tus_store_meta(upload_id, meta)

    if total_length > 0 and new_offset >= total_length:
        target_dir = Path(str(meta.get("target_dir") or ""))
        rel_prefix = str(meta.get("rel_prefix") or "")
        subdir = str(meta.get("subdir") or "")
        filename = str(meta.get("filename") or "")
        uploaded_by = str(meta.get("uploaded_by") or "")
        try:
            last_modified_ms = int(meta.get("last_modified_ms") or 0)
        except Exception:
            last_modified_ms = 0

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            ok, saved_name, err = _commit_uploaded_file(
                target_dir=target_dir,
                rel_prefix=rel_prefix,
                subdir=subdir,
                source_path=data_path,
                original_name=filename,
                last_modified_ms=last_modified_ms,
                uploaded_by=uploaded_by,
            )
            try:
                meta_path.unlink(missing_ok=True)
            except Exception:
                pass
            if ok:
                try:
                    log_event("upload_done", saved=1, errors=0)
                except Exception:
                    pass
            else:
                try:
                    log_event("error", filename=filename, error=err)
                except Exception:
                    pass
                return jsonify({"ok": False, "error": err or "Upload finalize failed"}), 500, _tus_headers({"Upload-Offset": str(new_offset)})
        except Exception as e:
            return jsonify({"ok": False, "error": f"Upload finalize failed: {e}"}), 500, _tus_headers({"Upload-Offset": str(new_offset)})

    resp = make_response("", 204)
    for k, v in _tus_headers().items():
        resp.headers[k] = v
    resp.headers["Upload-Offset"] = str(new_offset)
    return resp


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    # Direct uploads: create only the specific target directory when needed
    destination = get_upload_destination()
    destination_override = str(request.form.get("destination") or "").strip().lower()
    if destination_override:
        if destination_override not in UPLOAD_DEST_CHOICES:
            return jsonify({"ok": False, "error": "Ugyldig upload-destination"}), 400
        destination = destination_override

    subdir = get_upload_subdir(destination)
    subdir_override_raw = request.form.get("subdir")
    if subdir_override_raw is not None:
        try:
            subdir = _normalize_upload_subdir(str(subdir_override_raw or ""))
        except Exception:
            return jsonify({"ok": False, "error": "Ugyldig upload-undermappe"}), 400

    target_root, rel_prefix = _upload_target_for_destination(destination)
    subdir = _ensure_default_upload_subdir(destination, target_root, subdir)
    target_dir = (target_root / subdir) if subdir else target_root
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Kan ikke oprette upload-destination: {e}"}), 500
    files = request.files.getlist("files") or []
    try:
        log_event("upload_start", count=len(files), destination=destination, subdir=subdir)
    except Exception:
        pass
    if not files:
        return jsonify({"ok": False, "error": "No files"}), 400
    saved = []
    errors: list[str] = []
    # Optional client-side metadata (array of {name,lastModified})
    client_meta = {}
    try:
        meta_raw = request.form.get("meta")
        if meta_raw:
            for entry in json.loads(meta_raw):
                n = str(entry.get("name"))
                lm = int(entry.get("lastModified")) if entry.get("lastModified") is not None else None
                if n and lm:
                    client_meta[n] = lm
    except Exception:
        client_meta = {}
    for f in files:
        try:
            name = secure_filename(f.filename or "")
            if not name:
                continue
            ext = Path(name).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                errors.append(f"Unsupported: {name}")
                try: log_event("upload_skip_unsupported", filename=name, ext=ext)
                except Exception: pass
                continue
            # Ensure unique filename
            target = target_dir / name
            stem = Path(name).stem
            suffix = Path(name).suffix
            i = 1
            while target.exists():
                target = target_dir / f"{stem}_{i}{suffix}"
                i += 1
            f.save(str(target))
            try: log_event("upload_saved", filename=name, path=str(target))
            except Exception: pass
            # If client provided lastModified, set file mtime to preserve original date
            try:
                lm_ms = client_meta.get(f.filename)
                if lm_ms:
                    ts = float(lm_ms) / 1000.0
                    os.utime(target, (ts, ts))
            except Exception:
                pass
            rel_leaf = f"{subdir}/{target.name}" if subdir else target.name
            rel = f"{rel_prefix}{rel_leaf}" if rel_prefix else rel_leaf
            try:
                meta = extract_metadata(target, rel)
                meta["uploaded_by"] = str(getattr(current_user, "username", "") or "")
                upsert_photo(meta)
                try: log_event("upload_indexed", rel_path=rel, width=meta.get("width"), height=meta.get("height"), has_gps=bool(meta.get("gps_lat") and meta.get("gps_lon")))
                except Exception: pass
                if ai_auto_ingest_enabled():
                    try:
                        threading.Thread(target=_embed_uploaded_photo_if_needed, args=(rel,), daemon=True).start()
                        try: log_event("ai_embed_queued", rel_path=rel)
                        except Exception: pass
                    except Exception as e:
                        try: log_event("error", rel_path=rel, error=f"ai_embed_queue: {e}")
                        except Exception: pass
                if ai_desc_auto_ingest_enabled():
                    try:
                        threading.Thread(target=_describe_uploaded_photo_if_needed, args=(rel,), daemon=True).start()
                        try: log_event("ai_desc_queued", rel_path=rel)
                        except Exception: pass
                    except Exception as e:
                        try: log_event("error", rel_path=rel, error=f"ai_desc_queue: {e}")
                        except Exception: pass
                if faces_auto_index_enabled():
                    try:
                        threading.Thread(target=index_faces_for_photo, args=(rel,), daemon=True).start()
                        try: log_event("faces_queued", rel_path=rel)
                        except Exception: pass
                    except Exception as e:
                        try: log_event("error", rel_path=rel, error=f"faces_queue: {e}")
                        except Exception: pass
            except Exception as e:
                errors.append(f"Index fail: {target.name}: {e}")
                try: log_event("error", filename=target.name, rel_path=rel, error=str(e))
                except Exception: pass
            saved.append(target.name)
        except Exception as e:
            errors.append(str(e))
            try: log_event("error", filename=(f.filename if f else None), error=str(e))
            except Exception: pass
    try:
        log_event("upload_done", saved=len(saved), errors=len(errors))
    except Exception:
        pass
    return jsonify({"ok": True, "saved": saved, "errors": errors})


@app.route("/api/upload/postprocess", methods=["POST"])
@login_required
def api_upload_postprocess():
    uploaded_by = str(getattr(current_user, "username", "") or "")
    rels = _pop_uploaded_rels(uploaded_by)

    if _is_upload_postprocess_running(uploaded_by):
        for rel in rels:
            _queue_uploaded_rel(uploaded_by, rel)
        with UPLOAD_PENDING_LOCK:
            pending_count = len(UPLOAD_PENDING_BY_USER.get((uploaded_by or "").strip() or "__unknown__", []))
        return jsonify({"ok": True, "started": False, "running": True, "pending": pending_count})

    if not rels:
        state = _get_upload_postprocess_state(uploaded_by)
        if state:
            with UPLOAD_PENDING_LOCK:
                pending_count = len(UPLOAD_PENDING_BY_USER.get((uploaded_by or "").strip() or "__unknown__", []))
            return jsonify({"ok": True, "started": False, "running": bool(state.get("running")), "pending": pending_count, "result": state.get("result"), "error": state.get("error")})
        return jsonify({"ok": True, "started": False, "running": False, "pending": 0, "result": {"ok": True, "received": 0, "indexed": 0, "index_errors": 0, "faces_enabled": faces_auto_index_enabled(), "faces_done": 0, "faces_errors": 0, "ai_enabled": ai_auto_ingest_enabled(), "ai_done": 0, "ai_errors": 0, "ai_desc_enabled": ai_desc_auto_ingest_enabled(), "ai_desc_done": 0, "ai_desc_errors": 0}})

    threading.Thread(target=_upload_postprocess_worker, args=(uploaded_by, rels), daemon=True).start()
    with UPLOAD_PENDING_LOCK:
        pending_count = len(UPLOAD_PENDING_BY_USER.get((uploaded_by or "").strip() or "__unknown__", []))
    return jsonify({"ok": True, "started": True, "running": True, "pending": pending_count, "queued": len(rels)})


@app.route("/api/upload/postprocess/status")
@login_required
def api_upload_postprocess_status():
    uploaded_by = str(getattr(current_user, "username", "") or "")
    state = _get_upload_postprocess_state(uploaded_by)
    with UPLOAD_PENDING_LOCK:
        pending_count = len(UPLOAD_PENDING_BY_USER.get((uploaded_by or "").strip() or "__unknown__", []))
    if not state:
        return jsonify({"ok": True, "running": False, "pending": pending_count, "result": None, "error": None, "phase": None, "current_rel": None, "stage_processed": 0, "stage_total": 0})
    return jsonify(
        {
            "ok": True,
            "running": bool(state.get("running")),
            "pending": pending_count,
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "result": state.get("result"),
            "error": state.get("error"),
            "phase": state.get("phase"),
            "current_rel": state.get("current_rel"),
            "stage_processed": int(state.get("stage_processed") or 0),
            "stage_total": int(state.get("stage_total") or 0),
        }
    )


@app.route("/api/logs/clear", methods=["POST"])
def api_logs_clear():
    fb = _forbid_user_role_for_maintenance()
    if fb:
        return jsonify(fb[0]), fb[1]
    global LOG_SEQ
    LOG_BUFFER.clear()
    LOG_SEQ = 0
    return jsonify({"ok": True})


# --- Authentication routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        with closing(get_conn()) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, is_admin, role, totp_enabled, totp_secret, totp_setup_done, totp_remember_days FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            if int(row["totp_enabled"] or 0) == 1:
                # If 2FA is enabled but not set up yet, send to setup
                try:
                    keys = set(row.keys())
                except Exception:
                    keys = set()
                setup_done = int(row["totp_setup_done"] or 0) if ("totp_setup_done" in keys) else 0
                totp_secret = row["totp_secret"] if ("totp_secret" in keys) else None
                if not totp_secret or setup_done == 0:
                    _log_login_attempt(username, int(row["id"]), str(row["username"]), True, "login_password", "2fa_setup_required")
                    user = _row_to_user(row)
                    login_user(user)
                    return redirect(url_for("setup_2fa"))
                # Otherwise require 2FA unless trusted cookie is valid
                if _trust_cookie_valid_for(int(row["id"])):
                    _log_login_attempt(username, int(row["id"]), str(row["username"]), True, "login_success", "trusted_device")
                    user = _row_to_user(row)
                    login_user(user)
                    next_url = request.args.get("next") or url_for("index")
                    return redirect(next_url)
                from flask import session
                session["2fa_user_id"] = int(row["id"])
                _log_login_attempt(username, int(row["id"]), str(row["username"]), True, "login_password", "2fa_required")
                return redirect(url_for("verify_2fa", next=request.args.get("next")))
            _log_login_attempt(username, int(row["id"]), str(row["username"]), True, "login_success", "password_ok")
            user = _row_to_user(row)
            login_user(user)
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        _log_login_attempt(username, None, None, False, "login_failed", "invalid_credentials")
        return render_template("login.html", error=_ui_text("login_invalid_credentials"))
    created = True if (request.args.get("created") in ("1", "true", "True")) else False
    return render_template("login.html", created=created)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/login/2fa", methods=["GET", "POST"])
def verify_2fa():
    from flask import session
    uid = session.get("2fa_user_id")
    if not uid:
        return redirect(url_for("login"))
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id, username, is_admin, role, totp_secret, totp_remember_days FROM users WHERE id= ?", (uid,)).fetchone()
        if not row or not row["totp_secret"]:
            return redirect(url_for("login"))
        totp = pyotp.TOTP(row["totp_secret"]) 
        if totp.verify(code, valid_window=1):
            _log_login_attempt(str(row["username"]), int(row["id"]), str(row["username"]), True, "login_2fa", "2fa_ok")
            user = _row_to_user(row)
            resp = redirect(request.args.get("next") or url_for("index"))
            login_user(user)
            # mark that initial setup is completed
            with closing(get_conn()) as conn:
                conn.execute("UPDATE users SET totp_setup_done=1 WHERE id=?", (current_user.id,))
                conn.commit()
            session.pop("2fa_user_id", None)
            # Set trusted-device cookie automatically if preference > 0
            pref_days = int(row["totp_remember_days"] or 0) if row else 0
            if pref_days > 0:
                token, max_age = _make_trust_cookie(int(row["id"]), pref_days)
                if token:
                    resp.set_cookie("fl_trust", token, max_age=max_age, httponly=True, samesite="Lax", path="/")
            return resp
        _log_login_attempt(str(row["username"]), int(row["id"]), str(row["username"]), False, "login_2fa", "invalid_code")
        return render_template("2fa_verify.html", error=_ui_text("invalid_code"))
    # GET
    return render_template("2fa_verify.html")


@app.route("/account/2fa", methods=["GET", "POST"])
@login_required
def setup_2fa():
    # Generate secret if missing
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT totp_secret, totp_enabled, totp_remember_days FROM users WHERE id=?",
            (current_user.id,),
        ).fetchone()
    secret = row["totp_secret"] if row else None
    if not secret:
        secret = pyotp.random_base32()
        with closing(get_conn()) as conn:
            conn.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, current_user.id))
            conn.commit()
    enabled_flag = int(row["totp_enabled"] or 0) if row else 0
    # Only prepare QR/secret for template when not enabled
    data_url = None
    if enabled_flag == 0:
        issuer = "FjordLens"
        user_label = f"{issuer}:{current_user.username}"
        otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_label, issuer_name=issuer)
        img = qrcode.make(otp_uri)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        # Verify code for any sensitive change (disable/change remember)
        code = (request.form.get("code") or "").strip()
        if action in {"disable", "remember", "save"}:
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                rdays = int(row["totp_remember_days"] or 0) if row else 0
                # For 'save', we only require code if changes are sensitive; we re-check below
                if action != "save":
                    return render_template("2fa_setup.html", qrcode_url=data_url, secret=None, enabled=row["totp_enabled"], error=_ui_text("invalid_code"), remember_days=rdays)
        if action == "disable":
            with closing(get_conn()) as conn:
                conn.execute("UPDATE users SET totp_enabled=0 WHERE id=?", (current_user.id,))
                conn.commit()
            rdays = int(row["totp_remember_days"] or 0) if row else 0
            # Clear trusted-device cookie when disabling 2FA
            resp = make_response(render_template("2fa_setup.html", qrcode_url=None, secret=None, enabled=False, ok=True, remember_days=rdays))
            resp.set_cookie("fl_trust", "", max_age=0)
            return resp
        if action == "save":
            try:
                new_days = max(0, min(30, int(request.form.get("days") or 0)))
            except ValueError:
                new_days = 0
            disable = (request.form.get("disable") in ("1", "on", "true", "True"))
            cur_days = int(row["totp_remember_days"] or 0) if row else 0
            cur_enabled = int(row["totp_enabled"] or 0) if row else 0
            needs_code = (cur_enabled == 1) and (disable or (new_days != cur_days))
            if needs_code and not pyotp.TOTP(secret).verify(code, valid_window=1):
                return render_template("2fa_setup.html", qrcode_url=(data_url if enabled_flag == 0 else None), secret=(secret if enabled_flag == 0 else None), enabled=cur_enabled, error=_ui_text("invalid_code"), remember_days=cur_days)
            enabled_after = cur_enabled
            with closing(get_conn()) as conn:
                if disable and cur_enabled == 1:
                    conn.execute("UPDATE users SET totp_enabled=0 WHERE id=?", (current_user.id,))
                    enabled_after = 0
                # Always update days to what the user chose
                conn.execute("UPDATE users SET totp_remember_days=? WHERE id=?", (new_days, current_user.id))
                conn.commit()
            resp = make_response(render_template("2fa_setup.html", qrcode_url=(data_url if enabled_after == 0 else None), secret=(secret if enabled_after == 0 else None), enabled=bool(enabled_after), ok=True, remember_days=new_days))
            # Manage trusted-device cookie according to new days and enabled state
            if enabled_after == 1 and new_days > 0:
                token, max_age = _make_trust_cookie(int(current_user.id), new_days)
                if token:
                    resp.set_cookie("fl_trust", token, max_age=max_age, httponly=True, samesite="Lax", path="/")
            else:
                resp.set_cookie("fl_trust", "", max_age=0)
            return resp
        if action == "remember":
            try:
                days = max(0, min(30, int(request.form.get("days") or 0)))
            except ValueError:
                days = 0
            with closing(get_conn()) as conn:
                conn.execute("UPDATE users SET totp_remember_days=? WHERE id=?", (days, current_user.id))
                conn.commit()
            # Set/refresh trusted-device cookie immediately after successful verification
            resp = make_response(render_template("2fa_setup.html", qrcode_url=(data_url if enabled_flag == 0 else None), secret=(secret if enabled_flag == 0 else None), enabled=row["totp_enabled"], ok=True, remember_days=days))
            if days > 0:
                token, max_age = _make_trust_cookie(int(current_user.id), days)
                if token:
                    resp.set_cookie("fl_trust", token, max_age=max_age, httponly=True, samesite="Lax", path="/")
            else:
                resp.set_cookie("fl_trust", "", max_age=0)
            return resp
        # enable flow (also accept preferred remember days)
        if pyotp.TOTP(secret).verify(code, valid_window=1):
            try:
                days = max(0, min(30, int(request.form.get("days") or 0)))
            except ValueError:
                days = 0
            with closing(get_conn()) as conn:
                conn.execute("UPDATE users SET totp_enabled=1, totp_setup_done=1, totp_remember_days=? WHERE id=?", (days, current_user.id))
                conn.commit()
            resp = make_response(render_template("2fa_setup.html", qrcode_url=None, secret=None, enabled=True, ok=True, remember_days=days))
            if days > 0:
                token, max_age = _make_trust_cookie(int(current_user.id), days)
                if token:
                    resp.set_cookie("fl_trust", token, max_age=max_age, httponly=True, samesite="Lax", path="/")
            return resp
        rdays = int(row["totp_remember_days"] or 0) if row else 0
        return render_template("2fa_setup.html", qrcode_url=(data_url if enabled_flag == 0 else None), secret=(secret if enabled_flag == 0 else None), enabled=row["totp_enabled"], error=_ui_text("invalid_code"), remember_days=rdays)
    rdays = int(row["totp_remember_days"] or 0) if row else 0
    return render_template("2fa_setup.html", qrcode_url=(data_url if enabled_flag == 0 else None), secret=(secret if enabled_flag == 0 else None), enabled=row["totp_enabled"], remember_days=rdays) 


@app.route("/admin/users", methods=["GET", "POST"]) 
@login_required
def admin_users():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    msg = None
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip()
        if action == "create":
            u = (request.form.get("username") or "").strip()
            p = request.form.get("password") or ""
            role = (request.form.get("role") or "user").strip().lower()
            enforce_2fa = 1 if (request.form.get("enforce_2fa") in ("1", "on", "true", "True")) else 0
            if role not in {"admin", "manager", "user"}:
                role = "user"
            if u and p:
                try:
                    with closing(get_conn()) as conn:
                        conn.execute(
                            "INSERT INTO users(username, password_hash, is_admin, role, totp_enabled, totp_setup_done, created_at) VALUES (?,?,?,?,?,?,?)",
                            (u, generate_password_hash(p), 1 if role == "admin" else 0, role, enforce_2fa, 0, now_iso()),
                        )
                        conn.commit()
                    msg = _ui_text("admin_user_created")
                except Exception as e:
                    msg = f"{_ui_text('error_prefix')} {e}"
        elif action == "delete":
            try:
                uid = int(request.form.get("user_id") or 0)
            except Exception:
                uid = 0
            if uid:
                if str(uid) == str(current_user.id):
                    msg = _ui_text("admin_cannot_delete_self")
                else:
                    try:
                        with closing(get_conn()) as conn:
                            row = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
                            if not row:
                                msg = _ui_text("admin_user_not_found")
                            else:
                                r = (row["role"] or "user").lower()
                                if r == "admin":
                                    c = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND id<>?", (uid,)).fetchone()
                                    if not c or int(c["c"]) <= 0:
                                        msg = _ui_text("admin_cannot_delete_last_admin")
                                    else:
                                        conn.execute("DELETE FROM users WHERE id=?", (uid,))
                                        conn.commit()
                                        msg = _ui_text("admin_user_deleted")
                                else:
                                    conn.execute("DELETE FROM users WHERE id=?", (uid,))
                                    conn.commit()
                                    msg = _ui_text("admin_user_deleted")
                    except Exception as e:
                        msg = f"{_ui_text('error_prefix')} {e}"
    with closing(get_conn()) as conn:
        users = conn.execute("SELECT id, username, is_admin, role, totp_enabled, created_at FROM users ORDER BY id").fetchall()
    return render_template("admin_users.html", users=users, msg=msg)


# --- JSON APIs for embedded UI ---
@app.route("/api/admin/users", methods=["GET", "POST"])
@login_required
def api_admin_users():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    if request.method == "GET":
        with closing(get_conn()) as conn:
            rows = conn.execute("SELECT id, username, role, is_admin, totp_enabled, ui_language, search_language, created_at FROM users ORDER BY id").fetchall()
            all_folders = _list_all_photo_folders(conn)
            acl_rows = conn.execute("SELECT user_id, folder_path FROM user_folder_access ORDER BY folder_path COLLATE NOCASE").fetchall()
            audit_rows = conn.execute(
                """
                SELECT id, at, username_input, user_id, username, success, event_type, reason, ip, country, device
                FROM login_audit
                ORDER BY id DESC
                LIMIT 300
                """
            ).fetchall()
        by_user_acl: dict[int, list[str]] = {}
        for ar in acl_rows:
            try:
                uid = int(ar["user_id"])
                folder_path = _normalize_folder_acl_path(ar["folder_path"])
            except Exception:
                continue
            if not folder_path:
                continue
            by_user_acl.setdefault(uid, []).append(folder_path)
        items = []
        for r in rows:
            allowed_folders = by_user_acl.get(int(r["id"]), [])
            items.append({
                "id": int(r["id"]),
                "username": r["username"],
                "role": (r["role"] or ("admin" if int(r["is_admin"] or 0) else "user")),
                "is_admin": bool(r["is_admin"] or 0),
                "totp_enabled": bool(r["totp_enabled"] or 0),
                "ui_language": _normalize_language(r["ui_language"], DEFAULT_UI_LANGUAGE),
                "search_language": _normalize_language(r["search_language"], DEFAULT_SEARCH_LANGUAGE),
                "allowed_folders": allowed_folders,
                "created_at": r["created_at"],
            })
        login_audit = []
        for ar in audit_rows:
            login_audit.append(
                {
                    "id": int(ar["id"] or 0),
                    "at": ar["at"],
                    "username_input": str(ar["username_input"] or ""),
                    "user_id": int(ar["user_id"]) if ar["user_id"] is not None else None,
                    "username": str(ar["username"] or ""),
                    "success": bool(int(ar["success"] or 0)),
                    "event_type": str(ar["event_type"] or ""),
                    "reason": str(ar["reason"] or ""),
                    "ip": str(ar["ip"] or ""),
                    "country": str(ar["country"] or ""),
                    "device": str(ar["device"] or ""),
                }
            )
        return jsonify({"ok": True, "items": items, "available_folders": all_folders, "login_audit": login_audit})
    # POST create user
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip()
    p = data.get("password") or ""
    role = (data.get("role") or "user").strip().lower()
    ui_language = _normalize_language(data.get("ui_language"), DEFAULT_UI_LANGUAGE)
    search_language = _normalize_language(data.get("search_language"), DEFAULT_SEARCH_LANGUAGE)
    raw_allowed = data.get("allowed_folders")
    allowed_folders = raw_allowed if isinstance(raw_allowed, list) else []
    if role not in {"admin", "manager", "user"}:
        role = "user"
    if not u or not p:
        return jsonify({"ok": False, "error": "username_password_required"}), 400
    try:
        with closing(get_conn()) as conn:
            cur = conn.execute(
                "INSERT INTO users(username, password_hash, is_admin, role, ui_language, search_language, created_at) VALUES (?,?,?,?,?,?,?)",
                (u, generate_password_hash(p), 1 if role == "admin" else 0, role, ui_language, search_language, now_iso()),
            )
            # Some SQLite drivers/types may expose lastrowid as Optional
            uid_raw = getattr(cur, "lastrowid", None)
            if uid_raw is None:
                row = conn.execute("SELECT id FROM users WHERE username=? ORDER BY id DESC LIMIT 1", (u,)).fetchone()
                uid = int(row["id"]) if row else 0
            else:
                uid = int(uid_raw)
            _set_user_allowed_folders(conn, uid, allowed_folders)
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/admin/shares", methods=["GET"])
@login_required
def api_admin_shares_list():
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    include_inactive = request.args.get("include_inactive") in {"1", "true", "True"}
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
             SELECT s.id, s.share_name, s.folder_path, s.can_upload, s.can_delete, s.password_hash,
                 s.token_plain, s.link_use_duckdns,
                   s.expires_at, s.revoked, s.created_at, s.last_used_at, s.created_by_user_id,
                   u.username AS created_by_username
            FROM share_links s
            LEFT JOIN users u ON u.id = s.created_by_user_id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
        folder_rows = conn.execute(
            "SELECT share_id, folder_path FROM share_link_folders ORDER BY folder_path COLLATE NOCASE"
        ).fetchall()

    folders_by_share: dict[int, list[str]] = {}
    for fr in folder_rows:
        try:
            sid = int(fr["share_id"] or 0)
        except Exception:
            continue
        fp = _normalize_upload_subdir(str(fr["folder_path"] or ""))
        if not sid or not fp:
            continue
        bucket = folders_by_share.setdefault(sid, [])
        if fp not in bucket:
            bucket.append(fp)

    items: list[dict[str, Any]] = []
    for r in rows:
        revoked = bool(int(r["revoked"] or 0))
        expired = _share_is_expired(r["expires_at"])
        active = (not revoked) and (not expired)
        if not include_inactive and not active:
            continue

        can_upload = bool(int(r["can_upload"] or 0))
        can_delete = bool(int(r["can_delete"] or 0))
        permission = "view"
        if can_upload and can_delete:
            permission = "manage"
        elif can_upload:
            permission = "upload"

        share_id = int(r["id"])
        folder_paths = list(folders_by_share.get(share_id, []))
        if not folder_paths:
            fallback = _normalize_upload_subdir(str(r["folder_path"] or ""))
            if fallback:
                folder_paths = [fallback]
        share_name = str(r["share_name"] or "").strip()
        if not share_name:
            if len(folder_paths) == 1:
                share_name = f"uploads/{folder_paths[0]}"
            elif folder_paths:
                share_name = f"{len(folder_paths)} mapper"

        link = _share_link_for_admin_row(r)

        items.append(
            {
                "id": share_id,
                "share_name": share_name,
                "folder_path": str(r["folder_path"] or ""),
                "folder_paths": folder_paths,
                "folder_count": len(folder_paths),
                "permission": permission,
                "can_upload": can_upload,
                "can_delete": can_delete,
                "password_enabled": bool(str(r["password_hash"] or "").strip()),
                "expires_at": r["expires_at"],
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
                "revoked": revoked,
                "expired": expired,
                "active": active,
                "created_by_user_id": int(r["created_by_user_id"] or 0),
                "created_by_username": (r["created_by_username"] or ""),
                "link": link,
                "link_available": bool(link),
            }
        )

    return jsonify({"ok": True, "items": items})


@app.route("/api/admin/shares/<int:share_id>/revoke", methods=["POST"])
@login_required
def api_admin_shares_revoke(share_id: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id, revoked FROM share_links WHERE id=?", (int(share_id),)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Share-link findes ikke"}), 404
        if int(row["revoked"] or 0) == 1:
            return jsonify({"ok": True, "already_revoked": True})
        conn.execute("UPDATE share_links SET revoked=1 WHERE id=?", (int(share_id),))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/shares/<int:share_id>/extend", methods=["POST"])
@login_required
def api_admin_shares_extend(share_id: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}
    try:
        expires_value = int(body.get("expires_value") or 7)
    except Exception:
        expires_value = 7
    expires_unit = str(body.get("expires_unit") or "days").strip().lower()
    if expires_value < 1:
        expires_value = 1
    if expires_unit not in {"hours", "days"}:
        expires_unit = "days"
    expires_hours = expires_value if expires_unit == "hours" else (expires_value * 24)
    expires_hours = max(1, min(expires_hours, 24 * 365))
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(timespec="seconds") + "Z"

    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id, revoked FROM share_links WHERE id=?", (int(share_id),)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Share-link findes ikke"}), 404
        if int(row["revoked"] or 0) == 1:
            return jsonify({"ok": False, "error": "Share-link er tilbagekaldt"}), 400
        conn.execute("UPDATE share_links SET expires_at=? WHERE id=?", (expires_at, int(share_id)))
        conn.commit()

    return jsonify({"ok": True, "expires_at": expires_at})


@app.route("/api/admin/shares/<int:share_id>/activate", methods=["POST"])
@login_required
def api_admin_shares_activate(share_id: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}
    try:
        expires_value = int(body.get("expires_value") or 7)
    except Exception:
        expires_value = 7
    expires_unit = str(body.get("expires_unit") or "days").strip().lower()
    if expires_value < 1:
        expires_value = 1
    if expires_unit not in {"hours", "days"}:
        expires_unit = "days"
    expires_hours = expires_value if expires_unit == "hours" else (expires_value * 24)
    expires_hours = max(1, min(expires_hours, 24 * 365))
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(timespec="seconds") + "Z"

    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id FROM share_links WHERE id=?", (int(share_id),)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Share-link findes ikke"}), 404
        conn.execute("UPDATE share_links SET revoked=0, expires_at=? WHERE id=?", (expires_at, int(share_id)))
        conn.commit()

    return jsonify({"ok": True, "expires_at": expires_at})


@app.route("/api/admin/shares/<int:share_id>", methods=["DELETE"])
@login_required
def api_admin_shares_delete(share_id: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id FROM share_links WHERE id=?", (int(share_id),)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Share-link findes ikke"}), 404
        conn.execute("DELETE FROM share_link_folders WHERE share_id=?", (int(share_id),))
        conn.execute("DELETE FROM share_links WHERE id=?", (int(share_id),))
        conn.commit()

    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:uid>", methods=["DELETE", "PUT"])
@login_required
def api_admin_users_delete(uid: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        new_username = (data.get("username") or "").strip()
        new_password = data.get("password") or ""
        new_role_raw = data.get("role")
        new_role = None
        if new_role_raw is not None:
            new_role = str(new_role_raw).strip().lower()
            if new_role not in {"admin", "manager", "user"}:
                return jsonify({"ok": False, "error": "invalid_role"}), 400
        ui_language = _normalize_language(data.get("ui_language"), DEFAULT_UI_LANGUAGE)
        search_language = _normalize_language(data.get("search_language"), DEFAULT_SEARCH_LANGUAGE)
        raw_allowed = data.get("allowed_folders")
        allowed_folders = raw_allowed if isinstance(raw_allowed, list) else None
        if not new_username:
            return jsonify({"ok": False, "error": "username_required"}), 400
        try:
            with closing(get_conn()) as conn:
                row = conn.execute("SELECT id, role FROM users WHERE id=?", (uid,)).fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "not_found"}), 404

                cur_role = (row["role"] or "user").lower()
                target_role = new_role or cur_role

                if cur_role == "admin" and target_role != "admin":
                    c = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND id<>?", (uid,)).fetchone()
                    if not c or int(c["c"]) <= 0:
                        return jsonify({"ok": False, "error": "last_admin"}), 400

                if new_password:
                    conn.execute(
                        "UPDATE users SET username=?, password_hash=?, role=?, is_admin=?, ui_language=?, search_language=? WHERE id=?",
                        (
                            new_username,
                            generate_password_hash(new_password),
                            target_role,
                            1 if target_role == "admin" else 0,
                            ui_language,
                            search_language,
                            uid,
                        ),
                    )
                else:
                    conn.execute(
                        "UPDATE users SET username=?, role=?, is_admin=?, ui_language=?, search_language=? WHERE id=?",
                        (
                            new_username,
                            target_role,
                            1 if target_role == "admin" else 0,
                            ui_language,
                            search_language,
                            uid,
                        ),
                    )
                if allowed_folders is not None:
                    _set_user_allowed_folders(conn, uid, allowed_folders)
                conn.commit()
            return jsonify({"ok": True})
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "username_exists"}), 409
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    if str(uid) == str(current_user.id):
        return jsonify({"ok": False, "error": "cannot_delete_self"}), 400
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "not_found"}), 404
            r = (row["role"] or "user").lower()
            if r == "admin":
                c = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND id<>?", (uid,)).fetchone()
                if not c or int(c["c"]) <= 0:
                    return jsonify({"ok": False, "error": "last_admin"}), 400
            conn.execute("DELETE FROM user_folder_access WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM users WHERE id=?", (uid,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/admin/users/<int:uid>/folders", methods=["PUT"])
@login_required
def api_admin_user_folders(uid: int):
    if not getattr(current_user, "is_admin", False):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    raw_allowed = data.get("allowed_folders")
    if not isinstance(raw_allowed, list):
        return jsonify({"ok": False, "error": "invalid_allowed_folders"}), 400
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "not_found"}), 404
            reduced = _set_user_allowed_folders(conn, uid, raw_allowed)
            conn.commit()
        return jsonify({"ok": True, "allowed_folders": reduced})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/me", methods=["GET"])
@login_required
def api_me():
    try:
        with closing(get_conn()) as conn:
            row = conn.execute(
                "SELECT id, username, role, ui_language, search_language FROM users WHERE id=?",
                (current_user.id,),
            ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify(
            {
                "ok": True,
                "item": {
                    "id": int(row["id"]),
                    "username": row["username"],
                    "role": (row["role"] or "user"),
                    "ui_language": _normalize_language(row["ui_language"], DEFAULT_UI_LANGUAGE),
                    "search_language": _normalize_language(row["search_language"], DEFAULT_SEARCH_LANGUAGE),
                },
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/me/profile", methods=["POST"])
@login_required
def api_me_profile():
    data = request.get_json(silent=True) or {}
    new_username = (data.get("username") or "").strip()
    new_password = data.get("password") or ""
    ui_language = _normalize_language(data.get("ui_language"), DEFAULT_UI_LANGUAGE)
    search_language = _normalize_language(data.get("search_language"), DEFAULT_SEARCH_LANGUAGE)

    if not new_username:
        return jsonify({"ok": False, "error": "username_required"}), 400

    try:
        with closing(get_conn()) as conn:
            if new_password:
                conn.execute(
                    "UPDATE users SET username=?, password_hash=?, ui_language=?, search_language=? WHERE id=?",
                    (
                        new_username,
                        generate_password_hash(new_password),
                        ui_language,
                        search_language,
                        current_user.id,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE users SET username=?, ui_language=?, search_language=? WHERE id=?",
                    (new_username, ui_language, search_language, current_user.id),
                )
            conn.commit()

        try:
            current_user.username = new_username
            current_user.ui_language = ui_language
            current_user.search_language = search_language
        except Exception:
            pass

        return jsonify(
            {
                "ok": True,
                "item": {
                    "id": int(current_user.id),
                    "username": new_username,
                    "role": getattr(current_user, "role", "user"),
                    "ui_language": ui_language,
                    "search_language": search_language,
                },
            }
        )
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "username_exists"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/me/2fa", methods=["GET", "POST"])
@login_required
def api_me_2fa():
    # fetch current state
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT totp_secret, totp_enabled, totp_remember_days FROM users WHERE id=?",
            (current_user.id,),
        ).fetchone()
    secret = row["totp_secret"] if row else None
    enabled = bool(row["totp_enabled"] or 0) if row else False
    remember_days = int(row["totp_remember_days"] or 0) if row else 0

    if request.method == "GET":
        # Only show secret/QR during initial setup (not enabled yet)
        qr_url = None
        secret_out = None
        if not enabled:
            if not secret:
                secret = pyotp.random_base32()
                with closing(get_conn()) as conn:
                    conn.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, current_user.id))
                    conn.commit()
            issuer = "FjordLens"
            user_label = f"{issuer}:{current_user.username}"
            otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_label, issuer_name=issuer)
            img = qrcode.make(otp_uri)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            qr_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            secret_out = secret
        return jsonify({
            "ok": True,
            "enabled": enabled,
            "remember_days": remember_days,
            "secret": secret_out,  # null when enabled
            "qr": qr_url,          # null when enabled
            "user": current_user.username,
        })

    # POST: actions
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    code = (data.get("code") or "").strip()
    days = int(data.get("days") or 0)

    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT totp_secret, totp_enabled, totp_remember_days FROM users WHERE id=?",
            (current_user.id,),
        ).fetchone()
    secret = row["totp_secret"] if row else None
    if not secret:
        secret = pyotp.random_base32()
        with closing(get_conn()) as conn:
            conn.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, current_user.id))
            conn.commit()

    if action == "regen":
        # Regenerate secret; if already enabled, require current valid code to rotate
        if enabled:
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                return jsonify({"ok": False, "error": "invalid_code"}), 400
        secret = pyotp.random_base32()
        with closing(get_conn()) as conn:
            conn.execute("UPDATE users SET totp_secret=?, totp_enabled=0, totp_setup_done=0 WHERE id=?", (secret, current_user.id))
            conn.commit()
        issuer = "FjordLens"
        user_label = f"{issuer}:{current_user.username}"
        otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_label, issuer_name=issuer)
        img = qrcode.make(otp_uri)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        return jsonify({"ok": True, "qr": data_url})

    if action in {"enable", "disable", "remember", "save"}:
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            return jsonify({"ok": False, "error": "invalid_code"}), 400
        with closing(get_conn()) as conn:
            if action == "disable":
                conn.execute("UPDATE users SET totp_enabled=0 WHERE id=?", (current_user.id,))
            elif action in {"enable", "save", "remember"}:
                days = max(0, min(30, int(days or 0)))
                conn.execute("UPDATE users SET totp_enabled=1, totp_setup_done=1, totp_remember_days=? WHERE id=?", (days, current_user.id))
            conn.commit()
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "unknown_action"}), 400


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
