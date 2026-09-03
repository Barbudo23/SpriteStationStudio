from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import os
import shutil
from uuid import uuid4

from core.batch import BatchOperation, BatchPlanError, BatchPlanStore, BatchStatus
from core.validation import decode_rgba_png, encode_rgba_png, validate_preview_png


CONTACT_SHEET_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class BatchContactSheetResult:
    output_dir: Path
    image_path: Path
    manifest_path: Path
    item_ids: tuple[str, ...]


def build_batch_contact_sheet(
    plan_path: Path,
    output_path: str = "review/contact-sheet",
    gap: int = 16,
) -> BatchContactSheetResult:
    """Create a new review package without changing source previews or BatchPlan."""
    plan_path = plan_path.expanduser().resolve()
    plan_root = plan_path.parent
    plan = BatchPlanStore().load(plan_path)
    if not 1 <= len(plan.items) <= 3:
        raise BatchPlanError("Contact sheet requires between one and three Preview items.")
    if any(item.operation != BatchOperation.PREVIEW for item in plan.items):
        raise BatchPlanError("Contact sheet accepts Preview operations only.")
    if any(item.status != BatchStatus.COMPLETED for item in plan.items):
        raise BatchPlanError("All Preview items must be completed before review.")
    if not 0 <= gap <= 128:
        raise BatchPlanError("Contact sheet gap must be between 0 and 128 pixels.")

    output_dir = _resolve_output(plan_root, output_path)
    if output_dir.exists():
        raise BatchPlanError(f"Contact sheet output already exists: {output_dir}")

    sources = []
    for item in plan.items:
        assert item.result_manifest is not None
        manifest_path = _resolve_manifest(plan_root, item.result_manifest)
        report = validate_preview_png(manifest_path)
        width, height, rgba = decode_rgba_png(report.sprite_path)
        sources.append((item, manifest_path, report.sprite_path, width, height, rgba))

    sheet_width = sum(source[3] for source in sources) + gap * (len(sources) - 1)
    sheet_height = max(source[4] for source in sources)
    canvas = bytearray(sheet_width * sheet_height * 4)
    x_offset = 0
    manifest_items = []
    for item, manifest_path, sprite_path, width, height, rgba in sources:
        y_offset = (sheet_height - height) // 2
        _blit(canvas, sheet_width, rgba, width, height, x_offset, y_offset)
        manifest_items.append({
            "itemId": item.item_id,
            "manifest": manifest_path.relative_to(plan_root).as_posix(),
            "sprite": sprite_path.relative_to(plan_root).as_posix(),
            "sha256": hashlib.sha256(sprite_path.read_bytes()).hexdigest(),
            "x": x_offset,
            "y": y_offset,
            "width": width,
            "height": height,
        })
        x_offset += width + gap

    staging = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    try:
        staging.mkdir(parents=True)
        image_path = staging / "contact_sheet.png"
        image_path.write_bytes(encode_rgba_png(sheet_width, sheet_height, bytes(canvas)))
        manifest = {
            "schemaVersion": CONTACT_SHEET_SCHEMA_VERSION,
            "application": "Sprite Station Studio",
            "kind": "batch_preview_contact_sheet",
            "readOnlyReview": True,
            "planId": plan.plan_id,
            "plan": os.path.relpath(plan_path, output_dir).replace("\\", "/"),
            "plan": os.path.relpath(plan_path, output_dir).replace("\\", "/"),
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "image": image_path.name,
            "canvas": {"width": sheet_width, "height": sheet_height, "colorMode": "RGBA"},
            "gap": gap,
            "items": manifest_items,
        }
        manifest_path = staging / "contact_sheet_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return BatchContactSheetResult(
        output_dir=output_dir,
        image_path=output_dir / "contact_sheet.png",
        manifest_path=output_dir / "contact_sheet_manifest.json",
        item_ids=tuple(item.item_id for item in plan.items),
    )


def _resolve_manifest(plan_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        raise BatchPlanError("Batch resultManifest must be relative to the plan directory.")
    resolved = (plan_root / candidate).resolve()
    try:
        resolved.relative_to(plan_root)
    except ValueError as exc:
        raise BatchPlanError("Batch resultManifest escapes the plan directory.") from exc
    return resolved


def _resolve_output(plan_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise BatchPlanError("Contact sheet output path must be a safe relative path.")
    resolved = (plan_root / candidate).resolve()
    try:
        resolved.relative_to(plan_root)
    except ValueError as exc:
        raise BatchPlanError("Contact sheet output path escapes the plan directory.") from exc
    return resolved


def _blit(
    target: bytearray,
    target_width: int,
    source: bytes,
    source_width: int,
    source_height: int,
    x_offset: int,
    y_offset: int,
) -> None:
    row_bytes = source_width * 4
    for row in range(source_height):
        source_start = row * row_bytes
        target_start = ((row + y_offset) * target_width + x_offset) * 4
        target[target_start:target_start + row_bytes] = source[source_start:source_start + row_bytes]
