from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from app.blender_runner import ForgeError
from core.validation import PreviewValidationError, decode_rgba_png


MAX_ANIMATION_PIXELS = 16 * 1024 * 1024
EXPECTED_DIRECTIONS = {
    4: (
        ("north_east", 45.0),
        ("south_east", 135.0),
        ("south_west", 225.0),
        ("north_west", 315.0),
    ),
    8: (
        ("north", 0.0),
        ("north_east", 45.0),
        ("east", 90.0),
        ("south_east", 135.0),
        ("south", 180.0),
        ("south_west", 225.0),
        ("west", 270.0),
        ("north_west", 315.0),
    ),
}


@dataclass(frozen=True)
class AnimationManifestReport:
    manifest_path: Path
    direction_count: int
    frame_count_per_direction: int
    frame_paths: tuple[Path, ...]
    sheet_paths: tuple[Path, ...]
    contact_sheet_path: Path
    checked_file_count: int
    action_name: str | None


def validate_animation_manifest(
    manifest_path: Path, source_path: Path | None = None
) -> AnimationManifestReport:
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
    action_name = manifest.get("actionName")
    if action_name is not None and (
        not isinstance(action_name, str)
        or not action_name.strip()
        or action_name != action_name.strip()
        or len(action_name) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in action_name)
    ):
        raise ForgeError("Animation manifest actionName is invalid.")
    if source_path is not None:
        source_path = source_path.expanduser().resolve()
        if not source_path.is_file() or _sha256(source_path) != manifest.get("sourceSha256"):
            raise ForgeError("Animation source SHA-256 does not match manifest.")

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
    frame_range = manifest.get("frameRange")
    if (
        not isinstance(frame_range, dict)
        or isinstance(frame_range.get("start"), bool)
        or isinstance(frame_range.get("end"), bool)
        or not isinstance(frame_range.get("start"), int)
        or not isinstance(frame_range.get("end"), int)
        or frame_range["start"] > frame_range["end"]
        or any(
            current >= following
            for current, following in zip(sampled_frames, sampled_frames[1:])
        )
        or sampled_frames[0] < frame_range["start"]
        or sampled_frames[-1] > frame_range["end"]
    ):
        raise ForgeError(
            "Animation manifest sampledFrames must increase inside frameRange."
        )
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
    for direction_index, direction in enumerate(directions):
        if not isinstance(direction, dict):
            raise ForgeError("Animation manifest direction is invalid.")
        direction_id = direction.get("id")
        if not isinstance(direction_id, str) or not direction_id or direction_id in direction_ids:
            raise ForgeError("Animation manifest direction IDs are invalid or duplicated.")
        direction_ids.add(direction_id)
        expected_id, expected_yaw = EXPECTED_DIRECTIONS[direction_count][direction_index]
        yaw = direction.get("yawDegrees")
        if (
            direction_id != expected_id
            or isinstance(yaw, bool)
            or not isinstance(yaw, (int, float))
            or float(yaw) != expected_yaw
        ):
            raise ForgeError("Animation direction identity, order or yaw is invalid.")
        sheet_path = _resolve_file(root, direction.get("sheet"), "Animation sheet")
        _verify_hash(sheet_path, direction.get("sheetSha256"), f"Animation sheet {direction_id}")
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
            _verify_hash(frame_path, frame.get("sha256"), f"Animation frame {direction_id}/{order}")
            _validate_png(frame_path, width, height, f"Animation frame {direction_id}/{order}")
            frame_paths.append(frame_path)
        _validate_png(
            sheet_path,
            sheet_width,
            height,
            f"Animation sheet {direction_id}",
            require_transparency=False,
        )
    contact_sheet_path = _resolve_file(
        root, manifest.get("contactSheet"), "Animation contact sheet"
    )
    _verify_hash(
        contact_sheet_path, manifest.get("contactSheetSha256"), "Animation contact sheet"
    )
    _validate_png(
        contact_sheet_path,
        width * min(direction_count, 4),
        height * ((direction_count + 3) // 4),
        "Animation contact sheet",
        require_transparency=False,
    )
    output_paths = [*frame_paths, *sheet_paths, contact_sheet_path]
    if len(output_paths) != len(set(output_paths)):
        raise ForgeError("Animation manifest contains duplicate output file paths.")

    return AnimationManifestReport(
        manifest_path=manifest_path,
        direction_count=direction_count,
        frame_count_per_direction=frame_count,
        frame_paths=tuple(frame_paths),
        sheet_paths=tuple(sheet_paths),
        contact_sheet_path=contact_sheet_path,
        checked_file_count=len(frame_paths) + len(sheet_paths) + 1 + (source_path is not None),
        action_name=action_name,
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_hash(path: Path, expected: object, label: str) -> None:
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
        or _sha256(path) != expected
    ):
        raise ForgeError(f"{label} SHA-256 does not match manifest.")
