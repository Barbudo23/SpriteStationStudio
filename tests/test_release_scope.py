from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


class ReleaseScopeTests(unittest.TestCase):
    def test_project_metadata_matches_current_dev_line(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["name"], "sprite-station-studio")
        self.assertEqual(metadata["project"]["version"], "0.8.3.dev0")
        gui = (root / "app" / "gui.py").read_text(encoding="utf-8")
        self.assertRegex(
            gui,
            re.compile(r'self\.title\(f"\{PRODUCT_NAME\} v0\.8\.3 Dev'),
        )

    def test_v090_scope_freezes_existing_contracts_and_ai(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scope = (root / "docs" / "RC_SCOPE_v0.9.0.md").read_text(encoding="utf-8")
        self.assertIn("Render manifest: `1.1`", scope)
        self.assertIn("Unity import preset: `1.0`", scope)
        self.assertIn("AI Center", scope)
        self.assertIn("максимум трёх", scope)
        self.assertIn("`UNKNOWN`", scope)


if __name__ == "__main__":
    unittest.main()
