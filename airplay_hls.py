from __future__ import annotations

import hashlib
from functools import wraps
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file
from flask_login import login_required

import app as core
import cast_airplay as cast_core

bp = Blueprint("airplay_hls", __name__)

AIRPLAY_IMAGE_DURATION = max(2, min(30, int(os.getenv("AIRPLAY_IMAGE_DURATION_SECONDS", "8") or 8)))
AIRPLAY_HLS_SEGMENT_SECONDS = max(2, min(8, int(os.getenv("AIRPLAY_HLS_SEGMENT_SECONDS", "4") or 4)))
AIRPLAY_MAX_ITEMS = max(1, min(1500, int(os.getenv("AIRPLAY_MAX_ITEMS", "400") or 400)))
AIRPLAY_ITEM_TIMEOUT = max(30, min(7200, int(os.getenv("AIRPLAY_HLS_ITEM_TIMEOUT_SECONDS", "1800") or 1800)))

_render_guard = threading.RLock()
_render_threads: Dict[str, threading.Thread] = {}


def _token_key(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()[:32]


def _root() -> Path:
    path = Path(core.DATA_DIR) / "cast_cache" / "airplay_hls"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_dir(token: str) -> Path:
    return _root() / _token_key(token)


def _status_path(token: str) -> Path:
    return _job_dir(token) / "status.json"


def _manifest_path(token: str) -> Path:
    return _job_dir(token) / "index.m3u8"


def _marker_path(token: str) -> Path:
    return _job_dir(token) / "rendering.lock"


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_status(token: str) -> Dict[str, Any]:
    try:
        data = json.loads(_status_path(token).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "state": "idle",
        "playable": False,
        "finished": False,
        "done": 0,
        "total": 0,
        "segments": 0,
        "error": "",
    }


def _write_status(token: str, **changes: Any) -> Dict[str, Any]:
    current = _read_status(token)
    current.update(changes)
    current["updated_at"] = time.time()
    _write_json_atomic(_status_path(token), current)
    return current


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


def _codec_args() -> List[str]:
    return [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-profile:v", "high",
        "-level", "4.0",
        "-pix_fmt", "yuv420p",
        "-g", str(AIRPLAY_HLS_SEGMENT_SECONDS * 30),
        "-keyint_min", str(AIRPLAY_HLS_SEGMENT_SECONDS * 30),
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
    ]


def _parse_child_playlist(path: Path) -> List[Tuple[float, str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    result: List[Tuple[float, str]] = []
    pending: Optional[float] = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            try:
                pending = float(line.split(":", 1)[1].split(",", 1)[0])
            except Exception:
                pending = None
        elif pending is not None and line and not line.startswith("#"):
            name = Path(line).name
            if name == line and re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                result.append((pending, name))
            pending = None
    return result


def _main_manifest(entries: List[Tuple[float, str, bool]], finished: bool, target_duration: int) -> str:
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:6",
        f"#EXT-X-TARGETDURATION:{max(2, int(target_duration))}",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:EVENT",
        "#EXT-X-INDEPENDENT-SEGMENTS",
    ]
    for duration, filename, discontinuity in entries:
        if discontinuity:
            lines.append("#EXT-X-DISCONTINUITY")
        lines.append(f"#EXTINF:{duration:.6f},")
        lines.append(filename)
    if finished:
        lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


def _write_main_manifest(token: str, entries: List[Tuple[float, str, bool]], finished: bool) -> None:
    target = max(AIRPLAY_HLS_SEGMENT_SECONDS, AIRPLAY_IMAGE_DURATION)
    if entries:
        target = max(target, int(math.ceil(max(d for d, _, _ in entries))))
    _write_text_atomic(_manifest_path(token), _main_manifest(entries, finished, target))


def _item_hls_command(item: Dict[str, Any], index: int, token: str, session: Dict[str, Any]) -> Tuple[List[str], Path]:
    job = _job_dir(token)
    child = job / f"item_{index:05d}.m3u8"
    seg_pattern = job / f"item_{index:05d}_%05d.ts"
    kind = str(item.get("kind") or "image").lower()

    base = [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
    if kind == "video":
        src = cast_core._disk_path(item)
        if src is None:
            raise FileNotFoundError("En video i valget findes ikke længere.")
        base += ["-fflags", "+genpts", "-i", str(src)]
        if _video_has_audio(src):
            base += [
                "-map", "0:v:0", "-map", "0:a:0",
                "-vf", _video_filter(),
                "-af", "aresample=async=1:first_pts=0",
                *_codec_args(),
            ]
        else:
            base += [
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", _video_filter(),
                *_codec_args(),
                "-shortest",
            ]
    else:
        src = cast_core._image_cache_path(item)
        duration = max(2, min(30, int(session.get("image_duration") or AIRPLAY_IMAGE_DURATION)))
        base += [
            "-loop", "1", "-framerate", "1", "-i", str(src),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(duration),
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", _video_filter(),
            *_codec_args(),
            "-shortest",
        ]

    base += [
        "-force_key_frames", f"expr:gte(t,n_forced*{AIRPLAY_HLS_SEGMENT_SECONDS})",
        "-f", "hls",
        "-hls_time", str(AIRPLAY_HLS_SEGMENT_SECONDS),
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments+temp_file",
        "-hls_segment_type", "mpegts",
        "-hls_segment_filename", str(seg_pattern),
        str(child),
    ]
    return base, child


def _transcode_item_progressive(
    token: str,
    item: Dict[str, Any],
    index: int,
    session: Dict[str, Any],
    entries: List[Tuple[float, str, bool]],
) -> int:
    cmd, child = _item_hls_command(item, index, token, session)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    seen: set[str] = set()
    started = time.time()
    first_of_item = True
    try:
        while True:
            for duration, filename in _parse_child_playlist(child):
                if filename in seen:
                    continue
                segment = _job_dir(token) / filename
                if not segment.exists() or segment.stat().st_size <= 0:
                    continue
                seen.add(filename)
                entries.append((duration, filename, bool(index > 0 and first_of_item)))
                first_of_item = False
                _write_main_manifest(token, entries, finished=False)
                _write_status(token, state="streaming", playable=True, segments=len(entries), current=index + 1)

            code = proc.poll()
            if code is not None:
                break
            if time.time() - started > AIRPLAY_ITEM_TIMEOUT:
                proc.kill()
                raise RuntimeError("Klargøringen af et AirPlay-medie tog for lang tid.")
            time.sleep(0.25)

        for duration, filename in _parse_child_playlist(child):
            if filename in seen:
                continue
            segment = _job_dir(token) / filename
            if segment.exists() and segment.stat().st_size > 0:
                seen.add(filename)
                entries.append((duration, filename, bool(index > 0 and first_of_item)))
                first_of_item = False
        _write_main_manifest(token, entries, finished=False)

        if code != 0:
            detail = ""
            try:
                detail = (proc.stderr.read() if proc.stderr else "") or ""
            except Exception:
                pass
            detail = detail.strip()
            if len(detail) > 2500:
                detail = detail[-2500:]
            raise RuntimeError(detail or "ffmpeg kunne ikke klargøre et AirPlay-medie.")
        if not seen:
            raise RuntimeError("Der blev ikke oprettet HLS-segmenter for et af medierne.")
        return len(seen)
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            if proc.stderr:
                proc.stderr.close()
        except Exception:
            pass


def _render_hls(token: str) -> None:
    entries: List[Tuple[float, str, bool]] = []
    try:
        session = cast_core._get_session(token)
        if not session:
            raise RuntimeError("AirPlay-sessionen er udløbet.")
        items = [item for item in (session.get("items") or []) if isinstance(item, dict)]
        if not items:
            raise RuntimeError("Der er ingen billeder eller videoer i AirPlay-sessionen.")
        if len(items) > AIRPLAY_MAX_ITEMS:
            raise RuntimeError(f"Der er valgt {len(items)} medier. AirPlay understøtter højst {AIRPLAY_MAX_ITEMS} ad gangen.")

        job = _job_dir(token)
        job.mkdir(parents=True, exist_ok=True)
        for path in job.iterdir():
            if path.name == "rendering.lock":
                continue
            if path.is_file():
                try:
                    path.unlink()
                except Exception:
                    pass
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

        _write_main_manifest(token, entries, finished=False)
        _write_status(
            token,
            state="preparing",
            playable=False,
            finished=False,
            done=0,
            current=0,
            total=len(items),
            segments=0,
            error="",
        )

        for index, item in enumerate(items):
            _transcode_item_progressive(token, item, index, session, entries)
            _write_status(
                token,
                state="streaming" if index + 1 < len(items) else "finishing",
                playable=bool(entries),
                done=index + 1,
                current=index + 1,
                total=len(items),
                segments=len(entries),
            )

        _write_main_manifest(token, entries, finished=True)
        _write_status(
            token,
            state="ready",
            playable=bool(entries),
            finished=True,
            done=len(items),
            current=len(items),
            total=len(items),
            segments=len(entries),
            error="",
        )
    except Exception as exc:
        if entries:
            try:
                _write_main_manifest(token, entries, finished=True)
            except Exception:
                pass
        _write_status(token, state="error", finished=True, error=str(exc), playable=bool(entries), segments=len(entries))
    finally:
        try:
            _marker_path(token).unlink()
        except Exception:
            pass
        with _render_guard:
            _render_threads.pop(_token_key(token), None)


def _claim_render(token: str) -> bool:
    marker = _marker_path(token)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        if marker.exists() and time.time() - marker.stat().st_mtime > max(3600, AIRPLAY_ITEM_TIMEOUT * 2):
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


def _start_render(token: str, force: bool = False) -> Dict[str, Any]:
    state = _read_status(token)
    if state.get("state") == "ready" and state.get("playable") and not force:
        return state
    key = _token_key(token)
    with _render_guard:
        existing = _render_threads.get(key)
        if existing is not None and existing.is_alive():
            return _read_status(token)
        if not _claim_render(token):
            return _read_status(token)
        thread = threading.Thread(target=_render_hls, args=(token,), daemon=True, name=f"fjordlens-airplay-hls-{key[:8]}")
        _render_threads[key] = thread
        thread.start()
    return _read_status(token)


def _public_url(path: str) -> str:
    return f"{cast_core._public_base_url().rstrip('/')}{path}"


def _status_payload(token: str) -> Dict[str, Any]:
    state = _read_status(token)
    token_q = quote(token, safe="")
    return {
        "ok": state.get("state") != "error",
        "state": str(state.get("state") or "idle"),
        "playable": bool(state.get("playable")),
        "ready": bool(state.get("finished") and state.get("playable")),
        "finished": bool(state.get("finished")),
        "done": int(state.get("done") or 0),
        "current": int(state.get("current") or 0),
        "total": int(state.get("total") or 0),
        "segments": int(state.get("segments") or 0),
        "error": str(state.get("error") or ""),
        "stream_url": _public_url(f"/airplay/hls/{token_q}/index.m3u8"),
        "web_player_url": _public_url(f"/airplay/hls/{token_q}/play"),
    }


@bp.post("/api/airplay-hls/<token>/prepare")
@login_required
def prepare(token: str):
    if not cast_core._get_session(token):
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    force = bool((request.get_json(silent=True) or {}).get("force"))
    _start_render(token, force=force)
    return jsonify(_status_payload(token))


@bp.get("/api/airplay-hls/<token>/status")
@login_required
def status(token: str):
    if not cast_core._get_session(token):
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    return jsonify(_status_payload(token))


@bp.get("/airplay/hls/<token>/index.m3u8")
def manifest(token: str):
    if not cast_core._get_session(token):
        return Response("AirPlay-sessionen er udløbet.\n", status=404, mimetype="text/plain")
    path = _manifest_path(token)
    if not path.exists():
        return Response("#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-TARGETDURATION:8\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PLAYLIST-TYPE:EVENT\n", mimetype="application/vnd.apple.mpegurl")
    response = send_file(path, mimetype="application/vnd.apple.mpegurl", conditional=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.get("/airplay/hls/<token>/<segment>")
def segment(token: str, segment: str):
    if not cast_core._get_session(token):
        return Response("AirPlay-sessionen er udløbet.", status=404, mimetype="text/plain")
    if not re.fullmatch(r"item_\d{5}_\d{5}\.ts", str(segment or "")):
        return Response("Ugyldigt segment.", status=404, mimetype="text/plain")
    path = _job_dir(token) / segment
    if not path.exists() or not path.is_file():
        return Response("Segmentet er ikke klar endnu.", status=404, mimetype="text/plain")
    response = send_file(path, mimetype="video/mp2t", conditional=True, max_age=3600)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.get("/airplay/hls/<token>/play")
def web_player(token: str):
    if not cast_core._get_session(token):
        return Response("AirPlay-sessionen er udløbet.", status=404, mimetype="text/plain")
    stream = f"/airplay/hls/{quote(token, safe='')}/index.m3u8"
    html = f"""<!doctype html>
<html lang=\"da\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\"><title>FjordLens AirPlay</title>
<style>html,body{{margin:0;height:100%;background:#000}}body{{display:grid;place-items:center}}video{{width:100%;height:100%;object-fit:contain;background:#000}}</style></head>
<body><video controls autoplay playsinline x-webkit-airplay=\"allow\" src=\"{stream}\"></video></body></html>"""
    return Response(html, mimetype="text/html")


def _inject_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-airplay-hls-assets"
        if marker in text:
            return response
        js = f'<script id="{marker}" src="/static/airplay_hls.js?v=1"></script>\n'
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def _install_public_route_bypass(flask_app) -> None:
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
        "airplay_hls.manifest",
        "airplay_hls.segment",
        "airplay_hls.web_player",
    }

    @wraps(original)
    def cast_airplay_aware_login_guard():
        if request.endpoint in public_endpoints:
            return None
        return original()

    index = funcs.index(original)
    funcs[index] = cast_airplay_aware_login_guard
    flask_app.extensions["cast_airplay_public_route_bypass_registered"] = True


def init_airplay_hls(flask_app) -> None:
    if "airplay_hls" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
    _install_public_route_bypass(flask_app)
    if not flask_app.extensions.get("airplay_hls_assets_registered"):
        flask_app.after_request(_inject_assets)
        flask_app.extensions["airplay_hls_assets_registered"] = True
