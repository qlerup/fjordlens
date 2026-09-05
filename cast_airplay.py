from __future__ import annotations

import json
import mimetypes
import os
import secrets
import tempfile
import threading
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from flask import Blueprint, Response, abort, jsonify, request, send_file
from flask_login import current_user, login_required
from PIL import Image, ImageOps

import app as core

try:
    import fcntl
except Exception:  # pragma: no cover - Windows/dev fallback
    fcntl = None

bp = Blueprint("cast_airplay", __name__)
_lock = threading.RLock()

SESSION_TTL_SECONDS = max(900, min(24 * 3600, int(os.getenv("CAST_SESSION_TTL_SECONDS", "14400") or 14400)))
CAST_NAMESPACE = "urn:x-cast:dk.glerup.fjordlens.gallery"
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".raf", ".orf", ".srw", ".pef"}


def _state_path() -> Path:
    return Path(core.DATA_DIR) / "cast_sessions.json"


def _cache_dir() -> Path:
    return Path(core.DATA_DIR) / "cast_cache"


@contextmanager
def _state_lock():
    with _lock:
        lock_path = _state_path().with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            handle.close()


def _load_state_unlocked() -> Dict[str, Any]:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"version": 1, "sessions": {}}


def _save_state_unlocked(state: Dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".cast-sessions-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(tmp_name, 0o600)
        except Exception:
            pass
        os.replace(tmp_name, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass


def _cleanup_sessions(state: Dict[str, Any]) -> None:
    now = time.time()
    sessions = state.setdefault("sessions", {})
    for token in list(sessions.keys()):
        item = sessions.get(token)
        if not isinstance(item, dict) or float(item.get("expires_at") or 0) <= now:
            sessions.pop(token, None)


def _read_sessions() -> Dict[str, Any]:
    with _state_lock():
        state = _load_state_unlocked()
        before = len(state.get("sessions") or {})
        _cleanup_sessions(state)
        if len(state.get("sessions") or {}) != before:
            _save_state_unlocked(state)
        return state


def _put_session(token: str, value: Dict[str, Any]) -> None:
    with _state_lock():
        state = _load_state_unlocked()
        _cleanup_sessions(state)
        state.setdefault("sessions", {})[token] = value
        _save_state_unlocked(state)


def _get_session(token: str) -> Optional[Dict[str, Any]]:
    token = str(token or "").strip()
    if not token:
        return None
    state = _read_sessions()
    item = (state.get("sessions") or {}).get(token)
    return item if isinstance(item, dict) else None


def _is_admin() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    role = str(getattr(current_user, "role", "") or "").lower()
    return bool(getattr(current_user, "is_admin", False) or role == "admin")


def _cast_app_id() -> str:
    env = str(os.getenv("GOOGLE_CAST_RECEIVER_APP_ID") or "").strip()
    if env:
        return env
    try:
        return str(core._get_setting("google_cast_receiver_app_id", "") or "").strip()
    except Exception:
        return ""


def _public_base_url() -> str:
    # Prefer FjordLens' configured public share/DNS URL when available. This
    # keeps Cast working even if the sender opened FjordLens through a LAN URL.
    try:
        configured = str(core._get_setting("share_duckdns_base_url", "") or "").strip()
        if configured:
            normalized = core._normalize_share_base_url(configured)
            if normalized:
                return str(normalized).rstrip("/")
    except Exception:
        pass
    try:
        env_base = str(getattr(core, "SHARE_DUCKDNS_BASE_URL", "") or "").strip()
        if env_base:
            normalized = core._normalize_share_base_url(env_base)
            if normalized:
                return str(normalized).rstrip("/")
    except Exception:
        pass
    proto = str(request.headers.get("X-Forwarded-Proto") or request.scheme or "https").split(",")[0].strip()
    host = str(request.headers.get("X-Forwarded-Host") or request.host or "").split(",")[0].strip()
    return f"{proto}://{host}".rstrip("/")


def _normalize_ids(values: Iterable[Any], limit: int = 1000) -> List[int]:
    result: List[int] = []
    seen = set()
    for value in values or []:
        try:
            photo_id = int(value)
        except Exception:
            continue
        if photo_id <= 0 or photo_id in seen:
            continue
        seen.add(photo_id)
        result.append(photo_id)
        if len(result) >= limit:
            break
    return result


def _normalize_folders(values: Iterable[Any], limit: int = 100) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        folder = str(value or "").replace("\\", "/").strip().strip("/")
        if not folder:
            continue
        if folder.startswith("uploads/"):
            folder = folder[len("uploads/"):]
        folder = folder.strip("/")
        if not folder or folder in seen:
            continue
        seen.add(folder)
        result.append(folder)
        if len(result) >= limit:
            break
    return result


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _resolve_rows(photo_ids: List[int], folders: List[str], max_items: int = 1500) -> List[Dict[str, Any]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    ordered_ids: List[int] = []
    with core.closing(core.get_conn()) as conn:
        if photo_ids:
            placeholders = ",".join("?" for _ in photo_ids)
            rows = conn.execute(
                f"SELECT id, rel_path, filename, ext FROM photos WHERE id IN ({placeholders})",
                photo_ids,
            ).fetchall()
            found = {int(row["id"]): row for row in rows}
            for pid in photo_ids:
                row = found.get(pid)
                if row is not None and pid not in by_id:
                    by_id[pid] = dict(row)
                    ordered_ids.append(pid)

        for folder in folders:
            prefix = f"uploads/{folder.strip('/')}".rstrip("/")
            pattern = _like_escape(prefix) + "/%"
            rows = conn.execute(
                "SELECT id, rel_path, filename, ext FROM photos WHERE rel_path LIKE ? ESCAPE '\\' ORDER BY COALESCE(captured_at, ''), id",
                (pattern,),
            ).fetchall()
            for row in rows:
                pid = int(row["id"])
                if pid in by_id:
                    continue
                by_id[pid] = dict(row)
                ordered_ids.append(pid)
                if len(ordered_ids) >= max_items:
                    break
            if len(ordered_ids) >= max_items:
                break

    result: List[Dict[str, Any]] = []
    for pid in ordered_ids[:max_items]:
        row = by_id[pid]
        rel = str(row.get("rel_path") or "")
        ext = str(row.get("ext") or Path(rel).suffix or "").lower()
        kind = "video" if ext in VIDEO_EXTS else "image" if ext in IMAGE_EXTS else ""
        if not kind:
            continue
        row["kind"] = kind
        row["ext"] = ext
        result.append(row)
    return result


def _disk_path(row: Dict[str, Any]) -> Optional[Path]:
    rel = str(row.get("rel_path") or "").replace("\\", "/").lstrip("/")
    if not rel:
        return None
    if rel.startswith("uploads/"):
        candidate = Path(core.UPLOAD_DIR) / rel[len("uploads/"):]
    else:
        candidate = Path(core.PHOTO_DIR) / rel
    try:
        candidate = candidate.resolve()
    except Exception:
        pass
    return candidate if candidate.exists() and candidate.is_file() else None


def _image_cache_path(row: Dict[str, Any]) -> Path:
    src = _disk_path(row)
    if src is None:
        raise FileNotFoundError("Billedfilen findes ikke længere")
    rel = str(row.get("rel_path") or "")
    try:
        viewable = Path(core.ensure_viewable_copy(src, rel))
    except Exception:
        viewable = src
    stamp = int(viewable.stat().st_mtime_ns if viewable.exists() else src.stat().st_mtime_ns)
    dest_dir = _cache_dir() / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{int(row['id'])}_{stamp}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    with Image.open(viewable) as source:
        image = ImageOps.exif_transpose(source)
        try:
            image.seek(0)
        except Exception:
            pass
        image = image.copy()
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "black")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
    tmp = dest.with_suffix(".tmp.jpg")
    image.save(tmp, format="JPEG", quality=88, optimize=True)
    os.replace(tmp, dest)
    return dest


def _row_for_session(session: Dict[str, Any], photo_id: int) -> Optional[Dict[str, Any]]:
    for item in session.get("items") or []:
        if isinstance(item, dict) and int(item.get("id") or 0) == int(photo_id):
            return item
    return None


def _session_public_payload(token: str, session: Dict[str, Any]) -> Dict[str, Any]:
    base = _public_base_url()
    items = []
    for item in session.get("items") or []:
        pid = int(item.get("id") or 0)
        if pid <= 0:
            continue
        kind = str(item.get("kind") or "image")
        ext = str(item.get("ext") or "").lower()
        mime = "image/jpeg" if kind == "image" else (mimetypes.guess_type("x" + ext)[0] or "video/mp4")
        items.append({
            "id": pid,
            "name": str(item.get("filename") or Path(str(item.get("rel_path") or "")).name or f"#{pid}"),
            "kind": kind,
            "mime": mime,
            "url": f"{base}/cast/media/{quote(token, safe='')}/{pid}",
        })
    return {
        "ok": True,
        "title": str(session.get("title") or "FjordLens"),
        "created_at": float(session.get("created_at") or 0),
        "expires_at": float(session.get("expires_at") or 0),
        "image_duration": int(session.get("image_duration") or 8),
        "loop": bool(session.get("loop", True)),
        "items": items,
    }


@bp.get("/api/cast-airplay/status")
@login_required
def status():
    base = _public_base_url()
    app_id = _cast_app_id()
    return jsonify({
        "ok": True,
        "cast_configured": bool(app_id),
        "cast_receiver_app_id": app_id,
        "receiver_url": f"{base}/cast/receiver",
        "can_admin": _is_admin(),
        "namespace": CAST_NAMESPACE,
    })


@bp.post("/api/cast-airplay/config")
@login_required
def save_config():
    if not _is_admin():
        abort(403)
    payload = request.get_json(silent=True) or {}
    app_id = str(payload.get("cast_receiver_app_id") or "").strip().upper()
    if app_id and (len(app_id) > 64 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in app_id)):
        return jsonify({"ok": False, "error": "Ugyldigt Cast Receiver App ID."}), 400
    try:
        core._set_setting("google_cast_receiver_app_id", app_id)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return status()


@bp.post("/api/cast-airplay/session")
@login_required
def create_session():
    payload = request.get_json(silent=True) or {}
    photo_ids = _normalize_ids(payload.get("photo_ids") or [])
    folders = _normalize_folders(payload.get("folder_paths") or [])
    if not photo_ids and not folders:
        return jsonify({"ok": False, "error": "Vælg mindst ét billede, én video eller én mappe."}), 400

    rows = _resolve_rows(photo_ids, folders)
    if not rows:
        return jsonify({"ok": False, "error": "Der blev ikke fundet billeder eller videoer i valget."}), 400

    token = secrets.token_urlsafe(36)
    now = time.time()
    title = str(payload.get("title") or "FjordLens").strip()[:120] or "FjordLens"
    session = {
        "created_at": now,
        "expires_at": now + SESSION_TTL_SECONDS,
        "created_by_user_id": int(getattr(current_user, "id", 0) or 0),
        "title": title,
        "loop": True,
        "image_duration": 8,
        "items": rows,
    }
    _put_session(token, session)
    base = _public_base_url()
    public = _session_public_payload(token, session)
    app_id = _cast_app_id()
    return jsonify({
        "ok": True,
        "token": token,
        "item_count": len(public["items"]),
        "contains_images": any(i.get("kind") == "image" for i in public["items"]),
        "contains_videos": any(i.get("kind") == "video" for i in public["items"]),
        "session_url": f"{base}/cast/session/{quote(token, safe='')}",
        "play_url": f"{base}/cast/play/{quote(token, safe='')}",
        "receiver_url": f"{base}/cast/receiver",
        "cast_receiver_app_id": app_id,
        "cast_configured": bool(app_id),
        "can_admin": _is_admin(),
        "namespace": CAST_NAMESPACE,
    })


@bp.get("/cast/session/<token>")
def public_session(token: str):
    session = _get_session(token)
    if not session:
        return jsonify({"ok": False, "error": "Cast-sessionen findes ikke eller er udløbet."}), 404
    response = jsonify(_session_public_payload(token, session))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/cast/media/<token>/<int:photo_id>")
def public_media(token: str, photo_id: int):
    session = _get_session(token)
    if not session:
        return ("Cast-sessionen er udløbet", 404)
    row = _row_for_session(session, photo_id)
    if not row:
        return ("Ikke en del af Cast-sessionen", 404)
    try:
        if str(row.get("kind") or "") == "image":
            path = _image_cache_path(row)
            response = send_file(path, mimetype="image/jpeg", conditional=True, max_age=3600)
        else:
            path = _disk_path(row)
            if path is None:
                return ("Filen findes ikke", 404)
            mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
            response = send_file(path, mimetype=mime, conditional=True, max_age=3600)
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
    except Exception as exc:
        return (f"Kunne ikke klargøre mediet: {exc}", 500)


@bp.get("/cast/receiver")
def cast_receiver():
    html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>FjordLens Cast</title>
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#000;color:#fff;font-family:system-ui,sans-serif}}
#stage{{position:fixed;inset:0;display:grid;place-items:center;background:#000}}
#photo,#video{{width:100%;height:100%;object-fit:contain;background:#000}}
#photo.hidden,#video.hidden{{display:none}}
#idle{{position:fixed;inset:0;display:grid;place-items:center;text-align:center;color:#aab9c0}}
#idle strong{{display:block;color:#fff;font-size:34px;margin-bottom:8px}}
#meta{{position:fixed;left:24px;right:24px;bottom:18px;text-align:center;font-size:14px;color:#dbe7eb;text-shadow:0 2px 8px #000;opacity:.75}}
</style>
<script src=\"https://www.gstatic.com/cast/sdk/libs/caf_receiver/v3/cast_receiver_framework.js\"></script>
</head><body>
<div id=\"stage\"><div id=\"idle\"><div><strong>FjordLens</strong>Vælg billeder eller en mappe på telefonen</div></div><img id=\"photo\" class=\"hidden\" alt=\"\"><video id=\"video\" class=\"hidden\" playsinline></video></div>
<div id=\"meta\"></div>
<script>
(() => {{
  'use strict';
  const NS = {json.dumps(CAST_NAMESPACE)};
  const context = cast.framework.CastReceiverContext.getInstance();
  const photo = document.getElementById('photo');
  const video = document.getElementById('video');
  const idle = document.getElementById('idle');
  const meta = document.getElementById('meta');
  let playlist = [];
  let index = 0;
  let timer = null;
  let imageDuration = 8000;
  let loop = true;

  function clearTimer() {{ if (timer) {{ clearTimeout(timer); timer = null; }} }}
  function hideAll() {{ photo.classList.add('hidden'); video.classList.add('hidden'); video.pause(); video.removeAttribute('src'); }}
  function updateState(item) {{
    const name = item && item.name ? item.name : 'FjordLens';
    meta.textContent = playlist.length ? `${{index + 1}} / ${{playlist.length}} · ${{name}}` : '';
    try {{ context.setApplicationState(playlist.length ? `FjordLens · ${{index + 1}}/${{playlist.length}}` : 'FjordLens'); }} catch (_) {{}}
  }}
  function advance(step) {{
    if (!playlist.length) return;
    let next = index + step;
    if (next >= playlist.length) {{ if (!loop) return; next = 0; }}
    if (next < 0) next = playlist.length - 1;
    index = next;
    showCurrent();
  }}
  async function showCurrent() {{
    clearTimer();
    hideAll();
    idle.style.display = playlist.length ? 'none' : 'grid';
    if (!playlist.length) return;
    const item = playlist[index];
    updateState(item);
    if (item.kind === 'video') {{
      video.src = item.url;
      video.classList.remove('hidden');
      try {{ await video.play(); }} catch (e) {{ timer = setTimeout(() => advance(1), 2500); }}
    }} else {{
      photo.src = item.url;
      photo.classList.remove('hidden');
      timer = setTimeout(() => advance(1), imageDuration);
    }}
  }}
  async function loadSession(url) {{
    clearTimer();
    const response = await fetch(url, {{cache:'no-store'}});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${{response.status}}`);
    playlist = Array.isArray(data.items) ? data.items : [];
    imageDuration = Math.max(2000, Number(data.image_duration || 8) * 1000);
    loop = data.loop !== false;
    index = 0;
    await showCurrent();
  }}
  video.addEventListener('ended', () => advance(1));
  video.addEventListener('error', () => {{ clearTimer(); timer = setTimeout(() => advance(1), 1800); }});
  context.addCustomMessageListener(NS, (event) => {{
    const msg = event && event.data ? event.data : {{}};
    if (msg.type === 'LOAD' && msg.session_url) loadSession(String(msg.session_url)).catch(() => {{}});
    else if (msg.type === 'NEXT') advance(1);
    else if (msg.type === 'PREV') advance(-1);
    else if (msg.type === 'PAUSE') {{ clearTimer(); if (!video.classList.contains('hidden')) video.pause(); }}
    else if (msg.type === 'PLAY') {{ if (!video.classList.contains('hidden')) video.play().catch(() => {{}}); else timer = setTimeout(() => advance(1), imageDuration); }}
  }});
  context.start();
}})();
</script></body></html>"""
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@bp.get("/cast/play/<token>")
def airplay_player(token: str):
    session = _get_session(token)
    if not session:
        return Response("Cast/AirPlay-sessionen er udløbet.", status=404, mimetype="text/plain")
    session_url = f"/cast/session/{quote(token, safe='')}"
    html = f"""<!doctype html>
<html lang=\"da\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
<title>FjordLens AirPlay</title>
<style>
html,body{{margin:0;min-height:100%;background:#061218;color:#eef7f7;font-family:system-ui,sans-serif}}
body{{display:flex;flex-direction:column;height:100dvh}}
header{{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.12)}}
header strong{{font-size:16px}} button{{appearance:none;border:1px solid rgba(255,255,255,.16);border-radius:999px;background:#10252d;color:#eef7f7;padding:10px 14px;font:inherit}}
#airplay{{background:#0f8d86;border-color:#20bcb0;font-weight:700}}
#stage{{position:relative;flex:1;min-height:0;background:#000;display:grid;place-items:center}} #photo,#video{{width:100%;height:100%;object-fit:contain;background:#000}} .hidden{{display:none!important}}
footer{{padding:10px 14px calc(10px + env(safe-area-inset-bottom));display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;border-top:1px solid rgba(255,255,255,.12)}}
#name{{text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#b9c9ce;font-size:13px}} #note{{position:absolute;left:12px;right:12px;bottom:12px;background:rgba(5,17,22,.86);border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 12px;font-size:12px;line-height:1.45;color:#d7e5e8}}
</style></head><body>
<header><strong>FjordLens · AirPlay</strong><button id=\"airplay\" class=\"hidden\">AirPlay</button></header>
<div id=\"stage\"><img id=\"photo\" class=\"hidden\" alt=\"\"><video id=\"video\" class=\"hidden\" controls playsinline x-webkit-airplay=\"allow\"></video><div id=\"note\" class=\"hidden\"></div></div>
<footer><button id=\"prev\">‹</button><div id=\"name\"></div><button id=\"next\">›</button></footer>
<script>
(() => {{
 const sessionUrl={json.dumps(session_url)}; const photo=document.getElementById('photo'); const video=document.getElementById('video'); const airplay=document.getElementById('airplay'); const note=document.getElementById('note'); const nameEl=document.getElementById('name');
 let items=[],index=0,timer=null,duration=8000;
 function clear(){{if(timer)clearTimeout(timer);timer=null;video.pause();video.removeAttribute('src');photo.classList.add('hidden');video.classList.add('hidden');note.classList.add('hidden');airplay.classList.add('hidden');}}
 function next(step=1){{if(!items.length)return;index=(index+step+items.length)%items.length;show();}}
 async function show(){{clear();const item=items[index];if(!item)return;nameEl.textContent=`${{index+1}} / ${{items.length}} · ${{item.name||''}}`;if(item.kind==='video'){{video.src=item.url;video.classList.remove('hidden');if(typeof video.webkitShowPlaybackTargetPicker==='function')airplay.classList.remove('hidden');try{{await video.play();}}catch(_ ){{}}}}else{{photo.src=item.url;photo.classList.remove('hidden');note.textContent='Billeder kan ikke sendes direkte til AirPlay fra en webapp. Brug Skærmdublering i iPhones Kontrolcenter for hele slideshowet.';note.classList.remove('hidden');timer=setTimeout(()=>next(1),duration);}}}}
 video.addEventListener('ended',()=>next(1));document.getElementById('next').onclick=()=>next(1);document.getElementById('prev').onclick=()=>next(-1);airplay.onclick=()=>{{try{{video.webkitShowPlaybackTargetPicker();}}catch(_ ){{}}}};
 fetch(sessionUrl,{{cache:'no-store'}}).then(r=>r.json()).then(data=>{{items=Array.isArray(data.items)?data.items:[];duration=Math.max(2000,Number(data.image_duration||8)*1000);show();}});
}})();
</script></body></html>"""
    return Response(html, mimetype="text/html")


def _inject_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-cast-airplay-assets"
        if marker in text:
            return response
        css = f'<link id="{marker}" rel="stylesheet" href="/static/cast_airplay.css?v=1">\n'
        js = '<script src="/static/cast_airplay.js?v=1"></script>\n'
        if "</head>" in text:
            text = text.replace("</head>", css + "</head>", 1)
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def init_cast_airplay(flask_app) -> None:
    if "cast_airplay" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
    if not flask_app.extensions.get("cast_airplay_assets_registered"):
        flask_app.after_request(_inject_assets)
        flask_app.extensions["cast_airplay_assets_registered"] = True
