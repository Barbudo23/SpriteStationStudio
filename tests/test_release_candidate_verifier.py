from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


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

    def test_archive_snapshot_is_immutable_after_source_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, _, _ = self.fixture(Path(tmp))
            original = archive.read_bytes()
            snapshot, size, digest = MODULE.snapshot_archive(archive)
            archive.write_bytes(b"replacement")
            with snapshot:
                self.assertEqual(snapshot.read(), original)
            self.assertEqual(size, len(original))
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())

    def test_archive_snapshot_rejects_compressed_size_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, _, _ = self.fixture(Path(tmp))
            with patch.object(MODULE, "MAX_ARCHIVE_BYTES", 16):
                with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "compressed size limit"):
                    MODULE.snapshot_archive(archive)

    def test_manifest_rejects_declared_archive_size_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest, _ = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archiveBytes"] = MODULE.MAX_ARCHIVE_BYTES + 1
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "archiveBytes exceeds"):
                MODULE.read_manifest(manifest)

    def test_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archiveSha256"] = "0" * 64
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "SHA-256"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_malformed_manifest_scalar_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archiveBytes"] = True
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "positive integer"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_manifest_archive_path_instead_of_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["archive"] = "../" + archive.name
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "archive name"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_non_hex_commit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["commit"] = "not-a-git-commit"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "commit is invalid"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_path_traversal_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp), unsafe=True)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "Unsafe archive member"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_symbolic_link_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, manifest, checksum = self.fixture(root)
            with ZipFile(archive, "a") as package:
                link = ZipInfo("SpriteStationStudio-test/link")
                link.create_system = 3
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                package.writestr(link, "../../outside")
            self.rebind_manifest(archive, manifest, checksum, file_count=4)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "Symbolic links"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_suspicious_compression_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, manifest, checksum = self.fixture(root)
            with ZipFile(archive, "a", compression=ZIP_DEFLATED) as package:
                package.writestr("SpriteStationStudio-test/zeros.bin", bytes(1024 * 1024))
            self.rebind_manifest(archive, manifest, checksum, file_count=4)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "compression ratio"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, manifest, checksum = self.fixture(root)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(archive, "a") as package:
                    package.writestr("SpriteStationStudio-test/run.py", "duplicate\n")
            self.rebind_manifest(archive, manifest, checksum, file_count=4)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "duplicate members"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_rejects_backslash_member_before_windows_extraction(self) -> None:
        with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "Backslashes"):
            MODULE.portable_member_key("SpriteStationStudio-test\\..\\outside.txt")

    def test_rejects_case_insensitive_portable_path_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, manifest, checksum = self.fixture(root)
            with ZipFile(archive, "a") as package:
                package.writestr("SpriteStationStudio-test/RUN.PY", "collision")
            self.rebind_manifest(archive, manifest, checksum, file_count=4)
            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "portable-path collisions"):
                MODULE.verify_release(archive, manifest, checksum)

    def test_clean_checks_reject_archive_replaced_after_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, manifest, checksum = self.fixture(Path(tmp))
            result = MODULE.verify_release(archive, manifest, checksum)
            archive.write_bytes(b"replacement after verification")

            with self.assertRaisesRegex(MODULE.ReleaseVerificationError, "changed after verification"):
                MODULE.run_clean_checks(
                    archive,
                    result["rootDirectory"],
                    result["archiveSha256"],
                )

    def rebind_manifest(
        self, archive: Path, manifest: Path, checksum: Path, *, file_count: int
    ) -> None:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["archiveSha256"] = digest
        payload["archiveBytes"] = archive.stat().st_size
        payload["trackedFileCount"] = file_count
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")


if __name__ == "__main__":
    unittest.main()
