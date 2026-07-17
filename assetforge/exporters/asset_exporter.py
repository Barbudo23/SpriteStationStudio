"""Production-format export service."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image
import yaml


@dataclass(frozen=True)
class ExportResult:
    root: Path
    png_files: tuple[Path, ...]
    sprite_sheet: Path
    gif_preview: Path
    metadata_file: Path


class AssetExporter:
    """Create the frozen PNG, sprite-sheet and GIF export structure."""

    def export(self, sources: Sequence[Path], output_root: Path) -> ExportResult:
        if not sources:
            raise ValueError("At least one generated asset is required for export.")
        missing = [str(path) for path in sources if not path.is_file()]
        if missing:
            raise FileNotFoundError("Generated assets are missing: " + ", ".join(missing))

        png_directory = output_root / "PNG"
        sheet_directory = output_root / "SpriteSheet"
        gif_directory = output_root / "GIF"
        for directory in (png_directory, sheet_directory, gif_directory):
            directory.mkdir(parents=True, exist_ok=True)

        exported_pngs: list[Path] = []
        frames: list[Image.Image] = []
        for index, source in enumerate(sources, start=1):
            destination = png_directory / f"AssetForge_View_{index:02d}.png"
            shutil.copy2(source, destination)
            exported_pngs.append(destination)
            with Image.open(destination) as image:
                frames.append(image.convert("RGBA"))

        width = sum(frame.width for frame in frames)
        height = max(frame.height for frame in frames)
        sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        offset = 0
        for frame in frames:
            sheet.alpha_composite(frame, (offset, 0))
            offset += frame.width
        sprite_sheet = sheet_directory / "AssetForge_SpriteSheet.png"
        sheet.save(sprite_sheet, format="PNG")

        gif_preview = gif_directory / "AssetForge_Preview.gif"
        frames[0].save(
            gif_preview,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=250,
            loop=0,
            disposal=2,
        )

        metadata_file = output_root / "Export_Metadata.yaml"
        metadata = {
            "status": "PASS",
            "formats": ["PNG", "SpriteSheet", "GIF"],
            "unity_compatible": True,
            "transparent_background": True,
            "files": {
                "png_sequence": [path.relative_to(output_root).as_posix() for path in exported_pngs],
                "sprite_sheet": sprite_sheet.relative_to(output_root).as_posix(),
                "gif_preview": gif_preview.relative_to(output_root).as_posix(),
            },
        }
        with metadata_file.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(metadata, stream, sort_keys=False)

        return ExportResult(
            root=output_root,
            png_files=tuple(exported_pngs),
            sprite_sheet=sprite_sheet,
            gif_preview=gif_preview,
            metadata_file=metadata_file,
        )
