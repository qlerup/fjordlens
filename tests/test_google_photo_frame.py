import os
import stat
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from flask import Flask, Response
from PIL import Image

import google_photo_frame as gpf


class GooglePhotoFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.old_core = gpf._core
        self.fake_core = SimpleNamespace(
            DATA_DIR=root / "data",
            UPLOAD_DIR=root / "uploads",
            PHOTO_DIR=root / "photos",
            THUMB_DIR=root / "thumbs",
        )
        gpf._core = self.fake_core

    def tearDown(self):
        gpf._core = self.old_core
        self.tmp.cleanup()

    def test_state_is_persisted_without_exposing_secret_fields(self):
        def patch(state):
            state["client_id"] = "client-id"
            state["client_secret"] = "secret-value"
            state["access_token"] = "access-value"
            state["refresh_token"] = "refresh-value"

        stored = gpf._mutate_state(patch)
        self.assertEqual(stored["client_secret"], "secret-value")
        self.assertEqual(gpf._read_state()["client_id"], "client-id")

        mode = stat.S_IMODE(gpf._state_path().stat().st_mode)
        self.assertEqual(mode, 0o600)

        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/"):
            public = gpf._public_status(gpf._read_state())
        self.assertEqual(public["client_id"], "client-id")
        self.assertNotIn("client_secret", public)
        self.assertNotIn("access_token", public)
        self.assertNotIn("refresh_token", public)

    def test_photo_id_coercion_deduplicates_and_enforces_batch_limit(self):
        self.assertEqual(gpf._coerce_photo_ids(["4", 4, 0, -1, "bad", 7]), [4, 7])
        with self.assertRaises(gpf.GooglePhotoFrameError):
            gpf._coerce_photo_ids(range(1, 27), max_items=25)

    def test_render_photo_creates_optimized_jpeg(self):
        source = Path(self.tmp.name) / "large.png"
        Image.new("RGB", (3200, 1800), "white").save(source)
        row = {"id": 9, "rel_path": "x", "filename": "family.png", "ext": ".png", "thumb_name": None}

        old_edge = os.environ.get("GOOGLE_PHOTO_FRAME_MAX_EDGE")
        os.environ["GOOGLE_PHOTO_FRAME_MAX_EDGE"] = "1200"
        try:
            with mock.patch.object(gpf, "_photo_row", return_value=row), mock.patch.object(gpf, "_candidate_photo_paths", return_value=[source]):
                payload, filename = gpf._render_photo_jpeg(9)
        finally:
            if old_edge is None:
                os.environ.pop("GOOGLE_PHOTO_FRAME_MAX_EDGE", None)
            else:
                os.environ["GOOGLE_PHOTO_FRAME_MAX_EDGE"] = old_edge

        self.assertEqual(filename, "family.jpg")
        with Image.open(BytesIO(payload)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 1200)

    def test_asset_injection_is_idempotent(self):
        app = Flask(__name__)
        with app.test_request_context("/"):
            first = gpf._inject_assets(Response("<html><head></head><body>ok</body></html>", mimetype="text/html"))
            second = gpf._inject_assets(first)
        text = second.get_data(as_text=True)
        self.assertEqual(text.count("fjordlens-google-photo-frame-assets"), 1)
        self.assertEqual(text.count("google_photo_frame.js"), 1)


if __name__ == "__main__":
    unittest.main()
