"""GS005 - automated structural quality assurance."""

from __future__ import annotations

from assetforge.core.state import AssetForgeState
from assetforge.qa import StructuralQAEvaluator


class GS005QA:
    """Apply configured acceptance thresholds to generated output."""

    step_id = "GS005"
    name = "Automated Quality Assurance"

    def __init__(self, evaluator: StructuralQAEvaluator | None = None) -> None:
        self._evaluator = evaluator or StructuralQAEvaluator()

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Evaluating generated assets.")

        qa_profile = state.configs.get("QA_Profile.yaml")
        generation = state.metadata.get("generation")
        camera_profile = state.metadata.get("active_camera_profile")
        character_profile = state.metadata.get("character_profile")
        if not isinstance(qa_profile, dict):
            return self._fail(state, "QA_Profile.yaml is not loaded.")
        if not isinstance(generation, dict) or generation.get("status") != "PASS":
            return self._fail(state, "Generation must pass before QA.")
        if not isinstance(camera_profile, dict) or not isinstance(character_profile, dict):
            return self._fail(state, "Locked character and camera profiles are required for QA.")

        result = self._evaluator.evaluate(
            generated_assets=state.generated_assets,
            generation=generation,
            camera_profile=camera_profile,
            character_profile=character_profile,
            qa_profile=qa_profile,
        )
        state.qa_score = result.score
        state.metadata["qa"] = {
            "status": "APPROVED" if result.approved else "REWORK",
            "mode": "structural",
            "score": result.score,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in result.checks
            ],
        }
        state.add_report("QA_Report.md")
        if not result.approved:
            failed = ", ".join(check.name for check in result.checks if not check.passed)
            return self._fail(state, f"QA requires rework: {failed}.")

        state.log(f"QA approved with score {result.score:.2f}.")
        state.approve()
        return state

    @staticmethod
    def _fail(state: AssetForgeState, message: str) -> AssetForgeState:
        state.fail(message)
        state.log("QA evaluation failed.")
        return state
