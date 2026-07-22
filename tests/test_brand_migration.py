from __future__ import annotations

import unittest
from pathlib import Path

from app.brand import (
    LEGACY_UNITY_IMPORTS_DIR,
    PRODUCT_NAME,
    PRODUCT_SHORT_NAME,
    UNITY_IMPORTS_DIR,
    config_path,
    legacy_config_path,
)


class BrandMigrationTests(unittest.TestCase):
    def test_public_brand_and_isolated_paths(self) -> None:
        self.assertEqual(PRODUCT_NAME, "Sprite Station Studio")
        self.assertEqual(PRODUCT_SHORT_NAME, "SSS")
        self.assertEqual(UNITY_IMPORTS_DIR, "SpriteStationImports")
        self.assertEqual(LEGACY_UNITY_IMPORTS_DIR, "AssetForgeImports")
        self.assertEqual(config_path("settings.json").parent.name, ".sprite_station_studio")
        self.assertEqual(legacy_config_path("settings.json").parent.name, ".assetforge")

    def test_migration_document_records_legacy_contracts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        migration = (root / "docs" / "BRAND_MIGRATION_SSS.md").read_text(encoding="utf-8")
        self.assertIn("Barbudo23/SpriteStationStudio", migration)
        self.assertIn("AssetForgeUnityBridge.Execute", migration)
        self.assertIn("Assets/SpriteStationImports", migration)
        self.assertIn("`.afs`", migration)


if __name__ == "__main__":
    unittest.main()
