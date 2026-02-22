import hashlib
import io
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image, ExifTags

APP_PORT = 8080
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "/photos")).resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
THUMB_DIR = DATA_DIR / "thumbs"
DB_PATH = DATA_DIR / "fjordlens.db"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".heif"}
THUMB_SIZE = (600, 600)

app = Flask(__name__)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)


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
            CREATE INDEX IF NOT EXISTS idx_photos_camera ON photos(camera_model);
            CREATE INDEX IF NOT EXISTS idx_photos_favorite ON photos(favorite);
            CREATE INDEX IF NOT EXISTS idx_photos_gps ON photos(gps_lat, gps_lon);

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
            """
        )
        conn.commit()


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
        if isinstance(v, tuple) and len(v) == 2 and v[1] != 0:
            return float(v[0]) / float(v[1])
        if hasattr(v, "numerator") and hasattr(v, "denominator") and getattr(v, "denominator", 0):
            return float(v.numerator) / float(v.denominator)
        return float(v)
    except Exception:
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


def make_thumb(img: Image.Image, rel_path: str, file_mtime: float, file_size: int) -> str:
    key = hashlib.md5(f"{rel_path}|{file_mtime}|{file_size}".encode("utf-8")).hexdigest()
    thumb_name = f"{key}.jpg"
    thumb_path = THUMB_DIR / thumb_name
    if thumb_path.exists():
        return thumb_name

    thumb = img.convert("RGB").copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(thumb_path, format="JPEG", quality=85, optimize=True)
    return thumb_name


def extract_metadata(path: Path, rel_path: str) -> Dict[str, Any]:
    stat = path.stat()
    metadata: Dict[str, Any] = {
        "rel_path": rel_path,
        "filename": path.name,
        "ext": path.suffix.lower(),
        "file_size": stat.st_size,
        "created_fs": datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
        "modified_fs": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }

    exif_map: Dict[str, Any] = {}
    thumb_name = None
    checksum = None
    phash = None

    try:
        with Image.open(path) as img:
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
            thumb_name = make_thumb(img, rel_path, stat.st_mtime, stat.st_size)
            try:
                phash = average_hash(img)
            except Exception:
                phash = None
    except Exception as e:
        # Unsupported or damaged image: still index file-level info
        metadata.setdefault("captured_at", datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"))
        metadata["thumb_error"] = str(e)

    metadata["checksum_sha256"] = sha256_file(path)
    metadata["phash"] = phash
    metadata["thumb_name"] = thumb_name
    metadata["ai_tags"] = build_ai_tags(metadata["filename"], exif_map, metadata.get("gps_lat"), metadata.get("gps_lon"))
    metadata["exif_json"] = exif_map
    metadata["metadata_json"] = {
        "file": {
            "rel_path": rel_path,
            "filename": path.name,
            "ext": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "created_fs": metadata["created_fs"],
            "modified_fs": metadata["modified_fs"],
        },
        "image": {
            "width": metadata.get("width"),
            "height": metadata.get("height"),
        },
        "exif": exif_map,
        "ai": {
            "tags": metadata["ai_tags"],
            "embedding": None,  # reserved for future CLIP/ONNX
            "faces": [],
        },
    }
    return metadata


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
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except Exception:
            rel = p.name
        yield p, rel


def scan_library() -> Dict[str, Any]:
    ensure_dirs()
    init_db()

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
            row["rel_path"]: (row["modified_fs"], row["file_size"])
            for row in conn.execute("SELECT rel_path, modified_fs, file_size FROM photos")
        }

    for path, rel_path in iter_photo_files(PHOTO_DIR):
        scanned += 1
        try:
            stat = path.stat()
            modified_fs = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_size = stat.st_size
            prev = existing.get(rel_path)
            if prev and prev[0] == modified_fs and prev[1] == file_size:
                continue

            meta = extract_metadata(path, rel_path)
            upsert_photo(meta)
            updated += 1
        except Exception as e:
            errors += 1
            if len(error_samples) < 5:
                error_samples.append(f"{rel_path}: {e}")

    return {
        "ok": True,
        "photo_dir": str(PHOTO_DIR),
        "scanned": scanned,
        "updated": updated,
        "errors": errors,
        "error_samples": error_samples,
    }


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
    return d


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


def query_photos(view: str, sort: str) -> list[Dict[str, Any]]:
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
    params = []
    if view == "favorites":
        where.append("favorite = 1")
    elif view == "steder":
        where.append("(gps_lat IS NOT NULL OR gps_name IS NOT NULL)")
    elif view == "kameraer":
        where.append("(camera_model IS NOT NULL AND camera_model != '')")
    elif view == "personer":
        where.append("people_count > 0")  # future face-service
    elif view == "recent":
        where.append("1=1")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM photos {where_sql} ORDER BY {order_by}"

    with closing(get_conn()) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_public(r) for r in rows]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def api_health():
    return jsonify({
        "ok": True,
        "photo_dir": str(PHOTO_DIR),
        "photo_dir_exists": PHOTO_DIR.exists(),
        "data_dir": str(DATA_DIR),
        "db_path": str(DB_PATH),
    })


@app.route("/api/scan", methods=["POST"])
def api_scan():
    result = scan_library()
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/photos")
def api_photos():
    q = request.args.get("q", "").strip()
    view = request.args.get("view", "library")
    sort = request.args.get("sort", "date_desc")

    items = query_photos(view, sort)
    if q:
        items = [p for p in items if matches_search(p, q)]

    return jsonify({
        "items": items,
        "count": len(items),
        "query": q,
        "view": view,
        "sort": sort,
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


@app.route("/api/debug/sample")
def api_debug_sample():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify(row_to_public(row) if row else {"empty": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
