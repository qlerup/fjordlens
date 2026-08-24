import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import app as fjordlens


class VideoThumbFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.thumbs = root / "thumbs"
        self.thumbs.mkdir()
        self.previous_thumb_dir = fjordlens.THUMB_DIR
        fjordlens.THUMB_DIR = self.thumbs

    def tearDown(self):
        fjordlens.THUMB_DIR = self.previous_thumb_dir
        self.tempdir.cleanup()

    def test_falls_back_to_first_frame_when_seeked_attempts_fail(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if "-ss" in command:
                # A video shorter than the seek target produces no frame.
                raise subprocess.CalledProcessError(234, command, stderr="seek past end")
            Image.new("RGB", (8, 8), "red").save(Path(command[-1]), format="JPEG")
            return SimpleNamespace(returncode=0)

        with patch.object(fjordlens.subprocess, "run", side_effect=fake_run):
            thumb_name = fjordlens._make_video_thumb(
                Path("short_clip.mp4"), "uploads/originals/short_clip.mp4", 0.0, 100
            )

        self.assertIsNotNone(thumb_name)
        self.assertTrue((self.thumbs / thumb_name).exists())
        # Both seeked attempts must be tried before the no-seek fallback succeeds.
        self.assertEqual(len(calls), 3)
        self.assertIn("-ss", calls[0])
        self.assertIn("-ss", calls[1])
        self.assertNotIn("-ss", calls[2])

    def test_returns_none_and_logs_when_every_attempt_fails(self):
        def fake_run(command, **kwargs):
            raise subprocess.CalledProcessError(234, command, stderr="no frames found")

        with (
            patch.object(fjordlens.subprocess, "run", side_effect=fake_run),
            patch.object(fjordlens, "log_event") as log_event,
        ):
            thumb_name = fjordlens._make_video_thumb(
                Path("broken.mp4"), "uploads/originals/broken.mp4", 0.0, 100
            )

        self.assertIsNone(thumb_name)
        log_event.assert_called_once()
        self.assertEqual(log_event.call_args.args[0], "error")


if __name__ == "__main__":
    unittest.main()
