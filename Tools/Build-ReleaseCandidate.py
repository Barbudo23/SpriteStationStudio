from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import shutil
from zipfile import ZipFile

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from app.version import RELEASE_CHANNEL, VERSION


def git(git_executable: Path, *args: str) -> str:
    result = subprocess.run(
        [str(git_executable), *args], cwd=REPOSITORY, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(output_dir: Path, git_executable: Path) -> tuple[Path, Path, Path]:
    if git(git_executable, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Tracked working tree changes must be committed before packaging.")
    commit = git(git_executable, "rev-parse", "HEAD")
    tracked_files = tuple(line for line in git(git_executable, "ls-files").splitlines() if line)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"SpriteStationStudio-v{VERSION}-{commit[:8]}"
    archive_path = output_dir / f"{base_name}.zip"
    manifest_path = output_dir / f"{base_name}.manifest.json"
    checksum_path = output_dir / f"{base_name}.sha256"
    for path in (archive_path, manifest_path, checksum_path):
        if path.exists():
            raise RuntimeError(f"Release output already exists: {path}")
    subprocess.run(
        [str(git_executable), "archive", "--format=zip", f"--prefix={base_name}/", f"--output={archive_path}", commit],
        cwd=REPOSITORY, check=True,
    )
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"Unsafe archive member: {name}")
        required = {
            f"{base_name}/run.py",
            f"{base_name}/pyproject.toml",
            f"{base_name}/RELEASE_NOTES_v0.9.0-rc1.md",
        }
        if not required.issubset(names):
            raise RuntimeError("Release archive is missing required entry points or notes.")
    checksum = sha256(archive_path)
    manifest = {
        "application": "Sprite Station Studio",
        "version": VERSION,
        "releaseChannel": RELEASE_CHANNEL,
        "commit": commit,
        "archive": archive_path.name,
        "archiveSha256": checksum,
        "archiveBytes": archive_path.stat().st_size,
        "trackedFileCount": len(tracked_files),
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "published": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_path.write_text(f"{checksum}  {archive_path.name}\n", encoding="ascii")
    return archive_path, manifest_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an unpublished Sprite Station Studio RC artifact.")
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY / "output/release-candidate")
    parser.add_argument("--git", type=Path, default=shutil.which("git"), help="Path to git executable.")
    args = parser.parse_args()
    if args.git is None or not args.git.is_file():
        parser.error("git executable was not found; provide --git PATH")
    archive, manifest, checksum = build(args.output_dir, args.git.resolve())
    print(json.dumps({
        "archive": str(archive), "manifest": str(manifest), "checksum": str(checksum)
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
