from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from app.approved_preview_staging import stage_approved_previews
from app.static_sprite_builder import build_static_sprite_set
from app.static_sprite_unity_adapter import build_static_sprite_unity_package
from core.batch import BatchPlanError


STATIC_SPRITE_WORKFLOW_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class StaticSpriteWorkflowResult:
    output_dir: Path
    manifest_path: Path
    approved_staging_manifest: Path
    sprite_set_manifest: Path
    unity_preset_path: Path
    unity_package_manifest: Path
    approved_item_ids: tuple[str, ...]


def run_static_sprite_workflow(
    review_path: Path,
    plan_path: Path,
    output_path: str = "workflow/approved-static-sprites",
    pixels_per_unit: int = 100,
) -> StaticSpriteWorkflowResult:
    """Publish the approved Static Sprite workflow as one all-or-nothing directory."""
    plan_path = plan_path.expanduser().resolve()
    plan_root = plan_path.parent
    output_dir = _resolve_output(plan_root, output_path)
    if output_dir.exists():
        raise BatchPlanError(f"Static Sprite workflow output already exists: {output_dir}")
    temporary = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    try:
        temporary_relative = temporary.relative_to(plan_root).as_posix()
        approved = stage_approved_previews(
            review_path,
            plan_path,
            f"{temporary_relative}/approved-staging",
        )
        sprite_set = build_static_sprite_set(
            approved.manifest_path,
            temporary / "static-sprite-set",
        )
        unity_package = build_static_sprite_unity_package(
            sprite_set.manifest_path,
            temporary / "unity-preview-package",
            pixels_per_unit=pixels_per_unit,
        )
        workflow_manifest = {
            "schemaVersion": STATIC_SPRITE_WORKFLOW_SCHEMA_VERSION,
            "application": "Sprite Station Studio",
            "kind": "approved_static_sprite_workflow",
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "readOnlyUnityPreparation": True,
            "approvedItemIds": list(approved.approved_item_ids),
            "artifacts": {
                "approvedStagingManifest": _artifact(temporary, approved.manifest_path),
                "staticSpriteSetManifest": _artifact(temporary, sprite_set.manifest_path),
                "unityImportPreset": _artifact(temporary, unity_package.preset_path),
                "unityPackageManifest": _artifact(temporary, unity_package.manifest_path),
            },
        }
        manifest_path = temporary / "static_sprite_workflow_manifest.json"
        manifest_path.write_text(
            json.dumps(workflow_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(output_dir)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    return StaticSpriteWorkflowResult(
        output_dir=output_dir,
        manifest_path=output_dir / "static_sprite_workflow_manifest.json",
        approved_staging_manifest=output_dir / "approved-staging/approved_staging_manifest.json",
        sprite_set_manifest=output_dir / "static-sprite-set/static_sprite_set_manifest.json",
        unity_preset_path=output_dir / "unity-preview-package/unity_import_preset.json",
        unity_package_manifest=output_dir / "unity-preview-package/unity_preview_package_manifest.json",
        approved_item_ids=approved.approved_item_ids,
    )


def _resolve_output(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise BatchPlanError("Static Sprite workflow output must be a safe relative path.")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError("Static Sprite workflow output escapes the plan directory.") from exc
    return resolved


def _artifact(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
