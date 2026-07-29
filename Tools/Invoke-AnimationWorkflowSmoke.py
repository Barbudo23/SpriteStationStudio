from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.animation_approval import (  # noqa: E402
    audit_approved_animation_package,
    publish_approved_animation,
    record_animation_review,
)
from app.animation_validation import validate_animation_manifest  # noqa: E402
from core.validation import encode_rgba_png  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_render(root: Path) -> tuple[Path, Path]:
    render = root / "render"
    render.mkdir()
    source = render / "synthetic_unit.glb"
    source.write_bytes(b"Sprite Station Studio synthetic animated model")
    pixels = bytes((40, 160, 220, 255, 0, 0, 0, 0) * 2)
    directions = []
    for index, name in enumerate(("north", "east", "south", "west")):
        frames = []
        for order, source_frame in enumerate((1, 3)):
            frame = render / "animation_frames" / name / f"{order:03d}.png"
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(encode_rgba_png(2, 2, pixels))
            frames.append({
                "order": order,
                "sourceFrame": source_frame,
                "file": frame.relative_to(render).as_posix(),
                "sha256": sha256(frame),
            })
        sheet = render / "animation_sheets" / f"{index:02d}_{name}.png"
        sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.write_bytes(encode_rgba_png(4, 2, pixels * 2))
        directions.append({
            "id": name,
            "sheet": sheet.relative_to(render).as_posix(),
            "sheetSha256": sha256(sheet),
            "frames": frames,
        })
    contact = render / "animation_contact_sheet.png"
    contact.write_bytes(encode_rgba_png(8, 2, pixels * 4))
    manifest = render / "animation_manifest.json"
    manifest.write_text(json.dumps({
        "schemaVersion": "1.1",
        "application": "Sprite Station Studio",
        "module": "Animation Sprite Renderer",
        "assetName": "synthetic_unit",
        "sourceSha256": sha256(source),
        "directionCount": 4,
        "sampledFrames": [1, 3],
        "frameCountPerDirection": 2,
        "canvas": {
            "width": 2, "height": 2,
            "transparent": True, "colorMode": "RGBA",
        },
        "directions": directions,
        "contactSheet": contact.name,
        "contactSheetSha256": sha256(contact),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest, source


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sss-animation-smoke-") as tmp:
        root = Path(tmp)
        manifest, source = create_render(root)
        render_audit = validate_animation_manifest(manifest, source)
        review = record_animation_review(manifest, source, "approved")
        package = publish_approved_animation(review.path, root / "approved")
        package_audit = audit_approved_animation_package(package.manifest_path)
        print(json.dumps({
            "application": "Sprite Station Studio",
            "workflow": "Animation Workflow",
            "synthetic": True,
            "directionCount": render_audit.direction_count,
            "frameCountPerDirection": render_audit.frame_count_per_direction,
            "renderCheckedFileCount": render_audit.checked_file_count,
            "packageArtifactCount": package_audit.artifact_count,
            "approved": review.decision == "approved",
            "auditValid": package_audit.valid,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
