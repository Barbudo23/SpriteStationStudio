from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.unity_runner import UnityCommandResult
from app.unity_sprite_preview import UnitySpritePreviewRunner


class UnitySpritePreviewTests(unittest.TestCase):
    def test_bridge_exposes_read_only_operation(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "unity_bridge_project"
            / "Assets"
            / "Editor"
            / "AssetForgeUnityBridge.cs"
        ).read_text(encoding="utf-8")
        self.assertIn('command.operation == "preview_sprite_import"', source)
        preview_method = source.split("private static void PreviewSpriteImport", 1)[1]
        preview_method = preview_method.split("private static void AnalyzeAsset", 1)[0]
        self.assertIn("report.readOnlyPreview = true", preview_method)
        self.assertNotIn("AssetDatabase.", preview_method)

    def test_builds_read_only_preview_command_and_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preset = root / "unity_import_preset.json"
            preset.write_text("{}", encoding="utf-8")
            bridge = root / "bridge"
            bridge.mkdir()
            unity = root / "Unity.exe"
            unity.write_text("", encoding="utf-8")
            runner_mock = Mock()

            def execute(*args, **kwargs):
                command = json.loads((root / "unity_preview_command.json").read_text())
                self.assertEqual(command["operation"], "preview_sprite_import")
                Path(command["reportPath"]).write_text(json.dumps({
                    "readOnlyPreview": True,
                    "spriteAssetCount": 1,
                }))
                return UnityCommandResult(0, "", "", Path(command["reportPath"]))

            runner_mock.execute.side_effect = execute
            result = UnitySpritePreviewRunner(runner_mock, bridge).run(unity, preset)
            self.assertTrue(result.report["readOnlyPreview"])
            self.assertEqual(result.report["spriteAssetCount"], 1)


if __name__ == "__main__":
    unittest.main()
