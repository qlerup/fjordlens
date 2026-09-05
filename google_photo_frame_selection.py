from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import login_required

import google_photo_frame as gpf

bp = Blueprint("google_photo_frame_selection", __name__)


@bp.get("/api/google-photo-frame/selection")
@login_required
def google_photo_frame_selection():
    """Return FjordLens photo IDs currently tracked as present in the Google album."""
    state = gpf._read_state()
    synced = state.get("synced") or {}
    active_ids = []
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
    return jsonify({"ok": True, "photo_ids": active_ids})


def init_google_photo_frame_selection(app) -> None:
    if "google_photo_frame_selection" not in app.blueprints:
        app.register_blueprint(bp)
