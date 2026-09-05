from flask import Response, request
from flask_login import current_user


def _inject_share_link_defaults(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-share-link-defaults"
        if marker in text:
            return response
        js = f'<script id="{marker}" src="/static/share_link_defaults.js?v=1"></script>\n'
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def _install_manager_share_permission(flask_app) -> None:
    """Allow managers to create share links without widening other admin-only maintenance permissions."""
    if flask_app.extensions.get("manager_share_permission_registered"):
        return

    try:
        import app as core
        original = core._forbid_user_role_for_maintenance
    except Exception:
        return

    def share_aware_forbid():
        try:
            if request.path == "/api/shares" and request.method == "POST":
                role = str(getattr(current_user, "role", "") or "").strip().lower()
                if getattr(current_user, "is_authenticated", False) and role == "manager":
                    return None
        except Exception:
            pass
        return original()

    core._forbid_user_role_for_maintenance = share_aware_forbid
    flask_app.extensions["manager_share_permission_registered"] = True


def init_share_link_defaults(flask_app) -> None:
    if not flask_app.extensions.get("share_link_defaults_registered"):
        flask_app.after_request(_inject_share_link_defaults)
        flask_app.extensions["share_link_defaults_registered"] = True
    _install_manager_share_permission(flask_app)
