"""File-based bridge between AssetForge and Codex built-in image generation."""

from __future__ import annotations

from dataclasses import dataclass
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
            dimensions = [image.width, image.height]

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
