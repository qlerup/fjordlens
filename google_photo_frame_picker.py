from flask import Response, request


def _inject_picker_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-google-photo-frame-picker-assets"
        if marker in text:
            return response
        css = f'<link id="{marker}" rel="stylesheet" href="/static/google_photo_frame_picker.css?v=1">\n'
        js = '<script src="/static/google_photo_frame_picker.js?v=1"></script>\n'
        if "</head>" in text:
            text = text.replace("</head>", css + "</head>", 1)
        if "</body>" in text:
            text = text.replace("</body>", js + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def init_google_photo_frame_picker(flask_app) -> None:
    if not flask_app.extensions.get("google_photo_frame_picker_assets_registered"):
        flask_app.after_request(_inject_picker_assets)
        flask_app.extensions["google_photo_frame_picker_assets_registered"] = True
