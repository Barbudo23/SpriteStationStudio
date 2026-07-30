from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.blender_runner import BlenderRunner, ForgeError, RenderRequest


class RenderRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.blender = root / ("blender.exe" if __import__("sys").platform.startswith("win") else "blender")
        self.blender.write_text("", encoding="utf-8")
        self.model = root / "model.glb"
        self.model.write_bytes(b"dummy")
        self.output = root / "output"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_request(self) -> None:
        RenderRequest(self.blender, self.model, self.output).validate()

    def test_auto_engine_is_valid(self) -> None:
        RenderRequest(self.blender, self.model, self.output, engine="AUTO").validate()

    def test_legacy_eevee_engine_is_valid(self) -> None:
        RenderRequest(
            self.blender, self.model, self.output, engine="BLENDER_EEVEE"
        ).validate()

    def test_missing_model(self) -> None:
        request = RenderRequest(self.blender, self.model.with_name("none.fbx"), self.output)
        with self.assertRaises(ForgeError):
            request.validate()

    def test_unsupported_extension(self) -> None:
        bad = self.model.with_suffix(".blend")
        bad.write_bytes(b"x")
        with self.assertRaises(ForgeError):
            RenderRequest(self.blender, bad, self.output).validate()

    def test_resolution_bounds(self) -> None:
        with self.assertRaises(ForgeError):
            RenderRequest(self.blender, self.model, self.output, resolution=64).validate()

    def test_rejects_coerced_or_fractional_resolution(self) -> None:
        for resolution in (True, "512", 512.5):
            with self.subTest(resolution=resolution):
                with self.assertRaises(ForgeError):
                    RenderRequest(
                        self.blender,
                        self.model,
                        self.output,
                        resolution=resolution,
                    ).validate()

    def test_rejects_invalid_engine_type(self) -> None:
        for engine in (["AUTO"], True, 1):
            with self.subTest(engine=engine):
                with self.assertRaises(ForgeError):
                    RenderRequest(
                        self.blender,
                        self.model,
                        self.output,
                        engine=engine,
                    ).validate()


class CommandTests(unittest.TestCase):
    def test_command_contains_worker_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender"
            blender.write_text("", encoding="utf-8")
            model = root / "hero.fbx"
            model.write_text("", encoding="utf-8")
            worker = root / "worker.py"
            worker.write_text("", encoding="utf-8")
            output = root / "out"

            request = RenderRequest(blender, model, output, resolution=1024)
            command = BlenderRunner(worker).build_command(request)

            self.assertIn("--background", command)
            self.assertIn(str(model), command)
            self.assertIn("1024", command)
            self.assertIn(str(worker), command)
            self.assertEqual(command[command.index("--camera-profile") + 1], "Strategy30")
            self.assertEqual(command[command.index("--pivot-mode") + 1], "bottom_center")

    def test_single_preview_uses_selected_camera_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            model = root / "hero.glb"
            worker = root / "worker.py"
            for path in (blender, model, worker):
                path.write_bytes(b"x")
            request = RenderRequest(
                blender, model, root / "out", camera_profile="Diablo"
            )
            command = BlenderRunner(worker).build_command(request)
            self.assertEqual(command[command.index("--camera-profile") + 1], "Diablo")
            self.assertEqual(command[command.index("--framing-margin") + 1], "1.5")

    def test_find_blender_uses_windows_registry_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blender = Path(tmp) / "Blender 5.1" / "blender.exe"
            blender.parent.mkdir()
            blender.write_text("", encoding="utf-8")

            with (
                patch("app.blender_runner.sys.platform", "win32"),
                patch("app.blender_runner.shutil.which", return_value=None),
                patch.dict("app.blender_runner.os.environ", {}, clear=True),
                patch.object(
                    BlenderRunner,
                    "_windows_registry_candidates",
                    return_value=[blender],
                ),
            ):
                self.assertEqual(BlenderRunner.find_blender(), blender.resolve())

    def test_rejects_existing_preview_output_before_blender_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            model = root / "hero.glb"
            worker = root / "worker.py"
            for path in (blender, model, worker):
                path.write_bytes(b"x")
            output = root / "out"
            output.mkdir()
            existing_preview = output / "Preview.png"
            existing_preview.write_bytes(b"user-owned")
            request = RenderRequest(blender, model, output)

            with self.assertRaisesRegex(ForgeError, "already exists"):
                BlenderRunner(worker).run(request)

            self.assertEqual(existing_preview.read_bytes(), b"user-owned")

    def test_preview_output_contract_includes_unity_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = RenderRequest(
                root / "blender.exe",
                root / "hero.glb",
                root / "out",
            )

            paths = BlenderRunner.output_contract_paths(request)

            self.assertIn(root / "out" / "unity_import_preset.json", paths)


if __name__ == "__main__":
    unittest.main()
