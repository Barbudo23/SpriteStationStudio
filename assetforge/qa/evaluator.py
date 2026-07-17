"""Provider-neutral structural QA evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class QACheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class QAResult:
    score: float
    approved: bool
    checks: tuple[QACheck, ...]


class StructuralQAEvaluator:
    """Validate pipeline invariants without depending on provider image semantics."""

    def evaluate(
        self,
        *,
        generated_assets: Sequence[str],
        generation: Mapping[str, Any],
        camera_profile: Mapping[str, Any],
        character_profile: Mapping[str, Any],
        qa_profile: Mapping[str, Any],
    ) -> QAResult:
        camera_ids = tuple(camera_profile.get("cameras", {}))
        steps = generation.get("steps", ())
        step_camera_ids = tuple(step.get("camera_id") for step in steps)
        minimum_score = qa_profile.get("acceptance", {}).get("minimum_score", 100)
        checks = (
            QACheck(
                "character_lock",
                character_profile.get("status") == "LOCKED",
                "Character profile must remain locked.",
            ),
            QACheck(
                "camera_lock",
                camera_profile.get("status") == "LOCKED",
                "Camera profile must remain locked.",
            ),
            QACheck(
                "view_coverage",
                bool(camera_ids) and step_camera_ids == camera_ids,
                "Every configured camera must have one ordered generation step.",
            ),
            QACheck(
                "asset_coverage",
                len(generated_assets) >= len(camera_ids) > 0,
                "At least one asset is required for every camera.",
            ),
            QACheck(
                "asset_uniqueness",
                len(generated_assets) == len(set(generated_assets)),
                "Generated asset identifiers must be unique.",
            ),
            QACheck(
                "provider_traceability",
                bool(generation.get("provider"))
                and all(step.get("provider") == generation.get("provider") for step in steps),
                "Every generation step must identify the selected provider.",
            ),
        )
        passed = sum(check.passed for check in checks)
        score = round(100.0 * passed / len(checks), 2)
        failed_checks_allowed = qa_profile.get("acceptance", {}).get("failed_checks", 0)
        failures = len(checks) - passed
        approved = score >= minimum_score and failures <= failed_checks_allowed
        return QAResult(score=score, approved=approved, checks=checks)
