"""GS004 - provider-independent generation dispatcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from assetforge.core.state import AssetForgeState
from assetforge.providers import BaseProvider, GenerationRequest


class GS004Generation:
    """Translate iteration configuration into provider requests per camera."""

    step_id = "GS004"
    name = "Universal Generation Dispatcher"

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Dispatching generation tasks.")

        error = self._validate(state)
        if error:
            state.fail(error)
            state.log("Generation dispatch failed.")
            return state

        provider = state.metadata["provider"]
        camera_profile = state.metadata["active_camera_profile"]
        project_root = Path(state.metadata["project_root"])
        mpi = state.configs["MPI.yaml"]
        manifest = state.configs["Manifest.yaml"]
        iteration = manifest.get("iteration", {})
        target = str(manifest.get("description") or iteration.get("name") or "Character asset").strip()
        references = tuple(
            str(project_root / "References" / filename)
            for filename in mpi["input"]["references"].values()
        )
        output_directory = (
            project_root
            / "iterations"
            / f"iteration_{state.iteration:02d}"
            / "WorkingAssets"
        )

        generated: list[dict[str, Any]] = []
        for camera_id, camera in camera_profile["cameras"].items():
            request = GenerationRequest(
                prompt=(
                    f"{target}; camera={camera['name']}; "
                    f"yaw={camera['yaw']}; preserve character identity and scale"
                ),
                reference_paths=references,
                parameters={
                    "camera_id": camera_id,
                    "camera": dict(camera),
                    "transparent_background": True,
                    "iteration": state.iteration,
                    "output_directory": str(output_directory),
                },
            )
            result = provider.generate(request)
            if not result.assets:
                state.fail(f"Provider returned no assets for {camera_id}.")
                state.log("Generation dispatch failed.")
                return state
            for asset in result.assets:
                state.add_asset(asset)
            generated.append(
                {
                    "camera_id": camera_id,
                    "provider": result.provider,
                    "assets": list(result.assets),
                    "metadata": dict(result.metadata),
                }
            )

        state.metadata["generation"] = {
            "status": "PASS",
            "provider": provider.name,
            "simulation": provider.is_simulation,
            "steps": generated,
        }
        state.log(f"Generated {len(state.generated_assets)} assets across {len(generated)} views.")
        state.approve()
        return state

    @staticmethod
    def _validate(state: AssetForgeState) -> str | None:
        provider = state.metadata.get("provider")
        if not isinstance(provider, BaseProvider):
            return "A valid BaseProvider is required."
        if state.metadata.get("character_profile", {}).get("status") != "LOCKED":
            return "Character profile must be locked before generation."
        camera_profile = state.metadata.get("active_camera_profile")
        if not isinstance(camera_profile, dict) or camera_profile.get("status") != "LOCKED":
            return "Camera profile must be locked before generation."
        if not camera_profile.get("cameras"):
            return "Camera profile contains no views."
        mpi = state.configs.get("MPI.yaml")
        if not isinstance(mpi, dict):
            return "MPI.yaml is not loaded."
        references = mpi.get("input", {}).get("references")
        if not isinstance(references, dict) or not references:
            return "MPI reference configuration is missing."
        if not state.metadata.get("project_root"):
            return "Project root is missing."
        return None
