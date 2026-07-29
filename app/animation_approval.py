from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from app.animation_validation import validate_animation_manifest
from app.blender_runner import ForgeError


@dataclass(frozen=True)
class AnimationReviewResult:
    path: Path
    decision: str
    manifest_sha256: str


@dataclass(frozen=True)
class ApprovedAnimationPackage:
    output_dir: Path
    manifest_path: Path
    copied_files: tuple[Path, ...]


def record_animation_review(
    animation_manifest: Path,
    source_model: Path,
    decision: str,
    output_name: str = "animation_review.json",
) -> AnimationReviewResult:
    manifest = animation_manifest.expanduser().resolve()
    source = source_model.expanduser().resolve()
    validate_animation_manifest(manifest, source)
    if decision not in {"approved", "rejected"}:
        raise ForgeError("Animation review decision must be approved or rejected.")
    if Path(output_name).name != output_name or Path(output_name).suffix.lower() != ".json":
        raise ForgeError("Animation review output must be a JSON filename.")
    output = manifest.parent / output_name
    if output.exists():
        raise ForgeError(f"Animation review already exists: {output}")
    manifest_hash = _sha256(manifest)
    payload = {
        "schemaVersion": "1.0",
        "application": "Sprite Station Studio",
        "kind": "animation_review_decision",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "animationManifest": manifest.name,
        "animationManifestSha256": manifest_hash,
        "sourceSha256": _sha256(source),
        "decision": decision,
    }
    temporary = output.parent / f".{output.name}.staging-{uuid4().hex}"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    except FileExistsError as exc:
        raise ForgeError(f"Animation review already exists: {output}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return AnimationReviewResult(output, decision, manifest_hash)


def publish_approved_animation(
    review_path: Path,
    output_dir: Path,
) -> ApprovedAnimationPackage:
    review_path = review_path.expanduser().resolve()
    review = _load_json(review_path, "Animation review")
    if (
        review.get("schemaVersion") != "1.0"
        or review.get("application") != "Sprite Station Studio"
        or review.get("kind") != "animation_review_decision"
    ):
        raise ForgeError("Animation review contract is unsupported.")
    if review.get("decision") != "approved":
        raise ForgeError("Only an approved animation can be published.")
    manifest = _resolve_file(
        review_path.parent, review.get("animationManifest"), "Animation manifest"
    )
    if _sha256(manifest) != review.get("animationManifestSha256"):
        raise ForgeError("Animation manifest changed after review.")
    audit = validate_animation_manifest(manifest)
    output_dir = output_dir.expanduser().resolve()
    source_root = manifest.parent
    try:
        output_dir.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ForgeError("Approved package must be outside the render output.")
    if output_dir.exists():
        raise ForgeError(f"Approved animation package already exists: {output_dir}")

    sources = [manifest, review_path, audit.contact_sheet_path]
    sources.extend(audit.frame_paths)
    sources.extend(audit.sheet_paths)
    for optional_name in ("unity_import_preset.json",):
        optional = source_root / optional_name
        if optional.is_file():
            sources.append(optional)
    unique_sources = tuple(dict.fromkeys(sources))
    staging = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    copied_relatives: list[Path] = []
    try:
        staging.mkdir(parents=True)
        artifacts = []
        for source in unique_sources:
            relative = (
                Path(source.name)
                if source == review_path or source == manifest
                else source.relative_to(source_root)
            )
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied_relatives.append(relative)
            artifacts.append({"path": relative.as_posix(), "sha256": _sha256(target)})
        package_manifest = staging / "approved_animation_package.json"
        package_manifest.write_text(json.dumps({
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "approved_animation_package",
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "reviewSha256": _sha256(review_path),
            "directionCount": audit.direction_count,
            "frameCountPerDirection": audit.frame_count_per_direction,
            "artifactCount": len(artifacts),
            "artifacts": artifacts,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        copied_relatives.append(Path(package_manifest.name))
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging, output_dir)
    except FileExistsError as exc:
        raise ForgeError(f"Approved animation package already exists: {output_dir}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return ApprovedAnimationPackage(
        output_dir,
        output_dir / "approved_animation_package.json",
        tuple(output_dir / relative for relative in copied_relatives),
    )


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ForgeError(f"{label} must be a JSON object.")
    return payload


def _resolve_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ForgeError(f"{label} path must be relative.")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ForgeError(f"{label} path escapes its package.") from exc
    if not path.is_file():
        raise ForgeError(f"{label} is missing: {path}")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
