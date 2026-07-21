from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.blender_runner import RenderRequest
from app.direction_runner import DirectionRenderRunner


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


if __name__ == "__main__":
    unittest.main()
