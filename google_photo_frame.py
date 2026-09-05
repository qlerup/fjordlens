from __future__ import annotations

import html
import json
import os
import secrets
import tempfile
import threading
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from flask import Blueprint, Response, abort, jsonify, redirect, request, session
from flask_login import current_user, login_required
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

try:
    import fcntl  # Linux production path
except Exception:  # pragma: no cover - Windows/dev fallback
    fcntl = None

bp = Blueprint("google_photo_frame", __name__)
_core = None
_state_thread_lock = threading.RLock()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
PHOTOS_API = "https://photoslibrary.googleapis.com/v1"
UPLOAD_URL = f"{PHOTOS_API}/uploads"
SCOPES = (
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",
    "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata",
)
DEFAULT_ALBUM_TITLE = "FjordLens Photo Frame"


class GooglePhotoFrameError(RuntimeError):
    pass


def _now_iso() -> str:
    try:
        if _core is not None and hasattr(_core, "now_iso"):
            return str(_core.now_iso())
    except Exception:
        pass
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _data_dir() -> Path:
    if _core is not None and getattr(_core, "DATA_DIR", None) is not None:
        return Path(_core.DATA_DIR)
    return Path(os.getenv("DATA_DIR", "/data"))


def _state_path() -> Path:
    return _data_dir() / "google_photo_frame.json"


def _default_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "",
        "album_title": os.getenv("GOOGLE_PHOTOS_ALBUM_TITLE", DEFAULT_ALBUM_TITLE),
        "album_id": "",
        "album_url": "",
        "remote_count": None,
        "access_token": "",
        "refresh_token": "",
        "token_expires_at": 0,
        "token_scope": "",
        "synced": {},
        "last_sync_at": "",
        "last_error": "",
    }


def _read_state_unlocked() -> Dict[str, Any]:
    state = _default_state()
    path = _state_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            state.update(raw)
    except FileNotFoundError:
        pass
    except Exception:
        # A damaged optional integration state must not prevent FjordLens startup.
        pass
    if not isinstance(state.get("synced"), dict):
        state["synced"] = {}
    return state


def _write_state_unlocked(state: Dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".google-photo-frame-", suffix=".json", dir=str(path.parent))
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


@contextmanager
def _exclusive_state_lock():
    with _state_thread_lock:
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


def _read_state() -> Dict[str, Any]:
    with _exclusive_state_lock():
        return _read_state_unlocked()


def _mutate_state(mutator) -> Dict[str, Any]:
    with _exclusive_state_lock():
        state = _read_state_unlocked()
        mutator(state)
        _write_state_unlocked(state)
        return state


def _effective_client_id(state: Dict[str, Any]) -> str:
    return str(os.getenv("GOOGLE_PHOTOS_CLIENT_ID") or state.get("client_id") or "").strip()


def _effective_client_secret(state: Dict[str, Any]) -> str:
    return str(os.getenv("GOOGLE_PHOTOS_CLIENT_SECRET") or state.get("client_secret") or "").strip()


def _is_admin() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    role = str(getattr(current_user, "role", "") or "").lower()
    return bool(getattr(current_user, "is_admin", False) or role == "admin")


def _require_admin() -> None:
    if not _is_admin():
        abort(403)


def _computed_callback_url() -> str:
    proto = str(request.headers.get("X-Forwarded-Proto") or request.scheme or "http").split(",")[0].strip()
    host = str(request.headers.get("X-Forwarded-Host") or request.host or "").split(",")[0].strip()
    return f"{proto}://{host}/api/google-photo-frame/oauth/callback"


def _oauth_redirect_uri(state: Dict[str, Any]) -> str:
    return str(
        os.getenv("GOOGLE_PHOTOS_REDIRECT_URI")
        or state.get("redirect_uri")
        or _computed_callback_url()
    ).strip()


def _connected(state: Dict[str, Any]) -> bool:
    return bool(state.get("refresh_token") or state.get("access_token"))


def _configured(state: Dict[str, Any]) -> bool:
    return bool(_effective_client_id(state) and _effective_client_secret(state))


def _error_message(response: requests.Response, fallback: str) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str) and error:
            return error
        if isinstance(payload, dict) and payload.get("error_description"):
            return str(payload["error_description"])
    except Exception:
        pass
    text = (response.text or "").strip()
    if text and len(text) <= 400:
        return text
    return fallback


def _refresh_access_token(state: Optional[Dict[str, Any]] = None) -> str:
    state = state or _read_state()
    access_token = str(state.get("access_token") or "")
    expires_at = float(state.get("token_expires_at") or 0)
    if access_token and expires_at > time.time() + 60:
        return access_token

    refresh_token = str(state.get("refresh_token") or "")
    if not refresh_token:
        if access_token:
            return access_token
        raise GooglePhotoFrameError("Google Photos er ikke forbundet endnu.")

    client_id = _effective_client_id(state)
    client_secret = _effective_client_secret(state)
    if not client_id or not client_secret:
        raise GooglePhotoFrameError("Google OAuth client-id eller client-secret mangler.")

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if not response.ok:
        raise GooglePhotoFrameError(_error_message(response, "Kunne ikke forny Google-token."))
    token_data = response.json()
    new_access = str(token_data.get("access_token") or "")
    if not new_access:
        raise GooglePhotoFrameError("Google returnerede ikke et access-token.")

    def patch(current: Dict[str, Any]) -> None:
        current["access_token"] = new_access
        current["token_expires_at"] = time.time() + int(token_data.get("expires_in") or 3600)
        if token_data.get("scope"):
            current["token_scope"] = str(token_data["scope"])
        current["last_error"] = ""

    _mutate_state(patch)
    return new_access


def _google_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ensure_album(token: Optional[str] = None, verify_existing: bool = True) -> Tuple[str, str, Optional[int]]:
    state = _read_state()
    token = token or _refresh_access_token(state)
    album_id = str(state.get("album_id") or "")

    if album_id and verify_existing:
        response = requests.get(f"{PHOTOS_API}/albums/{album_id}", headers=_google_headers(token), timeout=20)
        if response.ok:
            album = response.json()
            album_url = str(album.get("productUrl") or state.get("album_url") or "")
            remote_count = album.get("mediaItemsCount")

            def patch(current: Dict[str, Any]) -> None:
                current["album_url"] = album_url
                current["remote_count"] = remote_count
                current["last_error"] = ""

            _mutate_state(patch)
            return album_id, album_url, remote_count
        if response.status_code not in (403, 404):
            raise GooglePhotoFrameError(_error_message(response, "Kunne ikke læse Google Photos-albummet."))

        # Album disappeared or is no longer available to this OAuth client/account.
        def clear_album(current: Dict[str, Any]) -> None:
            current["album_id"] = ""
            current["album_url"] = ""
            current["remote_count"] = None
            for entry in current.get("synced", {}).values():
                if isinstance(entry, dict):
                    entry["in_album"] = False

        _mutate_state(clear_album)
        album_id = ""

    if album_id:
        return album_id, str(state.get("album_url") or ""), state.get("remote_count")

    title = str(state.get("album_title") or DEFAULT_ALBUM_TITLE).strip() or DEFAULT_ALBUM_TITLE
    response = requests.post(
        f"{PHOTOS_API}/albums",
        headers={**_google_headers(token), "Content-Type": "application/json"},
        json={"album": {"title": title}},
        timeout=20,
    )
    if not response.ok:
        raise GooglePhotoFrameError(_error_message(response, "Kunne ikke oprette Google Photos-album."))
    album = response.json()
    new_id = str(album.get("id") or "")
    if not new_id:
        raise GooglePhotoFrameError("Google returnerede ikke et album-id.")
    album_url = str(album.get("productUrl") or "")

    def patch(current: Dict[str, Any]) -> None:
        current["album_id"] = new_id
        current["album_url"] = album_url
        current["remote_count"] = 0
        current["last_error"] = ""

    _mutate_state(patch)
    return new_id, album_url, 0


def _photo_row(photo_id: int):
    if _core is None:
        raise GooglePhotoFrameError("FjordLens-core er ikke initialiseret.")
    with _core.closing(_core.get_conn()) as conn:
        return conn.execute(
            "SELECT id, rel_path, filename, ext, thumb_name FROM photos WHERE id=?",
            (int(photo_id),),
        ).fetchone()


def _candidate_photo_paths(row) -> List[Path]:
    rel = str(row["rel_path"] or "").replace("\\", "/").lstrip("/")
    candidates: List[Path] = []
    if rel.startswith("uploads/"):
        upload_dir = Path(_core.UPLOAD_DIR)
        candidates.append(upload_dir / rel[len("uploads/"):])
        if rel.startswith("uploads/originals/"):
            relative_original = Path(rel[len("uploads/originals/"):])
            converted_base = upload_dir / "converted" / relative_original
            for suffix in (".jpg", ".jpeg", ".png", ".webp"):
                candidates.append(converted_base.with_suffix(suffix))
    else:
        photo_dir = Path(_core.PHOTO_DIR)
        candidates.append(photo_dir / rel)
    thumb_name = str(row["thumb_name"] or "").strip()
    if thumb_name and getattr(_core, "THUMB_DIR", None) is not None:
        candidates.append(Path(_core.THUMB_DIR) / thumb_name)

    unique: List[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _render_photo_jpeg(photo_id: int) -> Tuple[bytes, str]:
    row = _photo_row(photo_id)
    if row is None:
        raise GooglePhotoFrameError(f"Billede {photo_id} findes ikke længere.")

    max_edge = max(720, min(4096, int(os.getenv("GOOGLE_PHOTO_FRAME_MAX_EDGE", "2048"))))
    quality = max(70, min(95, int(os.getenv("GOOGLE_PHOTO_FRAME_JPEG_QUALITY", "88"))))
    errors: List[str] = []
    for path in _candidate_photo_paths(row):
        if not path.exists() or not path.is_file():
            continue
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                try:
                    image.seek(0)
                except Exception:
                    pass
                image = image.copy()
            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            stem = Path(str(row["filename"] or f"photo-{photo_id}")).stem
            return output.getvalue(), f"{stem}.jpg"
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    if errors:
        raise GooglePhotoFrameError("Kunne ikke klargøre billedet til Google Photos: " + errors[-1])
    raise GooglePhotoFrameError(f"Billedfilen til {photo_id} kunne ikke findes.")


def _upload_new_media_item(token: str, album_id: str, photo_id: int) -> Dict[str, Any]:
    jpeg_bytes, filename = _render_photo_jpeg(photo_id)
    upload_response = requests.post(
        UPLOAD_URL,
        headers={
            **_google_headers(token),
            "Content-Type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": "image/jpeg",
            "X-Goog-Upload-Protocol": "raw",
        },
        data=jpeg_bytes,
        timeout=60,
    )
    if not upload_response.ok:
        raise GooglePhotoFrameError(_error_message(upload_response, "Google afviste billeduploaden."))
    upload_token = (upload_response.text or "").strip()
    if not upload_token:
        raise GooglePhotoFrameError("Google returnerede ikke et upload-token.")

    create_response = requests.post(
        f"{PHOTOS_API}/mediaItems:batchCreate",
        headers={**_google_headers(token), "Content-Type": "application/json"},
        json={
            "albumId": album_id,
            "newMediaItems": [
                {
                    "description": f"FjordLens photo #{photo_id}",
                    "simpleMediaItem": {"uploadToken": upload_token, "fileName": filename},
                }
            ],
        },
        timeout=30,
    )
    if not create_response.ok:
        raise GooglePhotoFrameError(_error_message(create_response, "Kunne ikke oprette billedet i Google Photos."))
    payload = create_response.json()
    results = payload.get("newMediaItemResults") or []
    result = results[0] if results else {}
    status = result.get("status") or {}
    if status.get("code") not in (None, 0):
        raise GooglePhotoFrameError(str(status.get("message") or "Google Photos kunne ikke oprette billedet."))
    media_item = result.get("mediaItem") or {}
    media_id = str(media_item.get("id") or "")
    if not media_id:
        raise GooglePhotoFrameError("Google Photos returnerede ikke et media-item-id.")
    return {
        "media_item_id": media_id,
        "filename": filename,
        "product_url": str(media_item.get("productUrl") or ""),
        "uploaded_at": _now_iso(),
        "in_album": True,
    }


def _add_existing_media_item(token: str, album_id: str, media_item_id: str) -> None:
    response = requests.post(
        f"{PHOTOS_API}/albums/{album_id}:batchAddMediaItems",
        headers={**_google_headers(token), "Content-Type": "application/json"},
        json={"mediaItemIds": [media_item_id]},
        timeout=20,
    )
    if not response.ok:
        raise GooglePhotoFrameError(_error_message(response, "Kunne ikke tilføje det eksisterende Google-billede til albummet."))


def _remove_media_item(token: str, album_id: str, media_item_id: str) -> None:
    response = requests.post(
        f"{PHOTOS_API}/albums/{album_id}:batchRemoveMediaItems",
        headers={**_google_headers(token), "Content-Type": "application/json"},
        json={"mediaItemIds": [media_item_id]},
        timeout=20,
    )
    if not response.ok:
        raise GooglePhotoFrameError(_error_message(response, "Kunne ikke fjerne billedet fra Google Photo Frame-albummet."))


def _coerce_photo_ids(values: Iterable[Any], max_items: int = 25) -> List[int]:
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
    if len(result) > max_items:
        raise GooglePhotoFrameError(f"Send højst {max_items} billeder pr. batch.")
    return result


def _public_status(state: Dict[str, Any]) -> Dict[str, Any]:
    synced = state.get("synced") or {}
    active = [entry for entry in synced.values() if isinstance(entry, dict) and entry.get("in_album", True)]
    return {
        "configured": _configured(state),
        "connected": _connected(state),
        "can_admin": _is_admin(),
        "client_id": _effective_client_id(state),
        "redirect_uri": _oauth_redirect_uri(state),
        "album_title": str(state.get("album_title") or DEFAULT_ALBUM_TITLE),
        "album_id": str(state.get("album_id") or ""),
        "album_url": str(state.get("album_url") or ""),
        "synced_count": len(active),
        "uploaded_count": len(synced),
        "remote_count": state.get("remote_count"),
        "last_sync_at": str(state.get("last_sync_at") or ""),
        "last_error": str(state.get("last_error") or ""),
    }


def _remember_error(message: str) -> None:
    def patch(state: Dict[str, Any]) -> None:
        state["last_error"] = str(message or "")[:1000]
    _mutate_state(patch)


@bp.get("/api/google-photo-frame/status")
@login_required
def status():
    state = _read_state()
    if request.args.get("refresh") == "1" and _connected(state) and _configured(state):
        try:
            token = _refresh_access_token(state)
            _ensure_album(token, verify_existing=True)
            state = _read_state()
        except Exception as exc:
            _remember_error(str(exc))
            state = _read_state()
    return jsonify({"ok": True, "item": _public_status(state)})


@bp.post("/api/google-photo-frame/config")
@login_required
def save_config():
    _require_admin()
    payload = request.get_json(silent=True) or {}
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    redirect_uri = str(payload.get("redirect_uri") or "").strip()
    album_title = str(payload.get("album_title") or DEFAULT_ALBUM_TITLE).strip() or DEFAULT_ALBUM_TITLE
    if not client_id and not os.getenv("GOOGLE_PHOTOS_CLIENT_ID"):
        return jsonify({"ok": False, "error": "Google OAuth client-id mangler."}), 400

    def patch(state: Dict[str, Any]) -> None:
        old_client_id = str(state.get("client_id") or "")
        if client_id:
            state["client_id"] = client_id
        if client_secret:
            state["client_secret"] = client_secret
        if redirect_uri:
            state["redirect_uri"] = redirect_uri
        else:
            state["redirect_uri"] = ""
        state["album_title"] = album_title
        if old_client_id and client_id and old_client_id != client_id:
            state["access_token"] = ""
            state["refresh_token"] = ""
            state["token_expires_at"] = 0
            state["album_id"] = ""
            state["album_url"] = ""
            state["remote_count"] = None
            for entry in state.get("synced", {}).values():
                if isinstance(entry, dict):
                    entry["in_album"] = False
        state["last_error"] = ""

    state = _mutate_state(patch)
    if not _effective_client_secret(state):
        return jsonify({"ok": False, "error": "Google OAuth client-secret mangler."}), 400
    return jsonify({"ok": True, "item": _public_status(state)})


@bp.get("/api/google-photo-frame/oauth/start")
@login_required
def oauth_start():
    _require_admin()
    state = _read_state()
    if not _configured(state):
        return Response("Google OAuth er ikke konfigureret endnu.", status=400, mimetype="text/plain")
    nonce = secrets.token_urlsafe(32)
    session["google_photo_frame_oauth_state"] = nonce
    params = {
        "client_id": _effective_client_id(state),
        "redirect_uri": _oauth_redirect_uri(state),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


def _oauth_result_page(ok: bool, message: str) -> Response:
    safe_message = html.escape(message)
    status_label = "Forbundet" if ok else "Fejl"
    color = "#1f9d68" if ok else "#c44545"
    payload = "connected" if ok else "error"
    body = f"""<!doctype html>
<html lang=\"da\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Google Photo Frame</title></head>
<body style=\"font-family:system-ui;background:#0c151a;color:#eef6f7;display:grid;place-items:center;min-height:100vh;margin:0\">
<div style=\"max-width:520px;padding:28px;text-align:center\"><h1 style=\"color:{color}\">{status_label}</h1><p>{safe_message}</p><p>Du kan lukke dette vindue.</p></div>
<script>
try {{ if (window.opener) window.opener.postMessage({{type:'fjordlens-google-photo-frame',status:'{payload}'}}, window.location.origin); }} catch (_) {{}}
if ({str(ok).lower()}) setTimeout(() => window.close(), 700);
</script></body></html>"""
    return Response(body, status=200 if ok else 400, mimetype="text/html")


@bp.get("/api/google-photo-frame/oauth/callback")
@login_required
def oauth_callback():
    _require_admin()
    expected = str(session.pop("google_photo_frame_oauth_state", "") or "")
    supplied = str(request.args.get("state") or "")
    if not expected or not secrets.compare_digest(expected, supplied):
        return _oauth_result_page(False, "OAuth state kunne ikke valideres. Start forbindelsen igen fra FjordLens.")
    if request.args.get("error"):
        return _oauth_result_page(False, str(request.args.get("error_description") or request.args.get("error")))
    code = str(request.args.get("code") or "")
    if not code:
        return _oauth_result_page(False, "Google returnerede ingen autorisationskode.")

    state = _read_state()
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": _effective_client_id(state),
            "client_secret": _effective_client_secret(state),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _oauth_redirect_uri(state),
        },
        timeout=20,
    )
    if not response.ok:
        message = _error_message(response, "Kunne ikke udveksle Google OAuth-koden.")
        _remember_error(message)
        return _oauth_result_page(False, message)
    token_data = response.json()
    access_token = str(token_data.get("access_token") or "")
    refresh_token = str(token_data.get("refresh_token") or state.get("refresh_token") or "")
    if not access_token:
        return _oauth_result_page(False, "Google returnerede ikke et access-token.")

    def patch(current: Dict[str, Any]) -> None:
        current["access_token"] = access_token
        current["refresh_token"] = refresh_token
        current["token_expires_at"] = time.time() + int(token_data.get("expires_in") or 3600)
        current["token_scope"] = str(token_data.get("scope") or "")
        current["last_error"] = ""

    _mutate_state(patch)
    try:
        album_id, _, _ = _ensure_album(access_token, verify_existing=True)
        return _oauth_result_page(True, f"Google Photos er forbundet, og albummet er klar ({album_id}).")
    except Exception as exc:
        _remember_error(str(exc))
        return _oauth_result_page(False, f"Google blev forbundet, men Photo Frame-albummet kunne ikke klargøres: {exc}")


@bp.post("/api/google-photo-frame/disconnect")
@login_required
def disconnect():
    _require_admin()

    def patch(state: Dict[str, Any]) -> None:
        state["access_token"] = ""
        state["refresh_token"] = ""
        state["token_expires_at"] = 0
        state["token_scope"] = ""
        state["last_error"] = ""

    state = _mutate_state(patch)
    return jsonify({"ok": True, "item": _public_status(state)})


@bp.post("/api/google-photo-frame/photos/add")
@login_required
def add_photos():
    _require_admin()
    payload = request.get_json(silent=True) or {}
    try:
        photo_ids = _coerce_photo_ids(payload.get("photo_ids") or [], max_items=25)
    except GooglePhotoFrameError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not photo_ids:
        return jsonify({"ok": False, "error": "Vælg mindst ét billede."}), 400

    state = _read_state()
    if not _configured(state) or not _connected(state):
        return jsonify({"ok": False, "error": "Google Photo Frame er ikke forbundet endnu."}), 400

    added = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    try:
        token = _refresh_access_token(state)
        album_id, _, _ = _ensure_album(token, verify_existing=True)
    except Exception as exc:
        _remember_error(str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 502

    for photo_id in photo_ids:
        try:
            current = _read_state()
            entry = (current.get("synced") or {}).get(str(photo_id))
            if isinstance(entry, dict) and entry.get("media_item_id"):
                if entry.get("in_album", True):
                    skipped += 1
                    continue
                try:
                    _add_existing_media_item(token, album_id, str(entry["media_item_id"]))

                    def mark_added(s: Dict[str, Any], pid=str(photo_id)) -> None:
                        existing = s.setdefault("synced", {}).setdefault(pid, {})
                        existing["in_album"] = True
                        existing["added_at"] = _now_iso()
                        s["last_sync_at"] = _now_iso()
                        s["last_error"] = ""
                        if isinstance(s.get("remote_count"), int):
                            s["remote_count"] = int(s["remote_count"]) + 1

                    _mutate_state(mark_added)
                    added += 1
                    continue
                except Exception:
                    # The Google item may have been manually deleted. Re-upload below.
                    def forget_stale(s: Dict[str, Any], pid=str(photo_id)) -> None:
                        s.setdefault("synced", {}).pop(pid, None)
                    _mutate_state(forget_stale)

            new_entry = _upload_new_media_item(token, album_id, photo_id)

            def remember(s: Dict[str, Any], pid=str(photo_id), value=new_entry) -> None:
                s.setdefault("synced", {})[pid] = value
                s["last_sync_at"] = _now_iso()
                s["last_error"] = ""
                if isinstance(s.get("remote_count"), int):
                    s["remote_count"] = int(s["remote_count"]) + 1

            _mutate_state(remember)
            added += 1
        except Exception as exc:
            failed.append({"photo_id": photo_id, "error": str(exc)})

    final_state = _read_state()
    active_count = sum(1 for value in final_state.get("synced", {}).values() if isinstance(value, dict) and value.get("in_album", True))
    if failed:
        _remember_error(failed[0]["error"])
    return jsonify({
        "ok": not failed,
        "added": added,
        "skipped": skipped,
        "failed": failed,
        "synced_count": active_count,
    }), (207 if failed and (added or skipped) else (502 if failed else 200))


@bp.post("/api/google-photo-frame/photos/remove")
@login_required
def remove_photos():
    _require_admin()
    payload = request.get_json(silent=True) or {}
    try:
        photo_ids = _coerce_photo_ids(payload.get("photo_ids") or [], max_items=25)
    except GooglePhotoFrameError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not photo_ids:
        return jsonify({"ok": False, "error": "Vælg mindst ét billede."}), 400

    state = _read_state()
    if not _configured(state) or not _connected(state):
        return jsonify({"ok": False, "error": "Google Photo Frame er ikke forbundet endnu."}), 400
    try:
        token = _refresh_access_token(state)
        album_id, _, _ = _ensure_album(token, verify_existing=True)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    removed = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    for photo_id in photo_ids:
        current = _read_state()
        entry = (current.get("synced") or {}).get(str(photo_id))
        if not isinstance(entry, dict) or not entry.get("media_item_id") or not entry.get("in_album", True):
            skipped += 1
            continue
        try:
            _remove_media_item(token, album_id, str(entry["media_item_id"]))

            def mark_removed(s: Dict[str, Any], pid=str(photo_id)) -> None:
                existing = s.setdefault("synced", {}).get(pid)
                if isinstance(existing, dict):
                    existing["in_album"] = False
                    existing["removed_at"] = _now_iso()
                s["last_sync_at"] = _now_iso()
                s["last_error"] = ""
                if isinstance(s.get("remote_count"), int):
                    s["remote_count"] = max(0, int(s["remote_count"]) - 1)

            _mutate_state(mark_removed)
            removed += 1
        except Exception as exc:
            failed.append({"photo_id": photo_id, "error": str(exc)})

    final_state = _read_state()
    active_count = sum(1 for value in final_state.get("synced", {}).values() if isinstance(value, dict) and value.get("in_album", True))
    if failed:
        _remember_error(failed[0]["error"])
    return jsonify({
        "ok": not failed,
        "removed": removed,
        "skipped": skipped,
        "failed": failed,
        "synced_count": active_count,
        "note": "Billedet fjernes fra Photo Frame-albummet. Google Photos API'et sletter ikke den uploadede kopi fra biblioteket.",
    }), (207 if failed and (removed or skipped) else (502 if failed else 200))


def _inject_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-google-photo-frame-assets"
        if marker in text:
            return response
        css = f'<link id="{marker}" rel="stylesheet" href="/static/google_photo_frame.css?v=1">\n'
        js = '<script src="/static/google_photo_frame.js?v=1"></script>\n'
        if "</head>" in text:
            text = text.replace("</head>", css + "</head>", 1)
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def init_google_photo_frame(flask_app, core_module=None) -> None:
    global _core
    if core_module is None:
        import app as core_module  # local import avoids circular import during module load
    _core = core_module
    if "google_photo_frame" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
    if not flask_app.extensions.get("google_photo_frame_assets_registered"):
        flask_app.after_request(_inject_assets)
        flask_app.extensions["google_photo_frame_assets_registered"] = True
