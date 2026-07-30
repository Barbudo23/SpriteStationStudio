from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app.blender_runner import ForgeError
from app.engine_export import (
    append_preset_to_zip,
    build_unity_import_preset,
    write_unity_import_preset,
)


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

    def test_rejects_non_object_manifest_root(self) -> None:
        with self.assertRaisesRegex(ForgeError, "JSON object"):
            build_unity_import_preset([])

    def test_reports_unreadable_or_malformed_manifest_as_forge_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            malformed = root / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "Cannot read"):
                write_unity_import_preset(malformed)

            missing = root / "missing.json"
            with self.assertRaisesRegex(ForgeError, "Cannot read"):
                write_unity_import_preset(missing)

    def test_preset_publication_is_atomic_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.base_manifest()
            manifest["sprite"] = "Preview.png"
            manifest_path = root / "preview_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "unity_import_preset.json"
            output.write_text("user-owned", encoding="utf-8")

            with self.assertRaisesRegex(ForgeError, "already exists"):
                write_unity_import_preset(manifest_path)

            self.assertEqual(output.read_text(encoding="utf-8"), "user-owned")
            self.assertEqual(
                list(root.glob(".unity_import_preset.json.staging-*")),
                [],
            )

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

    def test_refuses_to_overwrite_existing_update_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "asset.zip"
            preset_path = root / "unity_import_preset.json"
            update_path = root / "asset.zip.updating"
            preset_path.write_text("{}", encoding="utf-8")
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("sprite.png", b"original")
            archive_before = archive_path.read_bytes()
            update_path.write_bytes(b"user-owned-stage")

            with self.assertRaisesRegex(ForgeError, "already staged"):
                append_preset_to_zip(archive_path, preset_path)

            self.assertEqual(archive_path.read_bytes(), archive_before)
            self.assertEqual(update_path.read_bytes(), b"user-owned-stage")

    def test_zip_update_failure_preserves_source_and_cleans_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "asset.zip"
            archive_path.write_bytes(b"not-a-zip")
            archive_before = archive_path.read_bytes()
            preset_path = root / "unity_import_preset.json"
            preset_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ForgeError, "Cannot update"):
                append_preset_to_zip(archive_path, preset_path)

            self.assertEqual(archive_path.read_bytes(), archive_before)
            self.assertFalse((root / "asset.zip.updating").exists())

    def test_missing_preset_preserves_source_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "asset.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("sprite.png", b"original")
            archive_before = archive_path.read_bytes()

            with self.assertRaisesRegex(ForgeError, "Cannot update"):
                append_preset_to_zip(
                    archive_path,
                    root / "missing_unity_import_preset.json",
                )

            self.assertEqual(archive_path.read_bytes(), archive_before)
            self.assertFalse((root / "asset.zip.updating").exists())


if __name__ == "__main__":
    unittest.main()
