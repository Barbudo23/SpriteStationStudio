from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4

from app.animation_approval import audit_approved_animation_package
from app.blender_runner import ForgeError
from app.unity_animation_clip_descriptor import DESCRIPTOR_NAME
from app.unity_runner import UnityBridgeError, UnityRunner


APPROVED_PACKAGE_NAME = "approved_animation_package.json"
BUILD_REPORT_NAME = "unity_animation_clip_build_report.json"
BUNDLE_MANIFEST_NAME = "unity_animation_clip_bundle.json"
SOURCE_PACKAGE_DIR = "SourcePackage"
UNITY_ASSETS_DIR = "UnityAssets"
UNITY_JOB_ASSET_ROOT = "Assets/SpriteStationAnimationJob"
UNITY_OPERATION = "create_animation_clips"


@dataclass(frozen=True)
class UnityAnimationClipBuildResult:
    output_dir: Path
    manifest_path: Path
    report_path: Path
    unity_assets_dir: Path
    clip_paths: tuple[Path, ...]
    sheet_paths: tuple[Path, ...]
    clip_count: int
    keyframe_count: int
    unity_version: str


@dataclass(frozen=True)
class UnityAnimationClipBundleAudit:
    bundle_root: Path
    artifact_count: int
    clip_count: int
    sprite_sheet_count: int
    keyframe_count: int
    unity_version: str
    portable_reload_verified: bool
    valid: bool = True


class UnityAnimationClipBridge:
    """Create portable native Unity clips without touching a user Unity project."""

    def __init__(
        self,
        unity_runner: UnityRunner | None = None,
        bridge_project: Path | None = None,
    ) -> None:
        self.unity_runner = unity_runner or UnityRunner()
        self.bridge_project = (
            bridge_project.expanduser().resolve()
            if bridge_project is not None
            else Path(__file__).resolve().parents[1] / "unity_bridge_project"
        )

    def run(
        self,
        unity_path: Path,
        approved_package_manifest: Path,
        output_dir: Path,
        timeout: int = 900,
    ) -> UnityAnimationClipBuildResult:
        package_manifest = approved_package_manifest.expanduser().resolve()
        if package_manifest.name != APPROVED_PACKAGE_NAME or not package_manifest.is_file():
            raise UnityBridgeError(
                f"Select the approved package manifest named {APPROVED_PACKAGE_NAME}."
            )
        package_root = package_manifest.parent
        try:
            source_audit = audit_approved_animation_package(package_manifest)
        except ForgeError as exc:
            raise UnityBridgeError(
                f"Approved animation package audit failed: {exc}"
            ) from exc
        if source_audit.descriptor_path is None:
            raise UnityBridgeError(
                "Unity AnimationClip creation requires a timed approved package."
            )

        bridge_project = self.bridge_project.resolve()
        required_version = _validate_bridge_project(bridge_project)
        output_dir = output_dir.expanduser().resolve()
        _validate_output_location(output_dir, package_root, bridge_project)
        if output_dir.exists():
            raise UnityBridgeError(
                f"Unity AnimationClip bundle already exists: {output_dir}"
            )

        with tempfile.TemporaryDirectory(
            prefix="sprite-station-unity-animation-",
            ignore_cleanup_errors=True,
        ) as temporary_value:
            workspace = Path(temporary_value)
            snapshot = workspace / SOURCE_PACKAGE_DIR
            shutil.copytree(package_root, snapshot, copy_function=shutil.copy2)
            snapshot_manifest = snapshot / APPROVED_PACKAGE_NAME
            try:
                snapshot_audit = audit_approved_animation_package(snapshot_manifest)
            except ForgeError as exc:
                raise UnityBridgeError(
                    f"Copied approved package audit failed: {exc}"
                ) from exc
            if snapshot_audit.descriptor_path is None:
                raise UnityBridgeError(
                    "Copied approved package has no AnimationClip descriptor."
                )
            source_package_sha256 = _sha256(snapshot_manifest)

            disposable_bridge = workspace / "unity_bridge_project"
            _copy_bridge_project(bridge_project, disposable_bridge)
            command_path = workspace / "command.json"
            report_path = workspace / BUILD_REPORT_NAME
            log_path = workspace / "unity_animation_clip_build.log"
            command_path.write_text(
                json.dumps(
                    {
                        "operation": UNITY_OPERATION,
                        "packageManifestPath": str(snapshot_manifest),
                        "reportPath": str(report_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            self.unity_runner.execute(
                unity_path,
                disposable_bridge,
                "AssetForgeUnityBridge.Execute",
                command_path,
                log_path,
                timeout=timeout,
            )
            try:
                audit_approved_animation_package(snapshot_manifest)
            except ForgeError as exc:
                raise UnityBridgeError(
                    f"Unity changed the approved package snapshot: {exc}"
                ) from exc
            if _sha256(snapshot_manifest) != source_package_sha256:
                raise UnityBridgeError(
                    "Unity changed the approved package manifest during clip creation."
                )
            if not report_path.is_file():
                raise UnityBridgeError(
                    f"Unity AnimationClip report was not created: {report_path}"
                )

            report = _load_json(report_path, "Unity AnimationClip build report")
            descriptor = _load_json(
                snapshot / DESCRIPTOR_NAME,
                "Unity AnimationClip descriptor",
            )
            job_root = disposable_bridge / Path(UNITY_JOB_ASSET_ROOT)
            validated = _validate_build_report(
                report,
                descriptor,
                source_package_sha256=source_package_sha256,
                required_unity_version=required_version,
                generated_root=job_root,
            )
            _publish_bundle(
                output_dir=output_dir,
                source_snapshot=snapshot,
                source_package_sha256=source_package_sha256,
                unity_report_path=report_path,
                report=report,
                generated_root=job_root,
                validated_files=validated,
            )

        final_manifest = output_dir / BUNDLE_MANIFEST_NAME
        final_audit = audit_unity_animation_clip_bundle(final_manifest)
        final_report_path = output_dir / BUILD_REPORT_NAME
        final_report = _load_json(final_report_path, "Unity AnimationClip build report")
        clip_paths = tuple(
            output_dir / UNITY_ASSETS_DIR / item["path"]
            for item in final_report["files"]
            if item["role"] == "animation_clip"
        )
        sheet_paths = tuple(
            output_dir / UNITY_ASSETS_DIR / item["path"]
            for item in final_report["files"]
            if item["role"] == "sprite_sheet"
        )
        return UnityAnimationClipBuildResult(
            output_dir=output_dir,
            manifest_path=final_manifest,
            report_path=final_report_path,
            unity_assets_dir=output_dir / UNITY_ASSETS_DIR,
            clip_paths=clip_paths,
            sheet_paths=sheet_paths,
            clip_count=final_audit.clip_count,
            keyframe_count=final_audit.keyframe_count,
            unity_version=final_audit.unity_version,
        )


def audit_unity_animation_clip_bundle(
    bundle_manifest_path: Path,
) -> UnityAnimationClipBundleAudit:
    manifest_path = bundle_manifest_path.expanduser().resolve()
    if manifest_path.name != BUNDLE_MANIFEST_NAME or not manifest_path.is_file():
        raise UnityBridgeError(
            f"Unity AnimationClip bundle manifest must be named {BUNDLE_MANIFEST_NAME}."
        )
    root = manifest_path.parent
    bundle = _load_json(manifest_path, "Unity AnimationClip bundle")
    if (
        bundle.get("schemaVersion") != "1.0"
        or bundle.get("application") != "Sprite Station Studio"
        or bundle.get("kind") != "unity_animation_clip_bundle"
        or bundle.get("sourceApprovedPackage")
        != f"{SOURCE_PACKAGE_DIR}/{APPROVED_PACKAGE_NAME}"
        or bundle.get("unityAssetsRoot") != UNITY_ASSETS_DIR
    ):
        raise UnityBridgeError("Unity AnimationClip bundle contract is unsupported.")
    artifacts = bundle.get("artifacts")
    if (
        not isinstance(artifacts, list)
        or not artifacts
        or len(artifacts) != bundle.get("artifactCount")
    ):
        raise UnityBridgeError("Unity AnimationClip bundle artifact list is invalid.")

    resolved: dict[str, Path] = {}
    names: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise UnityBridgeError("Unity AnimationClip bundle artifact is invalid.")
        path = _resolve_bundle_file(root, artifact.get("path"))
        relative = path.relative_to(root).as_posix()
        key = relative.casefold()
        if key in names:
            raise UnityBridgeError(
                "Unity AnimationClip bundle contains duplicate artifact paths."
            )
        names.add(key)
        if not _is_sha256(artifact.get("sha256")) or _sha256(path) != artifact["sha256"]:
            raise UnityBridgeError(
                f"Unity AnimationClip bundle artifact hash mismatch: {relative}"
            )
        resolved[relative] = path

    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(resolved) != actual:
        raise UnityBridgeError(
            "Unity AnimationClip bundle artifact list is incomplete or unexpected."
        )

    source_manifest_relative = f"{SOURCE_PACKAGE_DIR}/{APPROVED_PACKAGE_NAME}"
    source_manifest = resolved.get(source_manifest_relative)
    report_path = resolved.get(BUILD_REPORT_NAME)
    if source_manifest is None or report_path is None:
        raise UnityBridgeError(
            "Unity AnimationClip bundle lacks its approved source or Unity report."
        )
    source_sha256 = _sha256(source_manifest)
    if (
        not _is_sha256(bundle.get("sourceApprovedPackageSha256"))
        or bundle["sourceApprovedPackageSha256"] != source_sha256
    ):
        raise UnityBridgeError(
            "Unity AnimationClip bundle source package hash is invalid."
        )
    try:
        source_audit = audit_approved_animation_package(source_manifest)
    except ForgeError as exc:
        raise UnityBridgeError(
            f"Bundled approved animation package audit failed: {exc}"
        ) from exc
    if source_audit.descriptor_path is None:
        raise UnityBridgeError("Bundled approved package has no clip descriptor.")

    report = _load_json(report_path, "Unity AnimationClip build report")
    descriptor = _load_json(
        source_manifest.parent / DESCRIPTOR_NAME,
        "Unity AnimationClip descriptor",
    )
    unity_version = bundle.get("unityVersion")
    if not isinstance(unity_version, str) or not unity_version:
        raise UnityBridgeError("Unity AnimationClip bundle Unity version is invalid.")
    validated_files = _validate_build_report(
        report,
        descriptor,
        source_package_sha256=source_sha256,
        required_unity_version=unity_version,
        generated_root=root / UNITY_ASSETS_DIR,
    )
    expected_unity_assets = {
        f"{UNITY_ASSETS_DIR}/{item['path']}" for item in validated_files
    }
    actual_unity_assets = {
        path.relative_to(root).as_posix()
        for path in (root / UNITY_ASSETS_DIR).rglob("*")
        if path.is_file()
    }
    if expected_unity_assets != actual_unity_assets:
        raise UnityBridgeError(
            "Unity AnimationClip bundle UnityAssets content is unexpected."
        )
    if (
        bundle.get("clipCount") != report.get("clipCount")
        or bundle.get("spriteSheetCount") != report.get("spriteSheetCount")
        or bundle.get("keyframeCount") != report.get("keyframeCount")
        or bundle.get("portableReloadVerified") is not True
        or report.get("portableReloadVerified") is not True
    ):
        raise UnityBridgeError("Unity AnimationClip bundle counts are inconsistent.")
    return UnityAnimationClipBundleAudit(
        bundle_root=root,
        artifact_count=len(resolved),
        clip_count=report["clipCount"],
        sprite_sheet_count=report["spriteSheetCount"],
        keyframe_count=report["keyframeCount"],
        unity_version=unity_version,
        portable_reload_verified=True,
    )


def _validate_build_report(
    report: dict,
    descriptor: dict,
    *,
    source_package_sha256: str,
    required_unity_version: str,
    generated_root: Path,
) -> tuple[dict, ...]:
    if (
        report.get("schemaVersion") != "1.0"
        or report.get("application") != "Sprite Station Studio"
        or report.get("kind") != "unity_animation_clip_build_report"
        or report.get("operation") != UNITY_OPERATION
        or report.get("sourcePackageSha256") != source_package_sha256
        or report.get("generatedAssetRoot") != UNITY_JOB_ASSET_ROOT
        or report.get("unityVersion") != required_unity_version
        or report.get("portableReloadVerified") is not True
        or report.get("warnings") != []
        or report.get("error") not in (None, "")
    ):
        raise UnityBridgeError("Unity AnimationClip build report identity is invalid.")

    clips = descriptor.get("clips")
    report_clips = report.get("clips")
    if not isinstance(clips, list) or not clips:
        raise UnityBridgeError("Unity AnimationClip descriptor contains no clips.")
    expected_keyframe_count = sum(
        len(clip.get("keyframes") or []) for clip in clips if isinstance(clip, dict)
    )
    if (
        not isinstance(report_clips, list)
        or len(report_clips) != len(clips)
        or descriptor.get("clipCount") != len(clips)
        or report.get("clipCount") != len(clips)
        or report.get("spriteSheetCount") != len(clips)
        or report.get("keyframeCount") != expected_keyframe_count
    ):
        raise UnityBridgeError("Unity AnimationClip build report counts are invalid.")

    expected_files: dict[str, str] = {}
    for clip in clips:
        if not isinstance(clip, dict):
            raise UnityBridgeError("Unity AnimationClip descriptor clip is invalid.")
        name = clip.get("name")
        direction = clip.get("directionId")
        if not _is_safe_unity_name(name) or not _is_safe_unity_name(direction):
            raise UnityBridgeError("Unity AnimationClip output name is unsafe.")
        entries = {
            f"Sheets/{direction}.png": "sprite_sheet",
            f"Sheets/{direction}.png.meta": "sprite_sheet_meta",
            f"Clips/{name}.anim": "animation_clip",
            f"Clips/{name}.anim.meta": "animation_clip_meta",
        }
        for path, role in entries.items():
            key = path.casefold()
            if key in (existing.casefold() for existing in expected_files):
                raise UnityBridgeError(
                    "Unity AnimationClip output paths collide case-insensitively."
                )
            expected_files[path] = role

    raw_files = report.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != len(expected_files):
        raise UnityBridgeError("Unity AnimationClip build file list is invalid.")
    validated_files: list[dict] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise UnityBridgeError("Unity AnimationClip build file is invalid.")
        relative = _safe_report_relative(item.get("path"))
        key = relative.casefold()
        if key in seen:
            raise UnityBridgeError("Unity AnimationClip build file paths are duplicated.")
        seen.add(key)
        expected_path = next(
            (value for value in expected_files if value.casefold() == key), None
        )
        if expected_path is None or item.get("role") != expected_files[expected_path]:
            raise UnityBridgeError("Unity AnimationClip build file is unexpected.")
        path = (generated_root / Path(relative)).resolve()
        try:
            path.relative_to(generated_root.resolve())
        except ValueError as exc:
            raise UnityBridgeError(
                "Unity AnimationClip build file escapes its generated root."
            ) from exc
        if (
            not path.is_file()
            or not _is_sha256(item.get("sha256"))
            or _sha256(path) != item["sha256"]
        ):
            raise UnityBridgeError(
                f"Unity AnimationClip build file integrity failed: {relative}"
            )
        validated_files.append(item)
    if seen != {path.casefold() for path in expected_files}:
        raise UnityBridgeError("Unity AnimationClip build files are incomplete.")

    sheet_guids: set[str] = set()
    for expected, actual in zip(clips, report_clips):
        sheet_guid = _validate_clip_report(expected, actual)
        if sheet_guid in sheet_guids:
            raise UnityBridgeError(
                "Unity AnimationClip clips unexpectedly share a sprite sheet GUID."
            )
        sheet_guids.add(sheet_guid)
    return tuple(validated_files)


def _validate_clip_report(expected: dict, actual: object) -> str:
    if not isinstance(actual, dict):
        raise UnityBridgeError("Unity AnimationClip report entry is invalid.")
    name = expected.get("name")
    binding = expected.get("binding")
    if (
        actual.get("name") != name
        or actual.get("assetPath") != f"{UNITY_JOB_ASSET_ROOT}/Clips/{name}.anim"
        or actual.get("binding") != binding
        or actual.get("loopTime") is not expected.get("loopTime")
        or not _float_equal(actual.get("frameRate"), expected.get("frameRate"))
        or not _float_equal(
            actual.get("durationSeconds"), expected.get("durationSeconds")
        )
    ):
        raise UnityBridgeError("Unity AnimationClip verification does not match descriptor.")
    expected_keys = expected.get("keyframes")
    actual_keys = actual.get("keyframes")
    if (
        not isinstance(expected_keys, list)
        or not isinstance(actual_keys, list)
        or len(expected_keys) != len(actual_keys)
    ):
        raise UnityBridgeError("Unity AnimationClip verified keyframes are invalid.")
    sheet_guid: str | None = None
    sprite_identities: dict[str, int] = {}
    used_local_ids: dict[int, str] = {}
    for expected_key, actual_key in zip(expected_keys, actual_keys):
        if not isinstance(expected_key, dict) or not isinstance(actual_key, dict):
            raise UnityBridgeError("Unity AnimationClip verified keyframe is invalid.")
        local_id = actual_key.get("spriteLocalId")
        if (
            actual_key.get("spriteName") != expected_key.get("spriteName")
            or actual_key.get("sourceFrame") != expected_key.get("sourceFrame")
            or actual_key.get("terminal") is not expected_key.get("terminal")
            or not _float_equal(
                actual_key.get("timeSeconds"), expected_key.get("timeSeconds")
            )
            or not _is_unity_guid(actual_key.get("spriteGuid"))
            or isinstance(local_id, bool)
            or not isinstance(local_id, int)
            or local_id == 0
        ):
            raise UnityBridgeError(
                "Unity AnimationClip verified keyframe does not match descriptor."
            )
        sprite_name = actual_key["spriteName"]
        sprite_guid = actual_key["spriteGuid"]
        if sheet_guid is None:
            sheet_guid = sprite_guid
        elif sprite_guid != sheet_guid:
            raise UnityBridgeError(
                "Unity AnimationClip keyframes reference more than one sprite sheet."
            )
        previous_id = sprite_identities.get(sprite_name)
        if previous_id is not None and previous_id != local_id:
            raise UnityBridgeError(
                "Unity AnimationClip sprite local ID changed between keyframes."
            )
        other_sprite = used_local_ids.get(local_id)
        if other_sprite is not None and other_sprite != sprite_name:
            raise UnityBridgeError(
                "Unity AnimationClip different sprites share a local ID."
            )
        sprite_identities[sprite_name] = local_id
        used_local_ids[local_id] = sprite_name
    if sheet_guid is None:
        raise UnityBridgeError("Unity AnimationClip has no verified sprite GUID.")
    return sheet_guid


def _publish_bundle(
    *,
    output_dir: Path,
    source_snapshot: Path,
    source_package_sha256: str,
    unity_report_path: Path,
    report: dict,
    generated_root: Path,
    validated_files: tuple[dict, ...],
) -> None:
    if output_dir.exists():
        raise UnityBridgeError(
            f"Unity AnimationClip bundle already exists: {output_dir}"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.parent / f".{output_dir.name}.staging-{uuid4().hex}"
    try:
        staging.mkdir(parents=False, exist_ok=False)
        shutil.copytree(
            source_snapshot,
            staging / SOURCE_PACKAGE_DIR,
            copy_function=shutil.copy2,
        )
        unity_assets = staging / UNITY_ASSETS_DIR
        for item in validated_files:
            relative = Path(item["path"])
            source = generated_root / relative
            destination = unity_assets / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copy2(unity_report_path, staging / BUILD_REPORT_NAME)

        artifacts = [
            {
                "path": path.relative_to(staging).as_posix(),
                "sha256": _sha256(path),
            }
            for path in sorted(
                (candidate for candidate in staging.rglob("*") if candidate.is_file()),
                key=lambda candidate: candidate.relative_to(staging).as_posix().casefold(),
            )
        ]
        bundle = {
            "schemaVersion": "1.0",
            "application": "Sprite Station Studio",
            "kind": "unity_animation_clip_bundle",
            "createdUtc": datetime.now(timezone.utc).isoformat(),
            "sourceApprovedPackage": f"{SOURCE_PACKAGE_DIR}/{APPROVED_PACKAGE_NAME}",
            "sourceApprovedPackageSha256": source_package_sha256,
            "unityAssetsRoot": UNITY_ASSETS_DIR,
            "unityVersion": report["unityVersion"],
            "portableReloadVerified": True,
            "clipCount": report["clipCount"],
            "spriteSheetCount": report["spriteSheetCount"],
            "keyframeCount": report["keyframeCount"],
            "artifactCount": len(artifacts),
            "artifacts": artifacts,
        }
        manifest_path = staging / BUNDLE_MANIFEST_NAME
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(bundle, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        audit_unity_animation_clip_bundle(manifest_path)
        try:
            os.rename(staging, output_dir)
        except OSError as exc:
            if output_dir.exists():
                raise UnityBridgeError(
                    f"Unity AnimationClip bundle already exists: {output_dir}"
                ) from exc
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _validate_bridge_project(bridge_project: Path) -> str:
    required = (
        bridge_project / "Assets/Editor/AssetForgeUnityBridge.cs",
        bridge_project / "Packages/manifest.json",
        bridge_project / "ProjectSettings/ProjectVersion.txt",
    )
    if not bridge_project.is_dir() or not all(path.is_file() for path in required):
        raise UnityBridgeError(f"Unity bridge project is incomplete: {bridge_project}")
    text = required[-1].read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^m_EditorVersion:\s*(\S+)\s*$", text, re.MULTILINE)
    if match is None:
        raise UnityBridgeError("Unity bridge project version is missing.")
    return match.group(1)


def _copy_bridge_project(source: Path, destination: Path) -> None:
    ignored_names = {
        "Library",
        "Logs",
        "Temp",
        "UserSettings",
        ".vs",
        "SpriteStationAnimationJob",
        "SpriteStationAnimationJob.meta",
        "AnimationBundlePortability",
    }

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name in ignored_names
            or name == "packages-lock.json"
            or name.endswith((".csproj", ".sln", ".slnx"))
        }
        return ignored

    shutil.copytree(source, destination, ignore=ignore, copy_function=shutil.copy2)


def _validate_output_location(output: Path, package_root: Path, bridge_project: Path) -> None:
    for protected, label in (
        (package_root.resolve(), "approved package"),
        (bridge_project.resolve(), "Unity bridge project"),
    ):
        if _is_relative_to(output, protected) or _is_relative_to(protected, output):
            raise UnityBridgeError(
                f"Unity AnimationClip output must be outside the {label}."
            )
    for candidate in (output, *output.parents):
        if (
            candidate.name.casefold() == "assets"
            and (candidate.parent / "ProjectSettings").is_dir()
        ):
            raise UnityBridgeError(
                "Unity AnimationClip build cannot write into a user Unity Assets folder."
            )


def _resolve_bundle_file(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise UnityBridgeError("Unity AnimationClip bundle path must be relative.")
    relative = Path(value)
    if ".." in relative.parts:
        raise UnityBridgeError("Unity AnimationClip bundle path is unsafe.")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise UnityBridgeError("Unity AnimationClip bundle path escapes its root.") from exc
    if not path.is_file():
        raise UnityBridgeError(f"Unity AnimationClip bundle file is missing: {value}")
    return path


def _safe_report_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise UnityBridgeError("Unity AnimationClip report path is invalid.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise UnityBridgeError("Unity AnimationClip report path is unsafe.")
    return value


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UnityBridgeError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UnityBridgeError(f"{label} must be a JSON object.")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_unity_guid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _is_safe_unity_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None
    )


def _float_equal(actual: object, expected: object) -> bool:
    if (
        isinstance(actual, bool)
        or isinstance(expected, bool)
        or not isinstance(actual, (int, float))
        or not isinstance(expected, (int, float))
        or not math.isfinite(float(actual))
        or not math.isfinite(float(expected))
    ):
        return False
    return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-5)
