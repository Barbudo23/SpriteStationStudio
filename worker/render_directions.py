from __future__ import annotations

import argparse
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
from mathutils import Vector

# Reuse proven helpers from the single-preview worker.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import (
    clear_scene,
    import_model,
    renderable_objects,
    world_bounds,
    normalize_scene,
    setup_camera,
    setup_lighting,
    configure_render,
)


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
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--engine", default="AUTO")
    parser.add_argument("--directions", type=int, choices=(4, 8), default=8)
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


def build_contact_sheet(frame_paths: list[tuple[str, Path]], output_path: Path) -> None:
    # Build inside Blender using image datablocks and compositor-independent pixel copy.
    loaded = []
    try:
        for name, path in frame_paths:
            loaded.append((name, bpy.data.images.load(str(path), check_existing=False)))

        cell = max(img.size[0] for _, img in loaded)
        cols = 4
        rows = math.ceil(len(loaded) / cols)
        label_h = 28
        sheet_w = cols * cell
        sheet_h = rows * (cell + label_h)

        sheet = bpy.data.images.new(
            "ContactSheet",
            width=sheet_w,
            height=sheet_h,
            alpha=True,
            float_buffer=False,
        )
        pixels = [0.10, 0.10, 0.10, 1.0] * (sheet_w * sheet_h)

        for index, (_, img) in enumerate(loaded):
            col = index % cols
            row = rows - 1 - (index // cols)
            x0 = col * cell
            y0 = row * (cell + label_h)
            src = list(img.pixels)
            iw, ih = img.size

            for y in range(ih):
                for x in range(iw):
                    si = (y * iw + x) * 4
                    di = ((y0 + y) * sheet_w + (x0 + x)) * 4
                    pixels[di:di + 4] = src[si:si + 4]

        sheet.pixels = pixels
        sheet.filepath_raw = str(output_path)
        sheet.file_format = "PNG"
        sheet.save()
    finally:
        for _, img in loaded:
            bpy.data.images.remove(img)
        if "sheet" in locals():
            bpy.data.images.remove(sheet)


def write_zip(output_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            archive.write(path, path.relative_to(output_dir))


def main() -> int:
    args = parse_args()
    model = Path(args.model).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = output_dir / "directions"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    started = time.perf_counter()
    report_path = output_dir / "directions_report.json"
    manifest_path = output_dir / "manifest.json"
    contact_sheet_path = output_dir / "contact_sheet.png"
    zip_path = output_dir / f"{model.stem}_{args.directions}dir.zip"

    try:
        clear_scene()
        import_model(model)

        objects = renderable_objects()
        if not objects:
            raise RuntimeError("No renderable objects found.")

        bounds = normalize_scene(objects)
        asset_root = create_asset_root()
        setup_camera(*bounds)
        setup_lighting(*bounds)
        resolved_engine = configure_render(
            frames_dir / "placeholder.png",
            args.resolution,
            args.engine,
        )

        directions = DIRECTIONS_8 if args.directions == 8 else DIRECTIONS_4
        frame_records = []
        frame_paths = []

        for index, (direction_id, yaw_degrees) in enumerate(directions):
            print(f"[Forge] Direction {index + 1}/{len(directions)}: {direction_id}")
            asset_root.rotation_euler[2] = math.radians(yaw_degrees)
            bpy.context.view_layer.update()

            output_path = frames_dir / f"{index:02d}_{direction_id}.png"
            bpy.context.scene.render.filepath = str(output_path)
            bpy.ops.render.render(write_still=True)

            frame_paths.append((direction_id, output_path))
            frame_records.append({
                "id": direction_id,
                "order": index,
                "yawDegrees": yaw_degrees,
                "file": output_path.relative_to(output_dir).as_posix(),
            })

        build_contact_sheet(frame_paths, contact_sheet_path)

        manifest = {
            "schemaVersion": "1.0",
            "application": "AssetForge Studio",
            "module": "Pseudo3D Forge",
            "sourceType": "3d_model",
            "assetName": model.stem,
            "directionCount": len(directions),
            "directions": frame_records,
            "canvas": {
                "width": args.resolution,
                "height": args.resolution,
            },
            "renderEngine": resolved_engine,
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "contactSheet": contact_sheet_path.name,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        report = {
            "schemaVersion": "1.0",
            "status": "success",
            "source": str(model),
            "directionCount": len(directions),
            "renderEngine": resolved_engine,
            "durationMs": round((time.perf_counter() - started) * 1000),
            "contactSheet": str(contact_sheet_path),
            "zip": str(zip_path),
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        write_zip(output_dir, zip_path)
        print(f"[Forge] SUCCESS: {zip_path}")
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
