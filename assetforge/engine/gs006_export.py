"""GS006 - export approved assets into production formats."""

from __future__ import annotations

from pathlib import Path

from assetforge.core.state import AssetForgeState
from assetforge.exporters import AssetExporter


class GS006Export:
    step_id = "GS006"
    name = "Export Assets"

    def __init__(self, exporter: AssetExporter | None = None) -> None:
        self._exporter = exporter or AssetExporter()

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Exporting approved assets.")
        if state.metadata.get("qa", {}).get("status") != "APPROVED":
            return self._fail(state, "QA approval is required before export.")
        project_root = state.metadata.get("project_root")
        if not project_root:
            return self._fail(state, "Project root is missing.")

        output_root = (
            Path(project_root)
            / "iterations"
            / f"iteration_{state.iteration:02d}"
            / "Export"
        )
        try:
            result = self._exporter.export(
                [Path(asset) for asset in state.generated_assets],
                output_root,
            )
        except (OSError, ValueError) as error:
            return self._fail(state, f"Export failed: {error}")

        state.metadata["export"] = {
            "status": "PASS",
            "root": str(result.root),
            "png_files": [str(path) for path in result.png_files],
            "sprite_sheet": str(result.sprite_sheet),
            "gif_preview": str(result.gif_preview),
            "metadata_file": str(result.metadata_file),
        }
        state.log(f"Exported {len(result.png_files)} PNG frames, sprite sheet, and GIF preview.")
        state.approve()
        return state

    @staticmethod
    def _fail(state: AssetForgeState, message: str) -> AssetForgeState:
        state.fail(message)
        state.log("Asset export failed.")
        return state
