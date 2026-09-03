from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from app.static_sprite_unity_adapter import build_static_sprite_unity_package
from app.unity_sprite_preview import UnitySpritePreviewRunner
from core.validation import encode_rgba_png


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated Static Sprite Unity preview smoke-test.")
    parser.add_argument("--unity", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sss-static-unity-smoke-") as tmp:
        root = Path(tmp)
        sprite_set = root / "static-sprite-set"
        sprites = []
        for index, item_id in enumerate(("smoke-red", "smoke-blue"), start=1):
            sprite = sprite_set / "sprites" / f"{item_id}.png"
            sprite.parent.mkdir(parents=True, exist_ok=True)
            pixels = bytearray(64 * 64 * 4)
            for y in range(12, 56):
                for x in range(16, 48):
                    offset = (y * 64 + x) * 4
                    pixels[offset:offset + 4] = bytes((220 if index == 1 else 40, 70, 220, 255))
            sprite.write_bytes(encode_rgba_png(64, 64, bytes(pixels)))
            sprites.append({
                "itemId": item_id,
                "sprite": f"sprites/{item_id}.png",
                "sha256": hashlib.sha256(sprite.read_bytes()).hexdigest(),
                "width": 64,
                "height": 64,
                "alphaBounds": [16, 12, 48, 56],
                "pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]},
            })
        manifest = sprite_set / "static_sprite_set_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.0", "application": "Sprite Station Studio",
            "kind": "static_sprite_set", "planId": "unity-smoke",
            "spriteCount": len(sprites), "sprites": sprites,
        }, indent=2) + "\n", encoding="utf-8")
        package = build_static_sprite_unity_package(manifest, root / "unity-preview-package")
        result = UnitySpritePreviewRunner(
            bridge_project=REPOSITORY / "unity_bridge_project"
        ).run(args.unity, package.preset_path, timeout=600)
        report = result.report
        assets = report.get("spriteAssets") or []
        if not report.get("readOnlyPreview"):
            raise RuntimeError("Unity report is not read-only.")
        if len(assets) != len(sprites) or not all(asset.get("valid") for asset in assets):
            raise RuntimeError("Unity did not validate every Static Sprite.")
        if report.get("warnings"):
            raise RuntimeError(f"Unity preview warnings: {report['warnings']}")
        print(json.dumps({
            "application": "Sprite Station Studio",
            "unity": str(args.unity.resolve()),
            "readOnlyPreview": True,
            "spriteAssetCount": len(assets),
            "validSpriteAssetCount": sum(bool(asset.get("valid")) for asset in assets),
            "warnings": report.get("warnings", []),
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
