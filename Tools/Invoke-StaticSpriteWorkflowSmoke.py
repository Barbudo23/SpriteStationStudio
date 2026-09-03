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
from app.static_sprite_workflow import run_static_sprite_workflow
from app.static_sprite_workflow_audit import audit_static_sprite_workflow
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanStore, record_batch_review
from core.validation import encode_rgba_png


def prepare_inputs(root: Path) -> tuple[Path, Path]:
    items = []
    for index in range(1, 4):
        item_id = f"smoke-preview-{index}"
        output = root / "renders" / item_id
        output.mkdir(parents=True)
        pixels = bytearray(32 * 32 * 4)
        for y in range(6, 28):
            for x in range(8, 24):
                offset = (y * 32 + x) * 4
                pixels[offset:offset + 4] = bytes((index * 60, 80, 180, 255))
        (output / "Preview.png").write_bytes(encode_rgba_png(32, 32, bytes(pixels)))
        (output / "preview_manifest.json").write_text(json.dumps({
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "sprite": "Preview.png",
            "canvas": {"width": 32, "height": 32, "transparent": True, "colorMode": "RGBA"},
            "normalization": {"pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]}},
        }, indent=2) + "\n", encoding="utf-8")
        items.append(BatchItem(
            item_id=item_id,
            operation=BatchOperation.PREVIEW,
            source_path=f"models/smoke-{index}.glb",
            output_path=f"renders/{item_id}",
        ))
    plan = BatchPlan.create(items, plan_id="sss-workflow-smoke")
    for item in items:
        plan = plan.mark_running(item.item_id).mark_completed(
            item.item_id, f"renders/{item.item_id}/preview_manifest.json"
        )
    plan_path = root / "batch_plan.json"
    BatchPlanStore().save(plan, plan_path)
    contact = build_batch_contact_sheet(plan_path)
    return plan_path, contact.manifest_path


def run_smoke(root: Path) -> dict:
    plan_path, contact_manifest_path = prepare_inputs(root)
    review = record_batch_review(contact_manifest_path, plan_path, {
        "smoke-preview-1": "approved",
        "smoke-preview-2": "rejected",
        "smoke-preview-3": "approved",
    })
    workflow = run_static_sprite_workflow(review.path, plan_path)
    audit = audit_static_sprite_workflow(workflow.manifest_path)
    return {
        "application": "Sprite Station Studio",
        "workflowSchemaVersion": "1.0",
        "auditValid": audit.valid,
        "approvedItemIds": list(audit.approved_item_ids),
        "artifactCount": audit.artifact_count,
        "checkedFileCount": audit.checked_file_count,
        "readOnlyUnityPreparation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Static Sprite workflow smoke-test.")
    parser.add_argument(
        "--prepare-gui-fixture", type=Path, metavar="DIR",
        help="Create a new persistent plan/contact pair for disposable GUI QA instead of running smoke.",
    )
    args = parser.parse_args()
    if args.prepare_gui_fixture is not None:
        fixture_root = args.prepare_gui_fixture.expanduser().resolve()
        fixture_root.mkdir(parents=True, exist_ok=False)
        plan_path, contact_path = prepare_inputs(fixture_root)
        print(json.dumps({
            "application": "Sprite Station Studio",
            "purpose": "disposable_gui_qa_fixture",
            "plan": str(plan_path),
            "contactManifest": str(contact_path),
        }, ensure_ascii=False, indent=2))
        return 0
    with tempfile.TemporaryDirectory(prefix="sss-static-workflow-smoke-") as tmp:
        print(json.dumps(run_smoke(Path(tmp)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
