from __future__ import annotations

import ast
import unittest
from pathlib import Path


class UnityPreviewGuiContractTests(unittest.TestCase):
    def test_gui_exposes_read_only_unity_preview(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app" / "gui.py"
        ).read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("UNITY IMPORT PREVIEW (READ-ONLY)", source)
        self.assertIn("def _preview_unity_sprite_import", source)
        self.assertIn('"unity_preview_ok"', source)
        self.assertIn("last_unity_preset_path", source)
        self.assertIn("EXPORT VERIFIED PACKAGE TO UNITY", source)
        self.assertIn("def _export_verified_unity_package", source)
        self.assertIn('"unity_export_ok"', source)
        self.assertIn("askyesno", source)
        self.assertGreaterEqual(
            source.count("last_unity_preview_report_path = None"), 3
        )


if __name__ == "__main__":
    unittest.main()
