from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.batch_contact_sheet import build_batch_contact_sheet
from core.batch import (
    BatchItem, BatchOperation, BatchPlan, BatchPlanError, BatchPlanStore,
    ReviewDecision, record_batch_review,
)
from core.validation import encode_rgba_png


class BatchReviewTests(unittest.TestCase):
    def prepare(self, root: Path):
        items = []
        for index in range(1, 4):
            output = root / "renders" / f"preview-{index}"
            output.mkdir(parents=True)
            rgba = bytes((index * 50, 80, 100, 255, 0, 0, 0, 0) * 2)
            (output / "Preview.png").write_bytes(encode_rgba_png(2, 2, rgba))
            (output / "preview_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1", "sprite": "Preview.png",
                "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
            }), encoding="utf-8")
            items.append(BatchItem(
                item_id=f"preview-{index}", operation=BatchOperation.PREVIEW,
                source_path=f"models/unit-{index}.glb", output_path=f"renders/preview-{index}",
            ))
        plan = BatchPlan.create(items, plan_id="decision-plan")
        for index in range(1, 4):
            item_id = f"preview-{index}"
            plan = plan.mark_running(item_id).mark_completed(
                item_id, f"renders/{item_id}/preview_manifest.json"
            )
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        contact = build_batch_contact_sheet(plan_path)
        return plan_path, contact

    def test_records_complete_decisions_without_mutating_review_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, contact = self.prepare(Path(tmp))
            plan_before = plan_path.read_bytes()
            contact_before = contact.manifest_path.read_bytes()
            image_before = contact.image_path.read_bytes()
            result = record_batch_review(contact.manifest_path, plan_path, {
                "preview-1": "approved", "preview-2": ReviewDecision.REJECTED,
                "preview-3": "approved",
            })
            payload = json.loads(result.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"], "1.0")
            self.assertEqual(payload["application"], "Sprite Station Studio")
            self.assertEqual(
                [item["decision"] for item in payload["items"]],
                ["approved", "rejected", "approved"],
            )
            self.assertEqual(plan_path.read_bytes(), plan_before)
            self.assertEqual(contact.manifest_path.read_bytes(), contact_before)
            self.assertEqual(contact.image_path.read_bytes(), image_before)

    def test_rejects_incomplete_or_invalid_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, contact = self.prepare(Path(tmp))
            with self.assertRaisesRegex(BatchPlanError, "exactly one"):
                record_batch_review(contact.manifest_path, plan_path, {"preview-1": "approved"})
            with self.assertRaisesRegex(BatchPlanError, "approved or rejected"):
                record_batch_review(contact.manifest_path, plan_path, {
                    "preview-1": "maybe", "preview-2": "rejected", "preview-3": "approved",
                })

    def test_rejects_changed_source_and_never_overwrites_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, contact = self.prepare(root)
            decisions = {f"preview-{index}": "approved" for index in range(1, 4)}
            (root / "renders" / "preview-2" / "Preview.png").write_bytes(b"changed")
            with self.assertRaisesRegex(BatchPlanError, "changed after"):
                record_batch_review(contact.manifest_path, plan_path, decisions)

            plan_path, contact = self.prepare(root / "second")
            record_batch_review(contact.manifest_path, plan_path, decisions)
            with self.assertRaisesRegex(BatchPlanError, "already exists"):
                record_batch_review(contact.manifest_path, plan_path, decisions)


if __name__ == "__main__":
    unittest.main()
