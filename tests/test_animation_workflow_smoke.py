from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


class AnimationWorkflowSmokeTests(unittest.TestCase):
    def test_synthetic_animation_workflow_is_reproducible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-S", "Tools/Invoke-AnimationWorkflowSmoke.py"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["directionCount"], 4)
        self.assertEqual(payload["frameCountPerDirection"], 2)
        self.assertEqual(payload["renderCheckedFileCount"], 14)
        self.assertEqual(payload["packageArtifactCount"], 17)
        self.assertEqual(
            payload["unityClipDescriptor"],
            "unity_animation_clip_descriptor.json",
        )
        self.assertEqual(payload["unityClipCount"], 4)
        self.assertEqual(payload["unityClipKeyframeCount"], 8)
        self.assertTrue(payload["approved"])
        self.assertTrue(payload["auditValid"])
