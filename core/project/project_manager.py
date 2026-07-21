from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid


PROJECT_FOLDERS = (
    "Assets",
    "Source",
    "AI",
    "Sprites",
    "Animations",
    "Atlases",
    "Cache",
    "Export",
    "Database",
    "Logs",
)


@dataclass
class AssetForgeProject:
    schema_version: int
    project_id: str
    name: str
    root_path: str
    created_utc: str
    modified_utc: str

    @property
    def descriptor_path(self) -> Path:
        return Path(self.root_path) / f"{self.name}.afs"

    @property
    def database_path(self) -> Path:
        return Path(self.root_path) / "Database" / "assets.sqlite3"


class ProjectManager:
    def create(self, parent: Path, name: str) -> AssetForgeProject:
        clean = "".join(ch for ch in name.strip() if ch.isalnum() or ch in "-_ ").strip()
        if not clean:
            raise ValueError("Project name is empty or invalid.")

        root = (parent.expanduser().resolve() / clean)
        root.mkdir(parents=True, exist_ok=False)
        for folder in PROJECT_FOLDERS:
            (root / folder).mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        project = AssetForgeProject(
            schema_version=1,
            project_id=str(uuid.uuid4()),
            name=clean,
            root_path=str(root),
            created_utc=now,
            modified_utc=now,
        )
        self.save(project)
        return project

    def save(self, project: AssetForgeProject) -> None:
        project.modified_utc = datetime.now(timezone.utc).isoformat()
        project.descriptor_path.write_text(
            json.dumps(asdict(project), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def open(self, descriptor: Path) -> AssetForgeProject:
        descriptor = descriptor.expanduser().resolve()
        if descriptor.suffix.lower() != ".afs" or not descriptor.is_file():
            raise ValueError(f"Invalid AssetForge project descriptor: {descriptor}")
        payload = json.loads(descriptor.read_text(encoding="utf-8"))
        project = AssetForgeProject(**payload)
        if not Path(project.root_path).is_dir():
            raise ValueError("Project root does not exist.")
        return project
