from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import BinaryIO
import unicodedata
from zipfile import ZipFile


class ReleaseVerificationError(RuntimeError):
    pass


MAX_MEMBER_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def snapshot_archive(path: Path) -> tuple[BinaryIO, int, str]:
    """Copy and hash one opened source so later ZIP reads use identical bytes."""
    digest = hashlib.sha256()
    snapshot = tempfile.TemporaryFile(mode="w+b")
    size = 0
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                snapshot.write(block)
                size += len(block)
        snapshot.seek(0)
        return snapshot, size, digest.hexdigest()
    except Exception:
        snapshot.close()
        raise


def read_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"Cannot read release manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseVerificationError("Release manifest must be a JSON object.")
    required = {
        "application", "version", "releaseChannel", "commit", "archive",
        "archiveSha256", "archiveBytes", "trackedFileCount", "published",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ReleaseVerificationError(f"Release manifest is missing: {', '.join(missing)}")
    if payload["application"] != "Sprite Station Studio":
        raise ReleaseVerificationError("Release manifest application brand is invalid.")
    if not isinstance(payload["version"], str) or not VERSION_PATTERN.fullmatch(payload["version"]):
        raise ReleaseVerificationError("Release manifest version is invalid.")
    if payload["releaseChannel"] not in {"local-rc-candidate", "github-prerelease"}:
        raise ReleaseVerificationError("Release manifest channel is invalid.")
    if not isinstance(payload["commit"], str) or not COMMIT_PATTERN.fullmatch(payload["commit"]):
        raise ReleaseVerificationError("Release manifest commit is invalid.")
    if (
        not isinstance(payload["archive"], str)
        or PurePosixPath(payload["archive"]).name != payload["archive"]
        or not payload["archive"].endswith(".zip")
    ):
        raise ReleaseVerificationError("Release manifest archive name is invalid.")
    if not isinstance(payload["archiveSha256"], str) or not SHA256_PATTERN.fullmatch(payload["archiveSha256"]):
        raise ReleaseVerificationError("Release manifest SHA-256 is invalid.")
    for field in ("archiveBytes", "trackedFileCount"):
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ReleaseVerificationError(f"Release manifest {field} must be a positive integer.")
    if not isinstance(payload["published"], bool):
        raise ReleaseVerificationError("Release manifest published must be boolean.")
    return payload


def portable_member_key(name: str) -> str:
    if "\\" in name:
        raise ReleaseVerificationError(f"Backslashes are not allowed in archive members: {name}")
    member = PurePosixPath(name)
    for part in member.parts:
        if part in {"", ".", ".."}:
            raise ReleaseVerificationError(f"Unsafe archive member: {name}")
        if part.endswith((" ", ".")) or ":" in part:
            raise ReleaseVerificationError(f"Non-portable archive member: {name}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise ReleaseVerificationError(f"Windows-reserved archive member: {name}")
    return unicodedata.normalize("NFC", name).casefold()


def verify_release(
    archive_path: Path,
    manifest_path: Path,
    checksum_path: Path | None = None,
) -> dict:
    archive_path = archive_path.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    manifest = read_manifest(manifest_path)
    if archive_path.name != manifest["archive"]:
        raise ReleaseVerificationError("Archive filename does not match release manifest.")
    archive_stream, actual_size, actual_hash = snapshot_archive(archive_path)
    if actual_size != manifest["archiveBytes"]:
        archive_stream.close()
        raise ReleaseVerificationError("Archive size does not match release manifest.")
    if actual_hash != manifest["archiveSha256"]:
        archive_stream.close()
        raise ReleaseVerificationError("Archive SHA-256 does not match release manifest.")
    if checksum_path is not None:
        try:
            fields = checksum_path.read_text(encoding="ascii").strip().split()
        except (OSError, UnicodeError) as exc:
            archive_stream.close()
            raise ReleaseVerificationError(f"Cannot read checksum file: {exc}") from exc
        if fields != [actual_hash, archive_path.name]:
            archive_stream.close()
            raise ReleaseVerificationError("Checksum file does not match archive and manifest.")

    with archive_stream, ZipFile(archive_stream) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ReleaseVerificationError("Release archive contains duplicate members.")
        portable_keys = [portable_member_key(name.rstrip("/")) for name in names]
        if len(portable_keys) != len(set(portable_keys)):
            raise ReleaseVerificationError("Release archive contains portable-path collisions.")
        file_names = [name for name in names if not name.endswith("/")]
        roots: set[str] = set()
        total_uncompressed = 0
        for entry in entries:
            name = entry.filename
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or not member.parts:
                raise ReleaseVerificationError(f"Unsafe archive member: {name}")
            unix_mode = entry.external_attr >> 16
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise ReleaseVerificationError(f"Symbolic links are not allowed: {name}")
            if entry.flag_bits & 0x1:
                raise ReleaseVerificationError(f"Encrypted members are not allowed: {name}")
            if entry.file_size > MAX_MEMBER_BYTES:
                raise ReleaseVerificationError(f"Archive member exceeds size limit: {name}")
            total_uncompressed += entry.file_size
            if total_uncompressed > MAX_TOTAL_BYTES:
                raise ReleaseVerificationError("Release archive exceeds total uncompressed size limit.")
            if entry.file_size and entry.compress_size == 0:
                raise ReleaseVerificationError(f"Invalid compressed size: {name}")
            if entry.compress_size and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
                raise ReleaseVerificationError(f"Suspicious compression ratio: {name}")
            roots.add(member.parts[0])
        if len(roots) != 1:
            raise ReleaseVerificationError("Release archive must have exactly one root directory.")
        root = next(iter(roots))
        required = {
            f"{root}/run.py",
            f"{root}/pyproject.toml",
            f"{root}/RELEASE_NOTES_v0.9.0-rc1.md",
        }
        if not required.issubset(file_names):
            raise ReleaseVerificationError("Release archive is missing an entry point or release metadata.")
        metadata = tomllib.loads(archive.read(f"{root}/pyproject.toml").decode("utf-8"))
        if metadata.get("project", {}).get("version") != manifest["version"]:
            raise ReleaseVerificationError("Archive project version does not match release manifest.")
        if len(file_names) != manifest["trackedFileCount"]:
            raise ReleaseVerificationError("Archive file count does not match release manifest.")

    return {
        "application": manifest["application"],
        "version": manifest["version"],
        "commit": manifest["commit"],
        "archive": archive_path.name,
        "archiveBytes": actual_size,
        "archiveSha256": actual_hash,
        "fileCount": manifest["trackedFileCount"],
        "rootDirectory": root,
        "valid": True,
    }


def run_clean_checks(archive_path: Path, root: str, expected_sha256: str) -> None:
    with tempfile.TemporaryDirectory(prefix="sss-release-verify-") as tmp:
        # Bind extraction to the exact bytes verified earlier. Keeping the same
        # file handle open prevents a path replacement between hashing and use.
        with archive_path.open("rb") as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
            if digest.hexdigest() != expected_sha256:
                raise ReleaseVerificationError(
                    "Archive changed after verification and before clean checks."
                )
            stream.seek(0)
            with ZipFile(stream) as archive:
                archive.extractall(tmp)
        source = Path(tmp) / root
        commands = (
            [sys.executable, "-S", "run.py", "--help"],
            [sys.executable, "-S", "-m", "unittest", "discover", "-s", "tests", "-q"],
            [sys.executable, "-S", "Tools/Invoke-StaticSpriteWorkflowSmoke.py"],
        )
        for command in commands:
            subprocess.run(command, cwd=source, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an unpublished or published SSS release artifact.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--checksum", type=Path)
    parser.add_argument("--run-clean-checks", action="store_true")
    args = parser.parse_args()
    result = verify_release(args.archive, args.manifest, args.checksum)
    if args.run_clean_checks:
        run_clean_checks(
            args.archive.resolve(),
            result["rootDirectory"],
            result["archiveSha256"],
        )
        result["cleanChecks"] = "PASS"
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
