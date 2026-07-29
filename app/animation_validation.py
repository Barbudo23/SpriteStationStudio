from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.blender_runner import ForgeError
from core.validation import PreviewValidationError, decode_rgba_png


MAX_ANIMATION_PIXELS = 16 * 1024 * 1024


@dataclass(frozen=True)
class AnimationManifestReport:
    manifest_path: Path
    direction_count: int
    frame_count_per_direction: int
    frame_paths: tuple[Path, ...]
    sheet_paths: tuple[Path, ...]


def validate_animation_manifest(manifest_path: Path) -> AnimationManifestReport:
    manifest_path = manifest_path.expanduser().resolve()
    root = manifest_path.parent
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read animation manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ForgeError("Animation manifest must be a JSON object.")
    if manifest.get("schemaVersion") != "1.1":
        raise ForgeError("Animation manifest schemaVersion must be 1.1.")
    if manifest.get("application") != "Sprite Station Studio":
        raise ForgeError("Animation manifest application brand is invalid.")
    if manifest.get("module") != "Animation Sprite Renderer":
        raise ForgeError("Animation manifest module is invalid.")

    direction_count = manifest.get("directionCount")
    directions = manifest.get("directions")
    sampled_frames = manifest.get("sampledFrames")
    frame_count = manifest.get("frameCountPerDirection")
    if direction_count not in {4, 8}:
        raise ForgeError("Animation manifest directionCount must be 4 or 8.")
    if not isinstance(directions, list) or len(directions) != direction_count:
        raise ForgeError("Animation manifest directions do not match directionCount.")
    if (
        not isinstance(sampled_frames, list)
        or not sampled_frames
        or len(sampled_frames) > 128
        or not all(isinstance(value, int) and not isinstance(value, bool) for value in sampled_frames)
        or len(sampled_frames) != len(set(sampled_frames))
    ):
        raise ForgeError("Animation manifest sampledFrames are invalid.")
    if frame_count != len(sampled_frames):
        raise ForgeError("Animation manifest frameCountPerDirection is inconsistent.")
    canvas = manifest.get("canvas")
    if not isinstance(canvas, dict):
        raise ForgeError("Animation manifest canvas is invalid.")
    width = canvas.get("width")
    height = canvas.get("height")
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or not 1 <= width <= 4096
        or not 1 <= height <= 4096
        or width * height > MAX_ANIMATION_PIXELS
        or canvas.get("transparent") is not True
        or canvas.get("colorMode") != "RGBA"
    ):
        raise ForgeError("Animation manifest canvas must be safe transparent RGBA.")
    sheet_width = width * frame_count
    if sheet_width * height > MAX_ANIMATION_PIXELS:
        raise ForgeError("Animation sheets exceed the safe decoded-pixel limit.")

    frame_paths: list[Path] = []
    sheet_paths: list[Path] = []
    direction_ids: set[str] = set()
    for direction in directions:
        if not isinstance(direction, dict):
            raise ForgeError("Animation manifest direction is invalid.")
        direction_id = direction.get("id")
        if not isinstance(direction_id, str) or not direction_id or direction_id in direction_ids:
            raise ForgeError("Animation manifest direction IDs are invalid or duplicated.")
        direction_ids.add(direction_id)
        sheet_path = _resolve_file(root, direction.get("sheet"), "Animation sheet")
        sheet_paths.append(sheet_path)
        frames = direction.get("frames")
        if not isinstance(frames, list) or len(frames) != frame_count:
            raise ForgeError(f"Animation frames are incomplete: {direction_id}")
        for order, (frame, expected_source) in enumerate(zip(frames, sampled_frames)):
            if (
                not isinstance(frame, dict)
                or frame.get("order") != order
                or frame.get("sourceFrame") != expected_source
            ):
                raise ForgeError(f"Animation frame sequence is inconsistent: {direction_id}")
            frame_path = _resolve_file(
                root, frame.get("file"), f"Animation frame {direction_id}/{order}"
            )
            _validate_png(frame_path, width, height, f"Animation frame {direction_id}/{order}")
            frame_paths.append(frame_path)
        _validate_png(
            sheet_path,
            sheet_width,
            height,
            f"Animation sheet {direction_id}",
            require_transparency=False,
        )

    return AnimationManifestReport(
        manifest_path=manifest_path,
        direction_count=direction_count,
        frame_count_per_direction=frame_count,
        frame_paths=tuple(frame_paths),
        sheet_paths=tuple(sheet_paths),
    )


def _validate_png(
    path: Path,
    expected_width: int,
    expected_height: int,
    label: str,
    *,
    require_transparency: bool = True,
) -> None:
    try:
        width, height, rgba = decode_rgba_png(
            path,
            max_width=expected_width,
            max_height=expected_height,
            max_pixels=MAX_ANIMATION_PIXELS,
        )
    except PreviewValidationError as exc:
        raise ForgeError(f"{label} PNG is invalid: {exc}") from exc
    if (width, height) != (expected_width, expected_height):
        raise ForgeError(
            f"{label} dimensions mismatch: {width}x{height} != "
            f"{expected_width}x{expected_height}."
        )
    alpha = rgba[3::4]
    if not any(value > 0 for value in alpha):
        raise ForgeError(f"{label} contains no visible pixels.")
    if require_transparency and not any(value < 255 for value in alpha):
        raise ForgeError(f"{label} contains no transparent pixels.")


def _resolve_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ForgeError(f"{label} path must be relative.")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ForgeError(f"{label} path escapes animation output.") from exc
    if not path.is_file():
        raise ForgeError(f"{label} is missing: {path}")
    return path
