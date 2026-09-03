from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.batch import (
    BatchItem,
    BatchOperation,
    BatchPlan,
    BatchPlanError,
    BatchPlanStore,
    BatchStatus,
)


def item(index: int, operation: BatchOperation = BatchOperation.PREVIEW) -> BatchItem:
    return BatchItem(
        item_id=f"item-{index}",
        operation=operation,
        source_path=f"models/model-{index}.glb",
        output_path=f"renders/item-{index}",
    )


class BatchPlanTests(unittest.TestCase):
    def test_round_trip_preserves_schema_and_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch_plan.json"
            plan = BatchPlan.create((item(1), item(2, BatchOperation.DIRECTIONS)))
            store = BatchPlanStore()
            store.save(plan, path)
            loaded = store.load(path)
            self.assertEqual(loaded, plan)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"], "1.0")
            self.assertEqual(len(payload["items"]), 2)

    def test_rejects_more_than_three_items(self) -> None:
        with self.assertRaises(BatchPlanError):
            BatchPlan.create(item(index) for index in range(4))

    def test_rejects_duplicate_outputs_and_parent_traversal(self) -> None:
        duplicate = BatchItem(
            item_id="other",
            operation=BatchOperation.PREVIEW,
            source_path="models/other.glb",
            output_path="renders/item-1",
        )
        with self.assertRaises(BatchPlanError):
            BatchPlan.create((item(1), duplicate))
        with self.assertRaises(BatchPlanError):
            BatchPlan.create((BatchItem(
                item_id="unsafe",
                operation=BatchOperation.PREVIEW,
                source_path="model.glb",
                output_path="../outside",
            ),))

    def test_state_transitions_are_explicit_and_completed_is_idempotent(self) -> None:
        plan = BatchPlan.create((item(1), item(2)))
        running = plan.mark_running("item-1")
        self.assertEqual(running.items[0].status, BatchStatus.RUNNING)
        self.assertEqual(running.items[0].attempt_count, 1)
        with self.assertRaises(BatchPlanError):
            running.mark_running("item-2")
        completed = running.mark_completed("item-1", "renders/item-1/manifest.json")
        self.assertEqual(completed.items[0].status, BatchStatus.COMPLETED)
        with self.assertRaises(BatchPlanError):
            completed.mark_running("item-1")
        self.assertEqual(completed.next_pending().item_id, "item-2")

    def test_failed_item_can_be_resumed_and_clears_error(self) -> None:
        plan = BatchPlan.create((item(1),)).mark_running("item-1")
        failed = plan.mark_failed("item-1", "Blender exited with code 1")
        resumed = failed.mark_running("item-1")
        self.assertEqual(resumed.items[0].status, BatchStatus.RUNNING)
        self.assertEqual(resumed.items[0].attempt_count, 2)
        self.assertIsNone(resumed.items[0].error)

    def test_unsupported_schema_is_rejected(self) -> None:
        payload = BatchPlan.create((item(1),)).to_dict()
        payload["schemaVersion"] = "2.0"
        with self.assertRaises(BatchPlanError):
            BatchPlan.from_dict(payload)

    def test_rejects_non_utc_timestamp_and_unsafe_source_path(self) -> None:
        payload = BatchPlan.create((item(1),)).to_dict()
        payload["createdUtc"] = "2026-07-22T10:00:00+03:00"
        with self.assertRaises(BatchPlanError):
            BatchPlan.from_dict(payload)
        unsafe = item(1).to_dict()
        unsafe["sourcePath"] = "../private/model.glb"
        payload = BatchPlan.create((item(1),)).to_dict()
        payload["items"] = [unsafe]
        with self.assertRaises(BatchPlanError):
            BatchPlan.from_dict(payload)

    def test_failed_atomic_replace_preserves_existing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch_plan.json"
            original = BatchPlan.create((item(1),), plan_id="original")
            BatchPlanStore().save(original, path)
            before = path.read_bytes()

            def fail_replace(source: Path, destination: Path) -> None:
                raise OSError("simulated replace failure")

            updated = original.mark_running("item-1")
            with self.assertRaises(OSError):
                BatchPlanStore(fail_replace).save(updated, path)
            self.assertEqual(path.read_bytes(), before)
            leftovers = list(path.parent.glob(".batch_plan.json.*"))
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
