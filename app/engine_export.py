from __future__ import annotations

import json
import math
import os
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from app.blender_runner import ForgeError


UNITY_PRESET_NAME = "unity_import_preset.json"


def _required_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def build_unity_import_preset(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ForgeError("Unity source manifest must be a JSON object.")
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
    if not isinstance(directions, list):
        raise ForgeError("Manifest contains invalid sprite directions.")

    if manifest.get("sprite"):
        sprite = _required_text(manifest["sprite"])
        if sprite is None:
            raise ForgeError("Manifest contains an invalid sprite file.")
        assets.append({
            **common,
            "file": sprite,
            "spriteMode": "Single",
            "name": manifest.get("assetName", "sprite"),
        })
    elif directions and any(
        isinstance(direction, dict)
        and ("frames" in direction or "sheet" in direction)
        for direction in directions
    ):
        seen_ids: set[str] = set()
        seen_files: set[str] = set()
        for direction in directions:
            if not isinstance(direction, dict):
                raise ForgeError("Manifest contains an invalid animation direction.")
            direction_id = _required_text(direction.get("id"))
            sheet = _required_text(direction.get("sheet"))
            frames = direction.get("frames")
            if (
                direction_id is None
                or sheet is None
                or not isinstance(frames, list)
                or not frames
                or direction_id in seen_ids
                or sheet in seen_files
            ):
                raise ForgeError("Manifest contains an invalid animation direction.")
            seen_ids.add(direction_id)
            seen_files.add(sheet)
            source_frames: list[int] = []
            for frame in frames:
                source_frame = (
                    frame.get("sourceFrame") if isinstance(frame, dict) else None
                )
                if (
                    isinstance(source_frame, bool)
                    or not isinstance(source_frame, int)
                    or source_frame < 0
                ):
                    raise ForgeError("Manifest contains an invalid animation frame.")
                source_frames.append(source_frame)
            if any(
                current <= previous
                for previous, current in zip(source_frames, source_frames[1:])
            ):
                raise ForgeError("Manifest contains invalid animation frame order.")
            slices = [
                {
                    "name": f"{direction_id}_{index:03d}",
                    "rect": [index * width, 0, width, height],
                    "pivot": common["pivot"],
                    "sourceFrame": source_frames[index],
                }
                for index in range(len(frames))
            ]
            assets.append({
                **common,
                "file": sheet,
                "spriteMode": "Multiple",
                "name": direction_id,
                "slices": slices,
            })
    else:
        seen_ids = set()
        seen_files = set()
        for direction in directions:
            if not isinstance(direction, dict):
                raise ForgeError("Manifest contains an invalid sprite direction.")
            direction_id = _required_text(direction.get("id"))
            file_name = _required_text(direction.get("file"))
            if (
                direction_id is None
                or file_name is None
                or direction_id in seen_ids
                or file_name in seen_files
            ):
                raise ForgeError("Manifest contains an invalid sprite direction.")
            seen_ids.add(direction_id)
            seen_files.add(file_name)
            assets.append({
                **common,
                "file": file_name,
                "spriteMode": "Single",
                "name": direction_id,
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
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError(
            f"Cannot read Unity source manifest: {manifest_path}"
        ) from exc
    preset = build_unity_import_preset(manifest)
    output_path = manifest_path.parent / UNITY_PRESET_NAME
    temporary_path = (
        output_path.parent / f".{output_path.name}.staging-{uuid4().hex}"
    )
    try:
        with temporary_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(preset, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, output_path)
        except FileExistsError as exc:
            raise ForgeError(
                f"Unity import preset already exists: {output_path}"
            ) from exc
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path


def append_preset_to_zip(zip_path: Path, preset_path: Path) -> None:
    temporary_path = zip_path.with_suffix(zip_path.suffix + ".updating")
    temporary_created = False
    try:
        try:
            temporary_file = temporary_path.open("x+b")
            temporary_created = True
        except FileExistsError as exc:
            raise ForgeError(
                f"Unity preset update is already staged: {temporary_path}"
            ) from exc
        with temporary_file:
            with (
                ZipFile(zip_path, "r") as source,
                ZipFile(temporary_file, "w", ZIP_DEFLATED) as target,
            ):
                for item in source.infolist():
                    if item.filename != UNITY_PRESET_NAME:
                        target.writestr(item, source.read(item.filename))
                target.write(preset_path, UNITY_PRESET_NAME)
        temporary_path.replace(zip_path)
    except (OSError, BadZipFile) as exc:
        raise ForgeError(f"Cannot update Unity preset ZIP: {zip_path}") from exc
    finally:
        if temporary_created:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
