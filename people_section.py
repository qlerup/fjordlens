"""People-section UX and manager permissions for FjordLens."""
from __future__ import annotations

from functools import wraps

from flask import jsonify, request
from flask_login import current_user


PEOPLE_FAST_ASSET = "/static/people_fast.js?v=4"
PEOPLE_CACHE_ASSET = "/static/people_cache.js?v=1"


def _allow_manager_for_people_action(original):
    """Allow managers to use People content-management actions only."""

    @wraps(original)
    def view(*args, **kwargs):
        user = current_user._get_current_object()
        role = str(getattr(user, "role", "user") or "user").strip().lower()
        if role != "manager":
            return original(*args, **kwargs)

        # These existing People endpoints all start by calling the admin-only
        # maintenance guard. Reuse their tested bodies, but bypass that guard
        # only for a manager request dispatched through these wrapped endpoints.
        previous_role = getattr(user, "role", "manager")
        try:
            user.role = "admin"
            return original(*args, **kwargs)
        finally:
            user.role = previous_role

    return view


def _can_manage_people() -> bool:
    try:
        return bool(getattr(current_user, "can_manage_media", False))
    except Exception:
        return False


def _register_bulk_hide_route(app, fjordlens) -> None:
    """Register one bulk hide/unhide endpoint for People cards."""
    if "api_people_hide_bulk" in app.view_functions:
        return

    def api_people_hide_bulk():
        if not _can_manage_people():
            return jsonify({"ok": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        raw_ids = data.get("ids")
        if not isinstance(raw_ids, list):
            return jsonify({"ok": False, "error": "Missing ids"}), 400

        person_ids: list[int] = []
        seen: set[int] = set()
        for raw in raw_ids[:1000]:
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid in seen:
                continue
            seen.add(pid)
            person_ids.append(pid)

        if not person_ids:
            return jsonify({"ok": False, "error": "No valid person ids"}), 400

        hidden_raw = data.get("hidden", True)
        hidden = 0 if hidden_raw in (False, 0, "0", "false", "False") else 1
        placeholders = ",".join("?" for _ in person_ids)

        try:
            with fjordlens.closing(fjordlens.get_conn()) as conn:
                rows = conn.execute(
                    f"SELECT id FROM people WHERE id IN ({placeholders})",
                    person_ids,
                ).fetchall()
                existing_ids = [int(row["id"]) for row in rows]
                if existing_ids:
                    existing_placeholders = ",".join("?" for _ in existing_ids)
                    conn.execute(
                        f"UPDATE people SET hidden=? WHERE id IN ({existing_placeholders})",
                        [hidden, *existing_ids],
                    )
                    conn.commit()

            return jsonify(
                {
                    "ok": True,
                    "hidden": bool(hidden),
                    "updated": len(existing_ids),
                    "ids": existing_ids,
                }
            )
        except Exception as exc:
            app.logger.exception("Could not bulk-update People visibility")
            return jsonify({"ok": False, "error": str(exc)}), 500

    app.add_url_rule(
        "/api/people/hide-bulk",
        endpoint="api_people_hide_bulk",
        view_func=api_people_hide_bulk,
        methods=["POST"],
    )


def _inject_people_fast_asset(app) -> None:
    @app.after_request
    def inject_people_fast_asset(response):
        try:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type:
                return response

            html = response.get_data(as_text=True)
            # Only the main FjordLens shell contains both markers.
            if (
                'data-view="personer"' not in html
                or "app.js" not in html
                or "</body>" not in html
            ):
                return response

            # Remove older injected People helper tags, then inject the current
            # versions in dependency order: UI helpers first, instant cache second.
            import re
            html = re.sub(
                r'<script\s+src="/static/people_fast\.js\?v=\d+"></script>\s*',
                "",
                html,
                flags=re.IGNORECASE,
            )
            html = re.sub(
                r'<script\s+src="/static/people_cache\.js\?v=\d+"></script>\s*',
                "",
                html,
                flags=re.IGNORECASE,
            )
            tags = (
                f'<script src="{PEOPLE_FAST_ASSET}"></script>\n'
                f'<script src="{PEOPLE_CACHE_ASSET}"></script>'
            )
            response.set_data(html.replace("</body>", f"{tags}\n</body>", 1))
            response.headers["Content-Length"] = str(len(response.get_data()))
        except Exception:
            app.logger.exception("Could not inject People helper assets")
        return response


def init_people_section(app) -> None:
    """Install People UX/access fixes once per Flask app."""
    if app.extensions.get("fjordlens_people_section_v5"):
        return

    import app as fjordlens

    # Managers already have can_manage_media and full media-library visibility.
    # Give them the People-specific content actions while keeping scan/logs/
    # settings/user administration behind the existing admin-only guard.
    for endpoint in (
        "api_people_train_one",
        "api_people_train_all",
        "api_faces_match_unknown",
        "api_people_hide",
        "api_people_rename",
    ):
        original = app.view_functions.get(endpoint)
        if original is not None:
            app.view_functions[endpoint] = _allow_manager_for_people_action(original)

    _register_bulk_hide_route(app, fjordlens)
    _inject_people_fast_asset(app)
    app.extensions["fjordlens_people_section_v5"] = True
