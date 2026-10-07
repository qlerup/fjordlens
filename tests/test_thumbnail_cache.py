import os
import unittest
from unittest.mock import patch

from flask import Flask

from thumbnail_cache import init_thumbnail_cache


class ThumbnailCacheTests(unittest.TestCase):
    def app(self):
        app = Flask(__name__)

        @app.get("/api/thumbs/photo.jpg")
        def thumbnail():
            return ("jpeg", 200, {
                "Content-Type": "image/jpeg",
                "Cache-Control": "private, no-store",
            })

        @app.get("/api/face-thumb/12")
        def face_thumbnail():
            return ("jpeg", 200, {
                "Content-Type": "image/jpeg",
                "Cache-Control": "private, no-store",
            })

        @app.get("/api/face-thumb/status/12")
        def face_status():
            return {"ready": True}

        @app.get("/api/people/video-frame/12")
        def video_frame():
            return ("jpeg", 200, {
                "Content-Type": "image/jpeg",
                "Cache-Control": "private, no-cache",
            })

        @app.get("/api/not-a-thumb")
        def regular():
            return ("ok", 200, {"Cache-Control": "no-store"})

        init_thumbnail_cache(app)
        return app

    def test_thumbnail_responses_are_cached_privately(self):
        client = self.app().test_client()
        for path in (
            "/api/thumbs/photo.jpg",
            "/api/face-thumb/12",
            "/api/people/video-frame/12",
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(
                    response.headers["Cache-Control"],
                    "private, max-age=21600, must-revalidate",
                )
                vary = response.headers.get("Vary", "")
                self.assertIn("Cookie", vary)
                self.assertIn("Authorization", vary)

    def test_status_and_non_thumbnail_routes_keep_existing_cache_policy(self):
        client = self.app().test_client()
        self.assertNotIn("max-age", client.get("/api/face-thumb/status/12").headers.get("Cache-Control", ""))
        self.assertEqual(client.get("/api/not-a-thumb").headers["Cache-Control"], "no-store")

    def test_zero_seconds_disables_override(self):
        with patch.dict(os.environ, {"FJORDLENS_THUMB_CACHE_MAX_AGE": "0"}):
            client = self.app().test_client()
            self.assertIn("no-store", client.get("/api/thumbs/photo.jpg").headers["Cache-Control"])

    def test_configurable_cache_window_is_capped(self):
        with patch.dict(os.environ, {"FJORDLENS_THUMB_CACHE_MAX_AGE": "99999999"}):
            client = self.app().test_client()
            self.assertEqual(
                client.get("/api/thumbs/photo.jpg").headers["Cache-Control"],
                "private, max-age=604800, must-revalidate",
            )


if __name__ == "__main__":
    unittest.main()
