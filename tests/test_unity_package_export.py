from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.unity_package_export import export_verified_package
from app.unity_runner import UnityBridgeError


class UnityPackageExportTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path, Path]:
        package = root / "package"
        (package / "directions").mkdir(parents=True)
        (package / "directions" / "north.png").write_bytes(b"png")
        preset = package / "unity_import_preset.json"
        preset.write_text(json.dumps({
            "assetName": "Test Soldier",
            "assets": [{"file": "directions/north.png"}],
        }))
        report = package / "unity_import_preview_report.json"
        report.write_text(json.dumps({
            "readOnlyPreview": True,
            "presetPath": str(preset.resolve()),
            "warnings": [],
            "spriteAssets": [{"file": "directions/north.png", "valid": True}],
        }))
        project = root / "UnityProject"
        (project / "Assets").mkdir(parents=True)
        (project / "ProjectSettings").mkdir()
        return preset, report, project

    def test_exports_to_new_sprite_station_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset, report, project = self.prepare(Path(tmp))
            result = export_verified_package(preset, report, project)
            self.assertEqual(result.target_dir.name, "Test_Soldier")
            self.assertEqual(result.target_dir.parent.name, "SpriteStationImports")
            self.assertTrue((result.target_dir / "directions" / "north.png").is_file())
            self.assertTrue((result.target_dir / preset.name).is_file())

    def test_refuses_to_overwrite_existing_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset, report, project = self.prepare(Path(tmp))
            export_verified_package(preset, report, project)
            with self.assertRaises(UnityBridgeError):
                export_verified_package(preset, report, project)

    def test_requires_successful_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset, report, project = self.prepare(Path(tmp))
            report.write_text(json.dumps({"readOnlyPreview": False}))
            with self.assertRaises(UnityBridgeError):
                export_verified_package(preset, report, project)

    def test_rejects_report_for_different_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset, report, project = self.prepare(Path(tmp))
            payload = json.loads(report.read_text())
            payload["presetPath"] = str(Path(tmp) / "other_preset.json")
            report.write_text(json.dumps(payload))
            with self.assertRaises(UnityBridgeError):
                export_verified_package(preset, report, project)


if __name__ == "__main__":
    unittest.main()
