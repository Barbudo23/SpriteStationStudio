from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from zipfile import ZipFile

from app.animation_runner import (
    AnimationRenderRequest,
    AnimationRenderRunner,
)
from app.blender_runner import ForgeError


class AnimationRunnerTests(unittest.TestCase):
    def make_request(self, root: Path) -> AnimationRenderRequest:
        blender = root / "blender.exe"
        model = root / "soldier.fbx"
        worker = root / "worker.py"
        blender.write_text("")
        model.write_text("")
        worker.write_text("")
        return AnimationRenderRequest(
            blender_path=blender,
            model_path=model,
            output_dir=root / "output",
            direction_count=8,
            frame_step=2,
            max_frames=24,
        ), worker

    def test_build_command_contains_animation_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, worker = self.make_request(Path(tmp))
            runner = AnimationRenderRunner(worker)
            command = runner.build_command(request)
            self.assertIn("--directions", command)
            self.assertIn("8", command)
            self.assertIn("--frame-step", command)
            self.assertIn("--max-frames", command)
            self.assertEqual(command[command.index("--camera-profile") + 1], "Strategy30")
            self.assertEqual(command[command.index("--pivot-mode") + 1], "bottom_center")

    def test_selected_camera_profile_is_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, worker = self.make_request(Path(tmp))
            request = AnimationRenderRequest(
                **{**request.__dict__, "camera_profile": "XCOM"}
            )
            command = AnimationRenderRunner(worker).build_command(request)
            self.assertEqual(command[command.index("--camera-profile") + 1], "XCOM")
            self.assertEqual(command[command.index("--camera-elevation") + 1], "35.0")

    def test_invalid_direction_count_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, worker = self.make_request(Path(tmp))
            request = AnimationRenderRequest(
                **{**request.__dict__, "direction_count": 6}
            )
            with self.assertRaises(ForgeError):
                AnimationRenderRunner(worker).build_command(request)

    @patch("app.animation_runner.subprocess.Popen")
    def test_run_validates_outputs(self, popen):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request, worker = self.make_request(root)
            request.output_dir.mkdir()
            report = {
                "status": "success",
                "directionCount": 8,
                "frameCountPerDirection": 12,
            }
            (request.output_dir / "animation_report.json").write_text(json.dumps(report))
            (request.output_dir / "animation_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1",
                "assetName": "soldier",
                "canvas": {"width": 256, "height": 256},
                "normalization": {"pivot": {"normalized": [0.5, 0.0]}},
                "directions": [{
                    "id": "north",
                    "sheet": "animation_sheets/00_north.png",
                    "frames": [{"sourceFrame": 1}],
                }],
            }))
            (request.output_dir / "animation_contact_sheet.png").write_bytes(b"png")
            with ZipFile(request.output_dir / "soldier_8dir_animation.zip", "w"):
                pass

            process = MagicMock()
            process.stdout = iter([])
            process.wait.return_value = 0
            popen.return_value = process

            result = AnimationRenderRunner(worker).run(request)
            self.assertEqual(result.report["directionCount"], 8)
            self.assertTrue(result.zip_path.is_file())


if __name__ == "__main__":
    unittest.main()
