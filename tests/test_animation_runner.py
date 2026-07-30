from pathlib import Path
import hashlib
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
from core.validation import encode_rgba_png


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

    def test_inverted_frame_range_rejected_before_blender(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, worker = self.make_request(Path(tmp))
            request = AnimationRenderRequest(
                **{**request.__dict__, "frame_start": 20, "frame_end": 10}
            )
            with self.assertRaisesRegex(ForgeError, "Frame Start"):
                AnimationRenderRunner(worker).build_command(request)

    @patch("app.animation_runner.subprocess.Popen")
    def test_existing_animation_output_is_not_overwritten(self, popen):
        with tempfile.TemporaryDirectory() as tmp:
            request, worker = self.make_request(Path(tmp))
            stale = request.output_dir / "animation_frames"
            stale.mkdir(parents=True)
            marker = stale / "keep.txt"
            marker.write_text("user data", encoding="utf-8")

            with self.assertRaisesRegex(ForgeError, "уже существует"):
                AnimationRenderRunner(worker).run(request)

            popen.assert_not_called()
            self.assertEqual(marker.read_text(encoding="utf-8"), "user data")

    @patch("app.animation_runner.subprocess.Popen")
    def test_run_validates_outputs(self, popen):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request, worker = self.make_request(root)
            report = {
                "status": "success",
                "directionCount": 8,
                "frameCountPerDirection": 12,
            }

            process = MagicMock()
            process.stdout = iter([])
            process.wait.return_value = 0

            def launch(*args, **kwargs):
                request.output_dir.mkdir(exist_ok=True)
                (request.output_dir / "animation_report.json").write_text(json.dumps(report))
                directions = []
                for index, name in enumerate(
                    ("north", "north_east", "east", "south_east",
                     "south", "south_west", "west", "north_west")
                ):
                    frame = request.output_dir / "animation_frames" / name / "000_frame_0001.png"
                    frame.parent.mkdir(parents=True)
                    pixels = bytes((255, 0, 0, 255, 0, 0, 0, 0) * 2)
                    frame.write_bytes(encode_rgba_png(2, 2, pixels))
                    sheet = request.output_dir / "animation_sheets" / f"{index:02d}_{name}.png"
                    sheet.parent.mkdir(parents=True, exist_ok=True)
                    sheet.write_bytes(encode_rgba_png(2, 2, pixels))
                    directions.append({
                        "id": name,
                        "yawDegrees": float(index * 45),
                        "sheet": sheet.relative_to(request.output_dir).as_posix(),
                        "sheetSha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
                        "frames": [{
                            "order": 0,
                            "sourceFrame": 1,
                            "file": frame.relative_to(request.output_dir).as_posix(),
                            "sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                        }],
                    })
                contact = request.output_dir / "animation_contact_sheet.png"
                contact.write_bytes(encode_rgba_png(8, 4, pixels * 8))
                (request.output_dir / "animation_manifest.json").write_text(json.dumps({
                    "schemaVersion": "1.1",
                    "application": "Sprite Station Studio",
                    "module": "Animation Sprite Renderer",
                    "assetName": "soldier",
                    "sourceSha256": hashlib.sha256(request.model_path.read_bytes()).hexdigest(),
                    "directionCount": 8,
                    "sampledFrames": [1],
                    "frameRange": {"start": 1, "end": 1},
                    "frameCountPerDirection": 1,
                    "canvas": {
                        "width": 2, "height": 2,
                        "transparent": True, "colorMode": "RGBA",
                    },
                    "normalization": {"pivot": {"normalized": [0.5, 0.0]}},
                    "directions": directions,
                    "contactSheet": contact.name,
                    "contactSheetSha256": hashlib.sha256(contact.read_bytes()).hexdigest(),
                }))
                with ZipFile(request.output_dir / "soldier_8dir_animation.zip", "w"):
                    pass
                return process

            popen.side_effect = launch

            result = AnimationRenderRunner(worker).run(request)
            self.assertEqual(result.report["directionCount"], 8)
            self.assertTrue(result.zip_path.is_file())


if __name__ == "__main__":
    unittest.main()
