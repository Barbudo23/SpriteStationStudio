from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.blender_runner import ForgeError


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
        sheet_paths.append(_resolve_file(root, direction.get("sheet"), "Animation sheet"))
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
            frame_paths.append(
                _resolve_file(root, frame.get("file"), f"Animation frame {direction_id}/{order}")
            )

    return AnimationManifestReport(
        manifest_path=manifest_path,
        direction_count=direction_count,
        frame_count_per_direction=frame_count,
        frame_paths=tuple(frame_paths),
        sheet_paths=tuple(sheet_paths),
    )


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
