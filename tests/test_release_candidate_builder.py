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
                os.replace(source, destination)

            with self.assertRaisesRegex(OSError, "injected publish failure"):
                MODULE.publish_transactionally(tuple(pairs), replace=fail_second)
            self.assertTrue(all(not destination.exists() for _, destination in pairs))


if __name__ == "__main__":
    unittest.main()
