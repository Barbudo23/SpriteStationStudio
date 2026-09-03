from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from core.batch import BatchPlanError
from core.validation import PreviewValidationError, validate_preview_png


STATIC_SPRITE_SET_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class StaticSpriteSetResult:
    output_dir: Path
    manifest_path: Path
    sprite_paths: tuple[Path, ...]
    item_ids: tuple[str, ...]


def build_static_sprite_set(staging_manifest_path: Path, output_dir: Path) -> StaticSpriteSetResult:
    """Build a deterministic static Sprite set from an approved staging package."""
    staging_manifest_path = staging_manifest_path.expanduser().resolve()
    staging_root = staging_manifest_path.parent
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise BatchPlanError(f"Static Sprite set output already exists: {output_dir}")
    try:
        output_dir.relative_to(staging_root)
    except ValueError:
        pass
    else:
        raise BatchPlanError("Static Sprite set output must be outside the staging package.")

    staging = _load_json(staging_manifest_path)
    if (
        staging.get("schemaVersion") != "1.0"
        or staging.get("kind") != "approved_preview_staging"
    ):
        raise BatchPlanError("Approved staging contract is unsupported.")
    if staging.get("application") != "Sprite Station Studio":
        raise BatchPlanError("Approved staging application brand is invalid.")
    raw_items = staging.get("items")
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 3:
        raise BatchPlanError("Approved staging must contain between one and three items.")
    if staging.get("approvedCount") != len(raw_items):
        raise BatchPlanError("Approved staging count does not match its items.")
    if not _is_sha256(staging.get("reviewSha256")):
        raise BatchPlanError("Approved staging review hash is invalid.")

    prepared = []
    item_ids = set()
    safe_names = set()
    for raw in raw_items:
        if not isinstance(raw, dict) or not isinstance(raw.get("itemId"), str):
            raise BatchPlanError("Approved staging item is invalid.")
        item_id = raw["itemId"]
        safe_name = _safe_name(item_id)
        if item_id in item_ids or safe_name.casefold() in safe_names:
            raise BatchPlanError("Approved staging item names are duplicated or collide.")
        item_ids.add(item_id)
        safe_names.add(safe_name.casefold())
        sprite_path = _resolve_file(staging_root, raw.get("sprite"), "Staged sprite")
        preview_manifest_path = _resolve_file(staging_root, raw.get("manifest"), "Staged manifest")
        expected_hash = raw.get("sourceSha256")
        if not _is_sha256(expected_hash) or _sha256(sprite_path) != expected_hash:
            raise BatchPlanError(f"Staged sprite integrity check failed: {item_id}")
        try:
            report = validate_preview_png(preview_manifest_path)
        except PreviewValidationError as exc:
            raise BatchPlanError(f"Staged Preview contract is invalid: {item_id}") from exc
        if report.sprite_path != sprite_path:
            raise BatchPlanError(f"Staged manifest references another sprite: {item_id}")
        preview_manifest = _load_json(preview_manifest_path)
        pivot = ((preview_manifest.get("normalization") or {}).get("pivot") or {})
        if pivot.get("mode") != "bottom_center" or pivot.get("normalized") != [0.5, 0.0]:
            raise BatchPlanError(f"Static Sprite requires bottom_center pivot: {item_id}")
        prepared.append((item_id, safe_name, sprite_path, report, expected_hash))

    temporary = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    sprite_relatives = []
    manifest_items = []
    try:
        (temporary / "sprites").mkdir(parents=True)
        for item_id, safe_name, sprite_path, report, source_hash in prepared:
            relative = Path("sprites") / f"{safe_name}.png"
            shutil.copy2(sprite_path, temporary / relative)
            sprite_relatives.append(relative)
            manifest_items.append({
                "itemId": item_id,
                "sprite": relative.as_posix(),
                "sha256": source_hash,
                "width": report.width,
                "height": report.height,
                "alphaBounds": list(report.alpha_bounds),
                "pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]},
            })
        output_manifest = {
            "schemaVersion": STATIC_SPRITE_SET_SCHEMA_VERSION,
            "application": "Sprite Station Studio",
            "kind": "static_sprite_set",
            "planId": staging.get("planId"),
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "approvedStagingSha256": _sha256(staging_manifest_path),
            "spriteCount": len(manifest_items),
            "sprites": manifest_items,
        }
        manifest_path = temporary / "static_sprite_set_manifest.json"
        manifest_path.write_text(
            json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

    return StaticSpriteSetResult(
        output_dir=output_dir,
        manifest_path=output_dir / "static_sprite_set_manifest.json",
        sprite_paths=tuple(output_dir / relative for relative in sprite_relatives),
        item_ids=tuple(item[0] for item in prepared),
    )


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchPlanError(f"Cannot read SpriteBuilder JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchPlanError("SpriteBuilder JSON root must be an object.")
    return payload


def _resolve_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise BatchPlanError(f"{label} path must be relative.")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError(f"{label} path escapes the staging package.") from exc
    if not path.is_file():
        raise BatchPlanError(f"{label} is missing: {path}")
    return path


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not safe:
        raise BatchPlanError("Sprite itemId cannot be converted to a safe filename.")
    return safe


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
