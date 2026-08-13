from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.animation_approval import (
    audit_approved_animation_package,
    publish_approved_animation,
    record_animation_review,
)
from app.blender_runner import ForgeError
from app.engine_export import write_unity_import_preset
from app.unity_animation_clip_descriptor import (
    DESCRIPTOR_NAME,
    validate_unity_animation_clip_descriptor,
)
from core.validation import encode_rgba_png


class AnimationApprovalTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "unit.glb"
        source.write_bytes(b"model")
        pixels = bytes((255, 0, 0, 255, 0, 0, 0, 0) * 2)
        directions = []
        expected = (
            ("north_east", 45.0), ("south_east", 135.0),
            ("south_west", 225.0), ("north_west", 315.0),
        )
        for index, (name, yaw) in enumerate(expected):
            frame = root / "animation_frames" / name / "000.png"
            frame.parent.mkdir(parents=True)
            frame.write_bytes(encode_rgba_png(2, 2, pixels))
            sheet = root / "animation_sheets" / f"{index:02d}_{name}.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            sheet.write_bytes(encode_rgba_png(2, 2, pixels))
            directions.append({
                "id": name,
                "yawDegrees": yaw,
                "sheet": sheet.relative_to(root).as_posix(),
                "sheetSha256": self.sha(sheet),
                "frames": [{
                    "order": 0, "sourceFrame": 1,
                    "file": frame.relative_to(root).as_posix(),
                    "sha256": self.sha(frame),
                }],
            })
        contact = root / "animation_contact_sheet.png"
        contact.write_bytes(encode_rgba_png(8, 2, pixels * 4))
        manifest = root / "animation_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.1",
            "application": "Sprite Station Studio",
            "module": "Animation Sprite Renderer",
            "sourceSha256": self.sha(source),
            "directionCount": 4,
            "sampledFrames": [1],
            "frameRange": {"start": 1, "end": 1},
            "frameCountPerDirection": 1,
            "canvas": {"width": 2, "height": 2, "transparent": True, "colorMode": "RGBA"},
            "directions": directions,
            "contactSheet": contact.name,
            "contactSheetSha256": self.sha(contact),
        }), encoding="utf-8")
        return manifest, source

    def test_records_integrity_bound_approval_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, source = self.fixture(Path(tmp))
            result = record_animation_review(manifest, source, "approved")
            self.assertEqual(result.decision, "approved")
            with self.assertRaisesRegex(ForgeError, "already exists"):
                record_animation_review(manifest, source, "approved")

    def test_publishes_approved_package_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["artifactCount"], 11)
            self.assertTrue(all(path.is_file() for path in result.copied_files))
            with self.assertRaisesRegex(ForgeError, "already exists"):
                publish_approved_animation(review.path, root / "approved")
            self.assertEqual(
                json.loads(result.manifest_path.read_text(encoding="utf-8"))["artifactCount"],
                11,
            )
            audit = audit_approved_animation_package(result.manifest_path)
            self.assertTrue(audit.valid)
            self.assertEqual(audit.direction_count, 4)

    def test_timed_package_contains_audited_unity_clip_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.timed_fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["artifactCount"], 13)
            descriptor = result.output_dir / DESCRIPTOR_NAME
            self.assertTrue(descriptor.is_file())
            descriptor_report = validate_unity_animation_clip_descriptor(
                descriptor,
                result.output_dir / "animation_manifest.json",
                result.output_dir / "unity_import_preset.json",
            )
            self.assertEqual(descriptor_report.clip_count, 4)
            self.assertEqual(descriptor_report.keyframe_count, 8)
            audit = audit_approved_animation_package(result.manifest_path)
            self.assertEqual(audit.descriptor_path, descriptor)
            self.assertEqual(audit.descriptor_clip_count, 4)
            self.assertEqual(audit.descriptor_keyframe_count, 8)

    def test_timed_package_requires_matching_unity_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.timed_fixture(render)
            preset = render / "unity_import_preset.json"
            preset.unlink()
            review = record_animation_review(manifest, source, "approved")
            with self.assertRaisesRegex(ForgeError, "requires unity_import_preset"):
                publish_approved_animation(review.path, root / "approved")
            self.assertFalse((root / "approved").exists())

    def test_timed_descriptor_tampering_fails_package_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.timed_fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            descriptor = result.output_dir / DESCRIPTOR_NAME
            descriptor.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "hash mismatch"):
                audit_approved_animation_package(result.manifest_path)

    def test_noncanonical_preset_rolls_back_timed_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.timed_fixture(render)
            preset_path = render / "unity_import_preset.json"
            preset = json.loads(preset_path.read_text(encoding="utf-8"))
            preset["assets"][0]["slices"][0]["rect"][0] = 1
            preset_path.write_text(json.dumps(preset), encoding="utf-8")
            review = record_animation_review(manifest, source, "approved")
            target = root / "approved"
            with self.assertRaisesRegex(ForgeError, "exactly match"):
                publish_approved_animation(review.path, target)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".approved.staging-*")), [])
            self.assertEqual(
                json.loads(preset_path.read_text(encoding="utf-8"))["assets"][0]["slices"][0]["rect"][0],
                1,
            )

    def test_descriptor_failure_rolls_back_whole_timed_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.timed_fixture(render)
            review = record_animation_review(manifest, source, "approved")
            target = root / "approved"
            with patch(
                "app.animation_approval._write_unity_animation_clip_descriptor",
                side_effect=OSError("injected descriptor failure"),
            ):
                with self.assertRaisesRegex(OSError, "injected descriptor failure"):
                    publish_approved_animation(review.path, target)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".approved.staging-*")), [])
            self.assertTrue(manifest.is_file())
            self.assertTrue((render / "unity_import_preset.json").is_file())

    def test_audit_rejects_published_frame_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            frame = result.output_dir / "animation_frames" / "north_east" / "000.png"
            frame.write_bytes(b"tampered")
            with self.assertRaisesRegex(ForgeError, "hash mismatch"):
                audit_approved_animation_package(result.manifest_path)

    def test_audit_rejects_incomplete_top_level_artifact_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            payload["artifacts"] = [
                artifact for artifact in payload["artifacts"]
                if artifact["path"] != "animation_frames/north_east/000.png"
            ]
            payload["artifactCount"] = len(payload["artifacts"])
            result.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "incomplete or unexpected"):
                audit_approved_animation_package(result.manifest_path)

    def test_manifest_changed_after_approval_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "approved")
            manifest.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ForgeError, "changed after review"):
                publish_approved_animation(review.path, root / "approved")
            self.assertFalse((root / "approved").exists())

    def test_rejected_or_changed_review_cannot_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "rejected")
            with self.assertRaisesRegex(ForgeError, "Only an approved"):
                publish_approved_animation(review.path, root / "rejected-package")
            self.assertFalse((root / "rejected-package").exists())

    def timed_fixture(self, root: Path) -> tuple[Path, Path]:
        manifest, source = self.fixture(root)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload.update({
            "assetName": "unit",
            "actionName": "Idle",
            "timing": {
                "fps": 20.0,
                "fpsSource": "override",
                "sourceFrameStep": 1,
                "sampleTimesSeconds": [0.0],
                "durationSeconds": 0.05,
                "loopPolicy": "loop",
            },
        })
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        write_unity_import_preset(manifest)
        return manifest, source

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
