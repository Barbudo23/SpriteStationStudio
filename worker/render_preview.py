from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--engine", default="AUTO")
    parser.add_argument("--camera-profile", default="Strategy30")
    parser.add_argument("--camera-azimuth", type=float, default=45.0)
    parser.add_argument("--camera-elevation", type=float, default=30.0)
    parser.add_argument("--framing-margin", type=float, default=1.35)
    parser.add_argument("--pivot-mode", choices=("bottom_center",), default="bottom_center")
    return parser.parse_args(argv)


def clear_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.armatures,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(collection):
            if datablock.users == 0:
                collection.remove(datablock)


def import_model(path: Path) -> None:
    ext = path.suffix.lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"Unsupported format: {ext}")


def renderable_objects() -> list[bpy.types.Object]:
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}
        and not obj.hide_render
    ]


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for original in objects:
        obj = original.evaluated_get(depsgraph)
        matrix = obj.matrix_world
        if hasattr(obj, "bound_box"):
            points.extend(matrix @ Vector(corner) for corner in obj.bound_box)

    if not points:
        raise RuntimeError("Imported scene contains no renderable geometry.")

    minimum = Vector((
        min(p.x for p in points),
        min(p.y for p in points),
        min(p.z for p in points),
    ))
    maximum = Vector((
        max(p.x for p in points),
        max(p.y for p in points),
        max(p.z for p in points),
    ))
    return minimum, maximum


def top_level_imported(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    object_set = set(objects)
    return [obj for obj in objects if obj.parent not in object_set]


def normalize_scene(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    minimum, maximum = world_bounds(objects)
    center_xy = Vector(((minimum.x + maximum.x) / 2, (minimum.y + maximum.y) / 2, 0))
    offset = Vector((-center_xy.x, -center_xy.y, -minimum.z))

    scene_objects = list(bpy.context.scene.objects)
    for obj in top_level_imported(scene_objects):
        obj.location += offset

    bpy.context.view_layer.update()
    return world_bounds(objects)


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_camera(
    minimum: Vector,
    maximum: Vector,
    azimuth_degrees: float = 45.0,
    elevation_degrees: float = 30.0,
    framing_margin: float = 1.35,
) -> bpy.types.Object:
    size = maximum - minimum
    center = (minimum + maximum) * 0.5
    max_dim = max(size.x, size.y, size.z, 0.001)

    if not 0.0 <= elevation_degrees < 90.0:
        raise ValueError("Camera elevation must be between 0 and 90 degrees.")
    if not 1.0 <= framing_margin <= 3.0:
        raise ValueError("Camera framing margin must be between 1.0 and 3.0.")

    azimuth = math.radians(azimuth_degrees)
    elevation = math.radians(elevation_degrees)
    distance = max_dim * 4.0
    horizontal = math.cos(elevation) * distance

    camera_data = bpy.data.cameras.new("ForgeCamera")
    camera = bpy.data.objects.new("ForgeCamera", camera_data)
    bpy.context.collection.objects.link(camera)

    camera.location = Vector((
        center.x + math.cos(azimuth) * horizontal,
        center.y + math.sin(azimuth) * horizontal,
        center.z + math.sin(elevation) * distance,
    ))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max_dim * framing_margin
    camera_data.lens = 50
    camera_data.clip_start = max(max_dim / 1000.0, 0.001)
    camera_data.clip_end = max(distance * 10.0, 1000.0)
    look_at(camera, center)

    bpy.context.scene.camera = camera
    return camera


def add_area_light(name: str, location: tuple[float, float, float],
                   energy: float, size: float, target: Vector) -> None:
    light_data = bpy.data.lights.new(name=name, type="AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light)
    light.location = location
    look_at(light, target)


def setup_lighting(minimum: Vector, maximum: Vector) -> None:
    size = maximum - minimum
    center = (minimum + maximum) * 0.5
    max_dim = max(size.x, size.y, size.z, 0.001)

    world = bpy.context.scene.world or bpy.data.worlds.new("ForgeWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
        background.inputs["Strength"].default_value = 0.35

    add_area_light(
        "Key",
        tuple(center + Vector((max_dim * 2.2, -max_dim * 2.0, max_dim * 3.0))),
        1200.0,
        max_dim * 2.0,
        center,
    )
    add_area_light(
        "Fill",
        tuple(center + Vector((-max_dim * 2.0, -max_dim * 1.0, max_dim * 1.5))),
        650.0,
        max_dim * 2.5,
        center,
    )
    add_area_light(
        "Rim",
        tuple(center + Vector((0.0, max_dim * 2.5, max_dim * 2.2))),
        900.0,
        max_dim * 1.5,
        center,
    )


def available_render_engines() -> set[str]:
    prop = bpy.types.RenderSettings.bl_rna.properties.get("engine")
    if prop is None:
        return {"BLENDER_WORKBENCH", "CYCLES"}
    return {item.identifier for item in prop.enum_items}


def resolve_render_engine(requested: str) -> str:
    available = available_render_engines()

    if requested != "AUTO" and requested in available:
        return requested

    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if candidate in available:
            return candidate

    for candidate in ("BLENDER_WORKBENCH", "CYCLES"):
        if candidate in available:
            return candidate

    raise RuntimeError(
        "No supported render engine is available. Found: "
        + ", ".join(sorted(available))
    )


def configure_render(output_path: Path, resolution: int, engine: str) -> str:
    scene = bpy.context.scene
    resolved_engine = resolve_render_engine(engine)
    scene.render.engine = resolved_engine
    print(f"[Forge] Render engine: {resolved_engine}")

    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(output_path)
    scene.render.use_file_extension = True

    if resolved_engine in {"BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"}:
        scene.render.image_settings.color_depth = "8"
    elif resolved_engine == "CYCLES":
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True

    return resolved_engine


def make_report(
    model: Path,
    output: Path,
    status: str,
    started: float,
    error: str | None = None,
    bounds: tuple[Vector, Vector] | None = None,
) -> dict:
    objects = list(bpy.context.scene.objects)
    report = {
        "schemaVersion": "1.0",
        "application": "Pseudo3D Forge",
        "version": "0.1.0",
        "status": status,
        "source": str(model),
        "format": model.suffix.lower().lstrip("."),
        "output": str(output),
        "objects": len(objects),
        "meshes": sum(1 for o in objects if o.type == "MESH"),
        "armatures": sum(1 for o in objects if o.type == "ARMATURE"),
        "materials": len(bpy.data.materials),
        "durationMs": round((time.perf_counter() - started) * 1000),
        "blenderVersion": bpy.app.version_string,
    }
    if bounds:
        minimum, maximum = bounds
        report["bounds"] = {
            "min": list(minimum),
            "max": list(maximum),
            "size": list(maximum - minimum),
        }
    if error:
        report["error"] = error
    return report


def main() -> int:
    args = parse_args()
    model = Path(args.model).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    preview = output_dir / "Preview.png"
    report_path = output_dir / "import_report.json"
    manifest_path = output_dir / "preview_manifest.json"
    started = time.perf_counter()
    bounds = None

    try:
        if not model.is_file():
            raise FileNotFoundError(model)

        print("[Forge] Cleaning scene")
        clear_scene()

        print(f"[Forge] Importing {model}")
        import_model(model)

        objects = renderable_objects()
        if not objects:
            raise RuntimeError("Import completed, but no renderable objects were found.")

        print("[Forge] Normalizing model")
        bounds = normalize_scene(objects)

        print("[Forge] Creating camera")
        setup_camera(
            *bounds,
            azimuth_degrees=args.camera_azimuth,
            elevation_degrees=args.camera_elevation,
            framing_margin=args.framing_margin,
        )

        print("[Forge] Creating lights")
        setup_lighting(*bounds)

        print("[Forge] Rendering preview")
        resolved_engine = configure_render(preview, args.resolution, args.engine)
        bpy.ops.render.render(write_still=True)

        if not preview.is_file():
            raise RuntimeError("Render finished, but Preview.png was not written.")

        report = make_report(model, preview, "success", started, bounds=bounds)
        report["renderEngine"] = resolved_engine
        report["cameraProfile"] = args.camera_profile
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest = {
            "schemaVersion": "1.1",
            "application": "AssetForge Studio",
            "module": "Single Sprite Preview",
            "sourceType": "3d_model",
            "assetName": model.stem,
            "sprite": preview.name,
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
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[Forge] SUCCESS: {preview}")
        return 0

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        report = make_report(
            model, preview, "error", started, error=error, bounds=bounds
        )
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[Forge] ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
