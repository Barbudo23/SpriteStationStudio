from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app.animation_approval import (
    publish_approved_animation,
    record_animation_review,
)
from app.engine_export import write_unity_import_preset
from app.unity_animation_clip_bridge import (
    BUILD_REPORT_NAME,
    BUNDLE_MANIFEST_NAME,
    UNITY_ASSETS_DIR,
    UNITY_JOB_ASSET_ROOT,
    UnityAnimationClipBridge,
    audit_unity_animation_clip_bundle,
)
from app.unity_runner import UnityBridgeError, UnityCommandResult
from core.validation import encode_rgba_png


class FakeClipUnityRunner:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.command: dict | None = None
        self.calls = 0

    def execute(
        self,
        unity_path: Path,
        project_path: Path,
        method: str,
        command_path: Path,
        log_path: Path,
        timeout: int = 900,
    ) -> UnityCommandResult:
        self.calls += 1
        if self.failure == "execute":
            raise UnityBridgeError("injected Unity failure")
        self.command = json.loads(command_path.read_text(encoding="utf-8"))
        package_manifest = Path(self.command["packageManifestPath"])
        package_root = package_manifest.parent
        descriptor = json.loads(
            (package_root / "unity_animation_clip_descriptor.json").read_text(
                encoding="utf-8"
            )
        )
        if self.failure == "mutate_package":
            package_manifest.write_text(
                package_manifest.read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )
        job_root = project_path / Path(UNITY_JOB_ASSET_ROOT)
        files: list[dict] = []
        report_clips: list[dict] = []

        def add_file(path: Path, relative: str, role: str) -> None:
            files.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "role": role,
                }
            )

        for clip in descriptor["clips"]:
            direction = clip["directionId"]
            sheet_relative = f"Sheets/{direction}.png"
            sheet = job_root / sheet_relative
            sheet.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package_root / clip["spriteSheet"], sheet)
            sheet_meta = Path(str(sheet) + ".meta")
            sheet_meta.write_text(f"guid: {hashlib.md5(direction.encode()).hexdigest()}\n")
            add_file(sheet, sheet_relative, "sprite_sheet")
            add_file(sheet_meta, sheet_relative + ".meta", "sprite_sheet_meta")

            name = clip["name"]
            clip_relative = f"Clips/{name}.anim"
            clip_path = job_root / clip_relative
            clip_path.parent.mkdir(parents=True, exist_ok=True)
            clip_path.write_bytes(("UNITY-ANIM:" + name).encode("utf-8"))
            clip_meta = Path(str(clip_path) + ".meta")
            clip_meta.write_text(f"guid: {hashlib.md5(name.encode()).hexdigest()}\n")
            add_file(clip_path, clip_relative, "animation_clip")
            add_file(clip_meta, clip_relative + ".meta", "animation_clip_meta")

            sprite_guid = hashlib.md5(direction.encode()).hexdigest()
            keyframes = []
            for keyframe in clip["keyframes"]:
                sprite_index = int(keyframe["spriteName"].rsplit("_", 1)[1])
                keyframes.append(
                    {
                        **keyframe,
                        "spriteGuid": sprite_guid,
                        "spriteLocalId": 1000 + sprite_index,
                    }
                )
            report_clips.append(
                {
                    "name": name,
                    "assetPath": f"{UNITY_JOB_ASSET_ROOT}/Clips/{name}.anim",
                    "frameRate": clip["frameRate"],
                    "durationSeconds": clip["durationSeconds"],
                    "loopTime": clip["loopTime"],
                    "binding": clip["binding"],
                    "keyframes": keyframes,
                }
            )

        if self.failure == "missing_meta":
            missing = next(item for item in files if item["role"] == "animation_clip_meta")
            (job_root / missing["path"]).unlink()
        report = {
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "unity_animation_clip_build_report",
            "operation": "create_animation_clips",
            "unityVersion": "6000.4.0f1",
            "sourcePackageSha256": hashlib.sha256(package_manifest.read_bytes()).hexdigest(),
            "generatedAssetRoot": UNITY_JOB_ASSET_ROOT,
            "portableReloadVerified": True,
            "clipCount": len(report_clips),
            "spriteSheetCount": len(report_clips),
            "keyframeCount": sum(len(item["keyframes"]) for item in report_clips),
            "warnings": [],
            "files": files,
            "clips": report_clips,
            "error": None,
        }
        if self.failure == "warnings":
            report["warnings"] = ["injected warning"]
        elif self.failure == "source_hash":
            report["sourcePackageSha256"] = "0" * 64
        elif self.failure == "guid":
            report["clips"][0]["keyframes"][0]["spriteGuid"] = "invalid"
        if self.failure == "version":
            report["unityVersion"] = "2022.3.0f1"
        if self.failure != "no_report":
            Path(self.command["reportPath"]).write_text(
                json.dumps(report), encoding="utf-8"
            )
        return UnityCommandResult(0, "", "", Path(self.command["reportPath"]))


class UnityAnimationClipBridgeTests(unittest.TestCase):
    def prepare_bridge(self, root: Path) -> Path:
        bridge = root / "bridge"
        editor = bridge / "Assets/Editor"
        editor.mkdir(parents=True)
        (editor / "AssetForgeUnityBridge.cs").write_text("// bridge\n")
        (bridge / "Packages").mkdir()
        (bridge / "Packages/manifest.json").write_text('{"dependencies": {}}\n')
        (bridge / "ProjectSettings").mkdir()
        (bridge / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.4.0f1\n"
        )
        return bridge

    def prepare_package(self, root: Path, *, timed: bool = True) -> Path:
        render = root / "render"
        render.mkdir(parents=True)
        source = render / "unit.glb"
        source.write_bytes(b"model")
        frame_pixels = bytes((255, 0, 0, 255, 0, 0, 0, 0) * 2)
        directions = []
        expected = (
            ("north_east", 45.0),
            ("south_east", 135.0),
            ("south_west", 225.0),
            ("north_west", 315.0),
        )
        for index, (direction, yaw) in enumerate(expected):
            frames = []
            for order, source_frame in enumerate((1, 3)):
                frame = render / "animation_frames" / direction / f"{order:03d}.png"
                frame.parent.mkdir(parents=True, exist_ok=True)
                frame.write_bytes(encode_rgba_png(2, 2, frame_pixels))
                frames.append(
                    {
                        "order": order,
                        "sourceFrame": source_frame,
                        "file": frame.relative_to(render).as_posix(),
                        "sha256": self.sha(frame),
                    }
                )
            sheet = render / "animation_sheets" / f"{index:02d}_{direction}.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            sheet.write_bytes(encode_rgba_png(4, 2, frame_pixels * 2))
            directions.append(
                {
                    "id": direction,
                    "yawDegrees": yaw,
                    "sheet": sheet.relative_to(render).as_posix(),
                    "sheetSha256": self.sha(sheet),
                    "frames": frames,
                }
            )
        contact = render / "animation_contact_sheet.png"
        contact.write_bytes(encode_rgba_png(8, 2, frame_pixels * 4))
        manifest_payload = {
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "module": "Animation Sprite Renderer",
            "assetName": "unit",
            "actionName": "Run",
            "sourceSha256": self.sha(source),
            "directionCount": 4,
            "sampledFrames": [1, 3],
            "frameRange": {"start": 1, "end": 3},
            "frameCountPerDirection": 2,
            "canvas": {
                "width": 2,
                "height": 2,
                "transparent": True,
                "colorMode": "RGBA",
            },
            "normalization": {"pivot": {"normalized": [0.5, 0.0]}},
            "directions": directions,
            "contactSheet": contact.name,
            "contactSheetSha256": self.sha(contact),
        }
        if timed:
            manifest_payload["timing"] = {
                "fps": 20.0,
                "fpsSource": "override",
                "sourceFrameStep": 2,
                "sampleTimesSeconds": [0.0, 0.1],
                "durationSeconds": 0.15,
                "loopPolicy": "loop",
            }
        manifest = render / "animation_manifest.json"
        manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
        if timed:
            write_unity_import_preset(manifest)
        review = record_animation_review(manifest, source, "approved")
        return publish_approved_animation(
            review.path, root / "approved"
        ).manifest_path

    def test_builds_audited_portable_bundle_without_touching_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            protected = self.snapshot(package.parent) | self.snapshot(bridge)
            runner = FakeClipUnityRunner()
            result = UnityAnimationClipBridge(runner, bridge).run(
                root / "Unity.exe", package, root / "bundle"
            )

            self.assertEqual(result.clip_count, 4)
            self.assertEqual(result.keyframe_count, 8)
            self.assertEqual(len(result.clip_paths), 4)
            self.assertEqual(len(result.sheet_paths), 4)
            self.assertTrue(all(path.is_file() for path in result.clip_paths))
            self.assertTrue(all(Path(str(path) + ".meta").is_file() for path in result.clip_paths))
            audit = audit_unity_animation_clip_bundle(result.manifest_path)
            self.assertTrue(audit.portable_reload_verified)
            self.assertEqual(audit.unity_version, "6000.4.0f1")
            self.assertEqual(protected, self.snapshot(package.parent) | self.snapshot(bridge))
            self.assertEqual(
                set(runner.command or {}),
                {"operation", "packageManifestPath", "reportPath"},
            )
            self.assertNotIn("presetPath", runner.command or {})
            self.assertNotIn("descriptorPath", runner.command or {})

    def test_requires_exact_approved_timed_package_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root, timed=False)
            bridge = self.prepare_bridge(root)
            runner = FakeClipUnityRunner()
            with self.assertRaisesRegex(UnityBridgeError, "timed approved package"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe", package, root / "bundle"
                )
            with self.assertRaisesRegex(UnityBridgeError, "named approved_animation_package"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe",
                    package.parent / "animation_manifest.json",
                    root / "other",
                )
            self.assertEqual(runner.calls, 0)

    def test_rejects_tampered_source_before_unity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            (package.parent / "animation_sheets/00_north_east.png").write_bytes(b"tampered")
            runner = FakeClipUnityRunner()
            with self.assertRaisesRegex(UnityBridgeError, "audit failed"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe", package, root / "bundle"
                )
            self.assertEqual(runner.calls, 0)

    def test_rejects_output_overlap_existing_and_user_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            runner = FakeClipUnityRunner()
            with self.assertRaisesRegex(UnityBridgeError, "outside the approved package"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe", package, package.parent / "bundle"
                )
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(UnityBridgeError, "already exists"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe", package, existing
                )
            project = root / "UserProject"
            (project / "Assets").mkdir(parents=True)
            (project / "ProjectSettings").mkdir()
            with self.assertRaisesRegex(UnityBridgeError, "user Unity Assets"):
                UnityAnimationClipBridge(runner, bridge).run(
                    root / "Unity.exe", package, project / "Assets/Generated"
                )
            self.assertEqual(runner.calls, 0)

    def test_unity_or_report_failure_leaves_no_partial_output(self) -> None:
        for failure, message in (
            ("execute", "injected Unity failure"),
            ("warnings", "identity is invalid"),
            ("source_hash", "identity is invalid"),
            ("version", "identity is invalid"),
            ("guid", "keyframe does not match"),
            ("missing_meta", "file integrity failed"),
            ("no_report", "report was not created"),
            ("mutate_package", "changed the approved package manifest"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = self.prepare_package(root)
                bridge = self.prepare_bridge(root)
                output = root / "bundle"
                with self.assertRaisesRegex(UnityBridgeError, message):
                    UnityAnimationClipBridge(
                        FakeClipUnityRunner(failure), bridge
                    ).run(root / "Unity.exe", package, output)
                self.assertFalse(output.exists())
                self.assertEqual(list(root.glob(".bundle.staging-*")), [])

    def test_publish_failure_rolls_back_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            output = root / "bundle"
            with patch(
                "app.unity_animation_clip_bridge.os.rename",
                side_effect=OSError("injected publish race"),
            ):
                with self.assertRaisesRegex(OSError, "injected publish race"):
                    UnityAnimationClipBridge(FakeClipUnityRunner(), bridge).run(
                        root / "Unity.exe", package, output
                    )
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".bundle.staging-*")), [])

    def test_bundle_audit_rejects_tampering_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            result = UnityAnimationClipBridge(FakeClipUnityRunner(), bridge).run(
                root / "Unity.exe", package, root / "bundle"
            )
            result.clip_paths[0].write_bytes(b"tampered")
            with self.assertRaisesRegex(UnityBridgeError, "hash mismatch"):
                audit_unity_animation_clip_bundle(result.manifest_path)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.prepare_package(root)
            bridge = self.prepare_bridge(root)
            result = UnityAnimationClipBridge(FakeClipUnityRunner(), bridge).run(
                root / "Unity.exe", package, root / "bundle"
            )
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            payload["artifacts"][0]["path"] = "../escape"
            result.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(UnityBridgeError, "unsafe"):
                audit_unity_animation_clip_bundle(result.manifest_path)

    def test_bridge_source_uses_native_animation_api_and_package_only_input(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "unity_bridge_project/Assets/Editor/AssetForgeUnityBridge.cs"
        ).read_text(encoding="utf-8")
        self.assertIn('command.operation == "create_animation_clips"', source)
        self.assertIn("AnimationUtility.SetObjectReferenceCurve", source)
        self.assertIn("AssetDatabase.CreateAsset", source)
        self.assertIn("packageManifestPath", source)
        method = source.split("private static void CreateAnimationClips", 1)[1]
        method = method.split("private static void ApplySpriteImport", 1)[0]
        self.assertNotIn("command.presetPath", method)
        self.assertNotIn("command.descriptorPath", method)

    @staticmethod
    def snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
