from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

import google_photo_frame as gpf

bp = Blueprint("google_photo_frame_selection", __name__)


def _can_manage() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    return bool(getattr(current_user, "is_admin", False) or role in {"admin", "manager"})


def _require_manage() -> None:
    if not _can_manage():
        abort(403)


def _active_ids(state: Dict[str, Any]) -> List[int]:
    synced = state.get("synced") or {}
    active_ids: List[int] = []
    for raw_id, entry in synced.items():
        if not isinstance(entry, dict) or not entry.get("in_album", True):
            continue
        try:
            photo_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if photo_id > 0:
            active_ids.append(photo_id)
    active_ids.sort()
    return active_ids


@bp.get("/api/google-photo-frame/selection")
@login_required
def google_photo_frame_selection():
    """Shared selection for all admins/managers."""
    _require_manage()
    state = gpf._read_state()
    return jsonify({"ok": True, "photo_ids": _active_ids(state), "can_manage": True})


def _prepare_ids():
    payload = request.get_json(silent=True) or {}
    try:
        photo_ids = gpf._coerce_photo_ids(payload.get("photo_ids") or [], max_items=25)
    except gpf.GooglePhotoFrameError as exc:
        return None, (jsonify({"ok": False, "error": str(exc)}), 400)
    if not photo_ids:
        return None, (jsonify({"ok": False, "error": "Vælg mindst ét billede."}), 400)
    return photo_ids, None


@bp.post("/api/google-photo-frame/manage/photos/add")
@login_required
def manager_add_photos():
    _require_manage()
    photo_ids, error = _prepare_ids()
    if error:
        return error

    state = gpf._read_state()
    if not gpf._configured(state) or not gpf._connected(state):
        return jsonify({"ok": False, "error": "Google Photo Frame er ikke forbundet endnu."}), 400

    added = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    try:
        token = gpf._refresh_access_token(state)
        album_id, _, _ = gpf._ensure_album(token, verify_existing=True)
    except Exception as exc:
        gpf._remember_error(str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 502

    for photo_id in photo_ids:
        try:
            current = gpf._read_state()
            entry = (current.get("synced") or {}).get(str(photo_id))
            if isinstance(entry, dict) and entry.get("media_item_id"):
                if entry.get("in_album", True):
                    skipped += 1
                    continue
                try:
                    gpf._add_existing_media_item(token, album_id, str(entry["media_item_id"]))

                    def mark_added(s: Dict[str, Any], pid=str(photo_id)) -> None:
                        existing = s.setdefault("synced", {}).setdefault(pid, {})
                        existing["in_album"] = True
                        existing["added_at"] = gpf._now_iso()
                        s["last_sync_at"] = gpf._now_iso()
                        s["last_error"] = ""
                        if isinstance(s.get("remote_count"), int):
                            s["remote_count"] = int(s["remote_count"]) + 1

                    gpf._mutate_state(mark_added)
                    added += 1
                    continue
                except Exception:
                    def forget_stale(s: Dict[str, Any], pid=str(photo_id)) -> None:
                        s.setdefault("synced", {}).pop(pid, None)
                    gpf._mutate_state(forget_stale)

            new_entry = gpf._upload_new_media_item(token, album_id, photo_id)

            def remember(s: Dict[str, Any], pid=str(photo_id), value=new_entry) -> None:
                s.setdefault("synced", {})[pid] = value
                s["last_sync_at"] = gpf._now_iso()
                s["last_error"] = ""
                if isinstance(s.get("remote_count"), int):
                    s["remote_count"] = int(s["remote_count"]) + 1

            gpf._mutate_state(remember)
            added += 1
        except Exception as exc:
            failed.append({"photo_id": photo_id, "error": str(exc)})

    final_state = gpf._read_state()
    active_count = len(_active_ids(final_state))
    if failed:
        gpf._remember_error(failed[0]["error"])
    return jsonify({"ok": not failed, "added": added, "skipped": skipped, "failed": failed, "synced_count": active_count}), (207 if failed and (added or skipped) else (502 if failed else 200))


@bp.post("/api/google-photo-frame/manage/photos/remove")
@login_required
def manager_remove_photos():
    _require_manage()
    photo_ids, error = _prepare_ids()
    if error:
        return error

    state = gpf._read_state()
    if not gpf._configured(state) or not gpf._connected(state):
        return jsonify({"ok": False, "error": "Google Photo Frame er ikke forbundet endnu."}), 400
    try:
        token = gpf._refresh_access_token(state)
        album_id, _, _ = gpf._ensure_album(token, verify_existing=True)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    removed = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    for photo_id in photo_ids:
        current = gpf._read_state()
        entry = (current.get("synced") or {}).get(str(photo_id))
        if not isinstance(entry, dict) or not entry.get("media_item_id") or not entry.get("in_album", True):
            skipped += 1
            continue
        try:
            gpf._remove_media_item(token, album_id, str(entry["media_item_id"]))

            def mark_removed(s: Dict[str, Any], pid=str(photo_id)) -> None:
                existing = s.setdefault("synced", {}).get(pid)
                if isinstance(existing, dict):
                    existing["in_album"] = False
                    existing["removed_at"] = gpf._now_iso()
                s["last_sync_at"] = gpf._now_iso()
                s["last_error"] = ""
                if isinstance(s.get("remote_count"), int):
                    s["remote_count"] = max(0, int(s["remote_count"]) - 1)

            gpf._mutate_state(mark_removed)
            removed += 1
        except Exception as exc:
            failed.append({"photo_id": photo_id, "error": str(exc)})

    final_state = gpf._read_state()
    active_count = len(_active_ids(final_state))
    if failed:
        gpf._remember_error(failed[0]["error"])
    return jsonify({"ok": not failed, "removed": removed, "skipped": skipped, "failed": failed, "synced_count": active_count}), (207 if failed and (removed or skipped) else (502 if failed else 200))


def init_google_photo_frame_selection(app) -> None:
    if "google_photo_frame_selection" not in app.blueprints:
        app.register_blueprint(bp)
