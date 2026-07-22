from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import shutil
import tempfile
import uuid


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

DIRECTION_ORDER = (
    "front_left",
    "front_right",
    "back_right",
    "back_left",
)


class ImageSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageAssetRequest:
    asset_name: str
    images: dict[str, Path]
    output_dir: Path

    def validate(self) -> None:
        clean_name = self.asset_name.strip()
        if not clean_name:
            raise ImageSourceError("Укажите имя ассета.")

        missing = [direction for direction in DIRECTION_ORDER if direction not in self.images]
        if missing:
            raise ImageSourceError(
                "Не выбраны изображения: " + ", ".join(missing)
            )

        for direction in DIRECTION_ORDER:
            path = self.images[direction]
            if not path.is_file():
                raise ImageSourceError(f"Файл не найден ({direction}): {path}")
            if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                raise ImageSourceError(
                    f"Неподдерживаемый формат ({direction}): {path.suffix}"
                )


@dataclass(frozen=True)
class ImageAssetResult:
    zip_path: Path
    manifest_path: Path
    workspace: Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_asset_name(value: str) -> str:
    result = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in value.strip()
    ).strip("_")
    return result or "ImageAsset"


def build_image_asset(request: ImageAssetRequest) -> ImageAssetResult:
    request.validate()
    request.output_dir.mkdir(parents=True, exist_ok=True)

    asset_name = safe_asset_name(request.asset_name)
    workspace = request.output_dir / f"{asset_name}_ImageAsset"
    if workspace.exists():
        shutil.rmtree(workspace)

    images_dir = workspace / "images"
    images_dir.mkdir(parents=True)

    directions_manifest: list[dict] = []
    for order, direction in enumerate(DIRECTION_ORDER):
        source = request.images[direction]
        target = images_dir / f"{direction}{source.suffix.lower()}"
        shutil.copy2(source, target)
        directions_manifest.append({
            "id": direction,
            "order": order,
            "file": target.relative_to(workspace).as_posix(),
            "sourceName": source.name,
            "sha256": sha256(target),
        })

    manifest = {
        "schemaVersion": "1.0",
        "application": "Sprite Station Studio",
        "module": "Pseudo3D Forge",
        "sourceType": "four_direction_images",
        "assetId": str(uuid.uuid4()),
        "assetName": asset_name,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "directions": directions_manifest,
        "processing": {
            "blenderUsed": False,
            "normalized": False,
            "pivotAligned": False,
            "backgroundRemoved": False,
        },
        "nextRecommendedStages": [
            "Validate dimensions",
            "Remove background or confirm alpha",
            "Normalize canvas",
            "Align pivot",
            "Create animation frames",
            "Build sprite sheet",
        ],
    }

    manifest_path = workspace / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readme = workspace / "README.txt"
    readme.write_text(
        "Sprite Station Studio image-source package.\n"
        "This package was created without Blender from four directional images.\n",
        encoding="utf-8",
    )

    zip_path = request.output_dir / f"{asset_name}_ImageAsset.zip"
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for file in sorted(workspace.rglob("*")):
            if file.is_file():
                archive.write(file, Path(workspace.name) / file.relative_to(workspace))

    return ImageAssetResult(
        zip_path=zip_path,
        manifest_path=manifest_path,
        workspace=workspace,
    )
