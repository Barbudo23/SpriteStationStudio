from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from app.engine_export import UNITY_PRESET_NAME
from app.unity_runner import UnityBridgeError
from core.validation import PreviewValidationError, decode_rgba_png


UNITY_ADAPTER_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class StaticSpriteUnityPackageResult:
    output_dir: Path
    preset_path: Path
    manifest_path: Path
    sprite_paths: tuple[Path, ...]


def build_static_sprite_unity_package(
    sprite_set_manifest_path: Path,
    output_dir: Path,
    pixels_per_unit: int = 100,
) -> StaticSpriteUnityPackageResult:
    """Create a portable Unity preview package without opening or modifying Unity."""
    sprite_set_manifest_path = sprite_set_manifest_path.expanduser().resolve()
    source_root = sprite_set_manifest_path.parent
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise UnityBridgeError(f"Unity adapter output already exists: {output_dir}")
    try:
        output_dir.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise UnityBridgeError("Unity adapter output must be outside the Static Sprite Set.")
    if not 1 <= pixels_per_unit <= 10000:
        raise UnityBridgeError("Pixels per unit must be between 1 and 10000.")

    sprite_set = _load_json(sprite_set_manifest_path)
    if sprite_set.get("schemaVersion") != "1.0" or sprite_set.get("kind") != "static_sprite_set":
        raise UnityBridgeError("Static Sprite Set contract is unsupported.")
    if sprite_set.get("application") != "Sprite Station Studio":
        raise UnityBridgeError("Static Sprite Set application brand is invalid.")
    raw_sprites = sprite_set.get("sprites")
    if not isinstance(raw_sprites, list) or not 1 <= len(raw_sprites) <= 3:
        raise UnityBridgeError("Static Sprite Set must contain between one and three sprites.")
    if sprite_set.get("spriteCount") != len(raw_sprites):
        raise UnityBridgeError("Static Sprite Set count does not match its sprites.")

    prepared = []
    names = set()
    for raw in raw_sprites:
        if not isinstance(raw, dict) or not isinstance(raw.get("itemId"), str):
            raise UnityBridgeError("Static Sprite Set item is invalid.")
        item_id = raw["itemId"]
        safe_name = _safe_name(item_id)
        if safe_name.casefold() in names:
            raise UnityBridgeError("Static Sprite Set item names collide.")
        names.add(safe_name.casefold())
        source = _resolve_file(source_root, raw.get("sprite"))
        expected_hash = raw.get("sha256")
        if not _is_sha256(expected_hash) or _sha256(source) != expected_hash:
            raise UnityBridgeError(f"Static Sprite Set integrity check failed: {item_id}")
        try:
            width, height, rgba = decode_rgba_png(source)
        except PreviewValidationError as exc:
            raise UnityBridgeError(f"Static Sprite Set PNG is invalid: {item_id}") from exc
        if raw.get("width") != width or raw.get("height") != height:
            raise UnityBridgeError(f"Static Sprite dimensions do not match manifest: {item_id}")
        alpha = rgba[3::4]
        visible = [index for index, value in enumerate(alpha) if value > 0]
        if not visible or not any(value < 255 for value in alpha):
            raise UnityBridgeError(f"Static Sprite requires visible pixels and transparency: {item_id}")
        xs = [index % width for index in visible]
        ys = [index // width for index in visible]
        alpha_bounds = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        if raw.get("alphaBounds") != alpha_bounds:
            raise UnityBridgeError(f"Static Sprite alpha bounds do not match manifest: {item_id}")
        pivot = raw.get("pivot") or {}
        if pivot.get("mode") != "bottom_center" or pivot.get("normalized") != [0.5, 0.0]:
            raise UnityBridgeError(f"Static Sprite pivot is unsupported: {item_id}")
        prepared.append((item_id, safe_name, source, expected_hash, width, height))

    temporary = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    relative_sprites = []
    try:
        (temporary / "sprites").mkdir(parents=True)
        assets = []
        package_sprites = []
        for item_id, safe_name, source, source_hash, width, height in prepared:
            relative = Path("sprites") / f"{safe_name}.png"
            shutil.copy2(source, temporary / relative)
            relative_sprites.append(relative)
            assets.append({
                "textureType": "Sprite",
                "alphaIsTransparency": True,
                "mipMaps": False,
                "wrapMode": "Clamp",
                "filterMode": "Bilinear",
                "compression": "Uncompressed",
                "pixelsPerUnit": pixels_per_unit,
                "pivot": [0.5, 0.0],
                "file": relative.as_posix(),
                "spriteMode": "Single",
                "name": item_id,
            })
            package_sprites.append({
                "itemId": item_id, "file": relative.as_posix(), "sha256": source_hash,
                "width": width, "height": height,
            })
        preset = {
            "schemaVersion": "1.0",
            "engine": "Unity",
            "sourceManifestVersion": sprite_set.get("schemaVersion"),
            "assetName": f"SSS_{_safe_name(str(sprite_set.get('planId') or 'StaticSprites'))}",
            "assets": assets,
            "applicationMode": "explicit_import",
        }
        preset_path = temporary / UNITY_PRESET_NAME
        preset_path.write_text(json.dumps(preset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        adapter_manifest = {
            "schemaVersion": UNITY_ADAPTER_SCHEMA_VERSION,
            "application": "Sprite Station Studio",
            "kind": "static_sprite_unity_preview_package",
            "readOnlyPreparation": True,
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "staticSpriteSetSha256": _sha256(sprite_set_manifest_path),
            "preset": UNITY_PRESET_NAME,
            "spriteCount": len(package_sprites),
            "sprites": package_sprites,
        }
        manifest_path = temporary / "unity_preview_package_manifest.json"
        manifest_path.write_text(
            json.dumps(adapter_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

    return StaticSpriteUnityPackageResult(
        output_dir=output_dir,
        preset_path=output_dir / UNITY_PRESET_NAME,
        manifest_path=output_dir / "unity_preview_package_manifest.json",
        sprite_paths=tuple(output_dir / relative for relative in relative_sprites),
    )


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnityBridgeError(f"Cannot read Static Sprite Set manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise UnityBridgeError("Static Sprite Set manifest must be a JSON object.")
    return payload


def _resolve_file(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise UnityBridgeError("Static Sprite path must be relative.")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise UnityBridgeError("Static Sprite path escapes its package.") from exc
    if not path.is_file():
        raise UnityBridgeError(f"Static Sprite file is missing: {path}")
    return path


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not safe:
        raise UnityBridgeError("Static Sprite name cannot be converted to a safe filename.")
    return safe


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
