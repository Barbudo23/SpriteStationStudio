"""File-based bridge between AssetForge and Codex built-in image generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import shutil
from typing import Any, Mapping

from PIL import Image
import yaml


REFERENCE_ROLES = {
    "Front.png": "back-left walking reference (Russian label: back-left, isometric 30 degrees)",
    "Back.png": "back-right walking reference (Russian label: back-right, isometric 30 degrees)",
    "Left.png": "front-right walking reference (Russian label: face-right, isometric 30 degrees)",
    "Right.png": "front-left walking reference (Russian label: face-left, isometric 30 degrees)",
}


@dataclass(frozen=True)
class CodexJob:
    request: Path
    output: Path
    prompt: str
    references: tuple[Path, ...]


@dataclass(frozen=True)
class CodexImportResult:
    status: str
    asset: Path
    report: Path


@dataclass(frozen=True)
class CodexBatchPlan:
    status: str
    plan: Path
    jobs: tuple[CodexJob, ...]


class CodexBridge:
    """Prepare a generation request and safely import one Codex-generated PNG."""

    def prepare(
        self,
        *,
        project_root: Path,
        iteration: int,
        configs: Mapping[str, Mapping[str, Any]],
        camera_id: str = "CAM01",
    ) -> CodexJob:
        cameras = configs["CameraLibrary.yaml"]["cameras"]
        if camera_id not in cameras:
            raise ValueError(f"Unknown Codex camera: {camera_id}")
        camera = cameras[camera_id]
        manifest = configs["Manifest.yaml"]
        target = str(
            manifest.get("description")
            or manifest.get("iteration", {}).get("name")
            or "Character asset"
        ).strip()
        reference_filenames = tuple(
            configs["MPI.yaml"]["input"]["references"].values()
        )
        references = tuple(
            project_root / "References" / filename for filename in reference_filenames
        )
        missing = [path for path in references if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Reference image not found: {missing[0]}")

        prompt = (
            "Use case: identity-preserve\n"
            "Asset type: Unity-ready isometric character animation frame\n"
            f"Primary request: Create {target}, camera {camera['name']}, yaw "
            f"{camera['yaw']} degrees, isometric pitch 30 degrees.\n"
            "Input images: Image 1 back-left; Image 2 back-right; Image 3 front-right; "
            "Image 4 front-left. Treat them as identity and equipment references only.\n"
            "Subject: the same adult male soldier walking with the same AK-pattern rifle, "
            "dark olive camouflage, hooded tactical jacket, vest, pouches, knee pads, "
            "boots, grenades, face, hair, beard, and body proportions.\n"
            "Composition/framing: one full-body character, centered, consistent scale, "
            "entire weapon and both boots visible, no crop.\n"
            "Scene/backdrop: perfectly flat solid #ff00ff chroma-key background. The "
            "background must be uniform with no shadow, gradient, texture, floor, or reflection.\n"
            "Constraints: preserve identity, clothing, equipment placement, weapon design, "
            "walking pose continuity, and isometric game-art rendering. Do not copy Russian "
            "headings, GIF icons, filenames, white panels, or any other text from references.\n"
            "Avoid: additional people, duplicated limbs or gear, watermark, text, logo, cast "
            "shadow, contact shadow, and #ff00ff anywhere on the character."
        )
        job_directory = (
            project_root / "codex_jobs" / f"iteration_{iteration:02d}" / camera_id
        )
        job_directory.mkdir(parents=True, exist_ok=True)
        request_path = job_directory / "Request.yaml"
        output_path = (
            project_root / "canary" / f"iteration_{iteration:02d}" / f"{camera_id}_codex.png"
        )
        request_path.write_text(
            yaml.safe_dump(
                {
                    "status": "AWAITING_CODEX",
                    "provider": "codex-built-in",
                    "iteration": iteration,
                    "camera_id": camera_id,
                    "camera": dict(camera),
                    "reference_images": [
                        {"path": str(path), "role": REFERENCE_ROLES.get(path.name, "reference")}
                        for path in references
                    ],
                    "prompt": prompt,
                    "expected_output": str(output_path),
                    "workflow_state_advanced": False,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        return CodexJob(
            request=request_path,
            output=output_path,
            prompt=prompt,
            references=references,
        )

    def import_result(
        self,
        *,
        job: CodexJob,
        source_image: Path,
        iteration: int,
        camera_id: str,
    ) -> CodexImportResult:
        if not source_image.is_file():
            raise FileNotFoundError(f"Codex result not found: {source_image}")
        dimensions = self._validate_alpha_png(source_image)

        job.output.parent.mkdir(parents=True, exist_ok=True)
        if source_image.resolve() != job.output.resolve():
            if job.output.exists():
                raise FileExistsError(f"Codex output already exists: {job.output}")
            shutil.copy2(source_image, job.output)
        report = job.output.parent / "Canary_Result.yaml"
        report.write_text(
            yaml.safe_dump(
                {
                    "status": "REVIEW_REQUIRED",
                    "iteration": iteration,
                    "camera_id": camera_id,
                    "provider": "codex-built-in",
                    "asset": str(job.output),
                    "request": str(job.request),
                    "dimensions": dimensions,
                    "alpha_validated": True,
                    "workflow_state_advanced": False,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return CodexImportResult(
            status="REVIEW_REQUIRED",
            asset=job.output,
            report=report,
        )

    def import_batch_result(
        self,
        *,
        job: CodexJob,
        source_image: Path,
        project_root: Path,
        iteration: int,
        camera_id: str,
    ) -> CodexImportResult:
        """Import a non-canary camera without overwriting the canary review record."""

        if not source_image.is_file():
            raise FileNotFoundError(f"Codex result not found: {source_image}")
        dimensions = self._validate_alpha_png(source_image)
        plan_path = (
            project_root / "codex_jobs" / f"iteration_{iteration:02d}" / "Batch_Plan.yaml"
        )
        if not plan_path.is_file():
            raise FileNotFoundError(f"Codex batch plan not found: {plan_path}")
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        if not isinstance(plan, dict) or plan.get("status") not in {"READY", "IN_PROGRESS"}:
            raise ValueError("Codex batch plan is not ready for imports.")
        pending = list(plan.get("pending_cameras", []))
        if camera_id not in pending:
            raise ValueError(f"Camera {camera_id} is not pending in the Codex batch plan.")

        job.output.parent.mkdir(parents=True, exist_ok=True)
        if source_image.resolve() != job.output.resolve():
            if job.output.exists():
                raise FileExistsError(f"Codex output already exists: {job.output}")
            shutil.copy2(source_image, job.output)
        report = job.output.parent / f"{camera_id}_Result.yaml"
        report.write_text(
            yaml.safe_dump(
                {
                    "status": "REVIEW_REQUIRED",
                    "iteration": iteration,
                    "camera_id": camera_id,
                    "provider": "codex-built-in",
                    "asset": str(job.output),
                    "request": str(job.request),
                    "dimensions": dimensions,
                    "alpha_validated": True,
                    "asset_sha256": sha256(job.output.read_bytes()).hexdigest(),
                    "workflow_state_advanced": False,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        pending.remove(camera_id)
        review_required = list(plan.get("review_required_cameras", []))
        review_required.append(camera_id)
        plan.update(
            {
                "status": "IN_PROGRESS",
                "pending_cameras": pending,
                "review_required_cameras": review_required,
                "generation_started": True,
                "workflow_state_advanced": False,
            }
        )
        plan_path.write_text(
            yaml.safe_dump(plan, sort_keys=False),
            encoding="utf-8",
        )
        return CodexImportResult(status="REVIEW_REQUIRED", asset=job.output, report=report)

    @staticmethod
    def _validate_alpha_png(source_image: Path) -> list[int]:
        with Image.open(source_image) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError("Codex result must be a PNG.")
            if image.mode != "RGBA":
                raise ValueError("Codex result must contain an RGBA alpha channel.")
            alpha = image.getchannel("A")
            minimum_alpha, maximum_alpha = alpha.getextrema()
            if minimum_alpha != 0 or maximum_alpha == 0:
                raise ValueError("Codex result must contain both transparent and opaque pixels.")
            corners = (
                alpha.getpixel((0, 0)),
                alpha.getpixel((image.width - 1, 0)),
                alpha.getpixel((0, image.height - 1)),
                alpha.getpixel((image.width - 1, image.height - 1)),
            )
            if any(value > 8 for value in corners):
                raise ValueError("Codex result corners must be transparent.")
            return [image.width, image.height]

    def approve_canary(
        self,
        *,
        project_root: Path,
        iteration: int,
        camera_id: str = "CAM01",
        approved_by: str = "user",
        approved_at: str | None = None,
    ) -> CodexImportResult:
        """Record explicit human approval without advancing production state."""

        report = project_root / "canary" / f"iteration_{iteration:02d}" / "Canary_Result.yaml"
        if not report.is_file():
            raise FileNotFoundError(f"Canary review record not found: {report}")
        data = yaml.safe_load(report.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Canary review record must contain a YAML mapping.")
        if data.get("status") not in {"REVIEW_REQUIRED", "APPROVED"}:
            raise ValueError("Canary must be awaiting review before approval.")
        if data.get("camera_id") != camera_id or int(data.get("iteration", 0)) != iteration:
            raise ValueError("Canary review record does not match the requested camera.")
        reviewer = approved_by.strip()
        if not reviewer:
            raise ValueError("Canary approver must not be empty.")
        asset = Path(str(data.get("asset", "")))
        if not asset.is_file():
            raise FileNotFoundError(f"Approved canary asset not found: {asset}")
        data.update(
            {
                "status": "APPROVED",
                "approved_by": reviewer,
                "approved_at": approved_at
                or datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "asset_sha256": sha256(asset.read_bytes()).hexdigest(),
                "workflow_state_advanced": False,
            }
        )
        report.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return CodexImportResult(status="APPROVED", asset=asset, report=report)

    def prepare_batch(
        self,
        *,
        project_root: Path,
        iteration: int,
        configs: Mapping[str, Mapping[str, Any]],
        approved_camera_id: str = "CAM01",
    ) -> CodexBatchPlan:
        """Prepare remaining internal camera jobs after explicit canary approval."""

        report = project_root / "canary" / f"iteration_{iteration:02d}" / "Canary_Result.yaml"
        if not report.is_file():
            raise FileNotFoundError(f"Canary review record not found: {report}")
        review = yaml.safe_load(report.read_text(encoding="utf-8"))
        if not isinstance(review, dict) or review.get("status") != "APPROVED":
            raise ValueError("Codex batch requires an explicitly APPROVED canary.")
        if review.get("camera_id") != approved_camera_id:
            raise ValueError("Approved canary camera does not match the batch anchor.")

        camera_ids = tuple(configs["CameraLibrary.yaml"]["cameras"])
        if approved_camera_id not in camera_ids:
            raise ValueError("Approved canary camera is not in CameraLibrary.yaml.")
        pending_ids = tuple(camera_id for camera_id in camera_ids if camera_id != approved_camera_id)
        jobs = tuple(
            self.prepare(
                project_root=project_root,
                iteration=iteration,
                configs=configs,
                camera_id=camera_id,
            )
            for camera_id in pending_ids
        )
        plan_path = (
            project_root / "codex_jobs" / f"iteration_{iteration:02d}" / "Batch_Plan.yaml"
        )
        plan_path.write_text(
            yaml.safe_dump(
                {
                    "status": "READY",
                    "provider": "codex-built-in",
                    "iteration": iteration,
                    "approved_canary": approved_camera_id,
                    "completed_cameras": [approved_camera_id],
                    "pending_cameras": list(pending_ids),
                    "total_cameras": len(camera_ids),
                    "generation_started": False,
                    "workflow_state_advanced": False,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return CodexBatchPlan(status="READY", plan=plan_path, jobs=jobs)
