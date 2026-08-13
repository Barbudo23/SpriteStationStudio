from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.animation_action_discovery import AnimationActionInfo
from app.blender_runner import ForgeError
from app.engine_export import write_unity_import_preset
from app.unity_animation_clip_bridge import (
    UnityAnimationClipBridge as RealUnityAnimationClipBridge,
)
from app.unity_animation_clip_descriptor import (
    build_unity_animation_clip_descriptor,
)
from app.unity_runner import UnityBridgeError
from core.validation import encode_rgba_png
from tests.test_unity_animation_clip_bridge import FakeClipUnityRunner


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "Tools/Invoke-TwoActionPhysicalQA.py"
TOOL_SPEC = importlib.util.spec_from_file_location(
    "sss_two_action_physical_qa_tool",
    TOOL_PATH,
)
if TOOL_SPEC is None or TOOL_SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Cannot load Two-Action QA tool: {TOOL_PATH}")
TOOL = importlib.util.module_from_spec(TOOL_SPEC)
sys.modules[TOOL_SPEC.name] = TOOL
TOOL_SPEC.loader.exec_module(TOOL)


class TwoActionPhysicalQATests(unittest.TestCase):
    def test_matches_actions_by_exact_suffix_with_variable_fbx_prefixes(self) -> None:
        discovered = (
            AnimationActionInfo(
                "DifferentRig|AnimationLayer|SSS_QA_Run",
                1.0,
                32.0,
                False,
            ),
            AnimationActionInfo(
                "Armature|Armature|Armature|SSS QA Run",
                1.0,
                20.0,
                True,
            ),
        )

        matched = TOOL._match_actions(discovered)

        self.assertEqual(
            [item.name for item in matched],
            [
                "Armature|Armature|Armature|SSS QA Run",
                "DifferentRig|AnimationLayer|SSS_QA_Run",
            ],
        )
        self.assertEqual([item.frame_end for item in matched], [20.0, 32.0])
        self.assertEqual([item.active for item in matched], [True, False])

    def test_action_suffix_mapping_rejects_extra_missing_and_ambiguous_sets(self) -> None:
        cases = (
            (
                (
                    AnimationActionInfo("Rig|SSS QA Run", 1.0, 20.0, True),
                ),
                "exactly two",
            ),
            (
                (
                    AnimationActionInfo("Rig|SSS QA Run", 1.0, 20.0, True),
                    AnimationActionInfo("Rig|Idle", 1.0, 20.0, False),
                ),
                "unique SSS_QA_Run",
            ),
            (
                (
                    AnimationActionInfo("RigA|SSS QA Run", 1.0, 20.0, True),
                    AnimationActionInfo("RigB|SSS QA Run", 1.0, 20.0, False),
                ),
                "unique SSS QA Run",
            ),
            (
                (
                    AnimationActionInfo("Rig|SSS QA Run", 1.0, 20.0, True),
                    AnimationActionInfo("Rig|SSS_QA_Run", 1.0, 32.0, False),
                    AnimationActionInfo("Rig|Unexpected", 1.0, 10.0, False),
                ),
                "exactly two",
            ),
        )
        for discovered, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ForgeError, message):
                    TOOL._match_actions(discovered)

    def test_collects_and_verifies_the_exact_prepared_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, fixture, renders = self.make_prepared_workspace(Path(tmp))
            artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)

            self.assertEqual(
                [item["path"] for item in artifacts],
                sorted(
                    (
                        "fixture/sss_two_action_fixture.fbx",
                        "render-1-loop/animation_contact_sheet.png",
                        "render-1-loop/animation_frames/north_east/000.png",
                        "render-1-loop/animation_manifest.json",
                        "render-2-once/animation_contact_sheet.png",
                        "render-2-once/animation_frames/north_east/000.png",
                        "render-2-once/animation_manifest.json",
                    ),
                    key=str.casefold,
                ),
            )
            self.assertTrue(
                all(
                    item["sha256"] == self.sha(workspace / item["path"])
                    for item in artifacts
                )
            )
            TOOL._verify_prepared_artifacts(workspace, artifacts)

    def test_prepared_artifact_audit_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, fixture, renders = self.make_prepared_workspace(Path(tmp))
            artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)
            fixture.write_bytes(b"tampered fixture")

            with self.assertRaisesRegex(ForgeError, "prepared artifact changed"):
                TOOL._verify_prepared_artifacts(workspace, artifacts)

    def test_prepared_artifact_audit_rejects_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, fixture, renders = self.make_prepared_workspace(Path(tmp))
            artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)
            (workspace / "render-1-loop/unexpected.bin").write_bytes(b"unexpected")

            with self.assertRaisesRegex(ForgeError, "incomplete or unexpected"):
                TOOL._verify_prepared_artifacts(workspace, artifacts)

    def test_prepared_artifact_audit_rejects_traversal_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, fixture, renders = self.make_prepared_workspace(Path(tmp))
            artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)
            traversal = [
                *artifacts,
                {"path": "../outside.bin", "sha256": "0" * 64},
            ]
            duplicate = [*artifacts, dict(artifacts[0])]

            with self.assertRaisesRegex(ForgeError, "path is unsafe"):
                TOOL._verify_prepared_artifacts(workspace, traversal)
            with self.assertRaisesRegex(ForgeError, "paths collide"):
                TOOL._verify_prepared_artifacts(workspace, duplicate)

    def test_finalize_requires_explicit_visual_confirmation_before_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, _, _ = self.make_finalize_state(Path(tmp), confirmed=False)
            with (
                patch.object(
                    TOOL.UnityRunner,
                    "validate_executable",
                    return_value=args.unity.resolve(),
                ),
                patch.object(TOOL, "_verify_prepared_artifacts") as verify,
                patch.object(TOOL, "UnityAnimationClipBridge") as bridge,
            ):
                with self.assertRaisesRegex(ForgeError, "Explicit contact-sheet approval"):
                    TOOL.finalize_qa(args)

            verify.assert_not_called()
            bridge.assert_not_called()
            self.assertFalse((args.workspace / "final").exists())

    def test_prepare_failure_removes_only_its_owned_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary.fbx"
            secondary = root / "secondary.fbx"
            blender = root / "blender.exe"
            unity = root / "Unity.exe"
            for path, value in (
                (primary, b"primary"),
                (secondary, b"secondary"),
                (blender, b"blender"),
                (unity, b"unity"),
            ):
                path.write_bytes(value)
            workspace = root / "qa"
            args = argparse.Namespace(
                workspace=workspace,
                primary_source=primary,
                secondary_source=secondary,
                blender=blender,
                unity=unity,
                timeout=1,
            )

            with (
                patch.object(
                    TOOL.UnityRunner,
                    "validate_executable",
                    return_value=unity.resolve(),
                ),
                patch.object(
                    TOOL,
                    "_create_fixture",
                    side_effect=ForgeError("injected fixture failure"),
                ),
            ):
                with self.assertRaisesRegex(ForgeError, "injected fixture failure"):
                    TOOL.prepare_qa(args)
            self.assertFalse(workspace.exists())

            workspace.mkdir()
            sentinel = workspace / "user-file.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            with patch.object(
                TOOL.UnityRunner,
                "validate_executable",
                return_value=unity.resolve(),
            ):
                with self.assertRaisesRegex(ForgeError, "workspace already exists"):
                    TOOL.prepare_qa(args)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_finalize_failure_cleans_staging_and_leaves_no_partial_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, state_path, original_state = self.make_finalize_state(Path(tmp))
            with (
                patch.object(
                    TOOL.UnityRunner,
                    "validate_executable",
                    return_value=args.unity.resolve(),
                ),
                patch.object(TOOL, "_snapshot_tree", return_value={"bridge": "stable"}),
                patch.object(
                    TOOL,
                    "record_animation_review",
                    side_effect=ForgeError("injected approval failure"),
                ),
                patch.object(TOOL, "UnityAnimationClipBridge") as bridge,
            ):
                with self.assertRaisesRegex(ForgeError, "injected approval failure"):
                    TOOL.finalize_qa(args)

            bridge.assert_not_called()
            self.assertFalse((args.workspace / "final").exists())
            self.assertEqual(list(args.workspace.glob(".final.staging-*")), [])
            self.assertEqual(state_path.read_bytes(), original_state)
            self.assertFalse((args.workspace / TOOL.REVIEW_NAME).exists())

    def test_failed_atomic_final_publish_removes_all_staged_products(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, state_path, original_state = self.make_finalize_state(Path(tmp))
            with self.fake_finalize_dependencies(args.workspace):
                with patch.object(TOOL.os, "rename", side_effect=OSError("publish race")):
                    with self.assertRaisesRegex(OSError, "publish race"):
                        TOOL.finalize_qa(args)

            self.assertFalse((args.workspace / "final").exists())
            self.assertEqual(list(args.workspace.glob(".final.staging-*")), [])
            self.assertEqual(state_path.read_bytes(), original_state)
            self.assertFalse((args.workspace / TOOL.REVIEW_NAME).exists())

    def test_finalize_rejects_state_paths_not_bound_to_prepared_artifacts(self) -> None:
        cases = (
            "fixture",
            "render-directory",
            "render-manifest",
            "render-contact-sheet",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                args, state_path, _ = self.make_finalize_state(root)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if case == "fixture":
                    prepared_fixture = args.workspace / state["fixture"]
                    escaped = root / "escaped-fixture.fbx"
                    escaped.write_bytes(prepared_fixture.read_bytes())
                    state["fixture"] = "../escaped-fixture.fbx"
                    state["fixtureSha256"] = self.sha(escaped)
                elif case == "render-directory":
                    render = state["renders"][0]
                    prepared_render = args.workspace / render["directory"]
                    escaped = root / "escaped-render"
                    TOOL.shutil.copytree(prepared_render, escaped)
                    render["directory"] = "../escaped-render"
                elif case == "render-contact-sheet":
                    render = state["renders"][0]
                    prepared_contact = args.workspace / render["contactSheet"]
                    escaped = root / "escaped-contact-sheet.png"
                    escaped.write_bytes(prepared_contact.read_bytes())
                    render["contactSheet"] = "../escaped-contact-sheet.png"
                    render["contactSheetSha256"] = self.sha(escaped)
                else:
                    render = state["renders"][0]
                    prepared_manifest = args.workspace / render["manifest"]
                    escaped = root / "escaped-animation-manifest.json"
                    escaped.write_bytes(prepared_manifest.read_bytes())
                    render["manifest"] = "../escaped-animation-manifest.json"
                    render["manifestSha256"] = self.sha(escaped)
                state_path.write_text(json.dumps(state), encoding="utf-8")

                with self.fake_finalize_dependencies(args.workspace):
                    with self.assertRaisesRegex(
                        ForgeError,
                        "unsafe|prepared artifact|workspace",
                    ):
                        TOOL.finalize_qa(args)
                self.assertFalse((args.workspace / "final").exists())

    def test_copied_snapshot_is_rehashed_before_any_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, state_path, _ = self.make_finalize_state(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            marker = args.workspace / state["renders"][0]["directory"] / "animation_report.json"
            marker.write_text('{"status":"success"}\n', encoding="utf-8")
            state["preparedArtifacts"].append(
                {
                    "path": marker.relative_to(args.workspace).as_posix(),
                    "sha256": self.sha(marker),
                }
            )
            state_path.write_text(json.dumps(state), encoding="utf-8")
            real_copy2 = TOOL.shutil.copy2

            def corrupt_snapshot(source: Path, destination: Path, *args, **kwargs):
                copied = real_copy2(source, destination, *args, **kwargs)
                if Path(source).resolve() == marker.resolve():
                    Path(copied).write_text('{"status":"tampered"}\n', encoding="utf-8")
                return copied

            with (
                self.fake_finalize_dependencies(args.workspace) as dependencies,
                patch.object(TOOL.shutil, "copy2", side_effect=corrupt_snapshot),
            ):
                with self.assertRaisesRegex(
                    ForgeError,
                    "snapshot|copied render|prepared artifact changed",
                ):
                    TOOL.finalize_qa(args)
            dependencies.approval.assert_not_called()
            self.assertFalse((args.workspace / "final").exists())

    def test_final_evidence_hash_closes_every_file_and_both_manifest_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, _, _ = self.make_finalize_state(Path(tmp))
            with self.fake_finalize_dependencies(args.workspace):
                TOOL.finalize_qa(args)

            final_dir = args.workspace / "final"
            result_path = final_dir / TOOL.FINAL_RESULT_NAME
            evidence = json.loads(result_path.read_text(encoding="utf-8"))
            artifacts = evidence.get("artifacts")
            with self.subTest(contract="complete artifact inventory"):
                self.assertIsInstance(artifacts, list)
                if isinstance(artifacts, list):
                    expected = {
                        path.relative_to(final_dir).as_posix(): self.sha(path)
                        for path in final_dir.rglob("*")
                        if path.is_file() and path != result_path
                    }
                    actual = {
                        item.get("path"): item.get("sha256")
                        for item in artifacts
                        if isinstance(item, dict)
                    }
                    self.assertEqual(actual, expected)
                    self.assertEqual(evidence.get("artifactCount"), len(expected))

            for index, bundle in enumerate(evidence.get("bundles", ()), start=1):
                approved_manifest = (
                    final_dir
                    / bundle["approvedPackage"]
                    / "approved_animation_package.json"
                )
                unity_manifest = (
                    final_dir
                    / bundle["unityBundle"]
                    / "unity_animation_clip_bundle.json"
                )
                with self.subTest(bundle=index, contract="approved package manifest hash"):
                    self.assertEqual(
                        bundle.get("approvedPackageManifestSha256"),
                        self.sha(approved_manifest),
                    )
                with self.subTest(bundle=index, contract="Unity bundle manifest hash"):
                    self.assertEqual(
                        bundle.get("unityBundleManifestSha256"),
                        self.sha(unity_manifest),
                    )

    def test_finalize_recovers_state_idempotently_after_published_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, state_path, original_state = self.make_finalize_state(Path(tmp))
            with self.fake_finalize_dependencies(args.workspace):
                with patch.object(
                    TOOL.os,
                    "replace",
                    side_effect=OSError("interrupted state update"),
                ):
                    with self.assertRaisesRegex(OSError, "interrupted state update"):
                        TOOL.finalize_qa(args)

            self.assertTrue((args.workspace / "final" / TOOL.FINAL_RESULT_NAME).is_file())
            self.assertEqual(state_path.read_bytes(), original_state)

            with self.fake_finalize_dependencies(args.workspace) as recovery_bridge:
                try:
                    recovered = TOOL.finalize_qa(args)
                except ForgeError as exc:
                    self.fail(f"Published final was not recoverable: {exc}")

            self.assertEqual(recovered["status"], "passed")
            completed = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(completed["status"], "passed")
            self.assertEqual(completed["final"], f"final/{TOOL.FINAL_RESULT_NAME}")
            recovery_bridge.run.assert_not_called()
            published_snapshot = TOOL._snapshot_tree(args.workspace / "final")

            with self.fake_finalize_dependencies(args.workspace) as repeat_bridge:
                repeated = TOOL.finalize_qa(args)
            self.assertEqual(repeated, recovered)
            self.assertEqual(
                TOOL._snapshot_tree(args.workspace / "final"),
                published_snapshot,
            )
            repeat_bridge.run.assert_not_called()

    def test_direct_final_audit_rejects_broken_review_package_bundle_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, _ = self.make_realistic_final(root)
            baseline = args.workspace / "final"
            baseline_result = self.load_json(baseline / TOOL.FINAL_RESULT_NAME)
            prepared_sha = baseline_result["preparedStateSha256"]
            TOOL._audit_final_result(
                baseline / TOOL.FINAL_RESULT_NAME,
                expected_prepared_state_sha256=prepared_sha,
            )

            cases = (
                "visual-review-hash",
                "approved-manifest-mismatch",
                "approved-contact-mismatch",
                "approved-review-mismatch",
                "bundle-source-hash-field",
                "bundle-source-package-mismatch",
            )
            for case in cases:
                with self.subTest(case=case):
                    candidate = root / f"final-{case}"
                    shutil.copytree(baseline, candidate)
                    if case == "visual-review-hash":
                        review_path = candidate / TOOL.REVIEW_NAME
                        review = self.load_json(review_path)
                        review["actions"][0]["animationReviewSha256"] = "0" * 64
                        self.write_json(review_path, review)
                    elif case == "approved-manifest-mismatch":
                        self.mutate_standalone_package(candidate, "manifest")
                    elif case == "approved-contact-mismatch":
                        self.mutate_standalone_package(candidate, "contact")
                    elif case == "approved-review-mismatch":
                        self.mutate_standalone_package(candidate, "review")
                    elif case == "bundle-source-hash-field":
                        bundle_path = (
                            candidate
                            / "unity-bundle-1"
                            / "unity_animation_clip_bundle.json"
                        )
                        bundle = self.load_json(bundle_path)
                        bundle["sourceApprovedPackageSha256"] = "0" * 64
                        self.write_json(bundle_path, bundle)
                    else:
                        self.mutate_bundle_source_package(candidate)
                    self.refresh_final_evidence(candidate)

                    with self.assertRaises((ForgeError, UnityBridgeError)):
                        TOOL._audit_final_result(
                            candidate / TOOL.FINAL_RESULT_NAME,
                            expected_prepared_state_sha256=prepared_sha,
                        )

    def test_recovery_rejects_final_link_or_junction_outside_workspace_before_state_update(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, state_path = self.make_realistic_final(root)
            final_dir = args.workspace / "final"
            outside = root / "outside-final"
            final_dir.rename(outside)
            prepared_state = (outside / TOOL.PREPARED_STATE_NAME).read_bytes()
            state_path.write_bytes(prepared_state)
            original_state = state_path.read_bytes()
            link_kind = "symlink"
            try:
                os.symlink(outside, final_dir, target_is_directory=True)
            except OSError as symlink_error:  # pragma: no cover - host policy dependent
                if os.name != "nt":
                    self.skipTest(f"Directory symlinks are unavailable: {symlink_error}")
                junction = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(final_dir), str(outside)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        "Neither a directory symlink nor junction is available: "
                        f"{symlink_error}; {junction.stdout.strip()}"
                    )
                link_kind = "junction"

            try:
                with (
                    patch.object(
                        TOOL.UnityRunner,
                        "validate_executable",
                        return_value=args.unity.resolve(),
                    ),
                    patch.object(TOOL, "UnityAnimationClipBridge") as bridge,
                ):
                    with self.assertRaisesRegex(
                        ForgeError,
                        "symlink|junction|reparse|outside|canonical|escapes.*workspace",
                    ):
                        TOOL.finalize_qa(args)

                bridge.assert_not_called()
                self.assertEqual(state_path.read_bytes(), original_state)
            finally:
                if os.path.lexists(final_dir):
                    if link_kind == "junction":
                        os.rmdir(final_dir)
                    else:
                        final_dir.unlink()

    def test_passed_state_audits_final_without_live_sources_or_prepared_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args, state_path = self.make_realistic_final(Path(tmp))
            state = self.load_json(state_path)
            final_snapshot = TOOL._snapshot_tree(args.workspace / "final")
            Path(state["primarySource"]).unlink()
            Path(state["secondarySource"]).unlink()
            (args.workspace / state["fixture"]).unlink()
            for render in state["renders"]:
                shutil.rmtree(args.workspace / render["directory"])

            with (
                patch.object(
                    TOOL.UnityRunner,
                    "validate_executable",
                    return_value=args.unity.resolve(),
                ),
                patch.object(TOOL, "UnityAnimationClipBridge") as bridge,
            ):
                try:
                    result = TOOL.finalize_qa(args)
                except ForgeError as exc:
                    self.fail(f"Completed final still depends on live prepared inputs: {exc}")

            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                TOOL._snapshot_tree(args.workspace / "final"),
                final_snapshot,
            )
            bridge.assert_not_called()

    def test_completed_state_rejects_pointer_hash_and_core_field_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, state_path = self.make_realistic_final(root)
            original_bytes = state_path.read_bytes()
            original = json.loads(original_bytes)
            outside_result = root / "outside-result.json"
            outside_result.write_bytes(
                (args.workspace / "final" / TOOL.FINAL_RESULT_NAME).read_bytes()
            )
            cases = (
                ("pointer", lambda value: value.__setitem__("final", "../outside-result.json")),
                ("hash", lambda value: value.__setitem__("finalSha256", "0" * 64)),
                ("actions", lambda value: value.__setitem__("actions", [])),
                ("fixture-report", lambda value: value.__setitem__("fixtureReport", {})),
            )
            for case, mutate in cases:
                with self.subTest(case=case):
                    state = json.loads(json.dumps(original))
                    mutate(state)
                    self.write_json(state_path, state)
                    try:
                        with (
                            patch.object(
                                TOOL.UnityRunner,
                                "validate_executable",
                                return_value=args.unity.resolve(),
                            ),
                            patch.object(TOOL, "UnityAnimationClipBridge") as bridge,
                        ):
                            with self.assertRaises((ForgeError, UnityBridgeError)):
                                TOOL.finalize_qa(args)
                        bridge.assert_not_called()
                    finally:
                        state_path.write_bytes(original_bytes)

    def test_worker_requires_matching_skeletons_and_exports_every_action(self) -> None:
        worker_path = ROOT / "worker/create_two_action_fixture.py"
        source = worker_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        export_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fbx"
        ]
        self.assertEqual(len(export_calls), 1)
        keyword_nodes = {
            item.arg: item.value
            for item in export_calls[0].keywords
            if item.arg is not None
        }
        keywords = {
            name: ast.literal_eval(keyword_nodes[name])
            for name in (
                "use_selection",
                "bake_anim",
                "bake_anim_use_all_actions",
                "bake_anim_use_nla_strips",
                "bake_anim_step",
                "bake_anim_simplify_factor",
            )
        }

        self.assertIs(keywords["use_selection"], True)
        self.assertIs(keywords["bake_anim"], True)
        self.assertIs(keywords["bake_anim_use_all_actions"], True)
        self.assertIs(keywords["bake_anim_use_nla_strips"], False)
        self.assertEqual(keywords["bake_anim_step"], 1.0)
        self.assertEqual(keywords["bake_anim_simplify_factor"], 0.0)
        self.assertIn("primary_skeleton = skeleton_signature(primary_armature)", source)
        self.assertIn("secondary_skeleton = skeleton_signature(secondary_armature)", source)
        self.assertIn("secondary_hierarchy != primary_hierarchy", source)
        self.assertIn("secondary_rest_pose != primary_rest_pose", source)
        self.assertIn("bone.matrix_local", source)
        self.assertIn("primary_source_sha256 = sha256_file(primary)", source)
        self.assertIn("secondary_source_sha256 = sha256_file(secondary)", source)
        self.assertGreaterEqual(source.count("sha256_file(primary)"), 3)
        self.assertGreaterEqual(source.count("sha256_file(secondary)"), 3)
        self.assertIn("filepath=str(staging)", source)
        self.assertIn("os.link(staging, output)", source)
        self.assertNotIn("output.unlink", source)
        self.assertIn("must contain exactly one armature", source)
        self.assertIn("primary_animation.action = secondary_action", source)
        self.assertIn("primary_animation.action = primary_action", source)
        self.assertIn("bpy.data.objects.remove(obj, do_unlink=True)", source)

    def test_fixture_report_requires_both_sources_and_verified_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blender = root / "blender.exe"
            primary = root / "primary.fbx"
            secondary = root / "secondary.fbx"
            output = root / "fixture.fbx"
            for path, value in (
                (blender, b"blender"),
                (primary, b"primary"),
                (secondary, b"secondary"),
                (output, b"fixture"),
            ):
                path.write_bytes(value)
            payload = {
                "schemaVersion": "1.0",
                "application": "Sprite Station Studio",
                "primarySourceSha256": self.sha(primary),
                "secondarySourceSha256": self.sha(secondary),
                "fixtureSha256": self.sha(output),
                "fixture": str(output),
                "skeletonsMatch": True,
                "boneCount": 24,
                "skeletonSignatureSha256": "1" * 64,
                "restMatrixDecimals": 6,
                "actions": [
                    {
                        "name": "SSS QA Run",
                        "frameRange": [1.0, 20.0],
                        "active": True,
                    },
                    {
                        "name": "SSS_QA_Run",
                        "frameRange": [1.0, 32.0],
                        "active": False,
                    },
                ],
            }

            completed = subprocess.CompletedProcess(
                [],
                0,
                stdout=TOOL.FIXTURE_RESULT_PREFIX + json.dumps(payload) + "\n",
            )
            with patch.object(TOOL.subprocess, "run", return_value=completed) as run:
                report = TOOL._create_fixture(
                    blender,
                    primary,
                    secondary,
                    output,
                    10,
                )
            self.assertEqual(report["boneCount"], 24)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--primary-source") + 1], str(primary))
            self.assertEqual(command[command.index("--secondary-source") + 1], str(secondary))
            self.assertIn("--factory-startup", command)
            self.assertIn("--background", command)

            for key, invalid_value in (("skeletonsMatch", False), ("boneCount", 23)):
                invalid = {**payload, key: invalid_value}
                completed = subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=TOOL.FIXTURE_RESULT_PREFIX + json.dumps(invalid) + "\n",
                )
                with self.subTest(key=key), patch.object(
                    TOOL.subprocess,
                    "run",
                    return_value=completed,
                ):
                    with self.assertRaisesRegex(ForgeError, "fixture report is invalid"):
                        TOOL._create_fixture(
                            blender,
                            primary,
                            secondary,
                            output,
                            10,
                        )

    def make_prepared_workspace(
        self,
        root: Path,
    ) -> tuple[Path, Path, list[dict]]:
        workspace = (root / "workspace").resolve()
        fixture = workspace / "fixture/sss_two_action_fixture.fbx"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(b"two-action fixture")
        renders = []
        for index, loop_policy in enumerate(("loop", "once"), start=1):
            render = workspace / f"render-{index}-{loop_policy}"
            frame = render / "animation_frames/north_east/000.png"
            frame.parent.mkdir(parents=True)
            frame.write_bytes(f"frame-{index}".encode("ascii"))
            manifest = render / "animation_manifest.json"
            manifest.write_text(
                json.dumps({"index": index, "loopPolicy": loop_policy}),
                encoding="utf-8",
            )
            contact = render / "animation_contact_sheet.png"
            contact.write_bytes(f"contact-{index}".encode("ascii"))
            renders.append(
                {
                    "directory": render.relative_to(workspace).as_posix(),
                    "manifest": manifest.relative_to(workspace).as_posix(),
                    "contactSheet": contact.relative_to(workspace).as_posix(),
                }
            )
        return workspace, fixture, renders

    def make_finalize_state(
        self,
        root: Path,
        *,
        confirmed: bool = True,
    ) -> tuple[argparse.Namespace, Path, bytes]:
        primary = (root / "primary.fbx").resolve()
        secondary = (root / "secondary.fbx").resolve()
        blender = (root / "blender.exe").resolve()
        unity = (root / "Unity.exe").resolve()
        for path, value in (
            (primary, b"primary"),
            (secondary, b"secondary"),
            (blender, b"blender"),
            (unity, b"unity"),
        ):
            path.write_bytes(value)
        workspace, fixture, renders = self.make_prepared_workspace(root)
        for index, render in enumerate(renders, start=1):
            manifest = workspace / render["manifest"]
            contact = workspace / render["contactSheet"]
            action_name = "Rig|SSS QA Run" if index == 1 else "Rig|SSS_QA_Run"
            loop_policy = "loop" if index == 1 else "once"
            manifest.write_text(
                json.dumps(
                    {
                        "sourceSha256": self.sha(fixture),
                        "actionName": action_name,
                        "timing": {"loopPolicy": loop_policy},
                    }
                ),
                encoding="utf-8",
            )
            render.update(
                {
                    "actionName": action_name,
                    "loopPolicy": loop_policy,
                    "manifestSha256": self.sha(manifest),
                    "contactSheetSha256": self.sha(contact),
                }
            )
        artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)
        state = {
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "two_action_physical_qa",
            "status": "awaiting_visual_review",
            "primarySource": str(primary),
            "primarySourceSha256": self.sha(primary),
            "secondarySource": str(secondary),
            "secondarySourceSha256": self.sha(secondary),
            "fixture": fixture.relative_to(workspace).as_posix(),
            "fixtureSha256": self.sha(fixture),
            "fixtureReport": {
                "schemaVersion": "1.0",
                "application": "Sprite Station Studio",
                "primarySourceSha256": self.sha(primary),
                "secondarySourceSha256": self.sha(secondary),
                "fixtureSha256": self.sha(fixture),
                "fixture": str(fixture),
                "boneCount": 24,
                "skeletonsMatch": True,
                "skeletonSignatureSha256": "1" * 64,
                "restMatrixDecimals": 6,
                "actions": [
                    {
                        "name": "SSS QA Run",
                        "frameRange": [1.0, 20.0],
                        "active": True,
                    },
                    {
                        "name": "SSS_QA_Run",
                        "frameRange": [1.0, 32.0],
                        "active": False,
                    },
                ],
            },
            "blender": str(blender),
            "unity": str(unity),
            "actions": [
                {
                    "name": renders[0]["actionName"],
                    "frame_start": 1.0,
                    "frame_end": 20.0,
                    "active": True,
                },
                {
                    "name": renders[1]["actionName"],
                    "frame_start": 1.0,
                    "frame_end": 32.0,
                    "active": False,
                },
            ],
            "renders": renders,
            "preparedArtifacts": artifacts,
        }
        state_path = workspace / TOOL.QA_MANIFEST_NAME
        state_path.write_text(json.dumps(state), encoding="utf-8")
        original_state = state_path.read_bytes()
        args = argparse.Namespace(
            workspace=workspace,
            blender=blender,
            unity=unity,
            reviewer="Local QA",
            confirm_contact_sheets_approved=confirmed,
            timeout=10,
        )
        return args, state_path, original_state

    def make_realistic_final(
        self,
        root: Path,
    ) -> tuple[argparse.Namespace, Path]:
        primary = (root / "primary.fbx").resolve()
        secondary = (root / "secondary.fbx").resolve()
        blender = (root / "blender.exe").resolve()
        unity = (root / "Unity.exe").resolve()
        for path, value in (
            (primary, b"primary-model"),
            (secondary, b"secondary-model"),
            (blender, b"blender"),
            (unity, b"unity"),
        ):
            path.write_bytes(value)

        workspace = (root / "realistic-workspace").resolve()
        fixture = workspace / TOOL.FIXTURE_RELATIVE
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(b"combined-two-action-model")
        directions = (
            ("north_east", 45.0),
            ("south_east", 135.0),
            ("south_west", 225.0),
            ("north_west", 315.0),
        )
        action_names = ("Rig|SSS QA Run", "Rig|SSS_QA_Run")
        renders: list[dict] = []
        for action_index, (layout, action_name) in enumerate(
            zip(TOOL.RENDER_LAYOUT, action_names),
            start=1,
        ):
            render_root = workspace / layout["directory"]
            color = 210 if action_index == 1 else 70
            frame_pixels = bytes((color, 30, 255 - color, 255, 0, 0, 0, 0) * 2)
            direction_payloads = []
            for direction_index, (direction, yaw) in enumerate(directions):
                frames = []
                for order, source_frame in enumerate((1, 3)):
                    frame = (
                        render_root
                        / "animation_frames"
                        / direction
                        / f"{order:03d}_frame_{source_frame:04d}.png"
                    )
                    frame.parent.mkdir(parents=True, exist_ok=True)
                    frame.write_bytes(encode_rgba_png(2, 2, frame_pixels))
                    frames.append(
                        {
                            "order": order,
                            "sourceFrame": source_frame,
                            "file": frame.relative_to(render_root).as_posix(),
                            "sha256": self.sha(frame),
                        }
                    )
                sheet = (
                    render_root
                    / "animation_sheets"
                    / f"{direction_index:02d}_{direction}.png"
                )
                sheet.parent.mkdir(parents=True, exist_ok=True)
                sheet.write_bytes(encode_rgba_png(4, 2, frame_pixels * 2))
                direction_payloads.append(
                    {
                        "id": direction,
                        "yawDegrees": yaw,
                        "sheet": sheet.relative_to(render_root).as_posix(),
                        "sheetSha256": self.sha(sheet),
                        "frames": frames,
                    }
                )
            contact = render_root / "animation_contact_sheet.png"
            contact.write_bytes(encode_rgba_png(8, 2, frame_pixels * 4))
            manifest_payload = {
                "schemaVersion": "1.1",
                "application": "Sprite Station Studio",
                "module": "Animation Sprite Renderer",
                "assetName": "sss_two_action_fixture",
                "actionName": action_name,
                "source": str(fixture),
                "sourceSha256": self.sha(fixture),
                "directionCount": 4,
                "frameRange": {"start": 1, "end": 3},
                "sampledFrames": [1, 3],
                "frameCountPerDirection": 2,
                "timing": {
                    "fps": 20.0,
                    "fpsSource": "override",
                    "sourceFrameStep": 2,
                    "sampleTimesSeconds": [0.0, 0.1],
                    "durationSeconds": 0.15,
                    "loopPolicy": layout["loopPolicy"],
                },
                "canvas": {
                    "width": 2,
                    "height": 2,
                    "transparent": True,
                    "colorMode": "RGBA",
                },
                "normalization": {
                    "pivot": {"mode": "bottom_center", "normalized": [0.5, 0.0]},
                },
                "directions": direction_payloads,
                "contactSheet": contact.name,
                "contactSheetSha256": self.sha(contact),
                "createdUtc": f"2026-08-13T00:00:0{action_index}+00:00",
            }
            manifest = render_root / "animation_manifest.json"
            self.write_json(manifest, manifest_payload)
            write_unity_import_preset(manifest)
            renders.append(
                {
                    "actionName": action_name,
                    "loopPolicy": layout["loopPolicy"],
                    "directory": layout["directory"],
                    "manifest": layout["manifest"],
                    "manifestSha256": self.sha(manifest),
                    "contactSheet": layout["contactSheet"],
                    "contactSheetSha256": self.sha(contact),
                }
            )

        artifacts = TOOL._collect_prepared_artifacts(workspace, fixture, renders)
        fixture_actions = [
            {
                "name": TOOL.EXPECTED_ACTION_SUFFIXES[0],
                "frameRange": [1.0, 20.0],
                "active": True,
            },
            {
                "name": TOOL.EXPECTED_ACTION_SUFFIXES[1],
                "frameRange": [1.0, 32.0],
                "active": False,
            },
        ]
        state = {
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "two_action_physical_qa",
            "status": "awaiting_visual_review",
            "primarySource": str(primary),
            "primarySourceSha256": self.sha(primary),
            "secondarySource": str(secondary),
            "secondarySourceSha256": self.sha(secondary),
            "fixture": TOOL.FIXTURE_RELATIVE,
            "fixtureSha256": self.sha(fixture),
            "fixtureReport": {
                "schemaVersion": "1.0",
                "application": "Sprite Station Studio",
                "primarySourceSha256": self.sha(primary),
                "secondarySourceSha256": self.sha(secondary),
                "fixtureSha256": self.sha(fixture),
                "fixture": str(fixture),
                "boneCount": 24,
                "skeletonsMatch": True,
                "skeletonSignatureSha256": "1" * 64,
                "restMatrixDecimals": 6,
                "actions": fixture_actions,
            },
            "blender": str(blender),
            "unity": str(unity),
            "actions": [
                {
                    "name": action_names[0],
                    "frame_start": 1.0,
                    "frame_end": 20.0,
                    "active": True,
                },
                {
                    "name": action_names[1],
                    "frame_start": 1.0,
                    "frame_end": 32.0,
                    "active": False,
                },
            ],
            "renders": renders,
            "preparedArtifacts": artifacts,
        }
        state_path = workspace / TOOL.QA_MANIFEST_NAME
        self.write_json(state_path, state)
        args = argparse.Namespace(
            workspace=workspace,
            blender=blender,
            unity=unity,
            reviewer="Synthetic Release QA",
            confirm_contact_sheets_approved=True,
            timeout=30,
        )
        bridge_project = self.make_fake_bridge(root / "fake-bridge")
        bridge = RealUnityAnimationClipBridge(
            FakeClipUnityRunner(),
            bridge_project,
        )
        with (
            patch.object(
                TOOL.UnityRunner,
                "validate_executable",
                return_value=unity,
            ),
            patch.object(TOOL, "_snapshot_tree", return_value={"bridge": "stable"}),
            patch.object(TOOL, "UnityAnimationClipBridge", return_value=bridge),
        ):
            result = TOOL.finalize_qa(args)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.load_json(state_path)["status"], "passed")
        return args, state_path

    def make_fake_bridge(self, root: Path) -> Path:
        editor = root / "Assets/Editor"
        editor.mkdir(parents=True)
        (editor / "AssetForgeUnityBridge.cs").write_text("// bridge\n", encoding="utf-8")
        (root / "Packages").mkdir()
        (root / "Packages/manifest.json").write_text(
            '{"dependencies": {}}\n',
            encoding="utf-8",
        )
        (root / "ProjectSettings").mkdir()
        (root / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.4.0f1\n",
            encoding="utf-8",
        )
        return root

    def mutate_standalone_package(self, final_dir: Path, mutation: str) -> None:
        package = final_dir / "approved-1"
        review_path = package / "animation_review.json"
        review = self.load_json(review_path)
        if mutation == "review":
            review["qaMutation"] = "standalone review differs"
            self.write_json(review_path, review)
            self.refresh_approved_package(package)
            return

        manifest_path = package / "animation_manifest.json"
        manifest = self.load_json(manifest_path)
        if mutation == "manifest":
            manifest["createdUtc"] = "2026-08-13T23:59:59+00:00"
        elif mutation == "contact":
            contact = package / manifest["contactSheet"]
            alternate_pixels = bytes((0, 220, 255, 255, 0, 0, 0, 0) * 8)
            contact.write_bytes(encode_rgba_png(8, 2, alternate_pixels))
            manifest["contactSheetSha256"] = self.sha(contact)
        else:  # pragma: no cover - test helper guard
            raise AssertionError(f"Unknown standalone package mutation: {mutation}")
        self.write_json(manifest_path, manifest)
        review["animationManifestSha256"] = self.sha(manifest_path)
        self.write_json(review_path, review)
        preset_path = package / "unity_import_preset.json"
        preset = self.load_json(preset_path)
        descriptor = build_unity_animation_clip_descriptor(
            manifest,
            preset,
            manifest_sha256=self.sha(manifest_path),
            preset_sha256=self.sha(preset_path),
        )
        self.write_json(package / "unity_animation_clip_descriptor.json", descriptor)
        self.refresh_approved_package(package)

    def mutate_bundle_source_package(self, final_dir: Path) -> None:
        bundle_root = final_dir / "unity-bundle-1"
        source_package = bundle_root / "SourcePackage"
        review = source_package / "animation_review.json"
        review_payload = self.load_json(review)
        review_payload["qaMutation"] = "bundle source differs from standalone"
        self.write_json(review, review_payload)
        self.refresh_approved_package(source_package)
        source_manifest = source_package / "approved_animation_package.json"
        source_sha256 = self.sha(source_manifest)

        report_path = bundle_root / "unity_animation_clip_build_report.json"
        report = self.load_json(report_path)
        report["sourcePackageSha256"] = source_sha256
        self.write_json(report_path, report)

        bundle_path = bundle_root / "unity_animation_clip_bundle.json"
        bundle = self.load_json(bundle_path)
        bundle["sourceApprovedPackageSha256"] = source_sha256
        for artifact in bundle["artifacts"]:
            artifact["sha256"] = self.sha(bundle_root / artifact["path"])
        self.write_json(bundle_path, bundle)

    def refresh_approved_package(self, package_root: Path) -> None:
        manifest_path = package_root / "approved_animation_package.json"
        package = self.load_json(manifest_path)
        package["reviewSha256"] = self.sha(package_root / "animation_review.json")
        for artifact in package["artifacts"]:
            artifact["sha256"] = self.sha(package_root / artifact["path"])
        self.write_json(manifest_path, package)

    def refresh_final_evidence(self, final_dir: Path) -> None:
        result_path = final_dir / TOOL.FINAL_RESULT_NAME
        result = self.load_json(result_path)
        result["visualReviewSha256"] = self.sha(final_dir / result["visualReview"])
        for bundle in result["bundles"]:
            bundle["approvedPackageManifestSha256"] = self.sha(
                final_dir / bundle["approvedPackageManifest"]
            )
            bundle["unityBundleManifestSha256"] = self.sha(
                final_dir / bundle["unityBundleManifest"]
            )
        for artifact in result["artifacts"]:
            path = final_dir / artifact["path"]
            artifact["sha256"] = self.sha(path)
            artifact["size"] = path.stat().st_size
        self.write_json(result_path, result)

    @staticmethod
    def load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @contextmanager
    def fake_finalize_dependencies(self, workspace: Path):
        state = json.loads(
            (workspace / TOOL.QA_MANIFEST_NAME).read_text(encoding="utf-8")
        )

        def record_review(manifest: Path, fixture: Path, decision: str):
            review = manifest.parent / "animation_review.json"
            review.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "application": "Sprite Station Studio",
                        "kind": "animation_review_decision",
                        "animationManifest": "animation_manifest.json",
                        "animationManifestSha256": self.sha(manifest),
                        "sourceSha256": self.sha(fixture),
                        "decision": decision,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(path=review)

        def publish(review: Path, output: Path):
            index = int(output.name.rsplit("-", 1)[1])
            render = state["renders"][index - 1]
            output.mkdir()
            source_root = review.parent
            for name in (
                "animation_manifest.json",
                "animation_contact_sheet.png",
                "animation_review.json",
            ):
                TOOL.shutil.copy2(source_root / name, output / name)
            descriptor = {
                "actionName": render["actionName"],
                "clips": [
                    {
                        "name": f"Action_{index}_{direction}",
                        "loopTime": render["loopPolicy"] == "loop",
                    }
                    for direction in range(4)
                ],
            }
            descriptor_path = output / "unity_animation_clip_descriptor.json"
            descriptor_path.write_text(
                json.dumps(descriptor),
                encoding="utf-8",
            )
            package_files = (
                output / "animation_manifest.json",
                output / "animation_contact_sheet.png",
                output / "animation_review.json",
                descriptor_path,
            )
            artifacts = [
                {
                    "path": path.name,
                    "sha256": self.sha(path),
                }
                for path in package_files
            ]
            package_manifest = output / "approved_animation_package.json"
            package_manifest.write_text(
                json.dumps(
                    {
                        "reviewSha256": self.sha(output / "animation_review.json"),
                        "artifacts": artifacts,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(
                output_dir=output,
                manifest_path=package_manifest,
            )

        def bridge_run(unity: Path, package: Path, output: Path, timeout: int = 900):
            output.mkdir()
            source_package = output / "SourcePackage"
            TOOL.shutil.copytree(package.parent, source_package)
            source_package_sha = self.sha(
                source_package / "approved_animation_package.json"
            )
            report = output / "unity_animation_clip_build_report.json"
            report.write_text(
                json.dumps({"sourcePackageSha256": source_package_sha}) + "\n",
                encoding="utf-8",
            )
            bundle_files = [
                path for path in output.rglob("*") if path.is_file()
            ]
            artifacts = [
                {
                    "path": path.relative_to(output).as_posix(),
                    "sha256": self.sha(path),
                }
                for path in bundle_files
            ]
            manifest = output / "unity_animation_clip_bundle.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sourceApprovedPackage": (
                            "SourcePackage/approved_animation_package.json"
                        ),
                        "sourceApprovedPackageSha256": source_package_sha,
                        "artifacts": artifacts,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(output_dir=output, manifest_path=manifest)

        bridge = Mock()
        bridge.run.side_effect = bridge_run
        package_audit = SimpleNamespace(artifact_count=17)
        bundle_audit = SimpleNamespace(
            clip_count=4,
            sprite_sheet_count=4,
            keyframe_count=8,
            artifact_count=35,
            portable_reload_verified=True,
        )
        approval = Mock(side_effect=record_review)
        bridge.approval = approval
        with (
            patch.object(
                TOOL.UnityRunner,
                "validate_executable",
                return_value=Path(state["unity"]),
            ),
            patch.object(TOOL, "_snapshot_tree", return_value={"bridge": "stable"}),
            patch.object(TOOL, "record_animation_review", approval),
            patch.object(TOOL, "publish_approved_animation", side_effect=publish),
            patch.object(
                TOOL,
                "audit_approved_animation_package",
                return_value=package_audit,
            ),
            patch.object(TOOL, "UnityAnimationClipBridge", return_value=bridge),
            patch.object(
                TOOL,
                "audit_unity_animation_clip_bundle",
                return_value=bundle_audit,
            ),
        ):
            yield bridge

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
