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
import threading
from PIL import Image, ExifTags
try:
    # Enable HEIC/HEIF support via pillow-heif if available
    from pillow_heif import register_heif_opener  # type: ignore
    register_heif_opener()
except Exception:
    pass
from urllib.parse import quote

APP_PORT = 8080
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "/photos")).resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
THUMB_DIR = DATA_DIR / "thumbs"
DB_PATH = DATA_DIR / "fjordlens.db"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".heif"}
THUMB_SIZE = (600, 600)


app = Flask(__name__)

# Global scan control
scan_stop_event = threading.Event()


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

    # If critical EXIF is missing (common when HEIC was re-encoded as JPG without metadata),
    # try to enrich from a sibling HEIC/HEIF with same basename — but ONLY if the images
    # are visually the same (verified via perceptual hash distance threshold).
    try:
        if (not metadata.get("gps_lat") and not metadata.get("gps_lon")) or (not metadata.get("lens_model")):
            stem = path.stem
            heif_candidate = None
            for ext in (".heic", ".HEIC", ".heif", ".HEIF"):
                p = path.with_suffix(ext)
                if p.exists():
                    heif_candidate = p
                    break
            if heif_candidate:
                try:
                    # Ensure we have a pHash on current file to compare with candidate
                    cur_phash = phash
                    if cur_phash is None:
                        try:
                            with Image.open(path) as _img_tmp:
                                cur_phash = average_hash(_img_tmp)
                        except Exception:
                            cur_phash = None

                    with Image.open(heif_candidate) as himg:
                        h_exif = parse_exif(himg)
                        cand_phash = None
                        try:
                            cand_phash = average_hash(himg)
                        except Exception:
                            cand_phash = None

                        # Require a reasonable visual match to avoid mis-enrichment
                        allow_enrich = False
                        if cur_phash and cand_phash:
                            dist = _hamdist_hex(cur_phash, cand_phash)
                            allow_enrich = dist <= 6  # threshold can be tuned
                        # If we cannot compare, do NOT enrich to avoid false matches

                        if allow_enrich:
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
                except Exception:
                    pass
    except Exception:
        pass

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
            stat = path.stat()
            modified_fs = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_size = stat.st_size
            prev = existing.get(rel_path)
            if prev:
                unchanged = (prev["modified_fs"] == modified_fs and prev["file_size"] == file_size)
                missing_meta = (prev["lens_model"] in (None, "")) or (prev["gps_lat"] is None and prev["gps_lon"] is None)
                if unchanged and not missing_meta:
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
        "stopped": bool(stop_event.is_set()) if stop_event else False,
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
    # Public URL to original (for viewer)
    rel = d.get("rel_path") or d.get("filename")
    if rel:
        try:
            d["original_url"] = f"/api/original/{quote(rel)}"
        except Exception:
            d["original_url"] = None
    else:
        d["original_url"] = None
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
        where.append("(gps_lat IS NOT NULL OR gps_name IS NOT NULL)")
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



# Start scan in thread
scan_thread = None

@app.route("/api/scan", methods=["POST"])
def api_scan():
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
    scan_stop_event.set()
    return jsonify({"ok": True, "stopped": True})

# Scan status
@app.route("/api/scan/status")
def api_scan_status():
    running = bool(scan_thread and scan_thread.is_alive())
    return jsonify({"ok": True, "running": running})


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


@app.route("/api/debug/sample")
def api_debug_sample():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM photos ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify(row_to_public(row) if row else {"empty": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
