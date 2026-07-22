from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from core.batch import BatchPlanError, BatchPlanStore
from core.validation import PreviewValidationError, validate_preview_png


APPROVED_STAGING_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ApprovedPreviewStagingResult:
    output_dir: Path
    manifest_path: Path
    approved_item_ids: tuple[str, ...]
    copied_files: tuple[Path, ...]


def stage_approved_previews(
    review_path: Path,
    plan_path: Path,
    output_path: str = "staging/approved-previews",
) -> ApprovedPreviewStagingResult:
    """Copy integrity-checked approved previews into a new isolated package."""
    review_path = review_path.expanduser().resolve()
    plan_path = plan_path.expanduser().resolve()
    plan_root = plan_path.parent
    review = _load_json(review_path, "Batch review")
    _require_contract(review, "1.0", "batch_preview_review_decision", "Batch review")
    plan = BatchPlanStore().load(plan_path)
    if review.get("planId") != plan.plan_id:
        raise BatchPlanError("Batch review does not match the selected BatchPlan.")

    contact_path = _resolve_inside(review_path.parent, review.get("contactManifest"), "Contact manifest")
    if _sha256(contact_path) != review.get("contactManifestSha256"):
        raise BatchPlanError("Contact manifest changed after the review decision.")
    contact = _load_json(contact_path, "Contact manifest")
    _require_contract(contact, "1.0", "batch_preview_contact_sheet", "Contact manifest")
    declared_plan = contact.get("plan")
    if not isinstance(declared_plan, str) or (contact_path.parent / declared_plan).resolve() != plan_path:
        raise BatchPlanError("Contact manifest does not reference the selected BatchPlan.")
    image_path = _resolve_inside(contact_path.parent, contact.get("image"), "Contact sheet")
    if _sha256(image_path) != review.get("contactSheetSha256"):
        raise BatchPlanError("Contact sheet changed after the review decision.")

    contact_items = _items_by_id(contact.get("items"), "Contact manifest")
    review_items = _items_by_id(review.get("items"), "Batch review")
    if set(contact_items) != set(review_items):
        raise BatchPlanError("Batch review items do not match the contact manifest.")
    plan_items = {item.item_id: item for item in plan.items}
    if set(contact_items) != set(plan_items):
        raise BatchPlanError("Contact manifest items do not match the selected BatchPlan.")

    approved = []
    for item_id, decision in review_items.items():
        value = decision.get("decision")
        if value not in {"approved", "rejected"}:
            raise BatchPlanError(f"Invalid review decision for {item_id}.")
        contact_item = contact_items[item_id]
        expected_hash = contact_item.get("sha256")
        if decision.get("sourceSha256") != expected_hash:
            raise BatchPlanError(f"Review source hash does not match contact manifest: {item_id}")
        sprite_path = _resolve_inside(plan_root, contact_item.get("sprite"), "Approved sprite")
        manifest_path = _resolve_inside(plan_root, contact_item.get("manifest"), "Approved manifest")
        expected_manifest = (plan_root / str(plan_items[item_id].result_manifest)).resolve()
        if manifest_path != expected_manifest:
            raise BatchPlanError(f"Approved manifest does not match BatchPlan: {item_id}")
        try:
            report = validate_preview_png(manifest_path)
        except PreviewValidationError as exc:
            raise BatchPlanError(f"Approved Preview changed after review: {item_id}") from exc
        if report.sprite_path != sprite_path or _sha256(sprite_path) != expected_hash:
            raise BatchPlanError(f"Approved Preview changed after review: {item_id}")
        if value == "approved":
            approved.append((item_id, sprite_path, manifest_path, expected_hash))
    if not approved:
        raise BatchPlanError("Batch review contains no approved Preview items.")
    safe_names = [_safe_name(item[0]) for item in approved]
    if len(safe_names) != len(set(name.casefold() for name in safe_names)):
        raise BatchPlanError("Approved itemId values collide as staging directory names.")

    output_dir = _resolve_output(plan_root, output_path)
    if output_dir.exists():
        raise BatchPlanError(f"Approved staging output already exists: {output_dir}")
    staging = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    copied_relatives = []
    package_items = []
    try:
        staging.mkdir(parents=True)
        for item_id, sprite_path, manifest_path, source_hash in approved:
            item_dir = Path("items") / _safe_name(item_id)
            sprite_relative = item_dir / "Preview.png"
            manifest_relative = item_dir / "preview_manifest.json"
            (staging / item_dir).mkdir(parents=True)
            shutil.copy2(sprite_path, staging / sprite_relative)
            shutil.copy2(manifest_path, staging / manifest_relative)
            copied_relatives.extend((sprite_relative, manifest_relative))
            package_items.append({
                "itemId": item_id,
                "sprite": sprite_relative.as_posix(),
                "manifest": manifest_relative.as_posix(),
                "sourceSha256": source_hash,
            })
        package_manifest = {
            "schemaVersion": APPROVED_STAGING_SCHEMA_VERSION,
            "application": "Sprite Station Studio",
            "kind": "approved_preview_staging",
            "planId": plan.plan_id,
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "reviewSha256": _sha256(review_path),
            "approvedCount": len(package_items),
            "items": package_items,
        }
        package_manifest_path = staging / "approved_staging_manifest.json"
        package_manifest_path.write_text(
            json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        copied_relatives.append(Path(package_manifest_path.name))
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return ApprovedPreviewStagingResult(
        output_dir=output_dir,
        manifest_path=output_dir / "approved_staging_manifest.json",
        approved_item_ids=tuple(item[0] for item in approved),
        copied_files=tuple(output_dir / relative for relative in copied_relatives),
    )


def _require_contract(payload: dict, schema: str, kind: str, label: str) -> None:
    if payload.get("schemaVersion") != schema or payload.get("kind") != kind:
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


def _items_by_id(value: object, label: str) -> dict[str, dict]:
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


def _resolve_inside(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise BatchPlanError(f"{label} path must be relative.")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError(f"{label} path escapes its root.") from exc
    if not resolved.is_file():
        raise BatchPlanError(f"{label} file is missing: {resolved}")
    return resolved


def _resolve_output(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise BatchPlanError("Approved staging output must be a safe relative path.")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPlanError("Approved staging output escapes the plan directory.") from exc
    return resolved


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not safe:
        raise BatchPlanError("Approved itemId cannot be converted to a safe directory name.")
    return safe


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise BatchPlanError(f"Integrity-checked file is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()
