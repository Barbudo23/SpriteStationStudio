"""Single-view paid-provider canary that never advances production state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from assetforge.providers import BaseProvider, GenerationRequest


@dataclass(frozen=True)
class CanaryResult:
    status: str
    asset: Path
    report: Path


class CanaryRunner:
    """Generate exactly one camera and record that human review is required."""

    def run(
        self,
        *,
        project_root: Path,
        iteration: int,
        configs: Mapping[str, Mapping[str, Any]],
        provider: BaseProvider,
        camera_id: str = "CAM01",
    ) -> CanaryResult:
        cameras = configs["CameraLibrary.yaml"]["cameras"]
        if camera_id not in cameras:
            raise ValueError(f"Unknown canary camera: {camera_id}")
        camera = cameras[camera_id]
        manifest = configs["Manifest.yaml"]
        iteration_data = manifest.get("iteration", {})
        target = str(
            manifest.get("description") or iteration_data.get("name") or "Character asset"
        ).strip()
        references = tuple(
            str(project_root / "References" / filename)
            for filename in configs["MPI.yaml"]["input"]["references"].values()
        )
        output_directory = project_root / "canary" / f"iteration_{iteration:02d}"
        request = GenerationRequest(
            prompt=(
                f"{target}; camera={camera['name']}; yaw={camera['yaw']}; "
                "preserve character identity, equipment, scale, and framing; "
                "isolated game character on a transparent background"
            ),
            reference_paths=references,
            parameters={
                "camera_id": camera_id,
                "camera": dict(camera),
                "iteration": iteration,
                "output_directory": str(output_directory),
            },
        )
        generation = provider.generate(request)
        if len(generation.assets) != 1:
            raise RuntimeError("Canary provider must return exactly one asset.")
        asset = Path(generation.assets[0])
        report = output_directory / "Canary_Result.yaml"
        report.write_text(
            yaml.safe_dump(
                {
                    "status": "REVIEW_REQUIRED",
                    "iteration": iteration,
                    "camera_id": camera_id,
                    "provider": generation.provider,
                    "asset": str(asset),
                    "metadata": dict(generation.metadata),
                    "workflow_state_advanced": False,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return CanaryResult(status="REVIEW_REQUIRED", asset=asset, report=report)
