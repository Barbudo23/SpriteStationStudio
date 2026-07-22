from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.approved_preview_staging import stage_approved_previews
from app.batch_contact_sheet import build_batch_contact_sheet
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanError, BatchPlanStore, record_batch_review
from core.validation import encode_rgba_png


class ApprovedPreviewStagingTests(unittest.TestCase):
    def prepare(self, root: Path, decisions: dict[str, str]):
        items = []
        for index in range(1, 4):
            item_id = f"preview-{index}"
            output = root / "renders" / item_id
            output.mkdir(parents=True)
            rgba = bytes((index * 60, 90, 120, 255, 0, 0, 0, 0) * 2)
            (output / "Preview.png").write_bytes(encode_rgba_png(2, 2, rgba))
            (output / "preview_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1", "sprite": "Preview.png",
                "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
            }), encoding="utf-8")
            items.append(BatchItem(
                item_id=item_id, operation=BatchOperation.PREVIEW,
                source_path=f"models/unit-{index}.glb", output_path=f"renders/{item_id}",
            ))
        plan = BatchPlan.create(items, plan_id="staging-plan")
        for index in range(1, 4):
            item_id = f"preview-{index}"
            plan = plan.mark_running(item_id).mark_completed(
                item_id, f"renders/{item_id}/preview_manifest.json"
            )
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        contact = build_batch_contact_sheet(plan_path)
        review = record_batch_review(contact.manifest_path, plan_path, decisions)
        return plan_path, contact, review

    def test_stages_only_approved_previews_without_mutating_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, contact, review = self.prepare(root, {
                "preview-1": "approved", "preview-2": "rejected", "preview-3": "approved",
            })
            protected = [plan_path, contact.manifest_path, contact.image_path, review.path]
            before = {path: path.read_bytes() for path in protected}
            result = stage_approved_previews(review.path, plan_path)
            self.assertEqual(result.approved_item_ids, ("preview-1", "preview-3"))
            self.assertTrue((result.output_dir / "items/preview-1/Preview.png").is_file())
            self.assertFalse((result.output_dir / "items/preview-2").exists())
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["application"], "Sprite Station Studio")
            self.assertEqual(payload["approvedCount"], 2)
            self.assertEqual({path: path.read_bytes() for path in protected}, before)
            self.assertEqual(list((root / "staging").glob(".*.staging-*")), [])

    def test_rejects_all_rejected_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            decisions = {f"preview-{index}": "rejected" for index in range(1, 4)}
            plan_path, _, review = self.prepare(Path(tmp), decisions)
            with self.assertRaisesRegex(BatchPlanError, "no approved"):
                stage_approved_previews(review.path, plan_path)

    def test_rejects_changed_source_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions = {f"preview-{index}": "approved" for index in range(1, 4)}
            plan_path, _, review = self.prepare(root, decisions)
            (root / "renders/preview-1/Preview.png").write_bytes(b"changed")
            with self.assertRaisesRegex(BatchPlanError, "changed after review"):
                stage_approved_previews(review.path, plan_path)

            plan_path, _, review = self.prepare(root / "second", decisions)
            stage_approved_previews(review.path, plan_path)
            with self.assertRaisesRegex(BatchPlanError, "already exists"):
                stage_approved_previews(review.path, plan_path)


if __name__ == "__main__":
    unittest.main()
