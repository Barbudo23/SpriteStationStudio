from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.batch_preview import BatchPreviewCoordinator
from app.blender_runner import ForgeError
from core.batch import (
    BatchItem,
    BatchOperation,
    BatchPlan,
    BatchPlanError,
    BatchPlanStore,
    BatchStatus,
)


class FakePreviewRunner:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []

    def run(self, request, on_output=None):
        self.requests.append(request)
        if self.fail:
            raise ForgeError("simulated Blender failure")
        request.output_dir.mkdir(parents=True)
        (request.output_dir / "Preview.png").write_bytes(b"png")
        manifest = request.output_dir / "preview_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.1",
            "sprite": "Preview.png",
        }), encoding="utf-8")
        return SimpleNamespace(manifest_path=manifest)


class BatchPreviewCoordinatorTests(unittest.TestCase):
    def prepare(self, root: Path, operation=BatchOperation.PREVIEW):
        blender = root / "blender.exe"
        blender.write_text("")
        model = root / "models" / "unit.glb"
        model.parent.mkdir()
        model.write_bytes(b"model")
        plan = BatchPlan.create((BatchItem(
            item_id="preview-1",
            operation=operation,
            source_path="models/unit.glb",
            output_path="renders/preview-1",
        ),), plan_id="plan-1")
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        return blender, plan_path

    def test_runs_preview_through_staging_and_checkpoints_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender, plan_path = self.prepare(root)
            runner = FakePreviewRunner()
            result = BatchPreviewCoordinator(blender, runner=runner).run_next(plan_path)

            self.assertEqual(result.plan.items[0].status, BatchStatus.COMPLETED)
            self.assertEqual(result.plan.items[0].attempt_count, 1)
            self.assertEqual(
                result.plan.items[0].result_manifest,
                "renders/preview-1/preview_manifest.json",
            )
            self.assertTrue((root / "renders/preview-1/Preview.png").is_file())
            self.assertNotEqual(runner.requests[0].output_dir, result.output_dir)
            self.assertEqual(list((root / "renders").glob(".*.staging-*")), [])
            self.assertEqual(BatchPlanStore().load(plan_path), result.plan)

    def test_failure_is_checkpointed_and_next_call_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender, plan_path = self.prepare(root)
            with self.assertRaises(ForgeError):
                BatchPreviewCoordinator(
                    blender, runner=FakePreviewRunner(fail=True)
                ).run_next(plan_path)
            failed = BatchPlanStore().load(plan_path)
            self.assertEqual(failed.items[0].status, BatchStatus.FAILED)
            self.assertIn("simulated Blender failure", failed.items[0].error)
            self.assertFalse((root / "renders/preview-1").exists())

            resumed = BatchPreviewCoordinator(
                blender, runner=FakePreviewRunner()
            ).run_next(plan_path)
            self.assertEqual(resumed.plan.items[0].status, BatchStatus.COMPLETED)
            self.assertEqual(resumed.plan.items[0].attempt_count, 2)

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender, plan_path = self.prepare(root)
            target = root / "renders" / "preview-1"
            target.mkdir(parents=True)
            protected = target / "user.txt"
            protected.write_text("keep")
            with self.assertRaises(BatchPlanError):
                BatchPreviewCoordinator(blender, runner=FakePreviewRunner()).run_next(
                    plan_path
                )
            self.assertEqual(protected.read_text(), "keep")
            self.assertEqual(
                BatchPlanStore().load(plan_path).items[0].status,
                BatchStatus.PENDING,
            )

    def test_rejects_non_preview_plan_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender, plan_path = self.prepare(root, BatchOperation.DIRECTIONS)
            before = plan_path.read_bytes()
            with self.assertRaises(BatchPlanError):
                BatchPreviewCoordinator(blender, runner=FakePreviewRunner()).run_next(
                    plan_path
                )
            self.assertEqual(plan_path.read_bytes(), before)

    def test_recovers_completed_output_after_interrupted_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender, plan_path = self.prepare(root)
            store = BatchPlanStore()
            running = store.load(plan_path).mark_running("preview-1")
            store.save(running, plan_path)
            target = root / "renders" / "preview-1"
            target.mkdir(parents=True)
            (target / "Preview.png").write_bytes(b"png")
            (target / "preview_manifest.json").write_text(json.dumps({
                "schemaVersion": "1.1",
                "sprite": "Preview.png",
            }))

            result = BatchPreviewCoordinator(
                blender, runner=FakePreviewRunner(fail=True)
            ).run_next(plan_path)
            self.assertEqual(result.item_id, None)
            self.assertEqual(result.plan.items[0].status, BatchStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
