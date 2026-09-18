import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as fjordlens
from convert_service import app as convert_worker


class MovConversionTests(unittest.TestCase):
    def test_probe_prefers_aac_and_does_not_select_apac(self):
        probe_result = SimpleNamespace(
            stdout=json.dumps({
                "streams": [
                    {"index": 1, "codec_name": "apac"},
                    {"index": 2, "codec_name": "aac"},
                ]
            })
        )
        decoder_result = SimpleNamespace(stdout=" A..... aac AAC decoder\n")

        with (
            patch.object(fjordlens.shutil, "which", return_value="ffprobe"),
            patch.object(fjordlens.subprocess, "run", side_effect=[probe_result, decoder_result]) as run,
        ):
            selected = fjordlens._probe_mov_audio_stream(Path("iphone.mov"), "ffmpeg")

        self.assertEqual(selected, 2)
        self.assertIn("-decoders", run.call_args_list[1].args[0])
        self.assertEqual(run.call_count, 2)

    def test_probe_uses_first_other_decodable_stream(self):
        probe_result = SimpleNamespace(
            stdout=json.dumps({
                "streams": [
                    {"index": 1, "codec_name": "apac"},
                    {"index": 3, "codec_name": "alac"},
                ]
            })
        )
        decoders = SimpleNamespace(stdout=" A..... alac ALAC decoder\n")

        with (
            patch.object(fjordlens.shutil, "which", return_value="ffprobe"),
            patch.object(
                fjordlens.subprocess, "run",
                side_effect=[probe_result, decoders],
            ),
        ):
            selected = fjordlens._probe_mov_audio_stream(Path("iphone.mov"), "ffmpeg")

        self.assertEqual(selected, 3)

    def test_conversion_without_decodable_audio_maps_video_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            dst = root / "iphone.mp4"
            src.write_bytes(b"mov")

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.object(fjordlens.shutil, "which", return_value="ffmpeg"),
                patch.object(fjordlens, "_probe_mov_audio_stream", return_value=None),
                patch.object(fjordlens, "_mov_nvenc_available", return_value=False),
                patch.object(fjordlens.subprocess, "run", side_effect=fake_run) as run,
            ):
                fjordlens._mov_to_mp4(src, dst)

            output_exists = dst.exists()

        command = run.call_args.args[0]
        self.assertIn("-an", command)
        self.assertIn("0:v:0", command)
        self.assertNotIn("0:a?", command)
        self.assertEqual(command[command.index("-map_metadata") + 1], "0")
        self.assertTrue(output_exists)

    def test_conversion_prefers_nvenc_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            dst = root / "iphone.mp4"
            src.write_bytes(b"mov")

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.object(fjordlens.shutil, "which", return_value="ffmpeg"),
                patch.object(fjordlens, "_probe_mov_audio_stream", return_value=2),
                patch.object(fjordlens, "_mov_nvenc_available", return_value=True),
                patch.object(fjordlens.subprocess, "run", side_effect=fake_run) as run,
            ):
                fjordlens._mov_to_mp4(src, dst)

            command = run.call_args.args[0]
            self.assertIn("h264_nvenc", command)
            self.assertNotIn("libx264", command)
            self.assertIn("-cq", command)
            self.assertTrue(dst.exists())

    def test_nvenc_failure_retries_with_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            dst = root / "iphone.mp4"
            src.write_bytes(b"mov")

            gpu_error = subprocess.CalledProcessError(
                1, ["ffmpeg"], stderr="Cannot load libnvidia-encode.so.1"
            )

            def cpu_success(command, **kwargs):
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.object(fjordlens.shutil, "which", return_value="ffmpeg"),
                patch.object(fjordlens, "_probe_mov_audio_stream", return_value=2),
                patch.object(fjordlens, "_mov_nvenc_available", return_value=True),
                patch.object(fjordlens.subprocess, "run") as run,
            ):
                calls = {"count": 0}

                def run_side_effect(command, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise gpu_error
                    return cpu_success(command, **kwargs)

                run.side_effect = run_side_effect
                fjordlens._mov_to_mp4(src, dst)

            self.assertIn("h264_nvenc", run.call_args_list[0].args[0])
            self.assertIn("libx264", run.call_args_list[1].args[0])
            self.assertTrue(dst.exists())

    def test_worker_nvdec_command_keeps_frames_on_gpu_for_nvenc(self):
        command = convert_worker._mov_command(
            "ffmpeg",
            Path("/uploads/originals/iphone.mov"),
            Path("/uploads/converted/iphone.mp4"),
            2,
            use_nvenc=True,
            use_nvdec=True,
        )

        self.assertIn("-hwaccel", command)
        self.assertEqual(command[command.index("-hwaccel") + 1], "cuda")
        self.assertIn("-hwaccel_output_format", command)
        self.assertEqual(command[command.index("-hwaccel_output_format") + 1], "cuda")
        self.assertLess(command.index("-hwaccel"), command.index("-i"))
        self.assertIn("h264_nvenc", command)
        self.assertNotIn("-pix_fmt", command)

    def test_worker_nvdec_failure_retries_cpu_decode_with_nvenc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            dst = root / "iphone.mp4"
            src.write_bytes(b"mov")

            first_error = subprocess.CalledProcessError(
                1,
                ["ffmpeg"],
                stderr="CUDA hwaccel failed",
            )

            def run_side_effect(command, **kwargs):
                if "-hwaccel" in command:
                    raise first_error
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.object(convert_worker.shutil, "which", return_value="ffmpeg"),
                patch.object(convert_worker, "_probe_audio_stream", return_value=2),
                patch.object(convert_worker, "_nvenc_available", return_value=True),
                patch.object(convert_worker, "_nvdec_available", return_value=True),
                patch.object(convert_worker.subprocess, "run", side_effect=run_side_effect) as run,
            ):
                engine = convert_worker._convert_mov(src, dst)

            self.assertEqual(engine, "nvenc")
            self.assertIn("-hwaccel", run.call_args_list[0].args[0])
            self.assertNotIn("-hwaccel", run.call_args_list[1].args[0])
            self.assertIn("h264_nvenc", run.call_args_list[1].args[0])
            self.assertTrue(dst.exists())

    def test_worker_nvdec_and_nvenc_failure_retries_full_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            dst = root / "iphone.mp4"
            src.write_bytes(b"mov")

            calls = {"count": 0}

            def run_side_effect(command, **kwargs):
                calls["count"] += 1
                if calls["count"] <= 2:
                    raise subprocess.CalledProcessError(
                        1,
                        command,
                        stderr="GPU path failed",
                    )
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.object(convert_worker.shutil, "which", return_value="ffmpeg"),
                patch.object(convert_worker, "_probe_audio_stream", return_value=None),
                patch.object(convert_worker, "_nvenc_available", return_value=True),
                patch.object(convert_worker, "_nvdec_available", return_value=True),
                patch.object(convert_worker.subprocess, "run", side_effect=run_side_effect) as run,
            ):
                engine = convert_worker._convert_mov(src, dst)

            self.assertEqual(engine, "cpu")
            self.assertIn("-hwaccel", run.call_args_list[0].args[0])
            self.assertIn("h264_nvenc", run.call_args_list[1].args[0])
            self.assertIn("libx264", run.call_args_list[2].args[0])
            self.assertTrue(dst.exists())

    def test_ffmpeg_error_includes_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / "iphone.mov"
            src.write_bytes(b"mov")
            error = subprocess.CalledProcessError(234, ["ffmpeg"], stderr="APAC decoder unavailable")

            with (
                patch.object(fjordlens.shutil, "which", return_value="ffmpeg"),
                patch.object(fjordlens, "_probe_mov_audio_stream", return_value=2),
                patch.object(fjordlens, "_mov_nvenc_available", return_value=False),
                patch.object(fjordlens.subprocess, "run", side_effect=error),
                self.assertLogs(fjordlens.logger, level="ERROR") as logs,
            ):
                with self.assertRaisesRegex(RuntimeError, "APAC decoder unavailable"):
                    fjordlens._mov_to_mp4(src, root / "iphone.mp4")

        self.assertIn("APAC decoder unavailable", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
