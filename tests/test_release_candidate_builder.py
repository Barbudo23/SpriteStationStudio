from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "Tools/Build-ReleaseCandidate.py"
SPEC = importlib.util.spec_from_file_location("sss_release_builder", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load release builder: {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleaseCandidateBuilderTests(unittest.TestCase):
    def test_current_release_notes_name_is_version_bound(self) -> None:
        self.assertEqual(MODULE.VERSION, "0.10.0rc1")
        self.assertEqual(MODULE.RELEASE_NOTES_FILE, "RELEASE_NOTES_v0.10.0-rc1.md")

    def test_transactional_publish_moves_complete_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = []
            pairs = []
            for name in ("release.zip", "manifest.json", "release.sha256"):
                source = root / "staging" / name
                source.parent.mkdir(exist_ok=True)
                source.write_text(name, encoding="utf-8")
                destination = root / "final" / name
                destination.parent.mkdir(exist_ok=True)
                staged.append(source)
                pairs.append((source, destination))
            MODULE.publish_transactionally(tuple(pairs))
            self.assertTrue(all(not path.exists() for path in staged))
            self.assertTrue(all(destination.is_file() for _, destination in pairs))

    def test_transactional_publish_rolls_back_after_injected_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairs = []
            for name in ("release.zip", "manifest.json", "release.sha256"):
                source = root / "staging" / name
                source.parent.mkdir(exist_ok=True)
                source.write_text(name, encoding="utf-8")
                destination = root / "final" / name
                destination.parent.mkdir(exist_ok=True)
                pairs.append((source, destination))
            calls = 0

            def fail_second(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected publish failure")
                os.link(source, destination)

            with self.assertRaisesRegex(OSError, "injected publish failure"):
                MODULE.publish_transactionally(tuple(pairs), link=fail_second)
            self.assertTrue(all(not destination.exists() for _, destination in pairs))

    def test_late_collision_is_preserved_and_other_outputs_roll_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairs = []
            for name in ("release.zip", "manifest.json", "release.sha256"):
                source = root / "staging" / name
                source.parent.mkdir(exist_ok=True)
                source.write_text(name, encoding="utf-8")
                destination = root / "final" / name
                destination.parent.mkdir(exist_ok=True)
                pairs.append((source, destination))
            calls = 0

            def collide_second(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    destination.write_text("external owner", encoding="utf-8")
                os.link(source, destination)

            with self.assertRaises(FileExistsError):
                MODULE.publish_transactionally(tuple(pairs), link=collide_second)
            self.assertFalse(pairs[0][1].exists())
            self.assertEqual(pairs[1][1].read_text(encoding="utf-8"), "external owner")
            self.assertFalse(pairs[2][1].exists())


if __name__ == "__main__":
    unittest.main()
