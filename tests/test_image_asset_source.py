from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app.image_asset_source import (
    DIRECTION_ORDER,
    ImageAssetRequest,
    ImageSourceError,
    build_image_asset,
)


class ImageAssetSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.images = {}
        for direction in DIRECTION_ORDER:
            path = self.root / f"{direction}.png"
            path.write_bytes(b"fake-png")
            self.images[direction] = path

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_requires_all_four_images(self) -> None:
        images = dict(self.images)
        images.pop("back_left")
        request = ImageAssetRequest("Unit", images, self.root / "out")
        with self.assertRaises(ImageSourceError):
            request.validate()

    def test_builds_zip_and_manifest_without_blender(self) -> None:
        result = build_image_asset(
            ImageAssetRequest("Unit 01", self.images, self.root / "out")
        )
        self.assertTrue(result.zip_path.is_file())
        self.assertTrue(result.manifest_path.is_file())

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["sourceType"], "four_direction_images")
        self.assertFalse(manifest["processing"]["blenderUsed"])
        self.assertEqual(len(manifest["directions"]), 4)

        with ZipFile(result.zip_path) as archive:
            names = archive.namelist()
        self.assertTrue(any(name.endswith("manifest.json") for name in names))
        self.assertEqual(
            sum("/images/" in name for name in names),
            4,
        )


if __name__ == "__main__":
    unittest.main()
