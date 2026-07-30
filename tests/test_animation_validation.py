from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from app.animation_validation import validate_animation_manifest
from app.blender_runner import ForgeError
from core.validation import encode_rgba_png


class AnimationValidationTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        rgba = bytes((255, 0, 0, 255, 0, 0, 0, 0) * 2)
        directions = []
        for index, name in enumerate(("north", "east", "south", "west")):
            frames = []
            for order, source in enumerate((1, 3)):
                path = root / "animation_frames" / name / f"{order:03d}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encode_rgba_png(2, 2, rgba))
                frames.append({
                    "order": order,
                    "sourceFrame": source,
                    "file": path.relative_to(root).as_posix(),
                })
            sheet = root / "animation_sheets" / f"{index:02d}_{name}.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            sheet.write_bytes(encode_rgba_png(4, 2, rgba * 2))
            directions.append({
                "id": name,
                "sheet": sheet.relative_to(root).as_posix(),
                "sheetSha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
                "frames": frames,
            })
            for frame in frames:
                frame_path = root / frame["file"]
                frame["sha256"] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        contact = root / "animation_contact_sheet.png"
        contact.write_bytes(encode_rgba_png(8, 2, rgba * 4))
        manifest = root / "animation_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "module": "Animation Sprite Renderer",
            "directionCount": 4,
            "sampledFrames": [1, 3],
            "frameCountPerDirection": 2,
            "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
            "directions": directions,
            "contactSheet": contact.name,
            "contactSheetSha256": hashlib.sha256(contact.read_bytes()).hexdigest(),
        }), encoding="utf-8")
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

    def test_rejects_invalid_frame_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(Path(tmp))
            frame = Path(tmp) / "animation_frames" / "north" / "000.png"
            frame.write_bytes(b"not png")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["directions"][0]["frames"][0]["sha256"] = hashlib.sha256(
                frame.read_bytes()
            ).hexdigest()
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "PNG is invalid"):
                validate_animation_manifest(manifest)

    def test_rejects_sheet_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(Path(tmp))
            sheet = Path(tmp) / "animation_sheets" / "00_north.png"
            sheet.write_bytes(encode_rgba_png(2, 2, bytes((255, 0, 0, 255) * 4)))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["directions"][0]["sheetSha256"] = hashlib.sha256(
                sheet.read_bytes()
            ).hexdigest()
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "dimensions mismatch"):
                validate_animation_manifest(manifest)

    def test_rejects_frame_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(Path(tmp))
            frame = Path(tmp) / "animation_frames" / "north" / "000.png"
            frame.write_bytes(encode_rgba_png(2, 2, bytes((0, 255, 0, 128) * 4)))
            with self.assertRaisesRegex(ForgeError, "SHA-256"):
                validate_animation_manifest(manifest)

    def test_rejects_duplicate_output_paths_between_directions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["directions"][1]["frames"][0] = dict(
                payload["directions"][0]["frames"][0]
            )
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "duplicate output file paths"):
                validate_animation_manifest(manifest)
