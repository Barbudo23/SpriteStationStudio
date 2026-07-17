"""
AssetForge Engine
GS001 - Input Validation
Version 0.1
"""

from pathlib import Path
from assetforge.core.state import AssetForgeState


class GS001InputValidation:
    step_id = "GS001"
    name = "Input Validation"

    REQUIRED = [
        "Front.png",
        "Back.png",
        "Left.png",
        "Right.png",
    ]

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Starting input validation.")

        project_root = Path(state.metadata.get("project_root", "."))

        missing = []

        for filename in self.REQUIRED:
            if not (project_root / "References" / filename).exists():
                missing.append(filename)

        if missing:
            state.fail(
                "Missing reference files: " + ", ".join(missing)
            )
            state.log("Input validation failed.")
            return state

        state.log("All required references validated.")
        state.approve()
        return state
