from __future__ import annotations

import hashlib
import html as html_lib
import json
import os
import shutil
import subprocess
import threading
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file
from flask_login import login_required

import app as core
import cast_airplay as cast_core

bp = Blueprint("airplay_stream", __name__)

AIRPLAY_IMAGE_DURATION = max(2, min(30, int(os.getenv("AIRPLAY_IMAGE_DURATION_SECONDS", "8") or 8)))
AIRPLAY_MAX_ITEMS = max(1, min(1500, int(os.getenv("AIRPLAY_MAX_ITEMS", "400") or 400)))
AIRPLAY_SEGMENT_TIMEOUT = max(30, min(1800, int(os.getenv("AIRPLAY_SEGMENT_TIMEOUT_SECONDS", "600") or 600)))
AIRPLAY_CONCAT_TIMEOUT = max(30, min(600, int(os.getenv("AIRPLAY_CONCAT_TIMEOUT_SECONDS", "180") or 180)))

_render_guard = threading.RLock()
_render_threads: Dict[str, threading.Thread] = {}


def _token_key(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()[:32]


def _airplay_root() -> Path:
    path = Path(core.DATA_DIR) / "cast_cache" / "airplay"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_dir(token: str) -> Path:
    return _airplay_root() / _token_key(token)


def _output_path(token: str) -> Path:
    return _job_dir(token) / "slideshow.mp4"


def _status_path(token: str) -> Path:
    return _job_dir(token) / "status.json"


def _render_marker_path(token: str) -> Path:
    return _job_dir(token) / "rendering.lock"


def _write_status(token: str, payload: Dict[str, Any]) -> None:
    job = _job_dir(token)
    job.mkdir(parents=True, exist_ok=True)
    data = {
        "state": str(payload.get("state") or "preparing"),
        "done": int(payload.get("done") or 0),
        "total": int(payload.get("total") or 0),
        "error": str(payload.get("error") or ""),
        "updated_at": time.time(),
    }
    tmp = job / ".status.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, _status_path(token))


def _read_status(token: str) -> Dict[str, Any]:
    output = _output_path(token)
    if output.exists() and output.stat().st_size > 0:
        return {"state": "ready", "done": 1, "total": 1, "error": ""}
    try:
        data = json.loads(_status_path(token).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"state": "idle", "done": 0, "total": 0, "error": ""}


def _run_ffmpeg(cmd: List[str], timeout: int) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "ffmpeg fejlede").strip()
        if len(detail) > 2500:
            detail = detail[-2500:]
        raise RuntimeError(detail)


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg er ikke installeret i FjordLens-containeren.")
    return path


def _ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


def _video_has_audio(path: Path) -> bool:
    probe = _ffprobe()
    if not probe:
        # FjordLens normally has ffprobe together with ffmpeg. If it is missing,
        # prefer the optional audio map path and let ffmpeg handle the source.
        return False
    try:
        proc = subprocess.run(
            [probe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
        return proc.returncode == 0 and bool((proc.stdout or "").strip())
    except Exception:
        return False


def _video_filter() -> str:
    return (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        "setsar=1,fps=30,format=yuv420p"
    )


def _common_video_args() -> List[str]:
    return [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-profile:v", "high",
        "-level", "4.0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
    ]


def _render_image_segment(item: Dict[str, Any], destination: Path, duration: int) -> None:
    src = cast_core._image_cache_path(item)
    cmd = [
        _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", "1", "-i", str(src),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", str(duration),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", _video_filter(),
        *_common_video_args(),
        "-shortest",
        str(destination),
    ]
    _run_ffmpeg(cmd, AIRPLAY_SEGMENT_TIMEOUT)


def _render_video_segment(item: Dict[str, Any], destination: Path) -> None:
    src = cast_core._disk_path(item)
    if src is None:
        raise FileNotFoundError("En video i valget findes ikke længere.")

    cmd: List[str] = [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    has_audio = _video_has_audio(src)
    if has_audio:
        cmd += [
            "-map", "0:v:0", "-map", "0:a:0",
            "-vf", _video_filter(),
            "-af", "aresample=async=1:first_pts=0,apad",
            *_common_video_args(),
            "-shortest",
            str(destination),
        ]
    else:
        cmd += [
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", _video_filter(),
            *_common_video_args(),
            "-shortest",
            str(destination),
        ]
    _run_ffmpeg(cmd, AIRPLAY_SEGMENT_TIMEOUT)


def _render_airplay_video(token: str) -> None:
    job = _job_dir(token)
    work = job / "work"
    output = _output_path(token)
    tmp_output = job / "slideshow.tmp.mp4"

    try:
        session = cast_core._get_session(token)
        if not session:
            raise RuntimeError("AirPlay-sessionen er udløbet.")
        items = [item for item in (session.get("items") or []) if isinstance(item, dict)]
        if not items:
            raise RuntimeError("Der er ingen billeder eller videoer i AirPlay-sessionen.")
        if len(items) > AIRPLAY_MAX_ITEMS:
            raise RuntimeError(f"Der er valgt {len(items)} medier. AirPlay-slideshow understøtter højst {AIRPLAY_MAX_ITEMS} ad gangen.")

        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)
        try:
            if tmp_output.exists():
                tmp_output.unlink()
        except Exception:
            pass

        segments: List[Path] = []
        total = len(items)
        _write_status(token, {"state": "preparing", "done": 0, "total": total})

        for index, item in enumerate(items):
            segment = work / f"segment_{index:05d}.mp4"
            kind = str(item.get("kind") or "image").lower()
            if kind == "video":
                _render_video_segment(item, segment)
            else:
                _render_image_segment(item, segment, int(session.get("image_duration") or AIRPLAY_IMAGE_DURATION))
            if not segment.exists() or segment.stat().st_size <= 0:
                raise RuntimeError("Et AirPlay-segment kunne ikke klargøres.")
            segments.append(segment)
            _write_status(token, {"state": "preparing", "done": index + 1, "total": total})

        concat_file = work / "concat.txt"
        concat_file.write_text("".join(f"file '{segment.name}'\n" for segment in segments), encoding="utf-8")
        _run_ffmpeg(
            [
                _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c", "copy", "-movflags", "+faststart", str(tmp_output),
            ],
            AIRPLAY_CONCAT_TIMEOUT,
        )
        if not tmp_output.exists() or tmp_output.stat().st_size <= 0:
            raise RuntimeError("Det færdige AirPlay-slideshow kunne ikke oprettes.")
        os.replace(tmp_output, output)
        _write_status(token, {"state": "ready", "done": total, "total": total})
    except Exception as exc:
        _write_status(token, {"state": "error", "error": str(exc), "done": 0, "total": 0})
    finally:
        shutil.rmtree(work, ignore_errors=True)
        try:
            if tmp_output.exists():
                tmp_output.unlink()
        except Exception:
            pass
        try:
            _render_marker_path(token).unlink()
        except Exception:
            pass
        with _render_guard:
            _render_threads.pop(_token_key(token), None)


def _claim_render(token: str) -> bool:
    marker = _render_marker_path(token)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        if marker.exists() and (time.time() - marker.stat().st_mtime) > max(1800, AIRPLAY_SEGMENT_TIMEOUT * 2):
            marker.unlink()
    except Exception:
        pass
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    try:
        os.write(fd, f"{os.getpid()} {time.time()}\n".encode("ascii", "ignore"))
    finally:
        os.close(fd)
    return True


def _start_render(token: str) -> Dict[str, Any]:
    state = _read_status(token)
    if state.get("state") == "ready":
        return state

    key = _token_key(token)
    with _render_guard:
        running = _render_threads.get(key)
        if running is not None and running.is_alive():
            return _read_status(token)
        if not _claim_render(token):
            return _read_status(token)
        thread = threading.Thread(target=_render_airplay_video, args=(token,), daemon=True, name=f"fjordlens-airplay-{key[:8]}")
        _render_threads[key] = thread
        _write_status(token, {"state": "preparing", "done": 0, "total": 0})
        thread.start()
    return _read_status(token)


def _status_payload(token: str) -> Dict[str, Any]:
    state = _read_status(token)
    return {
        "ok": state.get("state") != "error",
        "state": str(state.get("state") or "idle"),
        "ready": state.get("state") == "ready",
        "done": int(state.get("done") or 0),
        "total": int(state.get("total") or 0),
        "error": str(state.get("error") or ""),
        "play_url": f"/airplay/play/{quote(token, safe='')}",
    }


@bp.post("/api/airplay/<token>/prepare")
@login_required
def prepare_airplay(token: str):
    if not cast_core._get_session(token):
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    state = _read_status(token)
    if state.get("state") == "error":
        try:
            _status_path(token).unlink()
        except Exception:
            pass
    _start_render(token)
    return jsonify(_status_payload(token))


@bp.get("/api/airplay/<token>/status")
@login_required
def airplay_status(token: str):
    if not cast_core._get_session(token):
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    return jsonify(_status_payload(token))


@bp.get("/airplay/media/<token>.mp4")
def airplay_media(token: str):
    if not cast_core._get_session(token):
        return Response("AirPlay-sessionen er udløbet.", status=404, mimetype="text/plain")
    output = _output_path(token)
    if not output.exists() or output.stat().st_size <= 0:
        return Response("AirPlay-slideshowet er ikke klar endnu.", status=425, mimetype="text/plain")
    response = send_file(output, mimetype="video/mp4", conditional=True, max_age=3600)
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.get("/airplay/play/<token>")
def airplay_player(token: str):
    session = cast_core._get_session(token)
    if not session:
        return Response("AirPlay-sessionen er udløbet.", status=404, mimetype="text/plain")
    output = _output_path(token)
    if not output.exists() or output.stat().st_size <= 0:
        return Response("AirPlay-slideshowet er ikke klar endnu.", status=425, mimetype="text/plain")

    title = str(session.get("title") or "FjordLens")
    safe_title = html_lib.escape(title, quote=True)
    media_url = f"/airplay/media/{quote(token, safe='')}.mp4"
    html = f"""<!doctype html>
<html lang=\"da\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
<title>{safe_title}</title>
<style>
html,body{{margin:0;height:100%;background:#050b0e;color:#eef7f7;font-family:system-ui,-apple-system,sans-serif}}
body{{display:flex;flex-direction:column;height:100dvh}}
header{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.12);background:#07151a}}
header strong{{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
button{{appearance:none;border:1px solid rgba(255,255,255,.18);border-radius:999px;background:#10252d;color:#eef7f7;padding:10px 15px;font:inherit;font-weight:700}}
#airplay{{background:#0f8d86;border-color:#20bcb0}}
#stage{{position:relative;flex:1;min-height:0;background:#000;display:grid;place-items:center}}
video{{width:100%;height:100%;object-fit:contain;background:#000}}
#hint{{position:absolute;left:12px;right:12px;bottom:12px;padding:10px 12px;border-radius:12px;background:rgba(5,17,22,.82);border:1px solid rgba(255,255,255,.14);font-size:12px;line-height:1.45;color:#d7e5e8;pointer-events:none}}
.hidden{{display:none!important}}
</style></head><body>
<header><strong>{safe_title}</strong><button id=\"airplay\">AirPlay</button></header>
<div id=\"stage\"><video id=\"player\" controls playsinline loop preload=\"metadata\" x-webkit-airplay=\"allow\" src=\"{media_url}\"></video><div id=\"hint\">Tryk AirPlay og vælg dit Apple TV eller en AirPlay-kompatibel skærm. Billeder og videoer sendes som ét rigtigt AirPlay-slideshow — uden Skærmdublering.</div></div>
<script>
(() => {{
  const player = document.getElementById('player');
  const airplay = document.getElementById('airplay');
  const hint = document.getElementById('hint');
  const canPick = typeof player.webkitShowPlaybackTargetPicker === 'function';
  if (!canPick) {{ airplay.classList.add('hidden'); hint.textContent = 'Åbn denne side i Safari på iPhone/iPad for at vælge en AirPlay-enhed.'; }}
  airplay.addEventListener('click', () => {{
    try {{ player.webkitShowPlaybackTargetPicker(); }} catch (_) {{}}
  }});
  player.addEventListener('webkitcurrentplaybacktargetiswirelesschanged', () => {{
    try {{ if (player.webkitCurrentPlaybackTargetIsWireless) hint.classList.add('hidden'); }} catch (_) {{}}
  }});
}})();
</script></body></html>"""
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    return response


def _inject_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-true-airplay-assets"
        if marker in text:
            return response
        js = f'<script id="{marker}" src="/static/airplay_stream.js?v=1"></script>\n'
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def _install_public_route_bypass(flask_app) -> None:
    """Allow token-protected Cast/AirPlay receiver routes through FjordLens' login guard."""
    if flask_app.extensions.get("cast_airplay_public_route_bypass_registered"):
        return
    original = getattr(core, "enforce_login_for_app", None)
    funcs = flask_app.before_request_funcs.get(None, [])
    if original is None or original not in funcs:
        return

    public_endpoints = {
        "cast_airplay.public_session",
        "cast_airplay.public_media",
        "cast_airplay.cast_receiver",
        "cast_airplay.airplay_player",
        "airplay_stream.airplay_media",
        "airplay_stream.airplay_player",
    }

    @wraps(original)
    def cast_airplay_aware_login_guard():
        if request.endpoint in public_endpoints:
            return None
        return original()

    index = funcs.index(original)
    funcs[index] = cast_airplay_aware_login_guard
    flask_app.extensions["cast_airplay_public_route_bypass_registered"] = True


def init_airplay_stream(flask_app) -> None:
    if "airplay_stream" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
    if not flask_app.extensions.get("airplay_stream_assets_registered"):
        flask_app.after_request(_inject_assets)
        flask_app.extensions["airplay_stream_assets_registered"] = True
    _install_public_route_bypass(flask_app)
