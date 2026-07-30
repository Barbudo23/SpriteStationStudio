from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.blender_runner import RenderRequest
from app.direction_runner import DirectionRenderRunner
from app.blender_runner import ForgeError


class DirectionRunnerTests(unittest.TestCase):
    def test_builds_eight_direction_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            blender.write_text("", encoding="utf-8")
            model = root / "unit.glb"
            model.write_bytes(b"x")
            worker = root / "render_directions.py"
            worker.write_text("", encoding="utf-8")

            request = RenderRequest(blender, model, root / "out")
            command = DirectionRenderRunner(worker).build_command(request, 8)

            self.assertIn("--directions", command)
            self.assertIn("8", command)
            self.assertIn(str(model), command)
            self.assertEqual(command[command.index("--camera-profile") + 1], "Strategy30")
            self.assertEqual(command[command.index("--camera-elevation") + 1], "30.0")
            self.assertEqual(command[command.index("--pivot-mode") + 1], "bottom_center")

    def test_uses_selected_camera_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            blender.write_text("", encoding="utf-8")
            model = root / "unit.glb"
            model.write_bytes(b"x")
            worker = root / "render_directions.py"
            worker.write_text("", encoding="utf-8")

            request = RenderRequest(blender, model, root / "out")
            command = DirectionRenderRunner(worker).build_command(request, 4, "Commandos")

            self.assertEqual(command[command.index("--camera-profile") + 1], "Commandos")
            self.assertEqual(command[command.index("--camera-elevation") + 1], "42.0")
            self.assertEqual(command[command.index("--framing-margin") + 1], "1.45")

    def test_rejects_unknown_camera_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            blender.write_text("", encoding="utf-8")
            model = root / "unit.glb"
            model.write_bytes(b"x")
            worker = root / "render_directions.py"
            worker.write_text("", encoding="utf-8")

            request = RenderRequest(blender, model, root / "out")
            with self.assertRaises(ForgeError):
                DirectionRenderRunner(worker).build_command(request, 8, "Custom")

    def test_rejects_invalid_direction_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            blender.write_text("", encoding="utf-8")
            model = root / "unit.glb"
            model.write_bytes(b"x")
            worker = root / "render_directions.py"
            worker.write_text("", encoding="utf-8")

            request = RenderRequest(blender, model, root / "out")
            with self.assertRaises(Exception):
                DirectionRenderRunner(worker).build_command(request, 6)

    def test_rejects_existing_output_before_blender_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            blender.write_text("", encoding="utf-8")
            model = root / "unit.glb"
            model.write_bytes(b"x")
            worker = root / "render_directions.py"
            worker.write_text("", encoding="utf-8")
            output = root / "out"
            output.mkdir()
            existing_manifest = output / "manifest.json"
            existing_manifest.write_text("user-owned", encoding="utf-8")
            request = RenderRequest(blender, model, output)

            with self.assertRaisesRegex(ForgeError, "already exists"):
                DirectionRenderRunner(worker).run(request, 4)

            self.assertEqual(
                existing_manifest.read_text(encoding="utf-8"),
                "user-owned",
            )

    def test_output_contract_includes_zip_update_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = RenderRequest(
                root / "blender.exe",
                root / "unit.glb",
                root / "out",
            )

            paths = DirectionRenderRunner.output_contract_paths(request, 8)

            self.assertIn(root / "out" / "unit_8dir.zip.updating", paths)
            self.assertIn(root / "out" / "unity_import_preset.json", paths)


if __name__ == "__main__":
    unittest.main()
