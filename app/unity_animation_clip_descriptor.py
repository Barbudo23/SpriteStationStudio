from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from app.animation_validation import validate_animation_manifest, validate_animation_timing
from app.blender_runner import ForgeError
from app.engine_export import build_unity_import_preset


DESCRIPTOR_NAME = "unity_animation_clip_descriptor.json"
MANIFEST_NAME = "animation_manifest.json"
PRESET_NAME = "unity_import_preset.json"
MAX_CLIPS = 8
MAX_KEYFRAMES = 129


@dataclass(frozen=True)
class UnityAnimationClipDescriptorReport:
    descriptor_path: Path
    clip_count: int
    keyframe_count: int
    valid: bool = True


def build_unity_animation_clip_descriptor(
    manifest: dict,
    preset: dict,
    *,
    manifest_sha256: str,
    preset_sha256: str,
) -> dict:
    if not isinstance(manifest, dict) or not isinstance(preset, dict):
        raise ForgeError("Animation manifest and Unity preset must be JSON objects.")
    if not _is_sha256(manifest_sha256) or not _is_sha256(preset_sha256):
        raise ForgeError("AnimationClip descriptor source hashes are invalid.")
    sampled_frames = manifest.get("sampledFrames")
    frame_range = manifest.get("frameRange")
    timing = validate_animation_timing(
        manifest.get("timing"),
        sampled_frames=sampled_frames,
        frame_range=frame_range,
    )
    if timing is None:
        raise ForgeError("AnimationClip descriptor requires animation timing.")
    asset_name = manifest.get("assetName")
    if (
        not isinstance(asset_name, str)
        or not asset_name.strip()
        or asset_name != asset_name.strip()
        or len(asset_name) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in asset_name)
    ):
        raise ForgeError("AnimationClip descriptor assetName is invalid.")
    if (
        preset.get("schemaVersion") != "1.0"
        or preset.get("engine") != "Unity"
        or preset.get("assetName") != asset_name
    ):
        raise ForgeError("Unity preset identity does not match the animation manifest.")
    if preset != build_unity_import_preset(manifest):
        raise ForgeError("Unity preset does not exactly match the animation manifest.")
    preset_timing = preset.get("animationTiming")
    if not isinstance(preset_timing, dict):
        raise ForgeError("Unity preset lacks validated animationTiming.")
    expected_timing = {
        "fps": timing.fps,
        "fpsSource": timing.fps_source,
        "sourceFrameStep": timing.source_frame_step,
        "sampleTimesSeconds": list(timing.sample_times_seconds),
        "durationSeconds": timing.duration_seconds,
        "loopPolicy": timing.loop_policy,
    }
    if preset_timing != expected_timing:
        raise ForgeError("Unity preset animationTiming does not match the animation manifest.")

    directions = manifest.get("directions")
    assets = preset.get("assets")
    if (
        not isinstance(directions, list)
        or not isinstance(assets, list)
        or not directions
        or len(directions) != len(assets)
        or len(directions) > MAX_CLIPS
    ):
        raise ForgeError("AnimationClip descriptor direction assets are inconsistent.")

    clips: list[dict] = []
    clip_names: set[str] = set()
    sprite_names: set[str] = set()
    for direction, asset in zip(directions, assets):
        if not isinstance(direction, dict) or not isinstance(asset, dict):
            raise ForgeError("AnimationClip descriptor direction is invalid.")
        direction_id = direction.get("id")
        sheet = direction.get("sheet")
        frames = direction.get("frames")
        slices = asset.get("slices")
        if (
            not isinstance(direction_id, str)
            or not direction_id
            or asset.get("name") != direction_id
            or asset.get("spriteMode") != "Multiple"
            or not isinstance(sheet, str)
            or asset.get("file") != sheet
            or not isinstance(frames, list)
            or not isinstance(slices, list)
            or len(frames) != len(slices)
            or len(frames) != len(timing.sample_times_seconds)
            or not frames
            or len(frames) + 1 > MAX_KEYFRAMES
        ):
            raise ForgeError("AnimationClip descriptor slices do not match a direction.")

        keyframes: list[dict] = []
        for index, (frame, sprite_slice, time_seconds) in enumerate(
            zip(frames, slices, timing.sample_times_seconds)
        ):
            expected_name = f"{direction_id}_{index:03d}"
            source_frame = frame.get("sourceFrame") if isinstance(frame, dict) else None
            rect = sprite_slice.get("rect") if isinstance(sprite_slice, dict) else None
            if (
                not isinstance(sprite_slice, dict)
                or sprite_slice.get("name") != expected_name
                or sprite_slice.get("sourceFrame") != source_frame
                or not isinstance(rect, list)
                or len(rect) != 4
                or any(isinstance(value, bool) or not isinstance(value, int) for value in rect)
                or rect[0] < 0
                or rect[1] < 0
                or rect[2] <= 0
                or rect[3] <= 0
                or expected_name in sprite_names
            ):
                raise ForgeError("AnimationClip descriptor sprite slice contract is invalid.")
            sprite_names.add(expected_name)
            keyframes.append({
                "timeSeconds": time_seconds,
                "spriteName": expected_name,
                "sourceFrame": source_frame,
                "terminal": False,
            })
        keyframes.append({
            "timeSeconds": timing.duration_seconds,
            "spriteName": keyframes[-1]["spriteName"],
            "sourceFrame": keyframes[-1]["sourceFrame"],
            "terminal": True,
        })
        action_name = manifest.get("actionName")
        action_slug = _safe_name(action_name or "Animation")[:48]
        direction_slug = _safe_name(direction_id)
        max_asset_length = max(1, 128 - len(action_slug) - len(direction_slug) - 2)
        clip_name = (
            f"{_safe_name(asset_name)[:max_asset_length]}_"
            f"{action_slug}_{direction_slug}"
        )
        if clip_name in clip_names:
            raise ForgeError("AnimationClip descriptor clip names are duplicated.")
        clip_names.add(clip_name)
        sheet_hash = direction.get("sheetSha256")
        if not _is_sha256(sheet_hash):
            raise ForgeError("AnimationClip descriptor sprite sheet hash is invalid.")
        clips.append({
            "name": clip_name,
            "directionId": direction_id,
            "spriteSheet": sheet,
            "spriteSheetSha256": sheet_hash,
            "frameRate": timing.fps,
            "durationSeconds": timing.duration_seconds,
            "loopTime": timing.loop_policy == "loop",
            "binding": {
                "relativePath": "",
                "componentType": "UnityEngine.SpriteRenderer",
                "propertyName": "m_Sprite",
            },
            "keyframes": keyframes,
        })

    descriptor = {
        "schemaVersion": "1.0",
        "application": "Sprite Station Studio",
        "kind": "unity_animation_clip_descriptor",
        "sourceAnimationManifest": MANIFEST_NAME,
        "sourceAnimationManifestSha256": manifest_sha256,
        "sourceUnityPreset": PRESET_NAME,
        "sourceUnityPresetSha256": preset_sha256,
        "assetName": asset_name,
        "actionName": manifest.get("actionName"),
        "clipCount": len(clips),
        "clips": clips,
    }
    return descriptor


def _write_unity_animation_clip_descriptor(
    manifest_path: Path,
    preset_path: Path,
    output_path: Path | None = None,
) -> Path:
    manifest_path = manifest_path.expanduser().resolve()
    preset_path = preset_path.expanduser().resolve()
    validate_animation_manifest(manifest_path)
    manifest = _load_json(manifest_path, "Animation manifest")
    preset = _load_json(preset_path, "Unity preset")
    descriptor = build_unity_animation_clip_descriptor(
        manifest,
        preset,
        manifest_sha256=_sha256(manifest_path),
        preset_sha256=_sha256(preset_path),
    )
    output = (
        output_path.expanduser().resolve()
        if output_path is not None
        else manifest_path.parent / DESCRIPTOR_NAME
    )
    if output.name != DESCRIPTOR_NAME:
        raise ForgeError(f"AnimationClip descriptor must be named {DESCRIPTOR_NAME}.")
    if output.exists():
        raise ForgeError(f"AnimationClip descriptor already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.staging-{uuid4().hex}"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(descriptor, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise ForgeError(f"AnimationClip descriptor already exists: {output}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return output


def validate_unity_animation_clip_descriptor(
    descriptor_path: Path,
    manifest_path: Path,
    preset_path: Path,
) -> UnityAnimationClipDescriptorReport:
    descriptor_path = descriptor_path.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    preset_path = preset_path.expanduser().resolve()
    actual = _load_json(descriptor_path, "Unity AnimationClip descriptor")
    validate_animation_manifest(manifest_path)
    expected = build_unity_animation_clip_descriptor(
        _load_json(manifest_path, "Animation manifest"),
        _load_json(preset_path, "Unity preset"),
        manifest_sha256=_sha256(manifest_path),
        preset_sha256=_sha256(preset_path),
    )
    if actual != expected:
        raise ForgeError("Unity AnimationClip descriptor does not match approved sources.")
    clips = actual["clips"]
    return UnityAnimationClipDescriptorReport(
        descriptor_path=descriptor_path,
        clip_count=len(clips),
        keyframe_count=sum(len(clip["keyframes"]) for clip in clips),
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "Animation"


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ForgeError(f"{label} must be a JSON object.")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
