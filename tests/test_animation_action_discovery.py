from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.animation_action_discovery import AnimationActionDiscovery, RESULT_PREFIX
from app.blender_runner import ForgeError


class AnimationActionDiscoveryTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[AnimationActionDiscovery, Path, Path]:
        blender = root / "blender.exe"
        model = root / "unit.fbx"
        worker = root / "inspect.py"
        for path in (blender, model, worker):
            path.write_bytes(b"x")
        return AnimationActionDiscovery(worker), blender, model

    def test_build_command_is_background_read_only_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery, blender, model = self.fixture(Path(tmp))
            command = discovery.build_command(blender, model)
            self.assertIn("--background", command)
            self.assertIn("--factory-startup", command)
            self.assertEqual(command[-2:], ["--model", str(model)])
            self.assertNotIn("--output", command)

    @patch("app.animation_action_discovery.subprocess.run")
    def test_discovers_sorted_actions(self, run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery, blender, model = self.fixture(Path(tmp))
            payload = {
                "schemaVersion": "1.0",
                "actions": [
                    {"name": "Idle", "frameRange": [1.0, 24.0], "active": True},
                    {"name": "Run", "frameRange": [1.0, 12.0], "active": False},
                ],
            }
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="Blender log\n" + RESULT_PREFIX + json.dumps(payload) + "\n"
            )
            result = discovery.discover(blender, model)
            self.assertEqual([item.name for item in result], ["Idle", "Run"])
            self.assertTrue(result[0].active)
            self.assertEqual(result[1].frame_end, 12.0)

    def test_rejects_duplicate_unsorted_and_malformed_actions(self) -> None:
        invalid_lists = (
            [
                {"name": "Run", "frameRange": [1, 2], "active": False},
                {"name": "Idle", "frameRange": [1, 2], "active": True},
            ],
            [
                {"name": "Idle", "frameRange": [1, 2], "active": True},
                {"name": "Idle", "frameRange": [1, 2], "active": False},
            ],
            [{"name": " Bad", "frameRange": [1, 2], "active": False}],
            [{"name": "Run", "frameRange": [3, 2], "active": False}],
        )
        for actions in invalid_lists:
            with self.subTest(actions=actions):
                with self.assertRaises(ForgeError):
                    AnimationActionDiscovery._validate_payload({
                        "schemaVersion": "1.0", "actions": actions,
                    })

    @patch("app.animation_action_discovery.subprocess.run")
    def test_rejects_missing_or_multiple_reports(self, run) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery, blender, model = self.fixture(Path(tmp))
            for output in ("ordinary log", RESULT_PREFIX + "{}\n" + RESULT_PREFIX + "{}"):
                run.return_value = subprocess.CompletedProcess([], 0, stdout=output)
                with self.subTest(output=output):
                    with self.assertRaisesRegex(ForgeError, "exactly one"):
                        discovery.discover(blender, model)


if __name__ == "__main__":
    unittest.main()
