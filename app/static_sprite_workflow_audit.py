from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from core.batch import BatchPlanError
from core.validation import PreviewValidationError, decode_rgba_png


@dataclass(frozen=True)
class StaticSpriteWorkflowAudit:
    workflow_root: Path
    approved_item_ids: tuple[str, ...]
    artifact_count: int
    checked_file_count: int
    valid: bool = True


def audit_static_sprite_workflow(manifest_path: Path) -> StaticSpriteWorkflowAudit:
    """Strictly validate a published workflow without writing any files."""
    manifest_path = manifest_path.expanduser().resolve()
    root = manifest_path.parent
    workflow = _load_json(manifest_path, "Workflow manifest")
    _contract(workflow, "approved_static_sprite_workflow", "Workflow manifest")
    if workflow.get("readOnlyUnityPreparation") is not True:
        raise BatchPlanError("Workflow is not marked as read-only Unity preparation.")
    approved_ids = _item_id_list(workflow.get("approvedItemIds"), "Workflow approvedItemIds")
    artifacts = workflow.get("artifacts")
    expected_artifacts = {
        "approvedStagingManifest", "staticSpriteSetManifest",
        "unityImportPreset", "unityPackageManifest",
    }
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        raise BatchPlanError("Workflow artifacts are incomplete or unexpected.")
    resolved = {}
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict) or not _is_sha256(artifact.get("sha256")):
            raise BatchPlanError(f"Workflow artifact descriptor is invalid: {name}")
        path = _resolve_file(root, artifact.get("path"), f"Workflow artifact {name}")
        if _sha256(path) != artifact["sha256"]:
            raise BatchPlanError(f"Workflow artifact hash mismatch: {name}")
        resolved[name] = path

    staging = _load_json(resolved["approvedStagingManifest"], "Approved staging manifest")
    _contract(staging, "approved_preview_staging", "Approved staging manifest")
    staging_items = _items(staging.get("items"), "Approved staging")
    if staging.get("approvedCount") != len(staging_items):
        raise BatchPlanError("Approved staging count mismatch.")

    sprite_set = _load_json(resolved["staticSpriteSetManifest"], "Static Sprite Set manifest")
    _contract(sprite_set, "static_sprite_set", "Static Sprite Set manifest")
    sprite_items = _items(sprite_set.get("sprites"), "Static Sprite Set")
    if sprite_set.get("spriteCount") != len(sprite_items):
        raise BatchPlanError("Static Sprite Set count mismatch.")

    unity_package = _load_json(resolved["unityPackageManifest"], "Unity package manifest")
    _contract(unity_package, "static_sprite_unity_preview_package", "Unity package manifest")
    if unity_package.get("readOnlyPreparation") is not True:
        raise BatchPlanError("Unity package is not marked as read-only preparation.")
    unity_items = _items(unity_package.get("sprites"), "Unity package")
    if unity_package.get("spriteCount") != len(unity_items):
        raise BatchPlanError("Unity package sprite count mismatch.")

    preset = _load_json(resolved["unityImportPreset"], "Unity import preset")
    if preset.get("schemaVersion") != "1.0" or preset.get("engine") != "Unity":
        raise BatchPlanError("Unity import preset contract is unsupported.")
    if preset.get("applicationMode") != "explicit_import":
        raise BatchPlanError("Unity import preset must require explicit import.")
    preset_assets = preset.get("assets")
    if not isinstance(preset_assets, list) or len(preset_assets) != len(approved_ids):
        raise BatchPlanError("Unity import preset asset count mismatch.")

    item_sets = (set(staging_items), set(sprite_items), set(unity_items))
    if any(item_set != set(approved_ids) for item_set in item_sets):
        raise BatchPlanError("Workflow item identities differ between artifacts.")
    if {asset.get("name") for asset in preset_assets if isinstance(asset, dict)} != set(approved_ids):
        raise BatchPlanError("Unity preset assets do not match approved item identities.")

    checked_files = len(resolved)
    for item_id, item in staging_items.items():
        sprite = _resolve_file(resolved["approvedStagingManifest"].parent, item.get("sprite"), "Staged sprite")
        if _sha256(sprite) != item.get("sourceSha256"):
            raise BatchPlanError(f"Approved staging sprite hash mismatch: {item_id}")
        checked_files += 1
    for item_id, item in sprite_items.items():
        sprite = _resolve_file(resolved["staticSpriteSetManifest"].parent, item.get("sprite"), "Static Sprite")
        if _sha256(sprite) != item.get("sha256"):
            raise BatchPlanError(f"Static Sprite hash mismatch: {item_id}")
        try:
            width, height, _ = decode_rgba_png(sprite)
        except PreviewValidationError as exc:
            raise BatchPlanError(f"Static Sprite PNG is invalid: {item_id}") from exc
        if (item.get("width"), item.get("height")) != (width, height):
            raise BatchPlanError(f"Static Sprite dimensions mismatch: {item_id}")
        checked_files += 1
    for item_id, item in unity_items.items():
        sprite = _resolve_file(resolved["unityPackageManifest"].parent, item.get("file"), "Unity package sprite")
        if _sha256(sprite) != item.get("sha256"):
            raise BatchPlanError(f"Unity package sprite hash mismatch: {item_id}")
        checked_files += 1

    return StaticSpriteWorkflowAudit(
        workflow_root=root,
        approved_item_ids=approved_ids,
        artifact_count=len(resolved),
        checked_file_count=checked_files,
    )


def _contract(payload: dict, kind: str, label: str) -> None:
    if payload.get("schemaVersion") != "1.0" or payload.get("kind") != kind:
        raise BatchPlanError(f"{label} contract is unsupported.")
    if payload.get("application") != "Sprite Station Studio":
        raise BatchPlanError(f"{label} application brand is invalid.")


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchPlanError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchPlanError(f"{label} must be a JSON object.")
    return payload


def _item_id_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        raise BatchPlanError(f"{label} must contain between one and three values.")
    if not all(isinstance(item, str) and item for item in value) or len(value) != len(set(value)):
        raise BatchPlanError(f"{label} contains invalid or duplicate values.")
    return tuple(value)


def _items(value: object, label: str) -> dict[str, dict]:
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        raise BatchPlanError(f"{label} must contain between one and three items.")
    result = {}
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("itemId"), str):
            raise BatchPlanError(f"{label} item is invalid.")
        if item["itemId"] in result:
            raise BatchPlanError(f"{label} contains duplicate itemId values.")
        result[item["itemId"]] = item
    return result


def _resolve_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise BatchPlanError(f"{label} path must be relative.")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError(f"{label} path escapes its package.") from exc
    if not path.is_file():
        raise BatchPlanError(f"{label} is missing: {path}")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
