"""Build a deterministic AssetForge Stack release archive."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def iter_release_files(root: Path, release_directory: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        if release_directory in path.parents:
            continue
        yield path, relative.as_posix()


def build_release(root: Path, stack_revision: str) -> tuple[Path, Path]:
    release_directory = root / "releases"
    release_directory.mkdir(parents=True, exist_ok=True)
    archive_path = release_directory / f"AssetForge_{stack_revision}.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for source, member in iter_release_files(root, release_directory):
            info = ZipInfo(member, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    digest = sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = archive_path.with_suffix(".sha256")
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
    return archive_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="Stack_02_Rev00")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    archive, checksum = build_release(root, args.stack)
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
