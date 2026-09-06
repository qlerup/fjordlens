from flask import Response, request


def _inject_airplay_seek_fix(response: Response) -> Response:
    try:
        if request.endpoint != "airplay_controls.control_player":
            return response
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-airplay-seek-fix"
        if marker in text:
            return response
        script = f'<script id="{marker}" src="/static/airplay_seek_fix.js?v=20260906-1"></script>\n'
        if "</body>" in text:
            text = text.replace("</body>", script + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def init_airplay_seek_fix(flask_app) -> None:
    if flask_app.extensions.get("airplay_seek_fix_registered"):
        return
    flask_app.after_request(_inject_airplay_seek_fix)
    flask_app.extensions["airplay_seek_fix_registered"] = True
