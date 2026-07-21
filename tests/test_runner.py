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


if __name__ == "__main__":
    unittest.main()
