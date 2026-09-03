from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import tempfile

from app.brand import config_path, legacy_config_path


@dataclass
class AppSettings:
    schema_version: int = 1
    blender_executable: str = ""
    unity_executable: str = ""
    last_model_path: str = ""
    last_output_path: str = ""
    last_unity_project: str = ""
    last_assetforge_project: str = ""


class SettingsStore:
    """Atomic JSON settings store for Sprite Station Studio."""

    def __init__(self, path: Path | None = None):
        self.path = (path or config_path("settings.json")).expanduser().resolve()
        self.legacy_path = (
            None if path is not None else legacy_config_path("settings.json").resolve()
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppSettings:
        read_path = self.path
        if not read_path.is_file() and self.legacy_path and self.legacy_path.is_file():
            read_path = self.legacy_path
        if not read_path.is_file():
            return AppSettings()
        try:
            payload = json.loads(read_path.read_text(encoding="utf-8"))
            known = {
                field: payload.get(field, getattr(AppSettings(), field))
                for field in AppSettings.__dataclass_fields__
            }
            return AppSettings(**known)
        except (OSError, ValueError, TypeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        payload = json.dumps(asdict(settings), ensure_ascii=False, indent=2)
        fd, temp_name = tempfile.mkstemp(
            prefix="settings_",
            suffix=".json.tmp",
            dir=str(self.path.parent),
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
