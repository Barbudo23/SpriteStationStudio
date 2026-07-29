from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.animation_validation import validate_animation_manifest
from app.blender_runner import ForgeError


class AnimationValidationTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        frames = []
        for order, source in enumerate((1, 3)):
            path = root / "animation_frames" / "north" / f"{order:03d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"frame")
            frames.append({"order": order, "sourceFrame": source, "file": path.relative_to(root).as_posix()})
        sheet = root / "animation_sheets" / "00_north.png"
        sheet.parent.mkdir(parents=True)
        sheet.write_bytes(b"sheet")
        manifest = root / "animation_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "module": "Animation Sprite Renderer",
            "directionCount": 4,
            "sampledFrames": [1, 3],
            "frameCountPerDirection": 2,
            "directions": [
                {"id": name, "sheet": f"animation_sheets/{index:02d}_{name}.png", "frames": frames}
                for index, name in enumerate(("north", "east", "south", "west"))
            ],
        }), encoding="utf-8")
        for index, name in enumerate(("east", "south", "west"), start=1):
            target = root / "animation_sheets" / f"{index:02d}_{name}.png"
            target.write_bytes(b"sheet")
        return manifest

    def test_accepts_consistent_safe_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = validate_animation_manifest(self.fixture(Path(tmp)))
            self.assertEqual(report.direction_count, 4)
            self.assertEqual(report.frame_count_per_direction, 2)
            self.assertEqual(len(report.frame_paths), 8)

    def test_rejects_frame_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["directions"][0]["frames"][0]["file"] = "../outside.png"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "escapes"):
                validate_animation_manifest(manifest)
