from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import (
    clear_scene,
    import_model,
    renderable_objects,
    normalize_scene,
    setup_camera,
    setup_lighting,
    configure_render,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


DIRECTIONS_8 = (
    ("north", 0.0),
    ("north_east", 45.0),
    ("east", 90.0),
    ("south_east", 135.0),
    ("south", 180.0),
    ("south_west", 225.0),
    ("west", 270.0),
    ("north_west", 315.0),
)
DIRECTIONS_4 = (
    ("north_east", 45.0),
    ("south_east", 135.0),
    ("south_west", 225.0),
    ("north_west", 315.0),
)


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--engine", default="AUTO")
    parser.add_argument("--directions", type=int, choices=(4, 8), default=8)
    parser.add_argument("--frame-start", type=int)
    parser.add_argument("--frame-end", type=int)
    parser.add_argument("--frame-step", type=int, default=2)
    parser.add_argument("--max-frames", type=int, default=32)
    parser.add_argument("--camera-profile", default="Strategy30")
    parser.add_argument("--camera-azimuth", type=float, default=45.0)
    parser.add_argument("--camera-elevation", type=float, default=30.0)
    parser.add_argument("--framing-margin", type=float, default=1.35)
    parser.add_argument("--pivot-mode", choices=("bottom_center",), default="bottom_center")
    return parser.parse_args(argv)


def create_asset_root() -> bpy.types.Object:
    root = bpy.data.objects.new("AssetRoot", None)
    bpy.context.collection.objects.link(root)
    for obj in list(bpy.context.scene.objects):
        if obj is root:
            continue
        if obj.parent is None and obj.type not in {"CAMERA", "LIGHT"}:
            obj.parent = root
    return root


def detect_frame_range(args: argparse.Namespace) -> tuple[int, int]:
    scene = bpy.context.scene
    start = args.frame_start if args.frame_start is not None else int(scene.frame_start)
    end = args.frame_end if args.frame_end is not None else int(scene.frame_end)

    action_ranges = []
    for obj in scene.objects:
        animation_data = getattr(obj, "animation_data", None)
        action = getattr(animation_data, "action", None) if animation_data else None
        if action:
            action_ranges.append(action.frame_range)
    if action_ranges and args.frame_start is None:
        start = math.floor(min(r[0] for r in action_ranges))
    if action_ranges and args.frame_end is None:
        end = math.ceil(max(r[1] for r in action_ranges))

    if end < start:
        raise RuntimeError(f"Invalid animation range: {start}..{end}")
    return start, end


def sample_frames(start: int, end: int, step: int, max_frames: int) -> list[int]:
    frames = list(range(start, end + 1, max(1, step)))
    if not frames:
        frames = [start]
    if len(frames) > max_frames:
        if max_frames == 1:
            return [frames[0]]
        # Evenly sample while preserving first and last frame.
        indices = [
            round(index * (len(frames) - 1) / (max_frames - 1))
            for index in range(max_frames)
        ]
        frames = [frames[index] for index in indices]
    return frames


def copy_image_into(
    source: bpy.types.Image,
    target_pixels: list[float],
    target_width: int,
    x0: int,
    y0: int,
) -> None:
    src = list(source.pixels)
    width, height = source.size
    for y in range(height):
        src_start = y * width * 4
        dst_start = ((y0 + y) * target_width + x0) * 4
        target_pixels[dst_start:dst_start + width * 4] = src[src_start:src_start + width * 4]


def build_sheet(image_paths: list[Path], output_path: Path, columns: int) -> None:
    loaded = []
    sheet = None
    try:
        loaded = [bpy.data.images.load(str(path), check_existing=False) for path in image_paths]
        if not loaded:
            raise RuntimeError("No images for sprite sheet.")
        cell_w = max(image.size[0] for image in loaded)
        cell_h = max(image.size[1] for image in loaded)
        columns = max(1, columns)
        rows = math.ceil(len(loaded) / columns)
        width = cell_w * columns
        height = cell_h * rows
        pixels = [0.0, 0.0, 0.0, 0.0] * (width * height)
        for index, image in enumerate(loaded):
            col = index % columns
            row = rows - 1 - index // columns
            copy_image_into(image, pixels, width, col * cell_w, row * cell_h)
        sheet = bpy.data.images.new(
            output_path.stem,
            width=width,
            height=height,
            alpha=True,
            float_buffer=False,
        )
        sheet.pixels = pixels
        sheet.filepath_raw = str(output_path)
        sheet.file_format = "PNG"
        sheet.save()
    finally:
        for image in loaded:
            bpy.data.images.remove(image)
        if sheet is not None:
            bpy.data.images.remove(sheet)


def write_zip(output_dir: Path, zip_path: Path, included: list[Path]) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in included:
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(output_dir))


def main() -> int:
    args = parse_args()
    model = Path(args.model).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    frames_root = output_dir / "animation_frames"
    sheets_root = output_dir / "animation_sheets"
    for directory in (frames_root, sheets_root):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    report_path = output_dir / "animation_report.json"
    manifest_path = output_dir / "animation_manifest.json"
    contact_sheet_path = output_dir / "animation_contact_sheet.png"
    zip_path = output_dir / f"{model.stem}_{args.directions}dir_animation.zip"
    started = time.perf_counter()

    try:
        clear_scene()
        import_model(model)
        objects = renderable_objects()
        if not objects:
            raise RuntimeError("No renderable objects found.")

        bounds = normalize_scene(objects)
        asset_root = create_asset_root()
        setup_camera(
            *bounds,
            azimuth_degrees=args.camera_azimuth,
            elevation_degrees=args.camera_elevation,
            framing_margin=args.framing_margin,
        )
        setup_lighting(*bounds)
        resolved_engine = configure_render(
            frames_root / "placeholder.png",
            args.resolution,
            args.engine,
        )

        start, end = detect_frame_range(args)
        frames = sample_frames(start, end, args.frame_step, args.max_frames)
        directions = DIRECTIONS_8 if args.directions == 8 else DIRECTIONS_4
        direction_records = []
        all_outputs: list[Path] = []
        first_frame_paths: list[Path] = []

        total_renders = len(directions) * len(frames)
        render_number = 0
        scene = bpy.context.scene

        for direction_index, (direction_id, yaw_degrees) in enumerate(directions):
            direction_dir = frames_root / direction_id
            direction_dir.mkdir(parents=True)
            asset_root.rotation_euler[2] = math.radians(yaw_degrees)
            bpy.context.view_layer.update()

            frame_paths: list[Path] = []
            frame_records = []
            for order, frame_number in enumerate(frames):
                render_number += 1
                print(
                    f"[Forge] Animation render {render_number}/{total_renders}: "
                    f"{direction_id} frame {frame_number}"
                )
                scene.frame_set(frame_number)
                bpy.context.view_layer.update()
                output_path = direction_dir / f"{order:03d}_frame_{frame_number:04d}.png"
                scene.render.filepath = str(output_path)
                bpy.ops.render.render(write_still=True)
                frame_paths.append(output_path)
                all_outputs.append(output_path)
                frame_records.append({
                    "order": order,
                    "sourceFrame": frame_number,
                    "file": output_path.relative_to(output_dir).as_posix(),
                    "sha256": sha256_file(output_path),
                })

            if frame_paths:
                first_frame_paths.append(frame_paths[0])
            sheet_path = sheets_root / f"{direction_index:02d}_{direction_id}.png"
            build_sheet(frame_paths, sheet_path, columns=len(frame_paths))
            all_outputs.append(sheet_path)
            direction_records.append({
                "id": direction_id,
                "yawDegrees": yaw_degrees,
                "sheet": sheet_path.relative_to(output_dir).as_posix(),
                "sheetSha256": sha256_file(sheet_path),
                "frames": frame_records,
            })

        build_sheet(first_frame_paths, contact_sheet_path, columns=4)
        all_outputs.append(contact_sheet_path)

        manifest = {
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "module": "Animation Sprite Renderer",
            "assetName": model.stem,
            "source": str(model),
            "sourceSha256": sha256_file(model),
            "directionCount": len(directions),
            "frameRange": {"start": start, "end": end},
            "sampledFrames": frames,
            "frameCountPerDirection": len(frames),
            "canvas": {
                "width": args.resolution,
                "height": args.resolution,
                "transparent": True,
                "colorMode": "RGBA",
            },
            "camera": {
                "profile": args.camera_profile,
                "projection": "orthographic",
                "azimuthDegrees": args.camera_azimuth,
                "elevationDegrees": args.camera_elevation,
                "framingMargin": args.framing_margin,
            },
            "normalization": {
                "centeredXY": True,
                "groundAligned": True,
                "scalePolicy": "fit_largest_dimension",
                "pivot": {
                    "mode": args.pivot_mode,
                    "normalized": [0.5, 0.0],
                },
                "bounds": {
                    "minimum": [float(value) for value in bounds[0]],
                    "maximum": [float(value) for value in bounds[1]],
                },
            },
            "renderEngine": resolved_engine,
            "directions": direction_records,
            "contactSheet": contact_sheet_path.name,
            "contactSheetSha256": sha256_file(contact_sheet_path),
            "createdUtc": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        all_outputs.append(manifest_path)

        report = {
            "schemaVersion": "1.0",
            "status": "success",
            "source": str(model),
            "directionCount": len(directions),
            "frameCountPerDirection": len(frames),
            "totalRenderedFrames": total_renders,
            "frameRange": [start, end],
            "cameraProfile": args.camera_profile,
            "renderEngine": resolved_engine,
            "durationMs": round((time.perf_counter() - started) * 1000),
            "contactSheet": str(contact_sheet_path),
            "zip": str(zip_path),
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        all_outputs.append(report_path)

        write_zip(output_dir, zip_path, all_outputs)
        print(f"[Forge] ANIMATION SUCCESS: {zip_path}")
        return 0
    except Exception as exc:
        traceback.print_exc()
        report_path.write_text(
            json.dumps({
                "schemaVersion": "1.0",
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "durationMs": round((time.perf_counter() - started) * 1000),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
