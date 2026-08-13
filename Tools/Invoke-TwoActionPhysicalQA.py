from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.animation_action_discovery import (  # noqa: E402
    AnimationActionDiscovery,
    AnimationActionInfo,
)
from app.animation_approval import (  # noqa: E402
    audit_approved_animation_package,
    publish_approved_animation,
    record_animation_review,
)
from app.animation_runner import (  # noqa: E402
    AnimationRenderRequest,
    AnimationRenderRunner,
)
from app.blender_runner import ForgeError  # noqa: E402
from app.unity_animation_clip_bridge import (  # noqa: E402
    APPROVED_PACKAGE_NAME,
    BUILD_REPORT_NAME,
    BUNDLE_MANIFEST_NAME,
    UnityAnimationClipBridge,
    audit_unity_animation_clip_bundle,
)
from app.unity_runner import UnityRunner  # noqa: E402


FIXTURE_RESULT_PREFIX = "[SSS_TWO_ACTION_FIXTURE] "
QA_MANIFEST_NAME = "two_action_physical_qa.json"
REVIEW_NAME = "two_action_visual_review.json"
FINAL_RESULT_NAME = "two_action_physical_qa_result.json"
PREPARED_STATE_NAME = "prepared_two_action_physical_qa.json"
EXPECTED_ACTION_SUFFIXES = ("SSS QA Run", "SSS_QA_Run")
FIXTURE_RELATIVE = "fixture/sss_two_action_fixture.fbx"
RENDER_LAYOUT = (
    {
        "directory": "render-1-loop",
        "manifest": "render-1-loop/animation_manifest.json",
        "contactSheet": "render-1-loop/animation_contact_sheet.png",
        "actionSuffix": EXPECTED_ACTION_SUFFIXES[0],
        "loopPolicy": "loop",
    },
    {
        "directory": "render-2-once",
        "manifest": "render-2-once/animation_manifest.json",
        "contactSheet": "render-2-once/animation_contact_sheet.png",
        "actionSuffix": EXPECTED_ACTION_SUFFIXES[1],
        "loopPolicy": "once",
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the explicit two-stage Blender-to-Unity two-Action QA gate."
    )
    subparsers = parser.add_subparsers(dest="stage", required=True)
    prepare = subparsers.add_parser("prepare")
    _add_common(prepare)
    prepare.add_argument("--primary-source", type=Path, required=True)
    prepare.add_argument("--secondary-source", type=Path, required=True)
    finalize = subparsers.add_parser("finalize")
    _add_common(finalize)
    finalize.add_argument("--reviewer", required=True)
    finalize.add_argument(
        "--confirm-contact-sheets-approved",
        action="store_true",
        required=True,
    )
    args = parser.parse_args()

    result = prepare_qa(args) if args.stage == "prepare" else finalize_qa(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--unity", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)


def prepare_qa(args: argparse.Namespace) -> dict:
    workspace = args.workspace.expanduser().resolve()
    primary = args.primary_source.expanduser().resolve()
    secondary = args.secondary_source.expanduser().resolve()
    blender = args.blender.expanduser().resolve()
    unity = UnityRunner.validate_executable(args.unity)
    if workspace.exists():
        raise ForgeError(f"Two-Action QA workspace already exists: {workspace}")
    for label, source in (("primary", primary), ("secondary", secondary)):
        if not source.is_file() or source.suffix.lower() != ".fbx":
            raise ForgeError(f"Two-Action QA {label} source must be an existing FBX file.")
    if primary == secondary:
        raise ForgeError("Two-Action QA requires two distinct source files.")
    if not blender.is_file():
        raise ForgeError(f"Blender executable not found: {blender}")

    owner_token = uuid4().hex
    owner_marker = workspace / f".preparing-{owner_token}"
    try:
        workspace.mkdir(parents=True, exist_ok=False)
        owner_marker.write_text(owner_token, encoding="ascii")
        fixture = workspace / "fixture/sss_two_action_fixture.fbx"
        fixture.parent.mkdir(parents=True)
        fixture_report = _create_fixture(
            blender, primary, secondary, fixture, args.timeout
        )
        discovered = AnimationActionDiscovery().discover(
            blender, fixture, timeout_seconds=min(args.timeout, 300)
        )
        actions = _match_actions(discovered)
        if sum(item.active for item in actions) != 1:
            raise ForgeError("Two-Action fixture must have exactly one active Action.")

        render_runner = AnimationRenderRunner()
        renders: list[dict] = []
        for index, (action, loop_policy) in enumerate(
            zip(actions, ("loop", "once")), start=1
        ):
            output = workspace / f"render-{index}-{loop_policy}"
            request = AnimationRenderRequest(
                blender_path=blender,
                model_path=fixture,
                output_dir=output,
                resolution=64,
                engine="BLENDER_EEVEE_NEXT",
                direction_count=4,
                frame_start=1,
                frame_end=3,
                frame_step=2,
                max_frames=2,
                action_name=action.name,
                playback_fps=20.0,
                loop_policy=loop_policy,
            )
            result = render_runner.run(request)
            manifest = _load_json(result.manifest_path)
            if (
                manifest.get("sourceSha256") != _sha256(fixture)
                or manifest.get("actionName") != action.name
                or (manifest.get("timing") or {}).get("loopPolicy") != loop_policy
            ):
                raise ForgeError("Two-Action render manifest does not match its request.")
            renders.append(
                {
                    "actionName": action.name,
                    "loopPolicy": loop_policy,
                    "directory": output.relative_to(workspace).as_posix(),
                    "manifest": result.manifest_path.relative_to(workspace).as_posix(),
                    "manifestSha256": _sha256(result.manifest_path),
                    "contactSheet": result.contact_sheet_path.relative_to(workspace).as_posix(),
                    "contactSheetSha256": _sha256(result.contact_sheet_path),
                }
            )
        if renders[0]["contactSheetSha256"] == renders[1]["contactSheetSha256"]:
            raise ForgeError("Two-Action contact sheets are unexpectedly identical.")
        if any(_sha256(path) != expected for path, expected in (
            (primary, fixture_report["primarySourceSha256"]),
            (secondary, fixture_report["secondarySourceSha256"]),
            (fixture, fixture_report["fixtureSha256"]),
        )):
            raise ForgeError("Two-Action source or fixture changed during prepare.")

        prepared_artifacts = _collect_prepared_artifacts(workspace, fixture, renders)
        state = {
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "two_action_physical_qa",
            "status": "awaiting_visual_review",
            "primarySource": str(primary),
            "primarySourceSha256": _sha256(primary),
            "secondarySource": str(secondary),
            "secondarySourceSha256": _sha256(secondary),
            "fixture": fixture.relative_to(workspace).as_posix(),
            "fixtureSha256": _sha256(fixture),
            "fixtureReport": fixture_report,
            "blender": str(blender),
            "unity": str(unity),
            "actions": [asdict(item) for item in actions],
            "renders": renders,
            "preparedArtifacts": prepared_artifacts,
        }
        _write_new_json(workspace / QA_MANIFEST_NAME, state)
        owner_marker.unlink()
    except Exception:
        if owner_marker.is_file() and owner_marker.read_text(encoding="ascii") == owner_token:
            shutil.rmtree(workspace)
        raise
    return {
        "status": "awaiting_visual_review",
        "workspace": str(workspace),
        "contactSheets": [str(workspace / item["contactSheet"]) for item in renders],
        "nextCommand": (
            f'python Tools/Invoke-TwoActionPhysicalQA.py finalize '
            f'--workspace "{workspace}" --blender "{blender}" '
            f'--unity "{unity}" --reviewer "<name>" '
            "--confirm-contact-sheets-approved"
        ),
    }


def finalize_qa(args: argparse.Namespace) -> dict:
    if not getattr(args, "confirm_contact_sheets_approved", False):
        raise ForgeError("Explicit contact-sheet approval is required.")
    workspace = args.workspace.expanduser().resolve()
    blender = args.blender.expanduser().resolve()
    unity = UnityRunner.validate_executable(args.unity)
    state_path = workspace / QA_MANIFEST_NAME
    state = _load_json(state_path)
    if (
        state.get("schemaVersion") != "1.0"
        or state.get("application") != "Sprite Station Studio"
        or state.get("kind") != "two_action_physical_qa"
        or state.get("status") not in {"awaiting_visual_review", "passed"}
    ):
        raise ForgeError("Two-Action QA state contract is unsupported.")
    if str(blender) != state.get("blender") or str(unity) != state.get("unity"):
        raise ForgeError("Two-Action QA tools changed after prepare.")
    reviewer = args.reviewer.strip()
    if not reviewer or len(reviewer) > 128:
        raise ForgeError("Two-Action QA reviewer name is invalid.")

    final_dir = workspace / "final"
    if state["status"] == "passed":
        result = _audit_completed_state(state_path, state, final_dir)
        return _final_summary(workspace, result)

    validated = _validate_prepared_state(workspace, state)
    prepared_state_sha256 = _sha256(state_path)
    if final_dir.exists():
        result_path = _resolve_workspace_file(
            workspace,
            f"final/{FINAL_RESULT_NAME}",
            "recoverable final result",
        )
        if result_path != (final_dir / FINAL_RESULT_NAME).resolve():
            raise ForgeError("Two-Action recoverable final path is invalid.")
        result = _audit_final_result(
            result_path,
            expected_prepared_state_sha256=prepared_state_sha256,
        )
        _publish_completed_state(
            state_path,
            state,
            final_dir,
            prepared_state_sha256,
        )
        return _final_summary(workspace, result)

    staging = workspace / f".final.staging-{uuid4().hex}"
    bridge_before = _snapshot_tree(ROOT / "unity_bridge_project")
    try:
        staging.mkdir(parents=False, exist_ok=False)
        shutil.copy2(state_path, staging / PREPARED_STATE_NAME)
        if _sha256(staging / PREPARED_STATE_NAME) != prepared_state_sha256:
            raise ForgeError("Two-Action prepared state snapshot hash mismatch.")
        _copy_prepared_snapshot(
            workspace,
            staging,
            state["preparedArtifacts"],
        )
        snapshot_fixture = staging / FIXTURE_RELATIVE
        mechanical_reviews: list[dict] = []
        for render in validated["renders"]:
            manifest = staging / render["manifest"]
            animation_review = record_animation_review(
                manifest,
                snapshot_fixture,
                "approved",
            )
            mechanical_reviews.append(
                {
                    "actionName": render["actionName"],
                    "loopPolicy": render["loopPolicy"],
                    "manifest": render["manifest"],
                    "manifestSha256": _sha256(manifest),
                    "contactSheet": render["contactSheet"],
                    "contactSheetSha256": _sha256(staging / render["contactSheet"]),
                    "animationReview": animation_review.path.relative_to(staging).as_posix(),
                    "animationReviewSha256": _sha256(animation_review.path),
                }
            )

        review = {
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "kind": "two_action_visual_review",
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "decision": "approved",
            "reviewer": reviewer,
            "preparedStateSha256": prepared_state_sha256,
            "actions": mechanical_reviews,
        }
        review_path = staging / REVIEW_NAME
        _write_new_json(review_path, review)

        action_clip_keys: set[str] = set()
        bundles = []
        bridge = UnityAnimationClipBridge(UnityRunner())
        for index, render in enumerate(validated["renders"], start=1):
            render_copy = staging / render["directory"]
            animation_review_path = render_copy / "animation_review.json"
            package = publish_approved_animation(
                animation_review_path,
                staging / f"approved-{index}",
            )
            package_audit = audit_approved_animation_package(package.manifest_path)
            if package_audit.artifact_count != 17:
                raise ForgeError("Two-Action approved package artifact count is invalid.")
            descriptor = _load_json(
                package.output_dir / "unity_animation_clip_descriptor.json"
            )
            clips = descriptor.get("clips")
            if (
                descriptor.get("actionName") != render["actionName"]
                or not isinstance(clips, list)
                or len(clips) != 4
                or any(
                    clip.get("loopTime") != (render["loopPolicy"] == "loop")
                    for clip in clips
                )
            ):
                raise ForgeError("Two-Action descriptor contract is invalid.")
            for clip in clips:
                name = clip.get("name")
                if not isinstance(name, str) or len(name) > 128:
                    raise ForgeError("Two-Action clip name is invalid.")
                key = name.casefold()
                if key in action_clip_keys:
                    raise ForgeError("Two-Action Unity clip identities collided.")
                action_clip_keys.add(key)

            bundle = bridge.run(
                unity,
                package.manifest_path,
                staging / f"unity-bundle-{index}",
                timeout=args.timeout,
            )
            bundle_audit = audit_unity_animation_clip_bundle(bundle.manifest_path)
            if (
                bundle_audit.clip_count != 4
                or bundle_audit.sprite_sheet_count != 4
                or bundle_audit.keyframe_count != 8
                or bundle_audit.artifact_count != 35
                or not bundle_audit.portable_reload_verified
            ):
                raise ForgeError("Two-Action Unity bundle contract is invalid.")
            bundles.append(
                {
                    "actionName": render["actionName"],
                    "loopPolicy": render["loopPolicy"],
                    "approvedPackage": f"approved-{index}",
                    "approvedPackageManifest": (
                        f"approved-{index}/{APPROVED_PACKAGE_NAME}"
                    ),
                    "approvedPackageManifestSha256": _sha256(package.manifest_path),
                    "approvedArtifactCount": package_audit.artifact_count,
                    "unityBundle": f"unity-bundle-{index}",
                    "unityBundleManifest": (
                        f"unity-bundle-{index}/{BUNDLE_MANIFEST_NAME}"
                    ),
                    "unityBundleManifestSha256": _sha256(bundle.manifest_path),
                    "bundleArtifactCount": bundle_audit.artifact_count,
                    "clipCount": bundle_audit.clip_count,
                    "spriteSheetCount": bundle_audit.sprite_sheet_count,
                    "keyframeCount": bundle_audit.keyframe_count,
                    "portableReloadVerified": bundle_audit.portable_reload_verified,
                }
            )
        if len(action_clip_keys) != 8:
            raise ForgeError("Two-Action QA did not produce eight distinct clips.")
        if _snapshot_tree(ROOT / "unity_bridge_project") != bridge_before:
            raise ForgeError("Repository Unity bridge changed during Two-Action QA.")
        _verify_prepared_artifacts(workspace, state.get("preparedArtifacts"))
        if any(
            _sha256(path) != state[key]
            for path, key in (
                (validated["primary"], "primarySourceSha256"),
                (validated["secondary"], "secondarySourceSha256"),
                (validated["fixture"], "fixtureSha256"),
            )
        ):
            raise ForgeError("Two-Action QA input changed during finalize.")

        final_artifacts = _collect_tree_artifacts(staging)
        final_result = {
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "kind": "two_action_physical_qa_result",
            "status": "passed",
            "preparedStateSha256": prepared_state_sha256,
            "visualReview": REVIEW_NAME,
            "visualReviewSha256": _sha256(review_path),
            "bundles": bundles,
            "clipCount": 8,
            "spriteSheetCount": 8,
            "keyframeCount": 16,
            "bundleArtifactCount": 70,
            "distinctClipNames": True,
            "sourceUnchanged": True,
            "fixtureUnchanged": True,
            "artifactCount": len(final_artifacts),
            "artifacts": final_artifacts,
        }
        _write_new_json(staging / FINAL_RESULT_NAME, final_result)
        _audit_final_result(
            staging / FINAL_RESULT_NAME,
            expected_prepared_state_sha256=prepared_state_sha256,
        )
        os.rename(staging, final_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    result = _audit_final_result(
        final_dir / FINAL_RESULT_NAME,
        expected_prepared_state_sha256=prepared_state_sha256,
    )
    _publish_completed_state(
        state_path,
        state,
        final_dir,
        prepared_state_sha256,
    )
    return _final_summary(workspace, result)


def _match_actions(
    discovered: tuple[AnimationActionInfo, ...],
) -> tuple[AnimationActionInfo, ...]:
    if len(discovered) != 2:
        raise ForgeError("Two-Action fixture discovery must return exactly two Actions.")
    matched = []
    for suffix in EXPECTED_ACTION_SUFFIXES:
        matches = [item for item in discovered if item.name.endswith(suffix)]
        if len(matches) != 1:
            raise ForgeError(f"Two-Action fixture lacks one unique {suffix} Action.")
        matched.append(matches[0])
    if len({item.name.casefold() for item in matched}) != 2:
        raise ForgeError("Two-Action fixture Action names collide.")
    return tuple(matched)


def _validate_prepared_state(workspace: Path, state: dict) -> dict:
    if state.get("fixture") != FIXTURE_RELATIVE:
        raise ForgeError("Two-Action fixture path is unsafe or noncanonical.")
    fixture = _resolve_workspace_file(workspace, state.get("fixture"), "fixture")
    artifacts = state.get("preparedArtifacts")
    _verify_prepared_artifacts(workspace, artifacts)
    artifact_hashes = {
        item["path"].casefold(): item["sha256"]
        for item in artifacts
        if isinstance(item, dict)
    }
    if artifact_hashes.get(FIXTURE_RELATIVE.casefold()) != state.get("fixtureSha256"):
        raise ForgeError("Two-Action fixture is not bound to prepared artifacts.")
    allowed_roots = {"fixture", *(item["directory"] for item in RENDER_LAYOUT)}
    if any(Path(item["path"]).parts[0] not in allowed_roots for item in artifacts):
        raise ForgeError("Two-Action prepared artifact scope is unsupported.")

    state_renders = state.get("renders")
    if not isinstance(state_renders, list) or len(state_renders) != len(RENDER_LAYOUT):
        raise ForgeError("Two-Action render state is invalid.")
    validated_renders = []
    for render, layout in zip(state_renders, RENDER_LAYOUT):
        if not isinstance(render, dict) or any(
            render.get(key) != layout[key]
            for key in ("directory", "manifest", "contactSheet", "loopPolicy")
        ):
            raise ForgeError("Two-Action render paths are unsafe or noncanonical.")
        action_name = render.get("actionName")
        if not isinstance(action_name, str) or not action_name.endswith(layout["actionSuffix"]):
            raise ForgeError("Two-Action render Action binding is invalid.")
        directory = _resolve_workspace_directory(
            workspace,
            render["directory"],
            "render directory",
        )
        manifest = _resolve_workspace_file(
            workspace,
            render["manifest"],
            "render manifest",
        )
        contact = _resolve_workspace_file(
            workspace,
            render["contactSheet"],
            "render contact sheet",
        )
        if manifest.parent != directory or contact.parent != directory:
            raise ForgeError("Two-Action render files escape their canonical directory.")
        for path, expected in (
            (manifest, render.get("manifestSha256")),
            (contact, render.get("contactSheetSha256")),
        ):
            relative = path.relative_to(workspace).as_posix()
            if artifact_hashes.get(relative.casefold()) != expected or _sha256(path) != expected:
                raise ForgeError("Two-Action render is not bound to prepared artifacts.")
        validated_renders.append(dict(render))

    fixture_report = state.get("fixtureReport")
    report_actions = (
        fixture_report.get("actions") if isinstance(fixture_report, dict) else None
    )
    if (
        not isinstance(fixture_report, dict)
        or fixture_report.get("schemaVersion") != "1.0"
        or fixture_report.get("application") != "Sprite Station Studio"
        or fixture_report.get("primarySourceSha256")
        != state.get("primarySourceSha256")
        or fixture_report.get("secondarySourceSha256")
        != state.get("secondarySourceSha256")
        or fixture_report.get("fixtureSha256") != state.get("fixtureSha256")
        or fixture_report.get("fixture") != str(fixture)
        or fixture_report.get("boneCount") != 24
        or fixture_report.get("skeletonsMatch") is not True
        or not _is_sha256(fixture_report.get("skeletonSignatureSha256"))
        or fixture_report.get("restMatrixDecimals") != 6
        or not isinstance(report_actions, list)
        or len(report_actions) != 2
    ):
        raise ForgeError("Two-Action fixture report binding is invalid.")
    expected_report_actions = {
        EXPECTED_ACTION_SUFFIXES[0]: ([1.0, 20.0], True),
        EXPECTED_ACTION_SUFFIXES[1]: ([1.0, 32.0], False),
    }
    actual_report_actions = {
        item.get("name"): (item.get("frameRange"), item.get("active"))
        for item in report_actions
        if isinstance(item, dict)
    }
    if actual_report_actions != expected_report_actions:
        raise ForgeError("Two-Action fixture report Actions are invalid.")

    discovered_actions = state.get("actions")
    if not isinstance(discovered_actions, list) or len(discovered_actions) != 2:
        raise ForgeError("Two-Action discovered Action evidence is invalid.")
    for index, (action, render, frame_end) in enumerate(
        zip(discovered_actions, validated_renders, (20.0, 32.0))
    ):
        frame_start_value = action.get("frame_start") if isinstance(action, dict) else None
        frame_end_value = action.get("frame_end") if isinstance(action, dict) else None
        if (
            not isinstance(action, dict)
            or action.get("name") != render["actionName"]
            or isinstance(frame_start_value, bool)
            or not isinstance(frame_start_value, (int, float))
            or float(frame_start_value) != 1.0
            or isinstance(frame_end_value, bool)
            or not isinstance(frame_end_value, (int, float))
            or float(frame_end_value) != frame_end
            or action.get("active") is not (index == 0)
        ):
            raise ForgeError("Two-Action discovered Action binding is invalid.")

    primary = _validate_external_file(
        state.get("primarySource"),
        state.get("primarySourceSha256"),
        "primary source",
    )
    secondary = _validate_external_file(
        state.get("secondarySource"),
        state.get("secondarySourceSha256"),
        "secondary source",
    )
    if primary == secondary:
        raise ForgeError("Two-Action source bindings collide.")
    return {
        "primary": primary,
        "secondary": secondary,
        "fixture": fixture,
        "renders": tuple(validated_renders),
    }


def _copy_prepared_snapshot(
    workspace: Path,
    staging: Path,
    artifacts: list[dict],
) -> None:
    for item in artifacts:
        source = _resolve_workspace_file(workspace, item["path"], "prepared artifact")
        target = staging / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    expected = {
        item["path"].casefold(): item["sha256"]
        for item in artifacts
    }
    actual = {
        path.relative_to(staging).as_posix().casefold(): _sha256(path)
        for path in staging.rglob("*")
        if path.is_file() and path.name != PREPARED_STATE_NAME
    }
    if actual != expected:
        raise ForgeError("Two-Action copied snapshot does not match prepared artifacts.")


def _collect_tree_artifacts(root: Path) -> list[dict]:
    result_path = root / FINAL_RESULT_NAME
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }
        for path in sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and path != result_path
            ),
            key=lambda item: item.relative_to(root).as_posix().casefold(),
        )
    ]


def _audit_final_result(
    result_path: Path,
    *,
    expected_prepared_state_sha256: str,
) -> dict:
    result = _load_json(result_path)
    root = result_path.parent.resolve()
    if (
        result.get("schemaVersion") != "1.1"
        or result.get("application") != "Sprite Station Studio"
        or result.get("kind") != "two_action_physical_qa_result"
        or result.get("status") != "passed"
        or result.get("preparedStateSha256") != expected_prepared_state_sha256
        or result.get("clipCount") != 8
        or result.get("spriteSheetCount") != 8
        or result.get("keyframeCount") != 16
        or result.get("bundleArtifactCount") != 70
        or result.get("distinctClipNames") is not True
        or result.get("sourceUnchanged") is not True
        or result.get("fixtureUnchanged") is not True
    ):
        raise ForgeError("Two-Action final result identity is invalid.")
    prepared_state = _resolve_workspace_file(
        root,
        PREPARED_STATE_NAME,
        "prepared state snapshot",
    )
    if _sha256(prepared_state) != expected_prepared_state_sha256:
        raise ForgeError("Two-Action prepared state snapshot is invalid.")
    prepared_payload = _load_json(prepared_state)
    if (
        prepared_payload.get("schemaVersion") != "1.0"
        or prepared_payload.get("application") != "Sprite Station Studio"
        or prepared_payload.get("kind") != "two_action_physical_qa"
        or prepared_payload.get("status") != "awaiting_visual_review"
        or not _is_sha256(prepared_payload.get("fixtureSha256"))
    ):
        raise ForgeError("Two-Action prepared state snapshot contract is invalid.")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or result.get("artifactCount") != len(artifacts):
        raise ForgeError("Two-Action final artifact list is invalid.")
    expected: dict[str, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ForgeError("Two-Action final artifact is invalid.")
        path = _resolve_workspace_file(root, item.get("path"), "final artifact")
        relative = path.relative_to(root).as_posix()
        key = relative.casefold()
        if key in expected or item.get("size") != path.stat().st_size:
            raise ForgeError("Two-Action final artifacts collide or have invalid size.")
        if _sha256(path) != item.get("sha256"):
            raise ForgeError("Two-Action final artifact hash mismatch.")
        expected[key] = item["sha256"]
    actual = {
        path.relative_to(root).as_posix().casefold()
        for path in root.rglob("*")
        if path.is_file() and path != result_path
    }
    if set(expected) != actual:
        raise ForgeError("Two-Action final artifact set is incomplete or unexpected.")
    sorted_paths = sorted(expected, key=str.casefold)
    if [item.get("path", "").casefold() for item in artifacts] != sorted_paths:
        raise ForgeError("Two-Action final artifact list order is invalid.")
    bundles = result.get("bundles")
    if not isinstance(bundles, list) or len(bundles) != 2:
        raise ForgeError("Two-Action final bundle list is invalid.")
    action_names: set[str] = set()
    clip_names: set[str] = set()
    for index, (bundle, policy, suffix) in enumerate(
        zip(bundles, ("loop", "once"), EXPECTED_ACTION_SUFFIXES),
        start=1,
    ):
        if (
            not isinstance(bundle, dict)
            or bundle.get("loopPolicy") != policy
            or bundle.get("approvedPackage") != f"approved-{index}"
            or bundle.get("unityBundle") != f"unity-bundle-{index}"
            or bundle.get("approvedArtifactCount") != 17
            or bundle.get("bundleArtifactCount") != 35
            or bundle.get("clipCount") != 4
            or bundle.get("spriteSheetCount") != 4
            or bundle.get("keyframeCount") != 8
            or bundle.get("portableReloadVerified") is not True
        ):
            raise ForgeError("Two-Action final bundle summary is invalid.")
        action_name = bundle.get("actionName")
        if (
            not isinstance(action_name, str)
            or not action_name.endswith(suffix)
            or action_name.casefold() in action_names
        ):
            raise ForgeError("Two-Action final Action identities collide.")
        action_names.add(action_name.casefold())
        package_manifest = _resolve_workspace_file(
            root,
            bundle.get("approvedPackageManifest"),
            "approved package manifest",
        )
        unity_manifest = _resolve_workspace_file(
            root,
            bundle.get("unityBundleManifest"),
            "Unity bundle manifest",
        )
        if (
            package_manifest
            != (root / f"approved-{index}" / APPROVED_PACKAGE_NAME).resolve()
            or unity_manifest
            != (root / f"unity-bundle-{index}" / BUNDLE_MANIFEST_NAME).resolve()
            or _sha256(package_manifest) != bundle.get("approvedPackageManifestSha256")
            or _sha256(unity_manifest) != bundle.get("unityBundleManifestSha256")
        ):
            raise ForgeError("Two-Action final manifest binding is invalid.")
        package_audit = audit_approved_animation_package(package_manifest)
        bundle_audit = audit_unity_animation_clip_bundle(unity_manifest)
        if package_audit.artifact_count != 17 or (
            bundle_audit.artifact_count,
            bundle_audit.clip_count,
            bundle_audit.sprite_sheet_count,
            bundle_audit.keyframe_count,
            bundle_audit.portable_reload_verified,
        ) != (35, 4, 4, 8, True):
            raise ForgeError("Two-Action final nested audit failed.")
        descriptor = _load_json(
            package_manifest.parent / "unity_animation_clip_descriptor.json"
        )
        if descriptor.get("actionName") != action_name:
            raise ForgeError("Two-Action final descriptor Action is invalid.")
        clips = descriptor.get("clips")
        if not isinstance(clips, list) or len(clips) != 4:
            raise ForgeError("Two-Action final descriptor clips are invalid.")
        for clip in clips:
            name = clip.get("name") if isinstance(clip, dict) else None
            key = name.casefold() if isinstance(name, str) else ""
            if (
                not name
                or len(name) > 128
                or key in clip_names
                or clip.get("loopTime") != (policy == "loop")
            ):
                raise ForgeError("Two-Action final clip identities are invalid.")
            clip_names.add(key)
    if len(clip_names) != 8:
        raise ForgeError("Two-Action final does not contain eight distinct clips.")
    review = _resolve_workspace_file(root, result.get("visualReview"), "visual review")
    if review.parent != root or _sha256(review) != result.get("visualReviewSha256"):
        raise ForgeError("Two-Action final visual review binding is invalid.")
    review_payload = _load_json(review)
    review_actions = review_payload.get("actions")
    if (
        review_payload.get("schemaVersion") != "1.1"
        or review_payload.get("application") != "Sprite Station Studio"
        or review_payload.get("kind") != "two_action_visual_review"
        or review_payload.get("decision") != "approved"
        or review_payload.get("preparedStateSha256")
        != expected_prepared_state_sha256
        or not isinstance(review_payload.get("reviewer"), str)
        or not review_payload["reviewer"].strip()
        or not isinstance(review_actions, list)
        or len(review_actions) != 2
    ):
        raise ForgeError("Two-Action final visual review contract is invalid.")
    for index, (review_action, bundle, layout) in enumerate(
        zip(review_actions, bundles, RENDER_LAYOUT),
        start=1,
    ):
        mechanical_path = f"{layout['directory']}/animation_review.json"
        if (
            not isinstance(review_action, dict)
            or review_action.get("actionName") != bundle["actionName"]
            or review_action.get("loopPolicy") != bundle["loopPolicy"]
            or review_action.get("manifest") != layout["manifest"]
            or review_action.get("contactSheet") != layout["contactSheet"]
            or review_action.get("animationReview") != mechanical_path
        ):
            raise ForgeError("Two-Action final visual review Action is invalid.")
        for field, hash_field in (
            ("manifest", "manifestSha256"),
            ("contactSheet", "contactSheetSha256"),
            ("animationReview", "animationReviewSha256"),
        ):
            path = _resolve_workspace_file(root, review_action[field], field)
            if _sha256(path) != review_action.get(hash_field):
                raise ForgeError("Two-Action final visual review hash is invalid.")

        package_root = root / f"approved-{index}"
        bundle_root = root / f"unity-bundle-{index}"
        source_package_root = bundle_root / "SourcePackage"
        package_manifest = package_root / APPROVED_PACKAGE_NAME
        bundled_package_manifest = source_package_root / APPROVED_PACKAGE_NAME
        unity_manifest = bundle_root / BUNDLE_MANIFEST_NAME
        build_report = bundle_root / BUILD_REPORT_NAME
        package_payload = _load_json(package_manifest)
        bundled_package_payload = _load_json(bundled_package_manifest)
        unity_payload = _load_json(unity_manifest)
        build_payload = _load_json(build_report)
        package_artifacts = _artifact_hash_map(
            package_payload,
            "approved package",
        )
        bundled_package_artifacts = _artifact_hash_map(
            bundled_package_payload,
            "bundled approved package",
        )
        unity_artifacts = _artifact_hash_map(unity_payload, "Unity bundle")

        render_manifest = root / review_action["manifest"]
        render_contact = root / review_action["contactSheet"]
        render_review = root / review_action["animationReview"]
        approved_manifest = package_root / "animation_manifest.json"
        approved_contact = package_root / "animation_contact_sheet.png"
        approved_review = package_root / "animation_review.json"
        approved_descriptor = package_root / "unity_animation_clip_descriptor.json"
        bundled_manifest = source_package_root / "animation_manifest.json"
        bundled_contact = source_package_root / "animation_contact_sheet.png"
        bundled_review = source_package_root / "animation_review.json"
        bundled_descriptor = (
            source_package_root / "unity_animation_clip_descriptor.json"
        )
        mechanical_payload = _load_json(render_review)
        approved_review_payload = _load_json(approved_review)
        bundled_review_payload = _load_json(bundled_review)
        manifest_payload = _load_json(render_manifest)
        bundled_manifest_payload = _load_json(bundled_manifest)
        bundled_descriptor_payload = _load_json(bundled_descriptor)

        manifest_sha = review_action["manifestSha256"]
        contact_sha = review_action["contactSheetSha256"]
        review_sha = review_action["animationReviewSha256"]
        package_sha = bundle["approvedPackageManifestSha256"]
        if not _all_equal(
            manifest_sha,
            _sha256(render_manifest),
            mechanical_payload.get("animationManifestSha256"),
            package_artifacts.get("animation_manifest.json"),
            _sha256(approved_manifest),
            unity_artifacts.get("SourcePackage/animation_manifest.json"),
            _sha256(bundled_manifest),
        ):
            raise ForgeError("Two-Action reviewed manifest chain is invalid.")
        if not _all_equal(
            contact_sha,
            _sha256(render_contact),
            package_artifacts.get("animation_contact_sheet.png"),
            _sha256(approved_contact),
            unity_artifacts.get("SourcePackage/animation_contact_sheet.png"),
            _sha256(bundled_contact),
        ):
            raise ForgeError("Two-Action reviewed contact-sheet chain is invalid.")
        if not _all_equal(
            review_sha,
            _sha256(render_review),
            package_payload.get("reviewSha256"),
            package_artifacts.get("animation_review.json"),
            _sha256(approved_review),
            unity_artifacts.get("SourcePackage/animation_review.json"),
            _sha256(bundled_review),
        ):
            raise ForgeError("Two-Action mechanical review chain is invalid.")
        if not _all_equal(
            package_sha,
            _sha256(package_manifest),
            _sha256(bundled_package_manifest),
            unity_payload.get("sourceApprovedPackageSha256"),
            unity_artifacts.get(
                f"SourcePackage/{APPROVED_PACKAGE_NAME}"
            ),
            build_payload.get("sourcePackageSha256"),
        ):
            raise ForgeError("Two-Action approved package chain is invalid.")
        if package_artifacts != bundled_package_artifacts:
            raise ForgeError("Two-Action bundled package artifacts differ.")
        if package_payload != bundled_package_payload:
            raise ForgeError("Two-Action bundled package manifest differs.")
        if _sha256(approved_descriptor) != _sha256(bundled_descriptor):
            raise ForgeError("Two-Action bundled descriptor differs.")

        fixture_sha = prepared_payload["fixtureSha256"]
        if any(
            payload.get("sourceSha256") != fixture_sha
            for payload in (
                mechanical_payload,
                approved_review_payload,
                bundled_review_payload,
                manifest_payload,
                bundled_manifest_payload,
            )
        ):
            raise ForgeError("Two-Action fixture source chain is invalid.")
        if any(
            payload.get("schemaVersion") != "1.0"
            or payload.get("application") != "Sprite Station Studio"
            or payload.get("kind") != "animation_review_decision"
            or payload.get("decision") != "approved"
            or payload.get("animationManifest") != "animation_manifest.json"
            for payload in (
                mechanical_payload,
                approved_review_payload,
                bundled_review_payload,
            )
        ):
            raise ForgeError("Two-Action mechanical review contract is invalid.")
        action_name = bundle["actionName"]
        policy = bundle["loopPolicy"]
        standalone_descriptor_payload = _load_json(approved_descriptor)
        if any(
            payload.get("actionName") != action_name
            for payload in (
                manifest_payload,
                bundled_manifest_payload,
                standalone_descriptor_payload,
                bundled_descriptor_payload,
            )
        ) or any(
            (payload.get("timing") or {}).get("loopPolicy") != policy
            for payload in (manifest_payload, bundled_manifest_payload)
        ):
            raise ForgeError("Two-Action Action or loop-policy chain is invalid.")
        for descriptor_payload in (
            standalone_descriptor_payload,
            bundled_descriptor_payload,
        ):
            if any(
                clip.get("loopTime") != (policy == "loop")
                for clip in descriptor_payload.get("clips", ())
                if isinstance(clip, dict)
            ):
                raise ForgeError("Two-Action descriptor loop chain is invalid.")
    return result


def _artifact_hash_map(payload: dict, label: str) -> dict[str, str]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ForgeError(f"Two-Action {label} artifact list is invalid.")
    result: dict[str, str] = {}
    for item in artifacts:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not _is_sha256(item.get("sha256"))
            or item["path"] in result
        ):
            raise ForgeError(f"Two-Action {label} artifact is invalid.")
        result[item["path"]] = item["sha256"]
    return result


def _all_equal(*values: object) -> bool:
    return bool(values) and all(value == values[0] for value in values[1:])


def _publish_completed_state(
    state_path: Path,
    state: dict,
    final_dir: Path,
    prepared_state_sha256: str,
) -> None:
    if _sha256(state_path) != prepared_state_sha256:
        raise ForgeError("Two-Action prepared state changed before completion update.")
    _audit_final_result(
        final_dir / FINAL_RESULT_NAME,
        expected_prepared_state_sha256=prepared_state_sha256,
    )
    completed = {
        **state,
        "status": "passed",
        "preparedStateSha256": prepared_state_sha256,
        "final": f"final/{FINAL_RESULT_NAME}",
        "finalSha256": _sha256(final_dir / FINAL_RESULT_NAME),
    }
    temporary = state_path.parent / f".{QA_MANIFEST_NAME}.updating-{uuid4().hex}"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(completed, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if _sha256(state_path) != prepared_state_sha256:
            raise ForgeError("Two-Action prepared state changed during completion update.")
        _audit_final_result(
            final_dir / FINAL_RESULT_NAME,
            expected_prepared_state_sha256=prepared_state_sha256,
        )
        os.replace(temporary, state_path)
    finally:
        temporary.unlink(missing_ok=True)


def _audit_completed_state(state_path: Path, state: dict, final_dir: Path) -> dict:
    prepared_state_sha256 = state.get("preparedStateSha256")
    if not _is_sha256(prepared_state_sha256):
        raise ForgeError("Two-Action completed state lacks its prepare identity.")
    result_path = _resolve_workspace_file(
        state_path.parent,
        state.get("final"),
        "completed final result",
    )
    if result_path != (final_dir / FINAL_RESULT_NAME).resolve():
        raise ForgeError("Two-Action completed final path is invalid.")
    if _sha256(result_path) != state.get("finalSha256"):
        raise ForgeError("Two-Action completed final hash is invalid.")
    result = _audit_final_result(
        result_path,
        expected_prepared_state_sha256=prepared_state_sha256,
    )
    prepared_state_path = final_dir / PREPARED_STATE_NAME
    prepared_state = _load_json(prepared_state_path)
    expected_state = {
        **prepared_state,
        "status": "passed",
        "preparedStateSha256": prepared_state_sha256,
        "final": f"final/{FINAL_RESULT_NAME}",
        "finalSha256": _sha256(result_path),
    }
    if state != expected_state:
        raise ForgeError("Two-Action completed state differs from prepared evidence.")
    return result


def _final_summary(workspace: Path, result: dict) -> dict:
    return {
        "status": "passed",
        "workspace": str(workspace),
        "actions": [item["actionName"] for item in result["bundles"]],
        "loopPolicies": [item["loopPolicy"] for item in result["bundles"]],
        "clipCount": result["clipCount"],
        "spriteSheetCount": result["spriteSheetCount"],
        "keyframeCount": result["keyframeCount"],
        "bundleArtifactCount": result["bundleArtifactCount"],
        "portableReloadVerified": all(
            item["portableReloadVerified"] for item in result["bundles"]
        ),
        "distinctClipNames": result["distinctClipNames"],
        "sourcesUnchanged": result["sourceUnchanged"],
    }


def _create_fixture(
    blender: Path,
    primary: Path,
    secondary: Path,
    output: Path,
    timeout: int,
) -> dict:
    worker = ROOT / "worker/create_two_action_fixture.py"
    completed = subprocess.run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(worker),
            "--",
            "--primary-source",
            str(primary),
            "--secondary-source",
            str(secondary),
            "--output",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise ForgeError(
            "Blender Two-Action fixture creation failed.\n"
            + "\n".join(completed.stdout.splitlines()[-40:])
        )
    payloads = [
        line[len(FIXTURE_RESULT_PREFIX) :]
        for line in completed.stdout.splitlines()
        if line.startswith(FIXTURE_RESULT_PREFIX)
    ]
    if len(payloads) != 1:
        raise ForgeError("Blender did not return one Two-Action fixture report.")
    try:
        payload = json.loads(payloads[0])
    except json.JSONDecodeError as exc:
        raise ForgeError("Blender Two-Action fixture report is malformed.") from exc
    report_actions = payload.get("actions") if isinstance(payload, dict) else None
    expected_report_actions = {
        EXPECTED_ACTION_SUFFIXES[0]: ([1.0, 20.0], True),
        EXPECTED_ACTION_SUFFIXES[1]: ([1.0, 32.0], False),
    }
    actual_report_actions = {
        item.get("name"): (item.get("frameRange"), item.get("active"))
        for item in report_actions or ()
        if isinstance(item, dict)
    }
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != "1.0"
        or payload.get("application") != "Sprite Station Studio"
        or payload.get("primarySourceSha256") != _sha256(primary)
        or payload.get("secondarySourceSha256") != _sha256(secondary)
        or payload.get("fixtureSha256") != _sha256(output)
        or payload.get("skeletonsMatch") is not True
        or payload.get("boneCount") != 24
        or not _is_sha256(payload.get("skeletonSignatureSha256"))
        or payload.get("restMatrixDecimals") != 6
        or payload.get("fixture") != str(output)
        or not isinstance(report_actions, list)
        or len(report_actions) != 2
        or actual_report_actions != expected_report_actions
    ):
        raise ForgeError("Blender Two-Action fixture report is invalid.")
    return payload


def _collect_prepared_artifacts(
    workspace: Path,
    fixture: Path,
    renders: list[dict],
) -> list[dict]:
    roots = [fixture]
    roots.extend(workspace / item["directory"] for item in renders)
    files: list[Path] = []
    for root in roots:
        files.extend(
            [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        )
    return [
        {"path": path.relative_to(workspace).as_posix(), "sha256": _sha256(path)}
        for path in sorted(files, key=lambda item: item.relative_to(workspace).as_posix().casefold())
    ]


def _verify_prepared_artifacts(workspace: Path, artifacts: object) -> None:
    if not isinstance(artifacts, list) or not artifacts:
        raise ForgeError("Two-Action prepared artifact list is invalid.")
    expected: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ForgeError("Two-Action prepared artifact is invalid.")
        relative = _canonical_relative(item.get("path"), "prepared artifact")
        path = _resolve_workspace_file(workspace, relative, "prepared artifact")
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ForgeError(f"Two-Action prepared artifact changed: {relative}")
        key = relative.casefold()
        if key in expected:
            raise ForgeError("Two-Action prepared artifact paths collide.")
        expected.add(key)
    scope_names = {Path(item["path"]).parts[0] for item in artifacts}
    actual = {
        path.relative_to(workspace).as_posix().casefold()
        for scope_name in scope_names
        for path in (workspace / scope_name).rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ForgeError("Two-Action prepared artifact set is incomplete or unexpected.")


def _canonical_relative(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ForgeError(f"Two-Action {label} path is unsafe.")
    relative = Path(value)
    if (
        relative.is_absolute()
        or value != relative.as_posix()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ForgeError(f"Two-Action {label} path is unsafe or noncanonical.")
    return value


def _resolve_workspace_file(workspace: Path, value: object, label: str) -> Path:
    relative = _canonical_relative(value, label)
    root = workspace.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ForgeError(f"Two-Action {label} path escapes its workspace.") from exc
    if not path.is_file():
        raise ForgeError(f"Two-Action {label} file is missing: {relative}")
    return path


def _resolve_workspace_directory(workspace: Path, value: object, label: str) -> Path:
    relative = _canonical_relative(value, label)
    root = workspace.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ForgeError(f"Two-Action {label} path escapes its workspace.") from exc
    if not path.is_dir():
        raise ForgeError(f"Two-Action {label} directory is missing: {relative}")
    return path


def _validate_external_file(value: object, expected_sha256: object, label: str) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ForgeError(f"Two-Action {label} binding is invalid.")
    path = Path(value).expanduser().resolve()
    if not path.is_file() or not _is_sha256(expected_sha256) or _sha256(path) != expected_sha256:
        raise ForgeError(f"Two-Action {label} changed after prepare.")
    return path


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in {"Library", "Logs", "Temp", "UserSettings"} for part in path.relative_to(root).parts)
    }


def _write_new_json(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read Two-Action QA JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ForgeError("Two-Action QA JSON must be an object.")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
