from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.batch_contact_sheet import build_batch_contact_sheet
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanError, BatchPlanStore
from core.validation import decode_rgba_png, encode_rgba_png


class BatchContactSheetTests(unittest.TestCase):
    def prepare(self, root: Path, completed: int = 3) -> Path:
        items = []
        for index in range(1, 4):
            output = root / "renders" / f"preview-{index}"
            output.mkdir(parents=True)
            rgba = bytes((index * 40, 70, 90, 255, 0, 0, 0, 0) * 2)
            (output / "Preview.png").write_bytes(encode_rgba_png(2, 2, rgba))
            (output / "preview_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1", "sprite": "Preview.png",
                "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
            }), encoding="utf-8")
            items.append(BatchItem(
                item_id=f"preview-{index}", operation=BatchOperation.PREVIEW,
                source_path=f"models/unit-{index}.glb", output_path=f"renders/preview-{index}",
            ))
        plan = BatchPlan.create(items, plan_id="review-plan")
        for index in range(completed):
            item_id = f"preview-{index + 1}"
            plan = plan.mark_running(item_id).mark_completed(
                item_id, f"renders/{item_id}/preview_manifest.json"
            )
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        return plan_path

    def test_builds_atomic_read_only_sheet_for_three_previews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = self.prepare(root)
            source_paths = sorted((root / "renders").glob("*/Preview.png"))
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
            plan_before = plan_path.read_bytes()
            result = build_batch_contact_sheet(plan_path, gap=1)
            self.assertEqual(result.item_ids, ("preview-1", "preview-2", "preview-3"))
            width, height, _ = decode_rgba_png(result.image_path)
            self.assertEqual((width, height), (8, 2))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["readOnlyReview"])
            self.assertEqual(manifest["application"], "Sprite Station Studio")
            self.assertEqual(len(manifest["items"]), 3)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["items"]))
            self.assertEqual(plan_path.read_bytes(), plan_before)
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}, before
            )
            self.assertEqual(list((root / "review").glob(".*.staging-*")), [])

    def test_requires_all_items_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self.prepare(Path(tmp), completed=2)
            with self.assertRaisesRegex(BatchPlanError, "must be completed"):
                build_batch_contact_sheet(plan_path)

    def test_refuses_overwrite_and_unsafe_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = self.prepare(root)
            build_batch_contact_sheet(plan_path)
            with self.assertRaisesRegex(BatchPlanError, "already exists"):
                build_batch_contact_sheet(plan_path)
            with self.assertRaisesRegex(BatchPlanError, "safe relative"):
                build_batch_contact_sheet(plan_path, "../outside")


if __name__ == "__main__":
    unittest.main()
