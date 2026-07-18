"""Production provider backed by explicitly approved Codex image assets."""

from __future__ import annotations

from pathlib import Path

import yaml

from assetforge.providers.base import BaseProvider, GenerationRequest, GenerationResult


class CodexReviewedProvider(BaseProvider):
    """Return approved local Codex assets through the stable provider contract."""

    def __init__(self, project_root: Path, iteration: int) -> None:
        self.project_root = project_root
        self.iteration = iteration
        self.output_root = project_root / "canary" / f"iteration_{iteration:02d}"
        self.plan_path = (
            project_root / "codex_jobs" / f"iteration_{iteration:02d}" / "Batch_Plan.yaml"
        )
        self._validate_plan()

    @property
    def name(self) -> str:
        return "codex-reviewed"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        camera_id = str(request.parameters.get("camera_id", ""))
        if not camera_id:
            raise ValueError("camera_id is required for reviewed Codex generation.")
        report_name = "Canary_Result.yaml" if camera_id == "CAM01" else f"{camera_id}_Result.yaml"
        report_path = self.output_root / report_name
        if not report_path.is_file():
            raise FileNotFoundError(f"Approved Codex report not found: {report_path}")
        report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("status") != "APPROVED":
            raise ValueError(f"Codex asset {camera_id} is not approved.")
        asset = Path(str(report.get("asset", "")))
        if not asset.is_file():
            raise FileNotFoundError(f"Approved Codex asset not found: {asset}")
        return GenerationResult(
            assets=(str(asset),),
            provider=self.name,
            metadata={
                "review_status": "APPROVED",
                "approved_by": report.get("approved_by"),
                "approved_at": report.get("approved_at"),
                "asset_sha256": report.get("asset_sha256"),
                "source": "codex-built-in",
            },
        )

    def _validate_plan(self) -> None:
        if not self.plan_path.is_file():
            raise FileNotFoundError(f"Approved Codex batch plan not found: {self.plan_path}")
        plan = yaml.safe_load(self.plan_path.read_text(encoding="utf-8"))
        if not isinstance(plan, dict) or plan.get("status") != "APPROVED":
            raise ValueError("Codex batch plan must be APPROVED for production use.")
