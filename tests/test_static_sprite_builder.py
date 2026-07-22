from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.static_sprite_builder import build_static_sprite_set
from core.batch import BatchPlanError
from core.validation import encode_rgba_png


class StaticSpriteBuilderTests(unittest.TestCase):
    def prepare(self, root: Path, count: int = 2) -> Path:
        staging = root / "approved"
        items = []
        for index in range(1, count + 1):
            item_id = f"preview-{index}"
            item_dir = staging / "items" / item_id
            item_dir.mkdir(parents=True)
            rgba = bytes((index * 50, 100, 150, 255, 0, 0, 0, 0) * 2)
            sprite = item_dir / "Preview.png"
            sprite.write_bytes(encode_rgba_png(2, 2, rgba))
            manifest = item_dir / "preview_manifest.json"
            manifest.write_text(json.dumps({
                "schemaVersion": "1.1", "sprite": "Preview.png",
                "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
                "normalization": {"pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]}},
            }), encoding="utf-8")
            items.append({
                "itemId": item_id,
                "sprite": f"items/{item_id}/Preview.png",
                "manifest": f"items/{item_id}/preview_manifest.json",
                "sourceSha256": hashlib.sha256(sprite.read_bytes()).hexdigest(),
            })
        staging_manifest = staging / "approved_staging_manifest.json"
        staging_manifest.write_text(json.dumps({
            "schemaVersion": "1.0", "application": "Sprite Station Studio",
            "kind": "approved_preview_staging", "planId": "sprite-plan",
            "reviewSha256": "a" * 64, "approvedCount": len(items), "items": items,
        }), encoding="utf-8")
        return staging_manifest

    def test_builds_static_sprite_set_without_mutating_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging_manifest = self.prepare(root)
            protected = {path: path.read_bytes() for path in staging_manifest.parent.rglob("*") if path.is_file()}
            result = build_static_sprite_set(staging_manifest, root / "build/static-sprites")
            self.assertEqual(result.item_ids, ("preview-1", "preview-2"))
            self.assertEqual(len(result.sprite_paths), 2)
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["application"], "Sprite Station Studio")
            self.assertEqual(payload["kind"], "static_sprite_set")
            self.assertEqual(payload["spriteCount"], 2)
            self.assertEqual(payload["sprites"][0]["pivot"]["mode"], "bottom_center")
            self.assertEqual(payload["sprites"][0]["alphaBounds"], [0, 0, 1, 2])
            self.assertEqual({path: path.read_bytes() for path in protected}, protected)
            self.assertEqual(list((root / "build").glob(".*.staging-*")), [])

    def test_rejects_changed_sprite_and_wrong_pivot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging_manifest = self.prepare(root, count=1)
            (staging_manifest.parent / "items/preview-1/Preview.png").write_bytes(b"changed")
            with self.assertRaisesRegex(BatchPlanError, "integrity check failed"):
                build_static_sprite_set(staging_manifest, root / "build-one")

            staging_manifest = self.prepare(root / "second", count=1)
            manifest_path = staging_manifest.parent / "items/preview-1/preview_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["normalization"]["pivot"]["mode"] = "center"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BatchPlanError, "bottom_center"):
                build_static_sprite_set(staging_manifest, root / "build-two")

    def test_refuses_overwrite_and_output_inside_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging_manifest = self.prepare(root, count=1)
            output = root / "build"
            build_static_sprite_set(staging_manifest, output)
            with self.assertRaisesRegex(BatchPlanError, "already exists"):
                build_static_sprite_set(staging_manifest, output)
            with self.assertRaisesRegex(BatchPlanError, "outside the staging"):
                build_static_sprite_set(staging_manifest, staging_manifest.parent / "nested")


if __name__ == "__main__":
    unittest.main()
