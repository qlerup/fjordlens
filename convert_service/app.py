try:
    from memory_budget import MEMORY, MIB
except ModuleNotFoundError:
    from ai_service.memory_budget import MEMORY, MIB
import ctypes
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
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

import moment_cinema
import moment_music

app = Flask(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("fjordlens-convert")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")).resolve()
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/uploads")).resolve()
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "/photos")).resolve()
THUMB_DIR = Path(os.environ.get("THUMB_DIR", "/thumbs")).resolve()
CONVERSION_WORK_DIR = Path(os.environ.get("CONVERSION_WORK_DIR", str(DATA_DIR / "conversion_work"))).resolve()
ALLOWED_ROOTS = (DATA_DIR, UPLOAD_DIR, PHOTO_DIR, THUMB_DIR)

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


class _DynamicConversionLimiter:
    """FIFO-ish slot limiter whose capacity can be changed live (1..4)."""

    def __init__(self, limit: int):
        self._condition = threading.Condition()
        self._limit = max(1, min(4, int(limit)))
        self._active = 0

    def set_limit(self, limit: int) -> int:
        value = max(1, min(4, int(limit)))
        with self._condition:
            self._limit = value
            self._condition.notify_all()
        return value

    def snapshot(self) -> dict:
        with self._condition:
            return {"limit": self._limit, "active": self._active}

    @contextmanager
    def slot(self):
        with self._condition:
            while self._active >= self._limit:
                self._condition.wait()
            self._active += 1
        try:
            # RAM pressure delays a queued conversion; it is not a file error.
            with MEMORY.slot(512*MIB, timeout=None):
                yield
        finally:
            with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify_all()


CONVERT_LIMITER = _DynamicConversionLimiter(CONVERT_MAX_CONCURRENCY)

_NVENC_CACHE: Optional[bool] = None
_NVDEC_CACHE: Optional[bool] = None


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


def _normalize_video_device(value: Optional[str] = None) -> str:
    raw = str(value or MOV_CONVERT_DEVICE or "auto").strip().lower()
    if raw in {"gpu", "cuda", "nvenc"}:
        return "gpu"
    if raw == "cpu":
        return "cpu"
    return "auto"


def _nvenc_available(ffmpeg: str, device_mode: Optional[str] = None) -> bool:
    global _NVENC_CACHE
    if _normalize_video_device(device_mode) == "cpu":
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


def _nvdec_available(ffmpeg: str, device_mode: Optional[str] = None) -> bool:
    global _NVDEC_CACHE
    if _normalize_video_device(device_mode) == "cpu":
        return False
    if _NVDEC_CACHE is not None:
        return _NVDEC_CACHE
    try:
        hwaccels = subprocess.run(
            [ffmpeg, "-hide_banner", "-hwaccels"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        has_cuda = hwaccels.returncode == 0 and any(
            line.strip().lower() == "cuda"
            for line in (hwaccels.stdout or "").splitlines()
        )
        if not has_cuda:
            _NVDEC_CACHE = False
            logger.warning("NVDEC unavailable: ffmpeg does not expose CUDA hwaccel")
            return False
        ctypes.CDLL("libnvcuvid.so.1")
        _NVDEC_CACHE = True
    except Exception as exc:
        _NVDEC_CACHE = False
        logger.warning("NVDEC probe failed: %s", exc)
    return bool(_NVDEC_CACHE)


def _mov_command(
    ffmpeg: str,
    src: Path,
    dst: Path,
    audio_index: Optional[int],
    use_nvenc: bool,
    use_nvdec: bool = False,
) -> list[str]:
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if use_nvdec:
        command += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    command += [
        "-i", str(src),
        "-map_metadata", "0", "-map", "0:v:0",
    ]
    if use_nvenc:
        command += [
            "-c:v", "h264_nvenc", "-preset", MOV_CONVERT_GPU_PRESET,
            "-rc", "vbr", "-cq", str(MOV_CONVERT_CRF), "-b:v", "0",
        ]
        # With NVDEC the decoded frames stay in CUDA memory. Avoid forcing a
        # software pixel format because that can trigger an unnecessary download.
        if not use_nvdec:
            command += ["-pix_fmt", "yuv420p"]
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


def _convert_mov(src: Path, dst: Path, device_mode: Optional[str] = None) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")

    audio_index = _probe_audio_stream(src, ffmpeg)
    device = _normalize_video_device(device_mode)
    nvenc = _nvenc_available(ffmpeg, device)
    nvdec = nvenc and _nvdec_available(ffmpeg, device)

    attempts: list[tuple[bool, bool, str]] = []
    if nvdec:
        attempts.append((True, True, "nvdec+nvenc"))
    if nvenc:
        attempts.append((True, False, "nvenc"))
    attempts.append((False, False, "cpu"))

    last_error = None
    for use_nvenc, use_nvdec, engine in attempts:
        dst.unlink(missing_ok=True)
        try:
            subprocess.run(
                _mov_command(
                    ffmpeg,
                    src,
                    dst,
                    audio_index,
                    use_nvenc=use_nvenc,
                    use_nvdec=use_nvdec,
                ),
                check=True,
                capture_output=True,
                text=True,
                timeout=MOV_CONVERT_TIMEOUT_SEC,
            )
            if not dst.exists() or dst.stat().st_size <= 0:
                raise RuntimeError("ffmpeg produced empty output")
            return engine
        except Exception as exc:
            last_error = exc
            stderr = getattr(exc, "stderr", "") or ""
            detail = str(stderr or exc)[-800:]
            if use_nvdec:
                logger.warning(
                    "NVDEC+NVENC conversion failed for %s; retrying CPU decode + NVENC: %s",
                    src,
                    detail,
                )
                continue
            if use_nvenc:
                logger.warning(
                    "NVENC conversion failed for %s; retrying full CPU conversion: %s",
                    src,
                    detail,
                )
                continue
            raise RuntimeError(f"MOV conversion failed: {stderr or exc}") from exc

    raise RuntimeError(f"MOV conversion failed: {last_error}")



def _to_rgb_with_background(image: Image.Image, background_color: str = "black") -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, background_color)
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _normalize_jpeg(
    src: Path,
    dst: Path,
    max_edge: int = 4096,
    quality: int = 90,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    background_color: str = "black",
) -> None:
    with Image.open(src) as image:
        try:
            image.seek(0)
        except Exception:
            pass
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        rgb = _to_rgb_with_background(image, background_color)
        if max_width and max_height:
            bounds = (max(1, int(max_width)), max(1, int(max_height)))
        else:
            bounds = (max_edge, max_edge)
        rgb.thumbnail(bounds, Image.Resampling.LANCZOS)
        rgb.save(dst, format="JPEG", quality=quality, optimize=True, progressive=False)


def _image_thumb(src: Path, dst: Path, width: int = 600, height: int = 600) -> None:
    source = src
    temporary_raw: Optional[Path] = None
    if src.suffix.lower() in {".dng", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".raf", ".orf", ".srw", ".pef"}:
        temporary_raw = dst.with_name(f".{dst.stem}.raw-source.jpg")
        _convert_raw(src, temporary_raw)
        source = temporary_raw
    try:
        with Image.open(source) as image:
            try:
                image.seek(0)
            except Exception:
                pass
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            rgb = _to_rgb_with_background(image, "black")
            rgb.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
            rgb.save(dst, format="JPEG", quality=85, optimize=True)
    finally:
        if temporary_raw is not None:
            temporary_raw.unlink(missing_ok=True)


def _video_encoder_args(ffmpeg: str, *, quality: int = 23, cpu_preset: str = "veryfast") -> tuple[list[str], str]:
    if _nvenc_available(ffmpeg):
        return (
            [
                "-c:v", "h264_nvenc",
                "-preset", MOV_CONVERT_GPU_PRESET,
                "-rc", "vbr",
                "-cq", str(max(18, min(36, quality))),
                "-b:v", "0",
                "-pix_fmt", "yuv420p",
            ],
            "nvenc",
        )
    return (
        [
            "-c:v", "libx264",
            "-preset", cpu_preset,
            "-crf", str(max(18, min(36, quality))),
            "-pix_fmt", "yuv420p",
        ],
        "cpu",
    )


def _prepare_photoframe_video(src: Path, dst: Path, *, quality: int = 24, cpu_preset: str = "veryfast") -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")
    video_args, engine = _video_encoder_args(ffmpeg, quality=quality, cpu_preset=cpu_preset)
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-map", "0:v:0",
        "-map", "0:a?",
        *video_args,
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=MOV_CONVERT_TIMEOUT_SEC)
    except subprocess.CalledProcessError as exc:
        if engine != "nvenc":
            raise
        logger.warning("PhotoFrame NVENC failed; retrying on CPU: %s", (exc.stderr or "")[-800:])
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", cpu_preset,
            "-crf", str(max(18, min(36, quality))),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(dst),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=MOV_CONVERT_TIMEOUT_SEC)
        engine = "cpu"
    if not dst.exists() or dst.stat().st_size <= 0:
        raise RuntimeError("ffmpeg produced empty output")
    return engine


def _extract_video_thumb(
    src: Path,
    dst: Path,
    seek_seconds: float = 0.5,
    max_edge: int = 600,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")
    seek = max(0.0, min(60.0, float(seek_seconds)))
    commands = [
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(seek), "-i", str(src), "-frames:v", "1", str(dst)],
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-ss", str(seek), "-frames:v", "1", str(dst)],
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-frames:v", "1", str(dst)],
    ]
    last_error = None
    for command in commands:
        dst.unlink(missing_ok=True)
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
            if dst.exists() and dst.stat().st_size > 0:
                if max_edge > 0:
                    with Image.open(dst) as image:
                        frame = image.convert("RGB")
                        frame.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                        temp = dst.with_name(f".{dst.name}.thumbtmp")
                        frame.save(temp, format="JPEG", quality=85, optimize=True)
                        os.replace(temp, dst)
                return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not extract video thumbnail: {last_error}")


def _video_has_audio(src: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index",
             "-of", "csv=p=0", str(src)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return result.returncode == 0 and bool((result.stdout or "").strip())
    except Exception:
        return False


def _hls_item(
    src: Path,
    output_dir: Path,
    *,
    index: int,
    kind: str,
    image_duration: int,
    segment_seconds: int,
) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")

    output_dir.mkdir(parents=True, exist_ok=True)
    child = output_dir / f"item_{index:05d}.m3u8"
    seg_pattern = output_dir / f"item_{index:05d}_%05d.ts"
    filter_chain = (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        "setsar=1,fps=30,format=yuv420p"
    )
    video_args, engine = _video_encoder_args(ffmpeg, quality=23, cpu_preset="veryfast")
    gop = max(2, min(8, int(segment_seconds))) * 30
    common_codec = [
        *video_args,
        "-profile:v", "high",
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
    ]

    base = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if kind == "video":
        base += ["-fflags", "+genpts", "-i", str(src)]
        if _video_has_audio(src):
            base += [
                "-map", "0:v:0", "-map", "0:a:0",
                "-vf", filter_chain,
                "-af", "aresample=async=1:first_pts=0",
                *common_codec,
            ]
        else:
            base += [
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", filter_chain,
                *common_codec,
                "-shortest",
            ]
    else:
        duration = max(2, min(30, int(image_duration)))
        base += [
            "-loop", "1", "-framerate", "1", "-i", str(src),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(duration),
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", filter_chain,
            *common_codec,
            "-shortest",
        ]

    base += [
        "-force_key_frames", f"expr:gte(t,n_forced*{segment_seconds})",
        "-f", "hls",
        "-hls_time", str(segment_seconds),
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments+temp_file",
        "-hls_segment_type", "mpegts",
        "-hls_segment_filename", str(seg_pattern),
        str(child),
    ]

    try:
        subprocess.run(base, check=True, capture_output=True, text=True, timeout=MOV_CONVERT_TIMEOUT_SEC)
    except subprocess.CalledProcessError as exc:
        if engine != "nvenc":
            raise RuntimeError((exc.stderr or "")[-2500:]) from exc
        logger.warning("HLS NVENC failed; retrying CPU: %s", (exc.stderr or "")[-800:])
        cpu = [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        ]
        cpu_cmd = []
        for token in base:
            cpu_cmd.append(token)
        # Rebuild cleanly rather than mutating encoder args embedded in the command.
        base2 = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        if kind == "video":
            base2 += ["-fflags", "+genpts", "-i", str(src)]
            if _video_has_audio(src):
                base2 += ["-map", "0:v:0", "-map", "0:a:0", "-vf", filter_chain,
                          "-af", "aresample=async=1:first_pts=0", *cpu]
            else:
                base2 += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                          "-map", "0:v:0", "-map", "1:a:0", "-vf", filter_chain, *cpu, "-shortest"]
        else:
            duration = max(2, min(30, int(image_duration)))
            base2 += ["-loop", "1", "-framerate", "1", "-i", str(src),
                      "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                      "-t", str(duration), "-map", "0:v:0", "-map", "1:a:0",
                      "-vf", filter_chain, *cpu, "-shortest"]
        base2 += [
            "-force_key_frames", f"expr:gte(t,n_forced*{segment_seconds})",
            "-f", "hls", "-hls_time", str(segment_seconds), "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments+temp_file", "-hls_segment_type", "mpegts",
            "-hls_segment_filename", str(seg_pattern), str(child),
        ]
        subprocess.run(base2, check=True, capture_output=True, text=True, timeout=MOV_CONVERT_TIMEOUT_SEC)
        engine = "cpu"

    if not child.exists() or child.stat().st_size <= 0:
        raise RuntimeError("HLS playlist was not created")
    return {"playlist": str(child), "engine": engine}


def _render_moment(
    slides: list[dict],
    dst: Path,
    *,
    title: str,
    music: Optional[dict],
    width: int,
    height: int,
    fps: int,
    timeout_seconds: int,
) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")
    if not slides:
        raise ValueError("Moment has no slides")

    CONVERSION_WORK_DIR.mkdir(parents=True, exist_ok=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fjordlens-moment-", dir=str(CONVERSION_WORK_DIR)) as work:
        work_dir = Path(work)
        segments: list[Path] = []
        for index, slide in enumerate(slides):
            item = slide.get("item") or {}
            src_raw = str(slide.get("src") or "")
            second_raw = str(slide.get("second_src") or "")
            src = _safe_path(src_raw, must_exist=True) if src_raw else None
            second_src = _safe_path(second_raw, must_exist=True) if second_raw else None
            seg = work_dir / f"seg_{index:04d}.mp4"
            if moment_cinema.render_segment(
                ffmpeg,
                item,
                src,
                seg,
                size=(width, height),
                fps=fps,
                timeout=timeout_seconds,
                second_src=second_src,
            ):
                segments.append(seg)

        if not segments:
            raise RuntimeError("No moment segments were rendered")

        playlist = work_dir / "concat.txt"
        playlist.write_text("\n".join(f"file '{p.as_posix()}'" for p in segments), encoding="utf-8")
        combined = work_dir / "combined.mp4"
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(playlist),
                "-c:v", "copy", "-an", "-movflags", "+faststart", "-f", "mp4",
                str(combined),
            ],
            check=True,
            capture_output=True,
            timeout=max(120, timeout_seconds * 3),
        )
        if not combined.exists() or combined.stat().st_size <= 0:
            raise RuntimeError("Moment concat produced empty output")

        final_source = combined
        if music:
            scored = work_dir / "scored.mp4"
            moment_music.add_to_video(
                ffmpeg,
                combined,
                scored,
                work_dir,
                music,
                max(1800, timeout_seconds * 3),
            )
            final_source = scored

        _publish_local_file(final_source, dst)
        return {"bytes": dst.stat().st_size, "engine": "worker"}


def _convert(kind: str, src: Path, dst: Path, options: Optional[dict] = None) -> dict:
    options = options or {}
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
            engine = _convert_mov(local_src, local_dst, device_mode=options.get("device"))
        elif kind == "jpeg_normalize":
            max_width_raw = options.get("max_width")
            max_height_raw = options.get("max_height")
            _normalize_jpeg(
                local_src,
                local_dst,
                max_edge=max(512, min(8192, int(options.get("max_edge", 4096) or 4096))),
                quality=max(60, min(100, int(options.get("quality", 90) or 90))),
                max_width=(max(1, min(8192, int(max_width_raw))) if max_width_raw else None),
                max_height=(max(1, min(8192, int(max_height_raw))) if max_height_raw else None),
                background_color=(
                    "white"
                    if str(options.get("background") or "black").strip().lower() == "white"
                    else "black"
                ),
            )
        elif kind == "image_thumb":
            _image_thumb(
                local_src,
                local_dst,
                width=max(64, min(2048, int(options.get("width", 600) or 600))),
                height=max(64, min(2048, int(options.get("height", 600) or 600))),
            )
        elif kind == "photoframe_video":
            engine = _prepare_photoframe_video(
                local_src,
                local_dst,
                quality=max(18, min(36, int(options.get("quality", 24) or 24))),
                cpu_preset=str(options.get("cpu_preset") or "veryfast"),
            )
        else:
            raise ValueError("Ukendt konverteringstype")

        if not local_dst.exists() or local_dst.stat().st_size <= 0:
            raise RuntimeError("Konverteringen producerede ingen fil")
        _publish_local_file(local_dst, dst)
        return {"engine": engine, "bytes": dst.stat().st_size}


@app.post("/video-thumb")
def video_thumb():
    body = request.get_json(silent=True) or {}
    try:
        src = _safe_path(str(body.get("src") or ""), must_exist=True)
        dst = _safe_path(str(body.get("dst") or ""), must_exist=False)
        seek = float(body.get("seek_seconds", 0.5) or 0.5)
        max_edge = max(0, min(4096, int(body.get("max_edge", 600) or 0)))
        dst.parent.mkdir(parents=True, exist_ok=True)
        with CONVERT_LIMITER.slot():
            _extract_video_thumb(src, dst, seek, max_edge=max_edge)
        return jsonify({"ok": True, "dst": str(dst), "bytes": dst.stat().st_size})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Video thumbnail failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/hls/item")
def hls_item():
    body = request.get_json(silent=True) or {}
    try:
        src = _safe_path(str(body.get("src") or ""), must_exist=True)
        output_dir = _safe_path(str(body.get("output_dir") or ""), must_exist=False)
        index = max(0, int(body.get("index", 0) or 0))
        kind = str(body.get("kind") or "video").strip().lower()
        if kind not in {"video", "image"}:
            raise ValueError("Ugyldig HLS-type")
        image_duration = max(2, min(30, int(body.get("image_duration", 8) or 8)))
        segment_seconds = max(2, min(8, int(body.get("segment_seconds", 4) or 4)))
        with CONVERT_LIMITER.slot():
            result = _hls_item(
                src,
                output_dir,
                index=index,
                kind=kind,
                image_duration=image_duration,
                segment_seconds=segment_seconds,
            )
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("HLS item conversion failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/moment/render")
def moment_render():
    body = request.get_json(silent=True) or {}
    try:
        slides = body.get("slides") or []
        if not isinstance(slides, list):
            raise ValueError("slides skal være en liste")
        dst = _safe_path(str(body.get("dst") or ""), must_exist=False)
        width = max(320, min(3840, int(body.get("width", 1920) or 1920)))
        height = max(240, min(2160, int(body.get("height", 1080) or 1080)))
        fps = max(10, min(60, int(body.get("fps", 25) or 25)))
        timeout_seconds = max(30, min(7200, int(body.get("timeout_seconds", 120) or 120)))
        music = body.get("music")
        if music is not None and not isinstance(music, dict):
            raise ValueError("music skal være et objekt")
        with CONVERT_LIMITER.slot():
            result = _render_moment(
                slides,
                dst,
                title=str(body.get("title") or ""),
                music=music,
                width=width,
                height=height,
                fps=fps,
                timeout_seconds=timeout_seconds,
            )
        return jsonify({"ok": True, "dst": str(dst), **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Moment render failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/health")
def health():
    ffmpeg = shutil.which("ffmpeg")
    return jsonify({
        "ok": True,
        "service": "fjordlens-convert",
        "ffmpeg": bool(ffmpeg),
        "nvenc": bool(ffmpeg and _nvenc_available(ffmpeg, "auto")),
        "nvdec": bool(ffmpeg and _nvdec_available(ffmpeg, "auto")),
        "default_device": _normalize_video_device(),
        "max_concurrency": CONVERT_LIMITER.snapshot()["limit"],
        "active_conversions": CONVERT_LIMITER.snapshot()["active"],
    })


@app.post("/config/concurrency")
def configure_concurrency():
    body = request.get_json(silent=True) or {}
    try:
        value = int(body.get("concurrency"))
    except Exception:
        return jsonify({"ok": False, "error": "concurrency skal være et tal fra 1 til 4"}), 400
    if value < 1 or value > 4:
        return jsonify({"ok": False, "error": "concurrency skal være mellem 1 og 4"}), 400
    applied = CONVERT_LIMITER.set_limit(value)
    state = CONVERT_LIMITER.snapshot()
    return jsonify({"ok": True, "max_concurrency": applied, "active_conversions": state["active"]})


@app.post("/convert")
def convert():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "").strip().lower()
    try:
        src = _safe_path(str(body.get("src") or ""), must_exist=True)
        dst = _safe_path(str(body.get("dst") or ""), must_exist=False)
        if src == dst:
            raise ValueError("Kilde og destination må ikke være den samme")

        with CONVERT_LIMITER.slot():
            result = _convert(kind, src, dst, body)

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
