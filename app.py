import hashlib
import hmac
import io
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_from_directory, redirect, url_for, make_response
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
try:
    # Enable HEIC/HEIF support via pillow-heif if available
    from pillow_heif import register_heif_opener, HeifFile  # type: ignore
    register_heif_opener()
except Exception:
    pass
from urllib.parse import quote

APP_PORT = 8080
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "/photos")).resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
THUMB_DIR = DATA_DIR / "thumbs"
CONVERT_DIR = DATA_DIR / "converted"
DB_PATH = DATA_DIR / "fjordlens.db"
AI_URL = os.environ.get("AI_URL", "http://localhost:8001").rstrip("/")
AI_ENV_ENABLED_DEFAULT = (os.environ.get("AI_ENABLED", "1") not in {"0", "false", "False"})
AI_ENV_AUTO_INGEST_DEFAULT = (os.environ.get("AI_AUTO_INGEST", "0") in {"1", "true", "True"})

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
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

login_manager = LoginManager(app)
login_manager.login_view = "login"

# Global scan control
scan_stop_event = threading.Event()

# Simple in-memory log buffer for UI polling
from collections import deque
LOG_BUFFER: deque[Dict[str, Any]] = deque(maxlen=1000)
LOG_SEQ: int = 0


def log_event(event: str, **data: Any) -> None:
    global LOG_SEQ
    LOG_SEQ += 1
    LOG_BUFFER.append({"id": LOG_SEQ, "t": now_iso(), "event": event, **data})


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
    def __init__(self, id: int, username: str, role: Optional[str] = None, is_admin_fallback: Optional[bool] = None):
        self.id = str(id)
        self.username = username
        role_norm = (role or ("admin" if is_admin_fallback else "user") or "user").strip().lower()
        if role_norm not in {"admin", "manager", "user"}:
            role_norm = "user"
        self.role = role_norm

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
    role = None
    try:
        role = row["role"] if "role" in row.keys() else None
    except Exception:
        role = None
    is_admin_fallback = False
    try:
        is_admin_fallback = bool(row["is_admin"]) if "is_admin" in row.keys() else False
    except Exception:
        is_admin_fallback = False
    return User(int(row["id"]), row["username"], role, is_admin_fallback)


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute("SELECT id, username, is_admin, role FROM users WHERE id= ?", (user_id,)).fetchone()
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


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    ensure_dirs()
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
                embedding_json TEXT,
                metadata_json TEXT,
                exif_json TEXT,
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
                totp_secret TEXT,
                totp_enabled INTEGER DEFAULT 0,
                totp_setup_done INTEGER DEFAULT 0,
                totp_remember_days INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        conn.commit()
        # Simple migration for old DBs
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
            conn.execute("UPDATE users SET role='admin' WHERE (role IS NULL OR role='') AND is_admin=1")
            conn.execute("UPDATE users SET role='user' WHERE (role IS NULL OR role='') AND is_admin=0")
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
            conn.commit()
        except Exception:
            pass


@app.before_request
def enforce_login_for_app():
    # Allow static files and login endpoints without auth
    open_endpoints = {"login", "verify_2fa", "static", "setup"}
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


def ai_feature_enabled() -> bool:
    return _get_setting_bool("ai_enabled", AI_ENV_ENABLED_DEFAULT)


def ai_auto_ingest_enabled() -> bool:
    return _get_setting_bool("ai_auto_ingest", AI_ENV_AUTO_INGEST_DEFAULT)


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
            return render_template("setup.html", error="Forkert setup‑token", require_token=True)
        u = (request.form.get("username") or "").strip()
        p = request.form.get("password") or ""
        if not u or not p:
            return render_template("setup.html", error="Udfyld felterne", require_token=require_token)
        try:
            with closing(get_conn()) as conn:
                conn.execute(
                    "INSERT INTO users(username, password_hash, is_admin, created_at) VALUES (?,?,?,?)",
                    (u, generate_password_hash(p), 1, now_iso()),
                )
                conn.commit()
            return render_template("setup.html", ok=True, require_token=require_token)
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
    if meta.get(key) is None or meta.get(key) in (""):
        meta[key] = val


def _piexif_get_first(exif_dict: dict, ifd: str, tag: int) -> Optional[Any]:
    try:
        return exif_dict.get(ifd, {}).get(tag)
    except Exception:
        return None


def extract_exif_via_heif(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        hf = HeifFile(path)
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
    if thumb_path.exists() and not force:
        return thumb_name

    thumb = img.convert("RGB").copy()
    try:
        thumb = ImageOps.exif_transpose(thumb)
    except Exception:
        pass
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(thumb_path, format="JPEG", quality=85, optimize=True)
    return thumb_name


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

    # For video files, we don't attempt EXIF; capture minimal metadata
    if metadata["ext"] in VIDEO_EXTS:
        metadata.setdefault("captured_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"))
        # Keep width/height unknown; no EXIF; no phash
        return metadata

    exif_map: Dict[str, Any] = {}
    thumb_name = None
    checksum = None
    phash = None

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
        if GEOCODE_ENABLE and metadata.get("gps_lat") is not None and metadata.get("gps_lon") is not None:
            lat = float(metadata.get("gps_lat"))
            lon = float(metadata.get("gps_lon"))
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
    mj["ai"] = {"tags": metadata["ai_tags"], "embedding": None, "faces": []}
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
    ensure_dirs()
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


def upsert_photo(meta: Dict[str, Any]) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            INSERT INTO photos (
                rel_path, filename, ext, file_size, width, height, created_fs, modified_fs,
                captured_at, camera_make, camera_model, lens_model, iso, focal_length, f_number,
                exposure_time, gps_lat, gps_lon, gps_name, checksum_sha256, phash, thumb_name,
                favorite, people_count, ai_tags, embedding_json, metadata_json, exif_json,
                imported_at, last_scanned_at
            ) VALUES (
                :rel_path, :filename, :ext, :file_size, :width, :height, :created_fs, :modified_fs,
                :captured_at, :camera_make, :camera_model, :lens_model, :iso, :focal_length, :f_number,
                :exposure_time, :gps_lat, :gps_lon, :gps_name, :checksum_sha256, :phash, :thumb_name,
                COALESCE((SELECT favorite FROM photos WHERE rel_path=:rel_path), 0),
                COALESCE((SELECT people_count FROM photos WHERE rel_path=:rel_path), 0),
                :ai_tags, COALESCE((SELECT embedding_json FROM photos WHERE rel_path=:rel_path), NULL),
                :metadata_json, :exif_json,
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
                last_scanned_at=excluded.last_scanned_at
            """,
            {
                **meta,
                "ai_tags": json.dumps(meta.get("ai_tags", []), ensure_ascii=False),
                "metadata_json": json.dumps(meta.get("metadata_json", {}), ensure_ascii=False, default=str),
                "exif_json": json.dumps(meta.get("exif_json", {}), ensure_ascii=False, default=str),
                "imported_at": now_iso(),
                "last_scanned_at": now_iso(),
            },
        )
        conn.commit()


def iter_photo_files(root: Path) -> Iterable[Tuple[Path, str]]:
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
        yield p, rel


def scan_library(stop_event=None) -> Dict[str, Any]:
    ensure_dirs()
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
    for key in ("ai_tags", "embedding_json", "metadata_json", "exif_json"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
        else:
            d[key] = [] if key == "ai_tags" else None
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
    return d


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


DANISH_SYNONYMS = {
    "strand": {"strand", "beach", "hav", "kyst"},
    "hav": {"hav", "sea", "ocean", "strand", "kyst"},
    "skov": {"skov", "forest", "woods"},
    "bil": {"bil", "car", "auto", "tesla"},
    "solnedgang": {"solnedgang", "sunset", "aftenhimmel"},
    "kamera": {"kamera", "camera"},
    "familie": {"familie", "family", "jul", "middag"},
}


def normalize_query_terms(q: str) -> set[str]:
    q = (q or "").strip().lower()
    if not q:
        return set()
    words = {w for w in q.replace(",", " ").split() if w}
    expanded = set(words)
    for w in list(words):
        for key, group in DANISH_SYNONYMS.items():
            if w in group or w == key:
                expanded |= group
                expanded.add(key)
    return expanded


def matches_search(photo: Dict[str, Any], q: str) -> bool:
    terms = normalize_query_terms(q)
    if not terms:
        return True

    fields = [
        str(photo.get("filename") or "").lower(),
        str(photo.get("rel_path") or "").lower(),
        str(photo.get("camera_make") or "").lower(),
        str(photo.get("camera_model") or "").lower(),
        str(photo.get("lens_model") or "").lower(),
        str(photo.get("gps_name") or "").lower(),
        " ".join((photo.get("ai_tags") or [])).lower(),
        str(photo.get("captured_at") or "").lower(),
        str(photo.get("metadata_json") or "").lower(),
    ]
    blob = " ".join(fields)
    return all(any(term_part in blob for term_part in {t}) or (t in blob) for t in terms)


def query_photos(view: str, sort: str, folder: Optional[str] = None) -> list[Dict[str, Any]]:
    sort_map = {
        "date_desc": "COALESCE(captured_at, modified_fs) DESC",
        "date_asc": "COALESCE(captured_at, modified_fs) ASC",
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
        where.append("(rel_path LIKE ? || '/%')")
        params.append(folder)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM photos {where_sql} ORDER BY {order_by}"

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
        role = getattr(current_user, "role", None)
    except Exception:
        role = None
    return render_template("index.html", user_role=(role or "user"))


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
    ensure_dirs()
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


# --- AI: embeddings + search ---
ai_thread = None
ai_running = False
ai_counts: Dict[str, int] = {"embedded": 0, "failed": 0, "total": 0}
last_ai_result: Optional[Dict[str, Any]] = None


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
        p = PHOTO_DIR / rel
        ai_counts["total"] += 1
        try:
            emb = _ai_embed_image_path(p)
            if emb:
                with closing(get_conn()) as conn:
                    conn.execute("UPDATE photos SET embedding_json=? WHERE id=?", (json.dumps(emb), pid))
                    conn.commit()
                # Derive simple zero-shot tags via CLIP
                try:
                    tags = _classify_labels(emb)
                except Exception:
                    tags = []
                if tags:
                    try:
                        with closing(get_conn()) as conn:
                            cur = conn.execute("SELECT ai_tags FROM photos WHERE id=?", (pid,)).fetchone()
                            prev = []
                            if cur and cur["ai_tags"]:
                                try:
                                    prev = json.loads(cur["ai_tags"]) or []
                                except Exception:
                                    prev = []
                            merged = sorted({*(prev or []), *tags})
                            conn.execute("UPDATE photos SET ai_tags=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), pid))
                            conn.commit()
                    except Exception:
                        pass
                ai_counts["embedded"] += 1
                log_event("ai_embed_ok", rel_path=rel)
            else:
                ai_counts["failed"] += 1
                log_event("ai_embed_fail", rel_path=rel)
        except Exception:
            ai_counts["failed"] += 1
            log_event("ai_embed_fail", rel_path=rel)
    ai_running = False
    last_ai_result = {"ok": True, **ai_counts}
    log_event("ai_embed_done", **ai_counts)
    return last_ai_result


@app.route("/api/ai/ingest", methods=["POST"])
def api_ai_ingest():
    global ai_thread
    if ai_thread and ai_thread.is_alive():
        return jsonify({"ok": False, "error": "AI ingest already running"}), 409
    scan_stop_event.clear()
    def run():
        _embed_missing_photos(stop_event=scan_stop_event)
    ai_thread = threading.Thread(target=run, daemon=True)
    ai_thread.start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/ai/stop", methods=["POST"])
def api_ai_stop():
    if not ai_running:
        return jsonify({"ok": True, "running": False})
    scan_stop_event.set()
    return jsonify({"ok": True, "running": True, "stopping": True})


@app.route("/api/ai/status")
def api_ai_status():
    resp: Dict[str, Any] = {"ok": True, "running": ai_running, **ai_counts}
    if not ai_running and last_ai_result:
        resp["last"] = last_ai_result
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
    return jsonify({"items": items, "count": len(items), "q": q})


@app.route("/api/photos/<int:photo_id>/similar")
def api_similar(photo_id: int):
    limit = max(1, min(200, int(request.args.get("limit", "60"))))
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
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
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/photos/<int:photo_id>/ai-tags", methods=["POST"])
def api_ai_tags(photo_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT id, rel_path, embedding_json, ai_tags FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
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
    ensure_dirs()
    init_db()
    log_event("clear_start")
    thumbs_deleted = 0
    # Delete thumbs safely inside THUMB_DIR only
    for p in THUMB_DIR.glob("*"):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
                thumbs_deleted += 1
        except Exception as e:
            log_event("error", rel_path=str(p), error=str(e))

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

    res = {"ok": True, "removed": {"photos": photos, "faces": faces, "people": people, "thumbs": thumbs_deleted}}
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


@app.route("/api/photos")
def api_photos():
    q = request.args.get("q", "").strip()
    view = request.args.get("view", "library")
    sort = request.args.get("sort", "date_desc")
    folder = request.args.get("folder")

    items = query_photos(view, sort, folder=folder)
    if q:
        items = [p for p in items if matches_search(p, q)]

    return jsonify({
        "items": items,
        "count": len(items),
        "query": q,
        "view": view,
        "sort": sort,
        "folder": folder,
    })


@app.route("/api/photos/<int:photo_id>")
def api_photo_detail(photo_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "item": row_to_public(row)})


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
        total = conn.execute("SELECT COUNT(*) AS c FROM photos").fetchone()["c"]
        favorites = conn.execute("SELECT COUNT(*) AS c FROM photos WHERE favorite = 1").fetchone()["c"]
        places = conn.execute("SELECT COUNT(*) AS c FROM photos WHERE gps_lat IS NOT NULL OR gps_name IS NOT NULL").fetchone()["c"]
        cameras = [r["camera_model"] for r in conn.execute(
            "SELECT DISTINCT camera_model FROM photos WHERE camera_model IS NOT NULL AND camera_model != '' ORDER BY camera_model"
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
    return send_from_directory(THUMB_DIR, thumb_name)


@app.route("/api/original/<path:rel_path>")
def api_original(rel_path: str):
    # Serve original file safely from PHOTO_DIR
    # Prevent path escape
    safe_rel = rel_path.replace("..", "").lstrip("/")
    directory = str(PHOTO_DIR)
    return send_from_directory(directory, safe_rel)


@app.route("/api/viewable/<path:rel_path>")
def api_viewable(rel_path: str):
    # Return a browser/AI-friendly version; convert HEIC→JPEG into CONVERT_DIR when needed
    safe_rel = rel_path.replace("..", "").lstrip("/")
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
        if str(view_path).startswith(str(CONVERT_DIR)):
            rel_conv = str(view_path.relative_to(CONVERT_DIR)).replace("\\", "/")
            return send_from_directory(CONVERT_DIR, rel_conv)
        else:
            return send_from_directory(PHOTO_DIR, safe_rel)
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
                    user = _row_to_user(row)
                    login_user(user)
                    return redirect(url_for("setup_2fa"))
                # Otherwise require 2FA unless trusted cookie is valid
                if _trust_cookie_valid_for(int(row["id"])):
                    user = _row_to_user(row)
                    login_user(user)
                    next_url = request.args.get("next") or url_for("index")
                    return redirect(next_url)
                from flask import session
                session["2fa_user_id"] = int(row["id"])
                return redirect(url_for("verify_2fa", next=request.args.get("next")))
            user = _row_to_user(row)
            login_user(user)
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        return render_template("login.html", error="Forkert brugernavn eller adgangskode")
    return render_template("login.html")


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
        return render_template("2fa_verify.html", error="Ugyldig kode")
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
    issuer = "FjordLens"
    user_label = f"{issuer}:{current_user.username}"
    otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_label, issuer_name=issuer)
    # Render QR as data URL
    img = qrcode.make(otp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
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
                    return render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=row["totp_enabled"], error="Ugyldig kode", remember_days=rdays)
        if action == "disable":
            with closing(get_conn()) as conn:
                conn.execute("UPDATE users SET totp_enabled=0 WHERE id=?", (current_user.id,))
                conn.commit()
            rdays = int(row["totp_remember_days"] or 0) if row else 0
            # Clear trusted-device cookie when disabling 2FA
            resp = make_response(render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=False, ok=True, remember_days=rdays))
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
                return render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=cur_enabled, error="Ugyldig kode", remember_days=cur_days)
            enabled_after = cur_enabled
            with closing(get_conn()) as conn:
                if disable and cur_enabled == 1:
                    conn.execute("UPDATE users SET totp_enabled=0 WHERE id=?", (current_user.id,))
                    enabled_after = 0
                # Always update days to what the user chose
                conn.execute("UPDATE users SET totp_remember_days=? WHERE id=?", (new_days, current_user.id))
                conn.commit()
            resp = make_response(render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=bool(enabled_after), ok=True, remember_days=new_days))
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
            resp = make_response(render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=row["totp_enabled"], ok=True, remember_days=days))
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
            resp = make_response(render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=True, ok=True, remember_days=days))
            if days > 0:
                token, max_age = _make_trust_cookie(int(current_user.id), days)
                if token:
                    resp.set_cookie("fl_trust", token, max_age=max_age, httponly=True, samesite="Lax", path="/")
            return resp
        rdays = int(row["totp_remember_days"] or 0) if row else 0
        return render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=row["totp_enabled"], error="Ugyldig kode", remember_days=rdays)
    rdays = int(row["totp_remember_days"] or 0) if row else 0
    return render_template("2fa_setup.html", qrcode_url=data_url, secret=secret, enabled=row["totp_enabled"], remember_days=rdays) 


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
                    msg = "Bruger oprettet"
                except Exception as e:
                    msg = f"Fejl: {e}"
        elif action == "delete":
            try:
                uid = int(request.form.get("user_id") or 0)
            except Exception:
                uid = 0
            if uid:
                if str(uid) == str(current_user.id):
                    msg = "Du kan ikke slette din egen bruger"
                else:
                    try:
                        with closing(get_conn()) as conn:
                            row = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
                            if not row:
                                msg = "Bruger findes ikke"
                            else:
                                r = (row["role"] or "user").lower()
                                if r == "admin":
                                    c = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND id<>?", (uid,)).fetchone()
                                    if not c or int(c["c"]) <= 0:
                                        msg = "Kan ikke slette den sidste admin"
                                    else:
                                        conn.execute("DELETE FROM users WHERE id=?", (uid,))
                                        conn.commit()
                                        msg = "Bruger slettet"
                                else:
                                    conn.execute("DELETE FROM users WHERE id=?", (uid,))
                                    conn.commit()
                                    msg = "Bruger slettet"
                    except Exception as e:
                        msg = f"Fejl: {e}"
    with closing(get_conn()) as conn:
        users = conn.execute("SELECT id, username, is_admin, role, totp_enabled, created_at FROM users ORDER BY id").fetchall()
    return render_template("admin_users.html", users=users, msg=msg)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
