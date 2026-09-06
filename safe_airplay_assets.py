from flask import Response, request


def _inject_safe_airplay_assets(response: Response) -> Response:
    try:
        if request.path != "/" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        text = response.get_data(as_text=True)
        marker = "fjordlens-safe-airplay-assets"
        if marker in text:
            return response

        # The old cast_airplay injector also supplied the modal CSS. When its
        # JavaScript was disabled to avoid Safari freezes, the stylesheet was
        # accidentally disabled with it. Keep the lightweight clients, but
        # explicitly load the shared AirPlay/Cast styles here.
        css = '<link id="fjordlens-safe-airplay-css" rel="stylesheet" href="/static/cast_airplay.css?v=20260906-4">\n'
        scripts = (
            f'<script id="{marker}" src="/static/cast_airplay_safe.js?v=20260906-4"></script>\n'
            '<script src="/static/airplay_hls_safe.js?v=20260906-4"></script>\n'
        )
        if "</head>" in text:
            text = text.replace("</head>", css + "</head>", 1)
        if "</body>" in text:
            text = text.replace("</body>", scripts + "</body>", 1)
        response.set_data(text)
        response.headers.pop("Content-Length", None)
    except Exception:
        pass
    return response


def init_safe_airplay_assets(flask_app) -> None:
    if flask_app.extensions.get("safe_airplay_assets_registered"):
        return
    flask_app.after_request(_inject_safe_airplay_assets)
    flask_app.extensions["safe_airplay_assets_registered"] = True
