from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.batch_contact_sheet import build_batch_contact_sheet
from app.static_sprite_workflow import run_static_sprite_workflow
from app.static_sprite_workflow_audit import audit_static_sprite_workflow
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanError, BatchPlanStore, record_batch_review
from core.validation import encode_rgba_png


class StaticSpriteWorkflowTests(unittest.TestCase):
    def prepare(self, root: Path):
        items = []
        for index in range(1, 3):
            item_id = f"preview-{index}"
            output = root / "renders" / item_id
            output.mkdir(parents=True)
            rgba = bytes((index * 70, 90, 130, 255, 0, 0, 0, 0) * 2)
            (output / "Preview.png").write_bytes(encode_rgba_png(2, 2, rgba))
            (output / "preview_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1", "sprite": "Preview.png",
                "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
                "normalization": {"pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]}},
            }), encoding="utf-8")
            items.append(BatchItem(
                item_id=item_id, operation=BatchOperation.PREVIEW,
                source_path=f"models/unit-{index}.glb", output_path=f"renders/{item_id}",
            ))
        plan = BatchPlan.create(items, plan_id="workflow-plan")
        for index in range(1, 3):
            item_id = f"preview-{index}"
            plan = plan.mark_running(item_id).mark_completed(
                item_id, f"renders/{item_id}/preview_manifest.json"
            )
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        contact = build_batch_contact_sheet(plan_path)
        review = record_batch_review(contact.manifest_path, plan_path, {
            "preview-1": "approved", "preview-2": "rejected",
        })
        return plan_path, contact, review

    def test_publishes_complete_workflow_as_one_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, contact, review = self.prepare(root)
            protected = [plan_path, contact.manifest_path, contact.image_path, review.path]
            before = {path: path.read_bytes() for path in protected}
            result = run_static_sprite_workflow(review.path, plan_path)
            self.assertEqual(result.approved_item_ids, ("preview-1",))
            for path in (
                result.manifest_path, result.approved_staging_manifest,
                result.sprite_set_manifest, result.unity_preset_path,
                result.unity_package_manifest,
            ):
                self.assertTrue(path.is_file())
            workflow = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(workflow["application"], "Sprite Station Studio")
            self.assertTrue(workflow["readOnlyUnityPreparation"])
            for artifact in workflow["artifacts"].values():
                path = result.output_dir / artifact["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
            self.assertEqual({path: path.read_bytes() for path in protected}, before)
            self.assertEqual(list((root / "workflow").glob(".*.staging-*")), [])

    def test_audit_is_read_only_and_checks_all_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _, review = self.prepare(root)
            result = run_static_sprite_workflow(review.path, plan_path)
            before = {path: path.read_bytes() for path in result.output_dir.rglob("*") if path.is_file()}
            audit = audit_static_sprite_workflow(result.manifest_path)
            self.assertTrue(audit.valid)
            self.assertEqual(audit.approved_item_ids, ("preview-1",))
            self.assertEqual(audit.artifact_count, 4)
            self.assertGreaterEqual(audit.checked_file_count, 7)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_audit_rejects_artifact_and_nested_sprite_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _, review = self.prepare(root)
            result = run_static_sprite_workflow(review.path, plan_path)
            result.unity_preset_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(BatchPlanError, "artifact hash mismatch"):
                audit_static_sprite_workflow(result.manifest_path)

            plan_path, _, review = self.prepare(root / "second")
            result = run_static_sprite_workflow(review.path, plan_path)
            unity_sprite = next((result.output_dir / "unity-preview-package/sprites").glob("*.png"))
            unity_sprite.write_bytes(b"changed")
            with self.assertRaisesRegex(BatchPlanError, "Unity package sprite hash mismatch"):
                audit_static_sprite_workflow(result.manifest_path)

    def test_failure_leaves_no_partial_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _, review = self.prepare(root)
            (root / "renders/preview-1/Preview.png").write_bytes(b"changed")
            with self.assertRaises(BatchPlanError):
                run_static_sprite_workflow(review.path, plan_path)
            self.assertFalse((root / "workflow/approved-static-sprites").exists())
            self.assertEqual(list((root / "workflow").glob(".*.staging-*")), [])

    def test_refuses_overwrite_and_unsafe_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _, review = self.prepare(root)
            run_static_sprite_workflow(review.path, plan_path)
            with self.assertRaisesRegex(BatchPlanError, "already exists"):
                run_static_sprite_workflow(review.path, plan_path)
            with self.assertRaisesRegex(BatchPlanError, "safe relative"):
                run_static_sprite_workflow(review.path, plan_path, "../outside")


if __name__ == "__main__":
    unittest.main()
