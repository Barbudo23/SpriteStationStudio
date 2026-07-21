from __future__ import annotations

import ast
import unittest
from pathlib import Path


class GuiInitializationContractTests(unittest.TestCase):
    def test_update_source_mode_called_after_render_button_creation(self) -> None:
        gui_path = Path(__file__).resolve().parents[1] / "app" / "gui.py"
        source = gui_path.read_text(encoding="utf-8")

        button_pos = source.find("self.render_button = ttk.Button")
        call_pos = source.find("self._update_source_mode()", button_pos)

        self.assertGreaterEqual(button_pos, 0)
        self.assertGreater(call_pos, button_pos)

    def test_gui_source_is_valid_python(self) -> None:
        gui_path = Path(__file__).resolve().parents[1] / "app" / "gui.py"
        ast.parse(gui_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
