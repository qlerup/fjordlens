from flask import Blueprint, render_template

bp = Blueprint("privacy", __name__)


@bp.get("/privacy")
def privacy_policy():
    """Public privacy policy used by FjordLens and Google OAuth consent."""
    return render_template("privacy.html")


def init_privacy_page(flask_app) -> None:
    if "privacy" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
