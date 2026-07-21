from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from app.unity_runner import UnityBridgeError


@dataclass(frozen=True)
class UnityPackageExportResult:
    target_dir: Path
    copied_files: tuple[Path, ...]


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return name or "AssetForgeSprite"


def _validate_unity_assets_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    assets = resolved / "Assets" if (resolved / "Assets").is_dir() else resolved
    if assets.name.lower() != "assets" or not assets.is_dir():
        raise UnityBridgeError(
            "Select a Unity project root or its existing Assets directory."
        )
    if not (assets.parent / "ProjectSettings").is_dir():
        raise UnityBridgeError(f"Not a Unity project: {assets.parent}")
    return assets


def export_verified_package(
    preset_path: Path,
    preview_report_path: Path,
    unity_project_or_assets: Path,
) -> UnityPackageExportResult:
    preset_path = preset_path.expanduser().resolve()
    preview_report_path = preview_report_path.expanduser().resolve()
    if not preset_path.is_file() or not preview_report_path.is_file():
        raise UnityBridgeError("Unity preset and preview report are required.")

    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    report = json.loads(preview_report_path.read_text(encoding="utf-8"))
    if not report.get("readOnlyPreview"):
        raise UnityBridgeError("The package has no successful read-only Unity preview.")
    reported_preset = Path(str(report.get("presetPath", ""))).expanduser().resolve()
    if reported_preset != preset_path:
        raise UnityBridgeError("Unity preview report belongs to a different preset.")
    sprite_assets = report.get("spriteAssets") or []
    if not sprite_assets or not all(item.get("valid") for item in sprite_assets):
        raise UnityBridgeError("Unity preview contains invalid sprite assets.")
    if report.get("warnings"):
        raise UnityBridgeError("Resolve Unity preview warnings before export.")
    preset_files = {str(item.get("file", "")) for item in preset.get("assets") or []}
    report_files = {str(item.get("file", "")) for item in sprite_assets}
    if not preset_files or preset_files != report_files:
        raise UnityBridgeError("Unity preview report does not match preset assets.")

    assets_dir = _validate_unity_assets_dir(unity_project_or_assets)
    asset_name = _safe_name(str(preset.get("assetName") or "AssetForgeSprite"))
    export_root = assets_dir / "AssetForgeImports"
    target_dir = export_root / asset_name
    if target_dir.exists():
        raise UnityBridgeError(
            f"Export target already exists; no files were overwritten: {target_dir}"
        )

    source_root = preset_path.parent
    relative_files: list[Path] = []
    for asset in preset.get("assets") or []:
        relative = Path(str(asset.get("file", "")))
        source = (source_root / relative).resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise UnityBridgeError(f"Sprite path escapes package: {relative}") from exc
        if not source.is_file():
            raise UnityBridgeError(f"Sprite file not found: {source}")
        relative_files.append(relative)

    for candidate in (
        preset_path,
        preview_report_path,
        source_root / "manifest.json",
        source_root / "animation_manifest.json",
        source_root / "preview_manifest.json",
    ):
        if candidate.is_file():
            relative_files.append(Path(candidate.name))

    relative_files = list(dict.fromkeys(relative_files))
    staging = export_root / f".{asset_name}.staging-{uuid4().hex}"
    copied: list[Path] = []
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for relative in relative_files:
            source = source_root / relative
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(destination)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(target_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return UnityPackageExportResult(
        target_dir=target_dir,
        copied_files=tuple(target_dir / path.relative_to(staging) for path in copied),
    )
