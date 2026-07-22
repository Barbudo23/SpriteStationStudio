from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Callable
from uuid import uuid4

from app.blender_runner import BlenderRunner, ForgeError, RenderRequest
from core.batch import (
    BatchOperation,
    BatchPlan,
    BatchPlanError,
    BatchPlanStore,
    BatchStatus,
)
from core.validation import PreviewValidationError, validate_preview_png


@dataclass(frozen=True)
class BatchPreviewResult:
    plan: BatchPlan
    item_id: str | None
    output_dir: Path | None


class BatchPreviewCoordinator:
    """Runs one durable BatchPlan item through the existing Preview workflow."""

    def __init__(
        self,
        blender_path: Path,
        runner: BlenderRunner | None = None,
        store: BatchPlanStore | None = None,
        resolution: int = 512,
        engine: str = "AUTO",
        camera_profile: str = "Strategy30",
    ) -> None:
        self.blender_path = blender_path.expanduser().resolve()
        self.runner = runner or BlenderRunner()
        self.store = store or BatchPlanStore()
        self.resolution = resolution
        self.engine = engine
        self.camera_profile = camera_profile

    def run_next(
        self,
        plan_path: Path,
        on_output: Callable[[str], None] | None = None,
    ) -> BatchPreviewResult:
        plan_path = plan_path.expanduser().resolve()
        plan_root = plan_path.parent
        plan = self.store.load(plan_path)
        if any(item.operation != BatchOperation.PREVIEW for item in plan.items):
            raise BatchPlanError(
                "BatchPreviewCoordinator accepts preview operations only."
            )

        plan = self._recover_interrupted(plan, plan_root, plan_path)
        item = next(
            (
                candidate
                for candidate in plan.items
                if candidate.status in {BatchStatus.FAILED, BatchStatus.PENDING}
            ),
            None,
        )
        if item is None:
            return BatchPreviewResult(plan=plan, item_id=None, output_dir=None)

        source_path = self._resolve_source(plan_root, item.source_path)
        target_dir = self._resolve_output(plan_root, item.output_path)
        if target_dir.exists():
            raise BatchPlanError(
                f"Batch output already exists; no files were overwritten: {target_dir}"
            )

        running = plan.mark_running(item.item_id)
        self.store.save(running, plan_path)
        staging = target_dir.parent / f".{target_dir.name}.staging-{uuid4().hex}"
        try:
            request = RenderRequest(
                blender_path=self.blender_path,
                model_path=source_path,
                output_dir=staging,
                resolution=self.resolution,
                engine=self.engine,
                camera_profile=self.camera_profile,
            )
            result = self.runner.run(request, on_output=on_output)
            self._validate_preview_result(staging, result.manifest_path)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(target_dir)
            manifest_path = target_dir / result.manifest_path.relative_to(staging)
            manifest_reference = manifest_path.relative_to(plan_root).as_posix()
            completed = running.mark_completed(item.item_id, manifest_reference)
            self.store.save(completed, plan_path)
            return BatchPreviewResult(completed, item.item_id, target_dir)
        except Exception as exc:
            if target_dir.is_dir() and self._is_valid_completed_output(target_dir):
                manifest = (target_dir / "preview_manifest.json").relative_to(plan_root).as_posix()
                completed = running.mark_completed(item.item_id, manifest)
                self.store.save(completed, plan_path)
                return BatchPreviewResult(completed, item.item_id, target_dir)
            failed = running.mark_failed(item.item_id, f"{type(exc).__name__}: {exc}")
            self.store.save(failed, plan_path)
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _recover_interrupted(
        self,
        plan: BatchPlan,
        plan_root: Path,
        plan_path: Path,
    ) -> BatchPlan:
        running = next(
            (item for item in plan.items if item.status == BatchStatus.RUNNING),
            None,
        )
        if running is None:
            return plan
        target = self._resolve_output(plan_root, running.output_path)
        if target.is_dir() and self._is_valid_completed_output(target):
            manifest = (target / "preview_manifest.json").relative_to(plan_root).as_posix()
            recovered = plan.mark_completed(running.item_id, manifest)
        else:
            recovered = plan.mark_failed(
                running.item_id,
                "Interrupted before a verified Preview result was committed.",
            )
        self.store.save(recovered, plan_path)
        return recovered

    @staticmethod
    def _resolve_source(plan_root: Path, value: str) -> Path:
        candidate = Path(value)
        resolved = candidate.expanduser().resolve() if candidate.is_absolute() else (
            plan_root / candidate
        ).resolve()
        if not resolved.is_file():
            raise BatchPlanError(f"Batch source model not found: {resolved}")
        return resolved

    @staticmethod
    def _resolve_output(plan_root: Path, value: str) -> Path:
        candidate = Path(value)
        if candidate.is_absolute():
            raise BatchPlanError("Batch outputPath must be relative to the plan directory.")
        resolved = (plan_root / candidate).resolve()
        try:
            resolved.relative_to(plan_root)
        except ValueError as exc:
            raise BatchPlanError("Batch outputPath escapes the plan directory.") from exc
        return resolved

    @staticmethod
    def _validate_preview_result(staging: Path, manifest_path: Path) -> None:
        manifest_path = manifest_path.resolve()
        try:
            manifest_path.relative_to(staging.resolve())
        except ValueError as exc:
            raise ForgeError("Preview manifest was created outside the staging directory.") from exc
        try:
            validate_preview_png(manifest_path)
        except PreviewValidationError as exc:
            raise ForgeError(f"Preview PNG validation failed: {exc}") from exc

    @classmethod
    def _is_valid_completed_output(cls, target: Path) -> bool:
        try:
            cls._validate_preview_result(target, target / "preview_manifest.json")
            return True
        except (OSError, ValueError, json.JSONDecodeError, ForgeError):
            return False
