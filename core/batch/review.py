from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from core.batch.model import BatchPlanError
from core.batch.store import BatchPlanStore


BATCH_REVIEW_SCHEMA_VERSION = "1.0"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class BatchReviewResult:
    path: Path
    plan_id: str
    decisions: tuple[tuple[str, ReviewDecision], ...]


def record_batch_review(
    contact_manifest_path: Path,
    plan_path: Path,
    decisions: Mapping[str, ReviewDecision | str],
    output_name: str = "review_decision.json",
) -> BatchReviewResult:
    """Verify a contact sheet and atomically record one decision per item."""
    contact_manifest_path = contact_manifest_path.expanduser().resolve()
    contact_root = contact_manifest_path.parent
    plan_path = plan_path.expanduser().resolve()
    contact = _load_json(contact_manifest_path, "Contact sheet manifest")
    if contact.get("schemaVersion") != "1.0":
        raise BatchPlanError("Unsupported contact sheet schemaVersion.")
    if contact.get("application") != "Sprite Station Studio":
        raise BatchPlanError("Contact sheet application brand is invalid.")
    if contact.get("kind") != "batch_preview_contact_sheet" or contact.get("readOnlyReview") is not True:
        raise BatchPlanError("Contact sheet is not a read-only Batch Preview review.")

    declared_plan = contact.get("plan")
    if not isinstance(declared_plan, str) or (contact_root / declared_plan).resolve() != plan_path:
        raise BatchPlanError("Contact sheet does not reference the selected BatchPlan.")
    plan = BatchPlanStore().load(plan_path)
    if contact.get("planId") != plan.plan_id:
        raise BatchPlanError("Contact sheet does not match its BatchPlan.")
    image_path = _resolve_inside(contact_root, contact.get("image"), "Contact sheet image")
    if not image_path.is_file():
        raise BatchPlanError("Contact sheet image is missing.")

    raw_items = contact.get("items")
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 3:
        raise BatchPlanError("Contact sheet must contain between one and three items.")
    plan_root = plan_path.parent
    plan_items = {item.item_id: item for item in plan.items}
    item_ids = []
    source_hashes = []
    for raw in raw_items:
        if not isinstance(raw, dict) or not isinstance(raw.get("itemId"), str):
            raise BatchPlanError("Contact sheet item is invalid.")
        item_id = raw["itemId"]
        if item_id not in plan_items or not plan_items[item_id].result_manifest:
            raise BatchPlanError(f"Contact sheet item does not belong to BatchPlan: {item_id}")
        declared_manifest = _resolve_inside(plan_root, raw.get("manifest"), "Contact sheet manifest")
        expected_manifest = (plan_root / plan_items[item_id].result_manifest).resolve()
        if declared_manifest != expected_manifest:
            raise BatchPlanError(f"Contact sheet result manifest does not match BatchPlan: {item_id}")
        sprite = _resolve_inside(plan_root, raw.get("sprite"), "Contact sheet sprite")
        expected_hash = raw.get("sha256")
        if not sprite.is_file() or not isinstance(expected_hash, str):
            raise BatchPlanError(f"Reviewed sprite is missing or invalid: {item_id}")
        actual_hash = hashlib.sha256(sprite.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise BatchPlanError(f"Reviewed sprite changed after contact sheet creation: {item_id}")
        item_ids.append(item_id)
        source_hashes.append({"itemId": item_id, "sha256": actual_hash})
    if len(item_ids) != len(set(item_ids)):
        raise BatchPlanError("Contact sheet contains duplicate itemId values.")
    if set(item_ids) != set(plan_items):
        raise BatchPlanError("Contact sheet items do not match BatchPlan items.")

    normalized = {}
    try:
        normalized = {key: ReviewDecision(value) for key, value in decisions.items()}
    except (TypeError, ValueError) as exc:
        raise BatchPlanError("Review decisions must be approved or rejected.") from exc
    if set(normalized) != set(item_ids):
        raise BatchPlanError("Review requires exactly one decision for every contact sheet item.")

    if not output_name or Path(output_name).name != output_name or Path(output_name).suffix.lower() != ".json":
        raise BatchPlanError("Review output must be a JSON filename in the contact sheet directory.")
    output_path = contact_root / output_name
    if output_path.exists():
        raise BatchPlanError(f"Review decision already exists: {output_path}")
    payload = {
        "schemaVersion": BATCH_REVIEW_SCHEMA_VERSION,
        "application": "Sprite Station Studio",
        "kind": "batch_preview_review_decision",
        "planId": plan.plan_id,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "contactManifest": contact_manifest_path.name,
        "contactManifestSha256": hashlib.sha256(contact_manifest_path.read_bytes()).hexdigest(),
        "contactSheetSha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "items": [
            {"itemId": item_id, "decision": normalized[item_id].value, "sourceSha256": source["sha256"]}
            for item_id, source in zip(item_ids, source_hashes)
        ],
    }
    temporary = contact_root / f".{output_name}.staging-{uuid4().hex}"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return BatchReviewResult(
        path=output_path,
        plan_id=plan.plan_id,
        decisions=tuple((item_id, normalized[item_id]) for item_id in item_ids),
    )


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchPlanError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchPlanError(f"{label} must be a JSON object.")
    return payload


def _resolve_inside(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise BatchPlanError(f"{label} path is missing.")
    candidate = Path(value)
    if candidate.is_absolute():
        raise BatchPlanError(f"{label} path must be relative.")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError(f"{label} path escapes its root.") from exc
    return resolved
