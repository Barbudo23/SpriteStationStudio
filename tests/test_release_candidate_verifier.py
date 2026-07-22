from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "Tools/Verify-ReleaseCandidate.py"
SPEC = importlib.util.spec_from_file_location("sss_release_verifier", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load release verifier: {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleaseCandidateVerifierTests(unittest.TestCase):
    def fixture(self, root: Path, unsafe: bool = False) -> tuple[Path, Path, Path]:
        archive_path = root / "SpriteStationStudio-test.zip"
        prefix = "SpriteStationStudio-test"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr(f"{prefix}/run.py", "print('ok')\n")
            archive.writestr(
                f"{prefix}/pyproject.toml",
                '[project]\nname = "sprite-station-studio"\nversion = "0.9.0rc1"\n',
            )
            archive.writestr(f"{prefix}/RELEASE_NOTES_v0.9.0-rc1.md", "# RC1\n")
            if unsafe:
                archive.writestr("../outside.txt", "unsafe")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps({
            "application": "Sprite Station Studio",
            "version": "0.9.0rc1",
            "releaseChannel": "local-rc-candidate",
            "commit": "a" * 40,
            "archive": archive_path.name,
            "archiveSha256": digest,
            "archiveBytes": archive_path.stat().st_size,
            "trackedFileCount": 4 if unsafe else 3,
            "published": False,
        }), encoding="utf-8")
        checksum_path = root / "archive.sha256"
        checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
        return archive_path, manifest_path, checksum_path

    def test_accepts_valid_integrity_bound_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            result = MODULE.verify_release(archive, manifest, checksum)
            self.assertTrue(result["valid"])
            self.assertEqual(result["fileCount"], 3)
            self.assertEqual(result["version"], "0.9.0rc1")

    def test_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archiveSha256"] = "0" * 64
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "SHA-256"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_path_traversal_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp), unsafe=True)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "Unsafe archive member"):
                MODULE.verify_release(archive, manifest, checksum)


if __name__ == "__main__":
    unittest.main()
