"""GS003 - build and validate the active camera profile."""

from __future__ import annotations

from typing import Any

from assetforge.core.state import AssetForgeState


class GS003CameraSetup:
    """Apply the frozen eight-view camera library to the current iteration."""

    step_id = "GS003"
    name = "Camera Setup"

    CAMERA_IDS = tuple(f"CAM{index:02d}" for index in range(1, 9))
    REQUIRED_DEFAULTS = (
        "projection",
        "pitch",
        "background",
        "scale_locked",
        "camera_locked",
    )
    REQUIRED_RULES = (
        "preserve_pitch",
        "preserve_scale",
        "preserve_framing",
        "preserve_projection",
    )

    def execute(self, state: AssetForgeState) -> AssetForgeState:
        state.current_step = self.step_id
        state.log("Applying camera library.")

        camera_library = state.configs.get("CameraLibrary.yaml")
        error = self._validate(camera_library)
        if error:
            state.fail(error)
            state.log("Camera setup failed.")
            return state

        assert isinstance(camera_library, dict)
        defaults = camera_library["defaults"]
        cameras = camera_library["cameras"]
        rules = camera_library["rules"]
        state.metadata["active_camera_profile"] = {
            "status": "LOCKED",
            "defaults": dict(defaults),
            "cameras": {
                camera_id: dict(cameras[camera_id])
                for camera_id in self.CAMERA_IDS
            },
            "rules": dict(rules),
        }
        state.log(f"Locked {len(self.CAMERA_IDS)} camera views.")
        state.approve()
        return state

    def _validate(self, camera_library: Any) -> str | None:
        if not isinstance(camera_library, dict):
            return "CameraLibrary.yaml is not loaded."

        defaults = camera_library.get("defaults")
        cameras = camera_library.get("cameras")
        rules = camera_library.get("rules")
        if not isinstance(defaults, dict):
            return "Camera library defaults must be a mapping."
        if not isinstance(cameras, dict):
            return "Camera library cameras must be a mapping."
        if not isinstance(rules, dict):
            return "Camera library rules must be a mapping."

        missing_defaults = [key for key in self.REQUIRED_DEFAULTS if key not in defaults]
        if missing_defaults:
            return "Camera defaults are incomplete: " + ", ".join(missing_defaults)

        missing_cameras = [key for key in self.CAMERA_IDS if key not in cameras]
        if missing_cameras:
            return "Camera set is incomplete: " + ", ".join(missing_cameras)

        yaws: list[int | float] = []
        for camera_id in self.CAMERA_IDS:
            camera = cameras[camera_id]
            if not isinstance(camera, dict) or not camera.get("name"):
                return f"{camera_id} must define a name."
            yaw = camera.get("yaw")
            if not isinstance(yaw, (int, float)) or isinstance(yaw, bool):
                return f"{camera_id} must define a numeric yaw."
            yaws.append(yaw)
        if len(set(yaws)) != len(yaws):
            return "Camera yaw values must be unique."

        unlocked_rules = [key for key in self.REQUIRED_RULES if rules.get(key) is not True]
        if unlocked_rules:
            return "Camera lock rules are not enabled: " + ", ".join(unlocked_rules)

        if defaults.get("camera_locked") is not True:
            return "Camera library must enable camera_locked."
        if defaults.get("scale_locked") is not True:
            return "Camera library must enable scale_locked."
        return None
