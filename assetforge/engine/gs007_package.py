"""GS007 - assemble the current iteration package."""

from __future__ import annotations

from pathlib import Path

from assetforge.core.state import AssetForgeState
from assetforge.exporters import AssetPackager


class GS007Package:
    step_id = "GS007"
    name = "Package Assets"

    def __init__(self, packager: AssetPackager | None = None) -> None:
        self._packager = packager or AssetPackager()

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Packaging exported assets.")
        export = state.metadata.get("export")
        if not isinstance(export, dict) or export.get("status") != "PASS":
            return self._fail(state, "Successful export is required before packaging.")
        project_root_value = state.metadata.get("project_root")
        if not project_root_value:
            return self._fail(state, "Project root is missing.")

        project_root = Path(project_root_value)
        iteration_root = project_root / "iterations" / f"iteration_{state.iteration:02d}"
        stack_revision = str(state.metadata.get("stack_revision", "Stack_02_Rev00"))
        base_name = (
            state.configs.get("Manifest.yaml", {})
            .get("output", {})
            .get("package", f"Iteration_{state.iteration:02d}_Package.zip")
        )
        base_stem = Path(str(base_name)).stem
        package_name = f"{base_stem}_{stack_revision}.zip"
        try:
            result = self._packager.package(
                export_root=Path(export["root"]),
                iteration_root=iteration_root,
                package_directory=project_root / "packages",
                package_name=package_name,
            )
        except (KeyError, OSError, ValueError) as error:
            return self._fail(state, f"Packaging failed: {error}")

        state.metadata["package"] = {
            "status": "PASS",
            "file": str(result.package_file),
            "metadata_file": str(result.metadata_file),
            "sha256": result.checksum,
            "members": list(result.members),
        }
        state.log(f"Created package {result.package_file.name} with {len(result.members)} files.")
        state.approve()
        return state

    @staticmethod
    def _fail(state: AssetForgeState, message: str) -> AssetForgeState:
        state.fail(message)
        state.log("Asset packaging failed.")
        return state
