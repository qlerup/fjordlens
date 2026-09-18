import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

try:
    import rawpy
except Exception:
    rawpy = None

app = Flask(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("fjordlens-convert")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/uploads")).resolve()
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "/photos")).resolve()
CONVERSION_WORK_DIR = Path(os.environ.get("CONVERSION_WORK_DIR", str(DATA_DIR / "conversion_work"))).resolve()
ALLOWED_ROOTS = (DATA_DIR, UPLOAD_DIR, PHOTO_DIR)

MOV_CONVERT_DEVICE = str(os.environ.get("MOV_CONVERT_DEVICE", "auto") or "auto").strip().lower()
if MOV_CONVERT_DEVICE not in {"auto", "gpu", "cuda", "nvenc", "cpu"}:
    MOV_CONVERT_DEVICE = "auto"
MOV_CONVERT_PRESET = str(os.environ.get("MOV_CONVERT_PRESET", "veryfast") or "veryfast").strip() or "veryfast"
MOV_CONVERT_GPU_PRESET = str(os.environ.get("MOV_CONVERT_GPU_PRESET", "p4") or "p4").strip() or "p4"
try:
    MOV_CONVERT_CRF = int(os.environ.get("MOV_CONVERT_CRF", "23") or 23)
except Exception:
    MOV_CONVERT_CRF = 23
MOV_CONVERT_CRF = max(18, min(36, MOV_CONVERT_CRF))
MOV_CONVERT_AUDIO_BITRATE = str(os.environ.get("MOV_CONVERT_AUDIO_BITRATE", "128k") or "128k").strip() or "128k"
try:
    MOV_CONVERT_TIMEOUT_SEC = int(os.environ.get("MOV_CONVERT_TIMEOUT_SEC", "7200") or 7200)
except Exception:
    MOV_CONVERT_TIMEOUT_SEC = 7200
MOV_CONVERT_TIMEOUT_SEC = max(60, min(21600, MOV_CONVERT_TIMEOUT_SEC))
try:
    CONVERT_MAX_CONCURRENCY = int(os.environ.get("CONVERT_MAX_CONCURRENCY", "1") or 1)
except Exception:
    CONVERT_MAX_CONCURRENCY = 1
CONVERT_MAX_CONCURRENCY = max(1, min(4, CONVERT_MAX_CONCURRENCY))
CONVERT_SEMAPHORE = threading.BoundedSemaphore(CONVERT_MAX_CONCURRENCY)

_NVENC_CACHE: Optional[bool] = None


def _safe_path(raw: str, *, must_exist: bool = False) -> Path:
    if not raw:
        raise ValueError("Path mangler")
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError("Path skal være absolut")
    resolved = path.resolve(strict=must_exist)
    if not any(resolved == root or resolved.is_relative_to(root) for root in ALLOWED_ROOTS):
        raise ValueError("Path er uden for tilladte mounts")
    return resolved


def _publish_local_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    publish_tmp = dst.with_name(f".{dst.stem}.{secrets.token_hex(6)}.publish{dst.suffix}")
    try:
        shutil.copy2(src, publish_tmp)
        os.replace(publish_tmp, dst)
    finally:
        try:
            publish_tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _convert_heic(src: Path, dst: Path) -> None:
    with Image.open(src) as image:
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        rgb = image.convert("RGB")
        exif_bytes = None
        try:
            exif_bytes = image.info.get("exif") or image.getexif().tobytes()
        except Exception:
            exif_bytes = None
        kwargs = {"format": "JPEG", "quality": 92, "optimize": True}
        if exif_bytes:
            kwargs["exif"] = exif_bytes
        rgb.save(dst, **kwargs)


def _convert_raw(src: Path, dst: Path) -> None:
    last_error = None
    if rawpy is not None:
        try:
            with rawpy.imread(str(src)) as raw:
                rgb = raw.postprocess(
                    use_auto_wb=True,
                    no_auto_bright=True,
                    output_color=rawpy.ColorSpace.sRGB,
                    output_bps=8,
                    gamma=None,
                    half_size=True,
                )
            Image.fromarray(rgb).save(dst, format="JPEG", quality=92, optimize=True)
            return
        except Exception as exc:
            last_error = exc

    exiftool_error = None
    try:
        exiftool = shutil.which("exiftool")
        if exiftool:
            for tag in ("PreviewImage", "JpgFromRaw", "ThumbnailImage"):
                try:
                    with dst.open("wb") as handle:
                        subprocess.run([exiftool, "-b", f"-{tag}", str(src)], check=True, stdout=handle)
                    if dst.exists() and dst.stat().st_size > 0:
                        return
                except Exception as exc:
                    exiftool_error = exc
                    dst.unlink(missing_ok=True)
        else:
            exiftool_error = RuntimeError("exiftool not available")
    except Exception as exc:
        exiftool_error = exc

    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not available")
        subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
             "-frames:v", "1", "-q:v", "2", str(dst)],
            check=True,
            capture_output=True,
            text=True,
            timeout=MOV_CONVERT_TIMEOUT_SEC,
        )
        if not dst.exists() or dst.stat().st_size <= 0:
            raise RuntimeError("ffmpeg produced empty output")
    except Exception as exc:
        raise RuntimeError(
            f"RAW convert failed; rawpy={last_error!r}, exiftool={exiftool_error!r}, ffmpeg={exc!r}"
        ) from exc


def _probe_audio_stream(src: Path, ffmpeg: str) -> Optional[int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index,codec_name", "-of", "json", str(src)],
            check=True, capture_output=True, text=True, timeout=MOV_CONVERT_TIMEOUT_SEC,
        )
        streams = json.loads(probe.stdout or "{}").get("streams", [])
        decoders = subprocess.run(
            [ffmpeg, "-v", "error", "-decoders"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        available = {
            match.group(1)
            for line in decoders.stdout.splitlines()
            if (match := re.match(r"^\s*A[A-Z.]{5}\s+(\S+)", line))
        }
    except Exception as exc:
        logger.warning("Audio probe failed for %s: %s", src, exc)
        return None

    streams.sort(key=lambda stream: str(stream.get("codec_name", "")).lower() != "aac")
    for stream in streams:
        codec = str(stream.get("codec_name", "")).strip().lower()
        try:
            index = int(stream["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if codec and codec in available:
            return index
    return None


def _nvenc_available(ffmpeg: str) -> bool:
    global _NVENC_CACHE
    if MOV_CONVERT_DEVICE == "cpu":
        return False
    if _NVENC_CACHE is not None:
        return _NVENC_CACHE
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=s=640x360:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, timeout=15,
        )
        _NVENC_CACHE = result.returncode == 0
        if not _NVENC_CACHE:
            logger.warning("NVENC unavailable: %s", (result.stderr or result.stdout or "").strip()[-800:])
    except Exception as exc:
        _NVENC_CACHE = False
        logger.warning("NVENC probe failed: %s", exc)
    return bool(_NVENC_CACHE)


def _mov_command(ffmpeg: str, src: Path, dst: Path, audio_index: Optional[int], use_nvenc: bool) -> list[str]:
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
        "-map_metadata", "0", "-map", "0:v:0",
    ]
    if use_nvenc:
        command += [
            "-c:v", "h264_nvenc", "-preset", MOV_CONVERT_GPU_PRESET,
            "-rc", "vbr", "-cq", str(MOV_CONVERT_CRF), "-b:v", "0",
            "-pix_fmt", "yuv420p",
        ]
    else:
        command += [
            "-c:v", "libx264", "-preset", MOV_CONVERT_PRESET,
            "-crf", str(MOV_CONVERT_CRF), "-pix_fmt", "yuv420p",
        ]

    if audio_index is None:
        command.append("-an")
    else:
        command += ["-map", f"0:{audio_index}", "-c:a", "aac", "-b:a", MOV_CONVERT_AUDIO_BITRATE]
    command += ["-movflags", "+faststart+use_metadata_tags", str(dst)]
    return command


def _convert_mov(src: Path, dst: Path) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")
    audio_index = _probe_audio_stream(src, ffmpeg)
    use_nvenc = _nvenc_available(ffmpeg)
    attempts = [True, False] if use_nvenc else [False]
    last_error = None

    for gpu_attempt in attempts:
        dst.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                _mov_command(ffmpeg, src, dst, audio_index, gpu_attempt),
                check=True,
                capture_output=True,
                text=True,
                timeout=MOV_CONVERT_TIMEOUT_SEC,
            )
            if not dst.exists() or dst.stat().st_size <= 0:
                raise RuntimeError("ffmpeg produced empty output")
            return "nvenc" if gpu_attempt else "cpu"
        except Exception as exc:
            last_error = exc
            stderr = getattr(exc, "stderr", "") or ""
            if gpu_attempt:
                logger.warning("NVENC conversion failed for %s; CPU fallback: %s", src, str(stderr or exc)[-800:])
                continue
            raise RuntimeError(f"MOV conversion failed: {stderr or exc}") from exc
    raise RuntimeError(f"MOV conversion failed: {last_error}")


def _convert(kind: str, src: Path, dst: Path) -> dict:
    CONVERSION_WORK_DIR.mkdir(parents=True, exist_ok=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fjordlens-convert-", dir=str(CONVERSION_WORK_DIR)) as work:
        root = Path(work)
        local_src = root / f"source{src.suffix.lower()}"
        local_dst = root / f"output{dst.suffix.lower()}"
        shutil.copy2(src, local_src)

        engine = "cpu"
        if kind == "heic":
            _convert_heic(local_src, local_dst)
        elif kind == "raw":
            _convert_raw(local_src, local_dst)
        elif kind == "mov":
            engine = _convert_mov(local_src, local_dst)
        else:
            raise ValueError("Ukendt konverteringstype")

        if not local_dst.exists() or local_dst.stat().st_size <= 0:
            raise RuntimeError("Konverteringen producerede ingen fil")
        _publish_local_file(local_dst, dst)
        return {"engine": engine, "bytes": dst.stat().st_size}


@app.get("/health")
def health():
    ffmpeg = shutil.which("ffmpeg")
    return jsonify({
        "ok": True,
        "service": "fjordlens-convert",
        "ffmpeg": bool(ffmpeg),
        "nvenc": bool(ffmpeg and _nvenc_available(ffmpeg)),
        "max_concurrency": CONVERT_MAX_CONCURRENCY,
    })


@app.post("/convert")
def convert():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "").strip().lower()
    try:
        src = _safe_path(str(body.get("src") or ""), must_exist=True)
        dst = _safe_path(str(body.get("dst") or ""), must_exist=False)
        if src == dst:
            raise ValueError("Kilde og destination må ikke være den samme")

        with CONVERT_SEMAPHORE:
            result = _convert(kind, src, dst)

        try:
            stat = src.stat()
            os.utime(dst, (stat.st_atime, stat.st_mtime))
        except Exception:
            pass

        return jsonify({"ok": True, "kind": kind, "src": str(src), "dst": str(dst), **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Conversion failed")
        return jsonify({"ok": False, "error": str(exc)}), 500
