from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.static_sprite_unity_adapter import build_static_sprite_unity_package
from app.unity_runner import UnityBridgeError
from core.validation import encode_rgba_png


class StaticSpriteUnityAdapterTests(unittest.TestCase):
    def test_reproducible_smoke_tool_is_valid_python(self) -> None:
        tool = Path(__file__).resolve().parents[1] / "Tools" / "Invoke-StaticSpriteUnitySmoke.py"
        source = tool.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"application": "Sprite Station Studio"', source)
        self.assertIn('"readOnlyPreview": True', source)

    def prepare(self, root: Path, count: int = 2) -> Path:
        sprite_root = root / "sprite-set"
        sprites = []
        for index in range(1, count + 1):
            item_id = f"preview-{index}"
            path = sprite_root / "sprites" / f"{item_id}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            rgba = bytes((index * 50, 100, 150, 255, 0, 0, 0, 0) * 2)
            path.write_bytes(encode_rgba_png(2, 2, rgba))
            sprites.append({
                "itemId": item_id, "sprite": f"sprites/{item_id}.png",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "width": 2, "height": 2, "alphaBounds": [0, 0, 1, 2],
                "pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]},
            })
        manifest = sprite_root / "static_sprite_set_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.0", "application": "Sprite Station Studio",
            "kind": "static_sprite_set", "planId": "unity-plan",
            "spriteCount": len(sprites), "sprites": sprites,
        }), encoding="utf-8")
        return manifest

    def test_builds_portable_preset_without_mutating_sprite_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_manifest = self.prepare(root)
            protected = {path: path.read_bytes() for path in source_manifest.parent.rglob("*") if path.is_file()}
            result = build_static_sprite_unity_package(source_manifest, root / "unity-preview")
            preset = json.loads(result.preset_path.read_text(encoding="utf-8"))
            package = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(preset["schemaVersion"], "1.0")
            self.assertEqual(len(preset["assets"]), 2)
            self.assertTrue(all(asset["spriteMode"] == "Single" for asset in preset["assets"]))
            self.assertTrue(all(asset["pivot"] == [0.5, 0.0] for asset in preset["assets"]))
            self.assertTrue(package["readOnlyPreparation"])
            self.assertEqual(package["application"], "Sprite Station Studio")
            self.assertEqual({path: path.read_bytes() for path in protected}, protected)
            self.assertFalse(any(result.output_dir.rglob("*.meta")))

    def test_rejects_stale_brand_and_changed_sprite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.prepare(root, count=1)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["application"] = "AssetForge Studio"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(UnityBridgeError, "brand"):
                build_static_sprite_unity_package(manifest, root / "wrong-brand")

            manifest = self.prepare(root / "second", count=1)
            (manifest.parent / "sprites/preview-1.png").write_bytes(b"changed")
            with self.assertRaisesRegex(UnityBridgeError, "integrity check failed"):
                build_static_sprite_unity_package(manifest, root / "changed")

    def test_refuses_overwrite_inside_source_and_invalid_ppu(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.prepare(root, count=1)
            output = root / "unity-preview"
            build_static_sprite_unity_package(manifest, output)
            with self.assertRaisesRegex(UnityBridgeError, "already exists"):
                build_static_sprite_unity_package(manifest, output)
            with self.assertRaisesRegex(UnityBridgeError, "outside"):
                build_static_sprite_unity_package(manifest, manifest.parent / "nested")
            with self.assertRaisesRegex(UnityBridgeError, "Pixels per unit"):
                build_static_sprite_unity_package(manifest, root / "bad-ppu", 0)


if __name__ == "__main__":
    unittest.main()
