"""Deterministic production package assembly."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml


@dataclass(frozen=True)
class PackageResult:
    package_file: Path
    metadata_file: Path
    checksum: str
    members: tuple[str, ...]


class AssetPackager:
    """Create a stable ZIP and package metadata from an approved export."""

    def package(
        self,
        *,
        export_root: Path,
        iteration_root: Path,
        package_directory: Path,
        package_name: str,
    ) -> PackageResult:
        required_export = (
            export_root / "PNG",
            export_root / "SpriteSheet",
            export_root / "GIF",
            export_root / "Export_Metadata.yaml",
        )
        missing = [str(path) for path in required_export if not path.exists()]
        required_docs = (
            iteration_root / "Production_Report" / "Production_Report.md",
            iteration_root / "Readme.md",
        )
        missing.extend(str(path) for path in required_docs if not path.is_file())
        if missing:
            raise FileNotFoundError("Package inputs are missing: " + ", ".join(missing))

        files: list[tuple[Path, str]] = []
        for directory_name in ("PNG", "SpriteSheet", "GIF"):
            directory = export_root / directory_name
            files.extend(
                (path, path.relative_to(export_root).as_posix())
                for path in sorted(directory.rglob("*"))
                if path.is_file()
            )
        files.extend(
            (
                (export_root / "Export_Metadata.yaml", "Export_Metadata.yaml"),
                (required_docs[0], "Production_Report.md"),
                (required_docs[1], "Readme.md"),
            )
        )

        package_directory.mkdir(parents=True, exist_ok=True)
        package_file = package_directory / package_name
        with ZipFile(package_file, "w", compression=ZIP_DEFLATED) as archive:
            for source, member in files:
                info = ZipInfo(member, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())

        checksum = sha256(package_file.read_bytes()).hexdigest()
        members = tuple(member for _, member in files)
        metadata_file = package_directory / f"{package_file.stem}_Metadata.yaml"
        metadata = {
            "status": "PASS",
            "package": package_file.name,
            "sha256": checksum,
            "members": list(members),
        }
        with metadata_file.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(metadata, stream, sort_keys=False)
        return PackageResult(package_file, metadata_file, checksum, members)
