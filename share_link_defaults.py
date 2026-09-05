from flask import Response, request


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


def init_share_link_defaults(flask_app) -> None:
    if not flask_app.extensions.get("share_link_defaults_registered"):
        flask_app.after_request(_inject_share_link_defaults)
        flask_app.extensions["share_link_defaults_registered"] = True
