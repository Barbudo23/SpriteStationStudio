from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app.blender_runner import ForgeError
from app.engine_export import append_preset_to_zip, build_unity_import_preset


class UnityExportPresetTests(unittest.TestCase):
    def base_manifest(self) -> dict:
        return {
            "schemaVersion": "1.1",
            "assetName": "soldier",
            "canvas": {"width": 256, "height": 256},
            "normalization": {"pivot": {"normalized": [0.5, 0.0]}},
        }

    def test_builds_direction_sprite_imports(self) -> None:
        manifest = self.base_manifest()
        manifest["directions"] = [
            {"id": "north", "file": "directions/00_north.png"},
            {"id": "east", "file": "directions/01_east.png"},
        ]
        preset = build_unity_import_preset(manifest)
        self.assertEqual(len(preset["assets"]), 2)
        self.assertEqual(preset["assets"][0]["spriteMode"], "Single")
        self.assertEqual(preset["assets"][0]["pivot"], [0.5, 0.0])

    def test_builds_single_preview_import(self) -> None:
        manifest = self.base_manifest()
        manifest["sprite"] = "Preview.png"
        preset = build_unity_import_preset(manifest)
        self.assertEqual(preset["assets"][0]["file"], "Preview.png")
        self.assertEqual(preset["assets"][0]["spriteMode"], "Single")

    def test_builds_animation_sheet_slices(self) -> None:
        manifest = self.base_manifest()
        manifest["directions"] = [{
            "id": "north",
            "sheet": "animation_sheets/00_north.png",
            "frames": [{"sourceFrame": 1}, {"sourceFrame": 3}],
        }]
        preset = build_unity_import_preset(manifest)
        asset = preset["assets"][0]
        self.assertEqual(asset["spriteMode"], "Multiple")
        self.assertEqual(asset["slices"][1]["rect"], [256, 0, 256, 256])

    def test_rejects_incomplete_or_aliased_animation_directions(self) -> None:
        invalid_directions = (
            [
                {
                    "id": "north",
                    "sheet": "animation_sheets/00_north.png",
                    "frames": [{"sourceFrame": 1}],
                },
                {"id": "east", "file": "directions/01_east.png"},
            ],
            [
                {
                    "id": "north",
                    "sheet": "animation_sheets/shared.png",
                    "frames": [{"sourceFrame": 1}],
                },
                {
                    "id": "east",
                    "sheet": "animation_sheets/shared.png",
                    "frames": [{"sourceFrame": 1}],
                },
            ],
        )
        for directions in invalid_directions:
            manifest = self.base_manifest()
            manifest["directions"] = directions
            with self.subTest(directions=directions):
                with self.assertRaisesRegex(ForgeError, "animation direction"):
                    build_unity_import_preset(manifest)

    def test_rejects_invalid_animation_frame_identity_or_order(self) -> None:
        for frames in (
            [],
            [{"sourceFrame": True}],
            [{"sourceFrame": "1"}],
            [{"sourceFrame": 2}, {"sourceFrame": 1}],
            [{"sourceFrame": 1}, {"sourceFrame": 1}],
        ):
            manifest = self.base_manifest()
            manifest["directions"] = [{
                "id": "north",
                "sheet": "animation_sheets/00_north.png",
                "frames": frames,
            }]
            with self.subTest(frames=frames):
                with self.assertRaisesRegex(
                    ForgeError, "animation (direction|frame)"
                ):
                    build_unity_import_preset(manifest)

    def test_rejects_duplicate_static_direction_identity_or_file(self) -> None:
        for directions in (
            [
                {"id": "north", "file": "directions/00_north.png"},
                {"id": "north", "file": "directions/01_east.png"},
            ],
            [
                {"id": "north", "file": "directions/shared.png"},
                {"id": "east", "file": "directions/shared.png"},
            ],
        ):
            manifest = self.base_manifest()
            manifest["directions"] = directions
            with self.subTest(directions=directions):
                with self.assertRaisesRegex(ForgeError, "sprite direction"):
                    build_unity_import_preset(manifest)

    def test_rejects_non_finite_out_of_range_or_boolean_pivot(self) -> None:
        for pivot in ([1.1, 0.0], [float("nan"), 0.0], [True, 0.0]):
            manifest = self.base_manifest()
            manifest["sprite"] = "Preview.png"
            manifest["normalization"]["pivot"]["normalized"] = pivot
            with self.subTest(pivot=pivot):
                with self.assertRaisesRegex(ForgeError, "invalid normalized pivot"):
                    build_unity_import_preset(manifest)

    def test_rejects_coerced_or_oversized_canvas_dimensions(self) -> None:
        for width, height in ((True, 64), ("64", 64), (64.5, 64), (4097, 64)):
            manifest = self.base_manifest()
            manifest["sprite"] = "Preview.png"
            manifest["canvas"] = {"width": width, "height": height}
            with self.subTest(width=width, height=height):
                with self.assertRaisesRegex(ForgeError, "valid sprite canvas"):
                    build_unity_import_preset(manifest)

    def test_appends_preset_to_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "asset.zip"
            preset_path = root / "unity_import_preset.json"
            preset_path.write_text("{}", encoding="utf-8")
            with ZipFile(archive_path, "w"):
                pass
            append_preset_to_zip(archive_path, preset_path)
            with ZipFile(archive_path) as archive:
                self.assertIn("unity_import_preset.json", archive.namelist())

            preset_path.write_text('{"version": 2}', encoding="utf-8")
            append_preset_to_zip(archive_path, preset_path)
            with ZipFile(archive_path) as archive:
                self.assertEqual(
                    archive.namelist().count("unity_import_preset.json"), 1
                )
                self.assertEqual(
                    archive.read("unity_import_preset.json"), b'{"version": 2}'
                )


if __name__ == "__main__":
    unittest.main()
