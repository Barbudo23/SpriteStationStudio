from __future__ import annotations

from dataclasses import dataclass

from app.blender_runner import ForgeError


@dataclass(frozen=True)
class CameraProfile:
    profile_id: str
    azimuth_degrees: float
    elevation_degrees: float
    framing_margin: float
    pivot_mode: str = "bottom_center"

    def validate(self) -> None:
        if not -360.0 <= self.azimuth_degrees <= 360.0:
            raise ForgeError("Camera azimuth must be between -360 and 360 degrees.")
        if not 0.0 <= self.elevation_degrees < 90.0:
            raise ForgeError("Camera elevation must be between 0 and 90 degrees.")
        if not 1.0 <= self.framing_margin <= 3.0:
            raise ForgeError("Camera framing margin must be between 1.0 and 3.0.")
        if self.pivot_mode != "bottom_center":
            raise ForgeError(f"Unsupported sprite pivot mode: {self.pivot_mode}")


CAMERA_PROFILES: dict[str, CameraProfile] = {
    "Strategy30": CameraProfile("Strategy30", 45.0, 30.0, 1.35),
    "XCOM": CameraProfile("XCOM", 45.0, 35.0, 1.40),
    "Commandos": CameraProfile("Commandos", 45.0, 42.0, 1.45),
    "Diablo": CameraProfile("Diablo", 45.0, 30.0, 1.50),
}

DEFAULT_CAMERA_PROFILE = "Strategy30"


def get_camera_profile(profile_id: str) -> CameraProfile:
    try:
        profile = CAMERA_PROFILES[profile_id]
    except KeyError as exc:
        available = ", ".join(CAMERA_PROFILES)
        raise ForgeError(
            f"Unknown camera profile '{profile_id}'. Available: {available}."
        ) from exc
    profile.validate()
    return profile
