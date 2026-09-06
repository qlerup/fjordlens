"""People-section UX and manager permissions for FjordLens."""
from __future__ import annotations

from functools import wraps

from flask_login import current_user


PEOPLE_FAST_ASSET = "/static/people_fast.js?v=2"


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
                or PEOPLE_FAST_ASSET in html
                or "</body>" not in html
            ):
                return response

            tag = f'<script src="{PEOPLE_FAST_ASSET}"></script>'
            response.set_data(html.replace("</body>", f"{tag}\n</body>", 1))
            response.headers["Content-Length"] = str(len(response.get_data()))
        except Exception:
            app.logger.exception("Could not inject People fast-loader asset")
        return response


def init_people_section(app) -> None:
    """Install People UX/access fixes once per Flask app."""
    if app.extensions.get("fjordlens_people_section_v3"):
        return

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

    _inject_people_fast_asset(app)
    app.extensions["fjordlens_people_section_v3"] = True
