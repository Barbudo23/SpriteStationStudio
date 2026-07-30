from __future__ import annotations

import ast
import re
import tomllib
import unittest
from pathlib import Path

from app.version import DISPLAY_VERSION, RELEASE_CHANNEL, VERSION


class ReleaseScopeTests(unittest.TestCase):
    def test_project_metadata_matches_current_dev_line(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["name"], "sprite-station-studio")
        self.assertEqual(metadata["project"]["version"], "0.10.0rc2")
        self.assertEqual(metadata["project"]["version"], VERSION)
        self.assertEqual(RELEASE_CHANNEL, "local-rc-candidate")
        gui = (root / "app" / "gui.py").read_text(encoding="utf-8")
        self.assertRegex(
            gui,
            re.compile(r'self\.title\(f"\{PRODUCT_NAME\} \{DISPLAY_VERSION\}'),
        )

    def test_readme_identifies_current_release_line(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"# Sprite Station Studio (SSS) — {DISPLAY_VERSION}",
            readme,
        )
        self.assertIn("v0.10.0-rc1", readme)
        self.assertIn("POST_RC_STABILIZATION_v0.10.md", readme)

    def test_v090_scope_freezes_existing_contracts_and_ai(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scope = (root / "docs" / "RC_SCOPE_v0.9.0.md").read_text(encoding="utf-8")
        self.assertIn("Render manifest: `1.1`", scope)
        self.assertIn("Unity import preset: `1.0`", scope)
        self.assertIn("AI Center", scope)
        self.assertIn("максимум трёх", scope)
        self.assertIn("`UNKNOWN`", scope)

    def test_workflow_readiness_does_not_claim_rc(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readiness = (root / "docs" / "WORKFLOW_READINESS_v0.9.0.md").read_text(encoding="utf-8")
        self.assertIn("READY FOR LIMITED GUI INTEGRATION", readiness)
        self.assertIn("NOT RC / NOT PRODUCTION READY", readiness)
        self.assertIn("Fresh physical E2E", readiness)
        self.assertIn("Sprite Station Studio", readiness)
        self.assertNotIn("AssetForge Studio", readiness)

    def test_physical_e2e_tool_is_reproducible_python(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tool = root / "Tools" / "Invoke-PhysicalStaticSpriteE2E.py"
        source = tool.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("freshBlenderPreviewCount", source)
        self.assertIn("workflowAuditAfterUnity", source)
        self.assertIn('"application": "Sprite Station Studio"', source)

    def test_release_candidate_builder_is_unpublished_and_no_overwrite(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "Tools" / "Build-ReleaseCandidate.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"published": False', source)
        self.assertIn("Release output already exists", source)
        self.assertIn('"archive", "--format=zip"', source)
        self.assertIn("provide --git PATH", source)

    def test_post_rc_policy_keeps_feature_scope_frozen(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = (root / "docs" / "POST_RC_STABILIZATION.md").read_text(encoding="utf-8")
        plan = (root / "docs" / "DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("post-rc/0.9.0-stabilization", policy)
        self.assertIn("post-rc/0.9.0-stabilization", plan)
        self.assertIn("возобновление AI Center", policy)
        self.assertIn("Когда нужен RC2", policy)
        self.assertIn("Stable требует отдельного решения", policy)


    def test_development_plan_tracks_current_rc2_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        plan = (root / "docs" / "DEVELOPMENT_PLAN.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("post-rc/0.10.0-stabilization", plan)
        self.assertIn("Local RC2 artifact", plan)
        self.assertIn("197/197", plan)
        self.assertIn("Remaining RC2 iterations", plan)
        self.assertIn("AI Center and Provider Reliability remain paused", plan)


if __name__ == "__main__":
    unittest.main()
