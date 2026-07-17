"""GS008 - finalize reports, progress, and the production package."""

from __future__ import annotations

from pathlib import Path

from assetforge.core.state import AssetForgeState
from assetforge.exporters import AssetPackager


class GS008Report:
    step_id = "GS008"
    name = "Production Report"

    def __init__(self, packager: AssetPackager | None = None) -> None:
        self._packager = packager or AssetPackager()

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Finalizing production iteration.")
        package = state.metadata.get("package")
        export = state.metadata.get("export")
        qa = state.metadata.get("qa")
        project_root_value = state.metadata.get("project_root")
        if not isinstance(package, dict) or package.get("status") != "PASS":
            return self._fail(state, "Successful package is required before reporting.")
        if not isinstance(export, dict) or export.get("status") != "PASS":
            return self._fail(state, "Successful export is required before reporting.")
        if not isinstance(qa, dict) or qa.get("status") != "APPROVED":
            return self._fail(state, "QA approval is required before reporting.")
        if not project_root_value:
            return self._fail(state, "Project root is missing.")

        project_root = Path(project_root_value)
        iteration_root = project_root / "iterations" / f"iteration_{state.iteration:02d}"
        report_directory = iteration_root / "Production_Report"
        report_directory.mkdir(parents=True, exist_ok=True)
        production_report = report_directory / "Production_Report.md"
        iteration_summary = iteration_root / "Iteration_Summary.md"
        production_report.write_text(self._production_report(state), encoding="utf-8")
        iteration_summary.write_text(self._iteration_summary(state), encoding="utf-8")

        package_path = Path(package["file"])
        try:
            rebuilt = self._packager.package(
                export_root=Path(export["root"]),
                iteration_root=iteration_root,
                package_directory=package_path.parent,
                package_name=package_path.name,
            )
        except (OSError, ValueError) as error:
            return self._fail(state, f"Final package rebuild failed: {error}")

        package.update(
            {
                "file": str(rebuilt.package_file),
                "metadata_file": str(rebuilt.metadata_file),
                "sha256": rebuilt.checksum,
                "members": list(rebuilt.members),
            }
        )
        state.progress = min(1.0, state.iteration / 10.0)
        state.metadata["iteration_status"] = "COMPLETE"
        state.metadata["next_iteration"] = state.iteration + 1 if state.iteration < 10 else None
        state.metadata["reporting"] = {
            "status": "COMPLETE",
            "production_report": str(production_report),
            "iteration_summary": str(iteration_summary),
        }
        for report in (str(production_report), str(iteration_summary)):
            state.add_report(report)
        state.log(
            f"Iteration {state.iteration:02d} complete; project progress {state.progress:.0%}."
        )
        state.approve()
        return state

    @staticmethod
    def _production_report(state: AssetForgeState) -> str:
        export = state.metadata["export"]
        return (
            f"# Production Report — Iteration {state.iteration:02d}\n\n"
            "Status: COMPLETE\n\n"
            f"QA score: {state.qa_score:.2f}\n\n"
            f"PNG frames: {len(export.get('png_files', []))}\n\n"
            "Formats: PNG sequence, SpriteSheet, GIF preview\n\n"
            f"Provider: {state.metadata.get('generation', {}).get('provider', 'unknown')}\n"
        )

    @staticmethod
    def _iteration_summary(state: AssetForgeState) -> str:
        next_iteration = state.iteration + 1 if state.iteration < 10 else "none"
        return (
            f"# Iteration {state.iteration:02d} Summary\n\n"
            "Status: COMPLETE\n\n"
            f"Project progress: {min(1.0, state.iteration / 10.0):.0%}\n\n"
            f"Next iteration: {next_iteration}\n"
        )

    @staticmethod
    def _fail(state: AssetForgeState, message: str) -> AssetForgeState:
        state.fail(message)
        state.log("Production reporting failed.")
        return state
