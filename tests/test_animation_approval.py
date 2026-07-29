from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.animation_approval import (
    audit_approved_animation_package,
    publish_approved_animation,
    record_animation_review,
)
from app.blender_runner import ForgeError
from core.validation import encode_rgba_png


class AnimationApprovalTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "unit.glb"
        source.write_bytes(b"model")
        pixels = bytes((255, 0, 0, 255, 0, 0, 0, 0) * 2)
        directions = []
        for index, name in enumerate(("north", "east", "south", "west")):
            frame = root / "animation_frames" / name / "000.png"
            frame.parent.mkdir(parents=True)
            frame.write_bytes(encode_rgba_png(2, 2, pixels))
            sheet = root / "animation_sheets" / f"{index:02d}_{name}.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            sheet.write_bytes(encode_rgba_png(2, 2, pixels))
            directions.append({
                "id": name,
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

    def test_audit_rejects_published_frame_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "render"
            render.mkdir()
            manifest, source = self.fixture(render)
            review = record_animation_review(manifest, source, "approved")
            result = publish_approved_animation(review.path, root / "approved")
            frame = result.output_dir / "animation_frames" / "north" / "000.png"
            frame.write_bytes(b"tampered")
            with self.assertRaisesRegex(ForgeError, "hash mismatch"):
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

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
