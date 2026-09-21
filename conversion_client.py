"""HTTP client for the dedicated FjordLens media conversion worker."""
import os
from pathlib import Path
from typing import Any, Optional

import requests

EXPLICIT_URL = str(os.environ.get("CONVERT_URL", "") or "").strip()
BASE_URL = (EXPLICIT_URL or "http://fjordlens-convert:8010").rstrip("/")


def enabled() -> bool:
    return bool(EXPLICIT_URL)
try:
    DEFAULT_TIMEOUT = float(os.environ.get("CONVERT_SERVICE_TIMEOUT_SEC", "21600") or 21600)
except Exception:
    DEFAULT_TIMEOUT = 21600.0
DEFAULT_TIMEOUT = max(30.0, min(43200.0, DEFAULT_TIMEOUT))


class ConversionServiceError(RuntimeError):
    pass


def _post(path: str, payload: dict[str, Any], *, timeout: Optional[float] = None) -> dict[str, Any]:
    if not BASE_URL:
        raise ConversionServiceError("Conversion service URL is not configured")
    try:
        response = requests.post(
            BASE_URL + path,
            json=payload,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ConversionServiceError(f"Conversion service unavailable: {exc}") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise ConversionServiceError(
            f"Conversion service returned invalid response ({response.status_code})"
        ) from exc
    if response.status_code >= 400 or not data.get("ok"):
        raise ConversionServiceError(str(data.get("error") or f"Conversion service HTTP {response.status_code}"))
    return data


def convert(kind: str, src: Path, dst: Path, **options: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": str(kind), "src": str(src), "dst": str(dst)}
    payload.update(options)
    return _post("/convert", payload)


def video_thumb(
    src: Path,
    dst: Path,
    *,
    seek_seconds: float = 0.5,
    max_edge: int = 600,
    retry_managed: bool = False,
) -> dict[str, Any]:
    return _post(
        "/video-thumb",
        {
            "src": str(src),
            "dst": str(dst),
            "seek_seconds": float(seek_seconds),
            "max_edge": int(max_edge),
            "retry_managed": bool(retry_managed),
        },
        timeout=120,
    )


def hls_item(
    *,
    src: Path,
    output_dir: Path,
    index: int,
    kind: str,
    image_duration: int,
    segment_seconds: int,
) -> dict[str, Any]:
    return _post(
        "/hls/item",
        {
            "src": str(src),
            "output_dir": str(output_dir),
            "index": int(index),
            "kind": str(kind),
            "image_duration": int(image_duration),
            "segment_seconds": int(segment_seconds),
        },
    )


def render_moment(
    *,
    slides: list[dict[str, Any]],
    dst: Path,
    title: str,
    music: Optional[dict[str, Any]],
    width: int,
    height: int,
    fps: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    return _post(
        "/moment/render",
        {
            "slides": slides,
            "dst": str(dst),
            "title": str(title or ""),
            "music": music,
            "width": int(width),
            "height": int(height),
            "fps": int(fps),
            "timeout_seconds": int(timeout_seconds),
        },
        timeout=max(DEFAULT_TIMEOUT, float(timeout_seconds) * max(3, len(slides) + 1)),
    )


def set_concurrency(concurrency: int) -> dict[str, Any]:
    value = max(1, min(4, int(concurrency)))
    return _post("/config/concurrency", {"concurrency": value}, timeout=10)


def health(timeout: float = 5.0) -> dict[str, Any]:
    if not BASE_URL:
        return {"ok": False, "error": "not configured"}
    try:
        response = requests.get(BASE_URL + "/health", timeout=timeout)
        data = response.json()
        return data if isinstance(data, dict) else {"ok": False}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
