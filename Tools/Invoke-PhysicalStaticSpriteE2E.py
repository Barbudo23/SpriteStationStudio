from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from app.batch_contact_sheet import build_batch_contact_sheet
from app.batch_preview import BatchPreviewCoordinator
from app.static_sprite_workflow import run_static_sprite_workflow
from app.static_sprite_workflow_audit import audit_static_sprite_workflow
from app.unity_sprite_preview import UnitySpritePreviewRunner
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanStore, record_batch_review


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a fresh physical Blender-to-Unity Static Sprite E2E.")
    parser.add_argument("--blender", required=True, type=Path)
    parser.add_argument("--unity", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--resolution", type=int, default=128)
    args = parser.parse_args()
    model = args.model.expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(f"3D model not found: {model}")
    with tempfile.TemporaryDirectory(prefix="sss-physical-static-e2e-") as tmp:
        root = Path(tmp)
        items = tuple(BatchItem(
            item_id=f"physical-preview-{index}",
            operation=BatchOperation.PREVIEW,
            source_path=model.as_posix(),
            output_path=f"renders/physical-preview-{index}",
        ) for index in range(1, 3))
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(BatchPlan.create(items, plan_id="sss-physical-e2e"), plan_path)
        batch = BatchPreviewCoordinator(
            args.blender,
            resolution=args.resolution,
            camera_profile="Strategy30",
        ).run_batch(plan_path, max_items=2)
        if batch.error or len(batch.completed_item_ids) != 2:
            raise RuntimeError(f"Fresh Blender Batch Preview failed: {batch.error}")
        contact = build_batch_contact_sheet(plan_path)
        review = record_batch_review(contact.manifest_path, plan_path, {
            "physical-preview-1": "approved",
            "physical-preview-2": "approved",
        })
        workflow = run_static_sprite_workflow(review.path, plan_path)
        before_unity = audit_static_sprite_workflow(workflow.manifest_path)
        unity_result = UnitySpritePreviewRunner(
            bridge_project=REPOSITORY / "unity_bridge_project"
        ).run(args.unity, workflow.unity_preset_path, timeout=600)
        assets = unity_result.report.get("spriteAssets") or []
        warnings = unity_result.report.get("warnings") or []
        if not unity_result.report.get("readOnlyPreview"):
            raise RuntimeError("Unity result is not marked read-only.")
        if len(assets) != 2 or not all(asset.get("valid") for asset in assets):
            raise RuntimeError("Unity did not validate both freshly rendered sprites.")
        if warnings:
            raise RuntimeError(f"Unity preview warnings: {warnings}")
        final_audit = audit_static_sprite_workflow(workflow.manifest_path)
        print(json.dumps({
            "application": "Sprite Station Studio",
            "model": str(model),
            "blender": str(args.blender.expanduser().resolve()),
            "unity": str(args.unity.expanduser().resolve()),
            "resolution": args.resolution,
            "freshBlenderPreviewCount": len(batch.completed_item_ids),
            "approvedItemIds": list(final_audit.approved_item_ids),
            "workflowAuditBeforeUnity": before_unity.valid,
            "workflowAuditAfterUnity": final_audit.valid,
            "unityReadOnlyPreview": True,
            "unityValidSpriteCount": sum(bool(asset.get("valid")) for asset in assets),
            "unityWarnings": warnings,
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
