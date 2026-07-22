from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.unity_runner import UnityBridgeError, UnityCommandResult
from app.unity_sprite_import import UnitySpriteImportRunner


class UnitySpriteImportTests(unittest.TestCase):
    def prepare(self, root: Path, imports_dir: str = "SpriteStationImports") -> tuple[Path, Path, Path]:
        project = root / "UnityProject"
        package = project / "Assets" / imports_dir / "Test_Soldier"
        package.mkdir(parents=True)
        (project / "ProjectSettings").mkdir()
        preset = package / "unity_import_preset.json"
        preset.write_text(json.dumps({"engine": "Unity", "assets": []}))
        unity = root / "Unity.exe"
        unity.write_text("")
        return project, package, unity

    def test_builds_apply_command_for_exported_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, package, unity = self.prepare(Path(tmp))
            runner_mock = Mock()

            def execute(*args, **kwargs):
                command = json.loads(Path(args[3]).read_text())
                self.assertEqual(command["operation"], "apply_sprite_import")
                self.assertEqual(Path(command["packagePath"]), package.resolve())
                Path(command["reportPath"]).write_text(json.dumps({
                    "importSettingsApplied": True,
                    "appliedAssetCount": 1,
                    "warnings": [],
                }))
                self.assertEqual(args[1], project.resolve())
                return UnityCommandResult(0, "", "", Path(command["reportPath"]))

            runner_mock.execute.side_effect = execute
            result = UnitySpriteImportRunner(runner_mock).run(unity, package)
            self.assertTrue(result.report["importSettingsApplied"])
            self.assertTrue(result.report_path.is_file())
            self.assertFalse((package / "unity_import_apply_command.json").exists())

    def test_rejects_directory_outside_assetforge_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "Assets" / "Other" / "Sprite"
            package.mkdir(parents=True)
            (root / "ProjectSettings").mkdir()
            (package / "unity_import_preset.json").write_text("{}")
            with self.assertRaises(UnityBridgeError):
                UnitySpriteImportRunner(Mock()).run(root / "Unity.exe", package)

    def test_accepts_legacy_assetforge_import_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, package, unity = self.prepare(Path(tmp), "AssetForgeImports")
            runner_mock = Mock()

            def execute(*args, **kwargs):
                command = json.loads(Path(args[3]).read_text())
                Path(command["reportPath"]).write_text(json.dumps({
                    "importSettingsApplied": True,
                    "appliedAssetCount": 0,
                    "warnings": [],
                }))
                return UnityCommandResult(0, "", "", Path(command["reportPath"]))

            runner_mock.execute.side_effect = execute
            result = UnitySpriteImportRunner(runner_mock).run(unity, package)
            self.assertTrue(result.report["importSettingsApplied"])

    def test_refuses_to_overwrite_existing_apply_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, package, unity = self.prepare(Path(tmp))
            (package / "unity_import_apply_report.json").write_text("{}")
            with self.assertRaises(UnityBridgeError):
                UnitySpriteImportRunner(Mock()).run(unity, package)

    def test_bridge_limits_mutation_to_exported_package(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "unity_bridge_project" / "Assets" / "Editor"
            / "AssetForgeUnityBridge.cs"
        ).read_text(encoding="utf-8")
        self.assertIn('command.operation == "apply_sprite_import"', source)
        method = source.split("private static void ApplySpriteImport", 1)[1]
        method = method.split("private static void PreviewSpriteImport", 1)[0]
        self.assertIn('"SpriteStationImports"', method)
        self.assertIn('"AssetForgeImports"', method)
        self.assertIn("importer.SaveAndReimport()", method)
        self.assertIn("report.importSettingsApplied", method)


if __name__ == "__main__":
    unittest.main()
