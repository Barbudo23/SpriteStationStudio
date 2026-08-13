from __future__ import annotations

import unittest

from app.blender_runner import ForgeError
from app.engine_export import build_unity_import_preset
from app.unity_animation_clip_descriptor import build_unity_animation_clip_descriptor


class UnityAnimationClipDescriptorTests(unittest.TestCase):
    def fixture(self) -> tuple[dict, dict]:
        timing = {
            "fps": 20.0,
            "fpsSource": "override",
            "sourceFrameStep": 2,
            "sampleTimesSeconds": [0.0, 0.1],
            "durationSeconds": 0.15,
            "loopPolicy": "loop",
        }
        directions = []
        assets = []
        for direction_id in ("north_east", "south_east"):
            directions.append({
                "id": direction_id,
                "sheet": f"animation_sheets/{direction_id}.png",
                "sheetSha256": "a" * 64,
                "frames": [
                    {"sourceFrame": 1},
                    {"sourceFrame": 3},
                ],
            })
            assets.append({
                "name": direction_id,
                "file": f"animation_sheets/{direction_id}.png",
                "spriteMode": "Multiple",
                "slices": [
                    {
                        "name": f"{direction_id}_000",
                        "rect": [0, 0, 64, 64],
                        "sourceFrame": 1,
                    },
                    {
                        "name": f"{direction_id}_001",
                        "rect": [64, 0, 64, 64],
                        "sourceFrame": 3,
                    },
                ],
            })
        manifest = {
            "schemaVersion": "1.1",
            "assetName": "Running Unit",
            "actionName": "Run",
            "sampledFrames": [1, 3],
            "frameRange": {"start": 1, "end": 3},
            "timing": timing,
            "canvas": {"width": 64, "height": 64},
            "normalization": {"pivot": {"normalized": [0.5, 0.0]}},
            "directions": directions,
        }
        preset = build_unity_import_preset(manifest)
        return manifest, preset

    def build(self, manifest: dict, preset: dict) -> dict:
        return build_unity_animation_clip_descriptor(
            manifest,
            preset,
            manifest_sha256="b" * 64,
            preset_sha256="c" * 64,
        )

    def test_builds_direction_clips_with_terminal_keyframes(self) -> None:
        manifest, preset = self.fixture()
        descriptor = self.build(manifest, preset)
        self.assertEqual(descriptor["clipCount"], 2)
        self.assertEqual(descriptor["clips"][0]["name"], "Running_Unit_Run_north_east")
        self.assertEqual(
            [item["timeSeconds"] for item in descriptor["clips"][0]["keyframes"]],
            [0.0, 0.1, 0.15],
        )
        self.assertTrue(descriptor["clips"][0]["keyframes"][-1]["terminal"])
        self.assertTrue(descriptor["clips"][0]["loopTime"])
        self.assertEqual(
            descriptor["clips"][0]["binding"]["propertyName"],
            "m_Sprite",
        )

    def test_rejects_preset_timing_mismatch(self) -> None:
        manifest, preset = self.fixture()
        preset["animationTiming"]["loopPolicy"] = "once"
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)

    def test_rejects_reordered_or_aliased_slices(self) -> None:
        manifest, preset = self.fixture()
        preset["assets"][0]["slices"][1]["name"] = "north_east_000"
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)

    def test_rejects_sheet_or_source_frame_mismatch(self) -> None:
        manifest, preset = self.fixture()
        preset["assets"][0]["file"] = "animation_sheets/other.png"
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)
        manifest, preset = self.fixture()
        preset["assets"][0]["slices"][0]["sourceFrame"] = 2
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)

    def test_rejects_noncanonical_slice_rect_or_import_settings(self) -> None:
        manifest, preset = self.fixture()
        preset["assets"][0]["slices"][1]["rect"] = [63, 0, 64, 64]
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)
        manifest, preset = self.fixture()
        preset["assets"][0]["filterMode"] = "Point"
        with self.assertRaisesRegex(ForgeError, "exactly match"):
            self.build(manifest, preset)

    def test_action_name_is_part_of_clip_identity(self) -> None:
        manifest, preset = self.fixture()
        run_names = [clip["name"] for clip in self.build(manifest, preset)["clips"]]
        manifest["actionName"] = "Idle"
        idle_preset = build_unity_import_preset(manifest)
        idle_names = [clip["name"] for clip in self.build(manifest, idle_preset)["clips"]]
        self.assertTrue(set(run_names).isdisjoint(idle_names))

    def test_rejects_missing_timing_or_invalid_hash(self) -> None:
        manifest, preset = self.fixture()
        del manifest["timing"]
        with self.assertRaisesRegex(ForgeError, "requires animation timing"):
            self.build(manifest, preset)
        manifest, preset = self.fixture()
        with self.assertRaisesRegex(ForgeError, "source hashes"):
            build_unity_animation_clip_descriptor(
                manifest,
                preset,
                manifest_sha256="invalid",
                preset_sha256="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
