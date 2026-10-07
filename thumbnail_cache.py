"""Browser/device caching for authenticated FjordLens thumbnail responses."""
import os

from flask import request


DEFAULT_THUMBNAIL_CACHE_SECONDS = 6 * 60 * 60
MAX_THUMBNAIL_CACHE_SECONDS = 7 * 24 * 60 * 60


def _cache_seconds():
    raw = os.environ.get(
        "FJORDLENS_THUMB_CACHE_MAX_AGE",
        str(DEFAULT_THUMBNAIL_CACHE_SECONDS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_THUMBNAIL_CACHE_SECONDS
    return max(0, min(value, MAX_THUMBNAIL_CACHE_SECONDS))


def _is_thumbnail_request(path):
    path = str(path or "")
    if path.startswith("/api/thumbs/"):
        return True
    if path.startswith("/api/people/video-frame/"):
        return True
    if path.startswith("/api/face-thumb/") and not path.startswith("/api/face-thumb/status/"):
        return True
    return False


def init_thumbnail_cache(app):
    """Allow private browser caching for thumbnail/image preview endpoints."""
    if app.extensions.get("fjordlens_thumbnail_cache_registered"):
        return
    app.extensions["fjordlens_thumbnail_cache_registered"] = True

    max_age = _cache_seconds()
    if max_age <= 0:
        return

    @app.after_request
    def _cache_thumbnail_response(response):
        if request.method not in {"GET", "HEAD"}:
            return response
        if response.status_code not in {200, 304}:
            return response
        if not _is_thumbnail_request(request.path):
            return response
        if response.status_code == 200:
            mimetype = str(response.mimetype or "")
            if mimetype and not mimetype.startswith("image/"):
                return response

        # The underlying endpoints already enforce authentication and folder ACLs.
        # Keep the cache private to this browser and vary by auth context, while
        # avoiding a full thumbnail download on every navigation/page refresh.
        response.headers["Cache-Control"] = (
            f"private, max-age={max_age}, must-revalidate"
        )
        response.vary.add("Cookie")
        response.vary.add("Authorization")
        return response
