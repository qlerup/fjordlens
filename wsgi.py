from flask import request

from app import app as application
from google_photo_frame import init_google_photo_frame
from privacy import init_privacy_page

# Register public/support pages and optional integrations without touching filesystem or DB at startup.
init_privacy_page(application)

# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)


@application.after_request
def inject_google_photo_frame_picker(response):
    """Load the in-place Google picker on the main FjordLens UI."""
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-google-photo-frame-picker"
        if marker in text:
            return response
        script = (
            f'<script id="{marker}" '
            'src="/static/google_photo_frame_picker.js?v=1"></script>\n'
        )
        if "</body>" in text:
            text = text.replace("</body>", script + "</body>", 1)
            response.set_data(text)
            response.headers.pop("Content-Length", None)
    except Exception:
        # The picker is an optional UI enhancement and must never break app startup/rendering.
        pass
    return response


# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
