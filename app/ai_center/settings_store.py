from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os
import tempfile

from app.ai_center.models import AIProvider, AISettings
from app.brand import config_path, legacy_config_path


class AISettingsStore:
    """Atomic non-secret settings store. API keys are never persisted."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or config_path("ai_center.json")).expanduser().resolve()
        self.legacy_path = (
            None if path is not None else legacy_config_path("ai_center.json").resolve()
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AISettings:
        read_path = self.path
        if not read_path.is_file() and self.legacy_path and self.legacy_path.is_file():
            read_path = self.legacy_path
        if not read_path.is_file():
            return AISettings()
        try:
            payload = json.loads(read_path.read_text(encoding="utf-8"))
            defaults = AISettings()
            settings = AISettings(
                schema_version=int(payload.get("schema_version", defaults.schema_version)),
                provider=AIProvider(payload.get("provider", defaults.provider.value)),
                openai_model=str(payload.get("openai_model", defaults.openai_model)),
                closeai_model=str(payload.get("closeai_model", defaults.closeai_model)),
                quality=str(payload.get("quality", defaults.quality)),
                size=str(payload.get("size", defaults.size)),
                background=str(payload.get("background", defaults.background)),
                max_images_per_run=int(
                    payload.get("max_images_per_run", defaults.max_images_per_run)
                ),
            )
            settings.validate()
            return settings
        except (OSError, ValueError, TypeError):
            return AISettings()

    def save(self, settings: AISettings) -> None:
        settings.validate()
        payload = asdict(settings)
        payload["provider"] = settings.provider.value
        fd, temp_name = tempfile.mkstemp(
            prefix="ai_center_", suffix=".json.tmp", dir=str(self.path.parent), text=True
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)
