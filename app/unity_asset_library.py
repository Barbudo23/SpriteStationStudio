from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import time
from typing import Iterable


MODEL_EXTENSIONS = {".fbx", ".obj", ".dae", ".3ds", ".blend", ".gltf", ".glb"}
PREFAB_EXTENSIONS = {".prefab"}
ANIMATION_EXTENSIONS = {".anim", ".controller", ".overridecontroller"}
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".psd", ".exr", ".hdr"}
MATERIAL_EXTENSIONS = {".mat"}
SCENE_EXTENSIONS = {".unity"}


@dataclass(frozen=True)
class UnityProject:
    name: str
    path: str
    unity_version: str | None = None
    modified_utc: float | None = None


@dataclass(frozen=True)
class UnityAssetRecord:
    id: str
    name: str
    asset_type: str
    extension: str
    absolute_path: str
    unity_path: str
    project_path: str
    size_bytes: int
    modified_utc: float
    guid: str | None = None
    preview_path: str | None = None


class UnityAssetLibrary:
    """Filesystem-backed Unity project and asset browser.

    It intentionally does not read Unity's internal Library database.
    Stable data comes from the project Assets directory and .meta files.
    """

    def __init__(self, cache_root: Path | None = None):
        self.cache_root = (
            cache_root
            or Path.home() / ".assetforge" / "unity_asset_library"
        ).expanduser().resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_unity_project(path: Path) -> bool:
        path = path.expanduser().resolve()
        return (
            (path / "Assets").is_dir()
            and (path / "ProjectSettings").is_dir()
        )

    @staticmethod
    def read_unity_version(project_path: Path) -> str | None:
        version_file = project_path / "ProjectSettings" / "ProjectVersion.txt"
        if not version_file.is_file():
            return None
        try:
            text = version_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        match = re.search(r"m_EditorVersion:\s*(\S+)", text)
        return match.group(1) if match else None

    @staticmethod
    def _project_from_path(path: Path) -> UnityProject | None:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            return None
        if not UnityAssetLibrary.is_unity_project(resolved):
            return None
        try:
            modified = resolved.stat().st_mtime
        except OSError:
            modified = None
        return UnityProject(
            name=resolved.name,
            path=str(resolved),
            unity_version=UnityAssetLibrary.read_unity_version(resolved),
            modified_utc=modified,
        )

    def find_projects(self, extra_roots: Iterable[Path] = ()) -> list[UnityProject]:
        candidates: set[Path] = set()
        home = Path.home()

        common_roots = [
            home / "Documents",
            home / "Desktop",
            home / "Unity",
            home / "Unity Projects",
            home / "Projects",
            home / "source" / "repos",
        ]
        common_roots.extend(extra_roots)

        # Unity Hub project list locations (schema varies, parse paths defensively).
        app_data = os.environ.get("APPDATA")
        hub_files: list[Path] = []
        if app_data:
            hub = Path(app_data) / "UnityHub"
            hub_files.extend([
                hub / "projects-v1.json",
                hub / "projects.json",
                hub / "secondaryInstallPath.json",
            ])

        for file_path in hub_files:
            if not file_path.is_file():
                continue
            try:
                raw = file_path.read_text(encoding="utf-8", errors="replace")
                for value in re.findall(r'"(?:path|location)"\s*:\s*"([^"]+)"', raw, re.I):
                    candidate = Path(value.replace("\\\\", "\\"))
                    candidates.add(candidate)
                # Fallback: extract Windows paths ending before Assets/ProjectSettings.
                for value in re.findall(r'([A-Za-z]:\\\\[^"\r\n]+)', raw):
                    candidates.add(Path(value.replace("\\\\", "\\")))
            except OSError:
                continue

        # Direct children + one nested level keeps startup bounded.
        for root in common_roots:
            root = root.expanduser()
            if not root.is_dir():
                continue
            candidates.add(root)
            try:
                for child in root.iterdir():
                    if child.is_dir():
                        candidates.add(child)
                        try:
                            for grandchild in child.iterdir():
                                if grandchild.is_dir():
                                    candidates.add(grandchild)
                        except OSError:
                            pass
            except OSError:
                pass

        projects: dict[str, UnityProject] = {}
        for candidate in candidates:
            project = self._project_from_path(candidate)
            if project:
                projects[project.path.lower()] = project

        return sorted(
            projects.values(),
            key=lambda item: item.modified_utc or 0.0,
            reverse=True,
        )

    @staticmethod
    def classify(path: Path) -> str | None:
        ext = path.suffix.lower()
        if ext in MODEL_EXTENSIONS:
            return "Model"
        if ext in PREFAB_EXTENSIONS:
            return "Prefab"
        if ext in ANIMATION_EXTENSIONS:
            return "Animation"
        if ext in TEXTURE_EXTENSIONS:
            return "Texture"
        if ext in MATERIAL_EXTENSIONS:
            return "Material"
        if ext in SCENE_EXTENSIONS:
            return "Scene"
        return None

    @staticmethod
    def read_guid(asset_path: Path) -> str | None:
        meta = Path(str(asset_path) + ".meta")
        if not meta.is_file():
            return None
        try:
            text = meta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        match = re.search(r"^guid:\s*([0-9a-fA-F]+)\s*$", text, re.M)
        return match.group(1) if match else None

    @staticmethod
    def _record_id(project_path: Path, unity_path: str) -> str:
        value = f"{project_path.resolve()}::{unity_path}".encode("utf-8")
        return hashlib.sha1(value).hexdigest()

    def scan_project(
        self,
        project_path: Path,
        asset_types: set[str] | None = None,
    ) -> list[UnityAssetRecord]:
        project_path = project_path.expanduser().resolve()
        if not self.is_unity_project(project_path):
            raise ValueError(f"Not a Unity project: {project_path}")

        assets_root = project_path / "Assets"
        records: list[UnityAssetRecord] = []

        for path in assets_root.rglob("*"):
            if not path.is_file() or path.name.endswith(".meta"):
                continue
            asset_type = self.classify(path)
            if asset_type is None:
                continue
            if asset_types and asset_type not in asset_types:
                continue

            try:
                stat = path.stat()
            except OSError:
                continue

            unity_path = path.relative_to(project_path).as_posix()
            records.append(UnityAssetRecord(
                id=self._record_id(project_path, unity_path),
                name=path.stem,
                asset_type=asset_type,
                extension=path.suffix.lower(),
                absolute_path=str(path.resolve()),
                unity_path=unity_path,
                project_path=str(project_path),
                size_bytes=stat.st_size,
                modified_utc=stat.st_mtime,
                guid=self.read_guid(path),
                preview_path=str(path.resolve()) if asset_type == "Texture" else None,
            ))

        records.sort(key=lambda record: (record.asset_type, record.name.lower(), record.unity_path.lower()))
        self.write_cache(project_path, records)
        return records

    def cache_path(self, project_path: Path) -> Path:
        digest = hashlib.sha1(str(project_path.resolve()).encode("utf-8")).hexdigest()
        return self.cache_root / f"{digest}.json"

    def write_cache(self, project_path: Path, records: list[UnityAssetRecord]) -> Path:
        cache_path = self.cache_path(project_path)
        payload = {
            "schemaVersion": 1,
            "projectPath": str(project_path.resolve()),
            "generatedUtc": time.time(),
            "assets": [asdict(record) for record in records],
        }
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return cache_path

    def read_cache(self, project_path: Path) -> list[UnityAssetRecord]:
        cache_path = self.cache_path(project_path)
        if not cache_path.is_file():
            return []
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return [UnityAssetRecord(**item) for item in payload.get("assets", [])]
        except (OSError, ValueError, TypeError):
            return []

    @staticmethod
    def filter_records(
        records: Iterable[UnityAssetRecord],
        query: str = "",
        asset_type: str = "All",
    ) -> list[UnityAssetRecord]:
        query = query.strip().lower()
        result = []
        for record in records:
            if asset_type != "All" and record.asset_type != asset_type:
                continue
            haystack = f"{record.name} {record.unity_path} {record.extension}".lower()
            if query and query not in haystack:
                continue
            result.append(record)
        return result
