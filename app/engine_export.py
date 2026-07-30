from __future__ import annotations

import json
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.blender_runner import ForgeError


UNITY_PRESET_NAME = "unity_import_preset.json"


def build_unity_import_preset(manifest: dict) -> dict:
    canvas = manifest.get("canvas") or {}
    width = canvas.get("width")
    height = canvas.get("height")
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or not 1 <= width <= 4096
        or not 1 <= height <= 4096
        or width * height > 4096 * 4096
    ):
        raise ForgeError("Manifest does not contain a valid sprite canvas.")

    normalization = manifest.get("normalization") or {}
    pivot = (normalization.get("pivot") or {}).get("normalized", [0.5, 0.0])
    if (
        not isinstance(pivot, list)
        or len(pivot) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
            for value in pivot
        )
    ):
        raise ForgeError("Manifest contains an invalid normalized pivot.")

    common = {
        "textureType": "Sprite",
        "alphaIsTransparency": True,
        "mipMaps": False,
        "wrapMode": "Clamp",
        "filterMode": "Bilinear",
        "compression": "Uncompressed",
        "pixelsPerUnit": 100,
        "pivot": [float(pivot[0]), float(pivot[1])],
    }
    assets: list[dict] = []
    directions = manifest.get("directions") or []

    if manifest.get("sprite"):
        assets.append({
            **common,
            "file": manifest["sprite"],
            "spriteMode": "Single",
            "name": manifest.get("assetName", "sprite"),
        })
    elif directions and "frames" in directions[0]:
        for direction in directions:
            frames = direction.get("frames") or []
            slices = [
                {
                    "name": f"{direction['id']}_{index:03d}",
                    "rect": [index * width, 0, width, height],
                    "pivot": common["pivot"],
                    "sourceFrame": frame.get("sourceFrame"),
                }
                for index, frame in enumerate(frames)
            ]
            assets.append({
                **common,
                "file": direction["sheet"],
                "spriteMode": "Multiple",
                "name": direction["id"],
                "slices": slices,
            })
    else:
        for direction in directions:
            assets.append({
                **common,
                "file": direction["file"],
                "spriteMode": "Single",
                "name": direction["id"],
            })

    if not assets:
        raise ForgeError("Manifest does not contain exportable sprite assets.")

    return {
        "schemaVersion": "1.0",
        "engine": "Unity",
        "sourceManifestVersion": manifest.get("schemaVersion"),
        "assetName": manifest.get("assetName"),
        "assets": assets,
        "applicationMode": "explicit_import",
    }


def write_unity_import_preset(manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preset = build_unity_import_preset(manifest)
    output_path = manifest_path.parent / UNITY_PRESET_NAME
    output_path.write_text(
        json.dumps(preset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def append_preset_to_zip(zip_path: Path, preset_path: Path) -> None:
    temporary_path = zip_path.with_suffix(zip_path.suffix + ".updating")
    try:
        with (
            ZipFile(zip_path, "r") as source,
            ZipFile(temporary_path, "w", ZIP_DEFLATED) as target,
        ):
            for item in source.infolist():
                if item.filename != UNITY_PRESET_NAME:
                    target.writestr(item, source.read(item.filename))
            target.write(preset_path, UNITY_PRESET_NAME)
        temporary_path.replace(zip_path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
