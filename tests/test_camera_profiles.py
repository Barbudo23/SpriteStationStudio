from __future__ import annotations

import unittest

from app.blender_runner import ForgeError
from app.camera_profiles import CAMERA_PROFILES, get_camera_profile


class CameraProfileTests(unittest.TestCase):
    def test_all_registered_profiles_are_valid(self) -> None:
        for profile in CAMERA_PROFILES.values():
            profile.validate()

    def test_strategy_profile_is_stable_default(self) -> None:
        profile = get_camera_profile("Strategy30")
        self.assertEqual(profile.elevation_degrees, 30.0)
        self.assertEqual(profile.pivot_mode, "bottom_center")

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaises(ForgeError):
            get_camera_profile("Unknown")


if __name__ == "__main__":
    unittest.main()
