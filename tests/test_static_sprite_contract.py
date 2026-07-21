from __future__ import annotations

import ast
import unittest
from pathlib import Path


class StaticSpriteContractTests(unittest.TestCase):
    def test_direction_worker_is_valid_python(self) -> None:
        source = self._worker_path().read_text(encoding="utf-8")
        ast.parse(source)

    def test_manifest_records_reproducible_sprite_metadata(self) -> None:
        source = self._worker_path().read_text(encoding="utf-8")
        for required in (
            '"schemaVersion": "1.1"',
            '"camera"',
            '"normalization"',
            '"pivot"',
            '"transparent": True',
            '"colorMode": "RGBA"',
        ):
            self.assertIn(required, source)

    @staticmethod
    def _worker_path() -> Path:
        return Path(__file__).resolve().parents[1] / "worker" / "render_directions.py"


if __name__ == "__main__":
    unittest.main()
