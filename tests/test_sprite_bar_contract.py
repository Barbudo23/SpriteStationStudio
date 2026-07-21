from __future__ import annotations
import ast
import unittest
from pathlib import Path

class SpriteBarContractTests(unittest.TestCase):
    def test_reference_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue(
            (root / "examples" / "ui_references" / "Iteration_02_Contact_Sheet.png").is_file()
        )

    def test_gui_has_sprite_bar_mode(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app" / "gui.py").read_text(encoding="utf-8")
        self.assertIn("Sprite Bar", source)
        self.assertIn('"sprite_bar"', source)
        ast.parse(source)

if __name__ == "__main__":
    unittest.main()
