from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from uuid import uuid4

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import clear_scene, import_model


RESULT_PREFIX = "[SSS_TWO_ACTION_FIXTURE] "
ACTION_NAMES = ("SSS QA Run", "SSS_QA_Run")
REST_MATRIX_DECIMALS = 6


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-source", required=True)
    parser.add_argument("--secondary-source", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def active_action(armature: bpy.types.Object) -> bpy.types.Action:
    animation_data = armature.animation_data
    action = animation_data.action if animation_data is not None else None
    if action is None:
        raise RuntimeError("Imported armature has no active Action.")
    return action


def skeleton_signature(
    armature: bpy.types.Object,
) -> tuple[tuple[str, str | None, tuple[float, ...]], ...]:
    """Return a deterministic hierarchy and rest-pose identity."""
    return tuple(
        sorted(
            (
                bone.name,
                bone.parent.name if bone.parent is not None else None,
                tuple(
                    round(float(value), REST_MATRIX_DECIMALS)
                    for row in bone.matrix_local
                    for value in row
                ),
            )
            for bone in armature.data.bones
        )
    )


def skeleton_signature_sha256(
    signature: tuple[tuple[str, str | None, tuple[float, ...]], ...],
) -> str:
    payload = json.dumps(
        signature,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    args = parse_args()
    primary = Path(args.primary_source).expanduser().resolve()
    secondary = Path(args.secondary_source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    staging = output.with_name(
        f".{output.stem}.staging-{uuid4().hex}{output.suffix}"
    )
    try:
        if any(path.suffix.lower() != ".fbx" or not path.is_file() for path in (primary, secondary)):
            raise RuntimeError("Two-Action fixture sources must be existing FBX files.")
        if primary == secondary:
            raise RuntimeError("Two-Action fixture requires two distinct source files.")
        if output.suffix.lower() != ".fbx":
            raise RuntimeError("Two-Action fixture output must be an FBX file.")
        if output.exists():
            raise RuntimeError(f"Two-Action fixture output already exists: {output}")
        if output in {primary, secondary}:
            raise RuntimeError("Two-Action fixture cannot overwrite a source model.")
        primary_source_sha256 = sha256_file(primary)
        secondary_source_sha256 = sha256_file(secondary)

        clear_scene()
        import_model(primary)
        if sha256_file(primary) != primary_source_sha256:
            raise RuntimeError("Primary fixture source changed during import.")
        primary_objects = set(bpy.context.scene.objects)
        primary_armatures = [obj for obj in primary_objects if obj.type == "ARMATURE"]
        if len(primary_armatures) != 1:
            raise RuntimeError("Primary fixture source must contain exactly one armature.")
        primary_armature = primary_armatures[0]
        primary_action = active_action(primary_armature)
        primary_action.name = ACTION_NAMES[0]
        primary_action.use_fake_user = True
        primary_skeleton = skeleton_signature(primary_armature)

        import_model(secondary)
        if sha256_file(secondary) != secondary_source_sha256:
            raise RuntimeError("Secondary fixture source changed during import.")
        secondary_objects = set(bpy.context.scene.objects) - primary_objects
        secondary_armatures = [obj for obj in secondary_objects if obj.type == "ARMATURE"]
        if len(secondary_armatures) != 1:
            raise RuntimeError("Secondary fixture source must contain exactly one armature.")
        secondary_armature = secondary_armatures[0]
        secondary_action = active_action(secondary_armature)
        secondary_skeleton = skeleton_signature(secondary_armature)
        primary_names = tuple(item[0] for item in primary_skeleton)
        secondary_names = tuple(item[0] for item in secondary_skeleton)
        if secondary_names != primary_names:
            raise RuntimeError("Two-Action fixture skeleton bone names do not match.")
        primary_hierarchy = tuple((item[0], item[1]) for item in primary_skeleton)
        secondary_hierarchy = tuple((item[0], item[1]) for item in secondary_skeleton)
        if secondary_hierarchy != primary_hierarchy:
            raise RuntimeError("Two-Action fixture skeleton hierarchy does not match.")
        primary_rest_pose = tuple((item[0], item[2]) for item in primary_skeleton)
        secondary_rest_pose = tuple((item[0], item[2]) for item in secondary_skeleton)
        if secondary_rest_pose != primary_rest_pose:
            raise RuntimeError("Two-Action fixture skeleton rest pose does not match.")
        secondary_action.name = ACTION_NAMES[1]
        secondary_action.use_fake_user = True

        primary_animation = primary_armature.animation_data_create()
        primary_animation.action = secondary_action
        for frame in (secondary_action.frame_range[0], secondary_action.frame_range[1]):
            bpy.context.scene.frame_set(int(frame))
            bpy.context.view_layer.update()
        primary_animation.action = primary_action

        for obj in secondary_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.scene.frame_start = int(
            min(primary_action.frame_range[0], secondary_action.frame_range[0])
        )
        bpy.context.scene.frame_end = int(
            max(primary_action.frame_range[1], secondary_action.frame_range[1])
        )
        bpy.context.scene.frame_set(bpy.context.scene.frame_start)

        bpy.ops.object.select_all(action="DESELECT")
        export_objects = [
            obj
            for obj in primary_objects
            if obj.name in bpy.context.scene.objects
            and obj.type in {"ARMATURE", "MESH", "EMPTY"}
        ]
        for obj in export_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = primary_armature

        output.parent.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            raise RuntimeError(f"Two-Action fixture staging path already exists: {staging}")
        bpy.ops.export_scene.fbx(
            filepath=str(staging),
            use_selection=True,
            object_types={"ARMATURE", "MESH", "EMPTY"},
            apply_unit_scale=True,
            add_leaf_bones=False,
            bake_anim=True,
            bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=True,
            bake_anim_force_startend_keying=True,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
            path_mode="COPY",
            embed_textures=True,
        )
        if not staging.is_file() or staging.stat().st_size == 0:
            raise RuntimeError("Blender did not create the Two-Action FBX fixture.")
        if (
            sha256_file(primary) != primary_source_sha256
            or sha256_file(secondary) != secondary_source_sha256
        ):
            raise RuntimeError("Two-Action fixture source changed during creation.")
        fixture_sha256 = sha256_file(staging)
        try:
            os.link(staging, output)
        except FileExistsError as exc:
            raise RuntimeError(
                f"Two-Action fixture output already exists: {output}"
            ) from exc
        if sha256_file(output) != fixture_sha256:
            raise RuntimeError("Published Two-Action fixture hash mismatch.")
        staging.unlink()

        actions = sorted(
            (
                {
                    "name": action.name,
                    "frameRange": [
                        float(action.frame_range[0]),
                        float(action.frame_range[1]),
                    ],
                    "active": action == primary_animation.action,
                }
                for action in (primary_action, secondary_action)
            ),
            key=lambda item: item["name"].casefold(),
        )
        print(
            RESULT_PREFIX
            + json.dumps(
                {
                    "schemaVersion": "1.0",
                    "application": "Sprite Station Studio",
                    "primarySourceSha256": primary_source_sha256,
                    "secondarySourceSha256": secondary_source_sha256,
                    "fixtureSha256": fixture_sha256,
                    "fixture": str(output),
                    "boneCount": len(primary_skeleton),
                    "skeletonsMatch": True,
                    "skeletonSignatureSha256": skeleton_signature_sha256(
                        primary_skeleton
                    ),
                    "restMatrixDecimals": REST_MATRIX_DECIMALS,
                    "actions": actions,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        staging.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
