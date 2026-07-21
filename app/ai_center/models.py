from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AIProvider(str, Enum):
    OPENAI = "openai"
    CODEX = "codex"
    CLOSEAI = "closeai"


@dataclass(frozen=True)
class AISettings:
    schema_version: int = 1
    provider: AIProvider = AIProvider.CODEX
    openai_model: str = "gpt-image-2"
    closeai_model: str = "gpt-image-1.5"
    quality: str = "low"
    size: str = "1024x1024"
    background: str = "auto"
    max_images_per_run: int = 3

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported AI settings schema version.")
        if self.quality not in {"auto", "low", "medium", "high"}:
            raise ValueError("AI image quality must be auto, low, medium, or high.")
        if self.background not in {"auto", "opaque", "transparent"}:
            raise ValueError("AI image background must be auto, opaque, or transparent.")
        if not 1 <= self.max_images_per_run <= 3:
            raise ValueError("AI image run limit must be between 1 and 3.")
        if not self.openai_model.strip() or not self.closeai_model.strip():
            raise ValueError("AI image model names must not be empty.")


@dataclass(frozen=True)
class AIGenerationRequest:
    prompt: str
    reference_paths: tuple[Path, ...]
    output_directory: Path
    camera_id: str = "CAM01"

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Generation prompt must not be empty.")
        if not 1 <= len(self.reference_paths) <= 4:
            raise ValueError("AI Center requires between one and four reference images.")
        for path in self.reference_paths:
            if not path.expanduser().is_file():
                raise FileNotFoundError(f"Reference image not found: {path}")
        if not self.camera_id.strip():
            raise ValueError("Camera ID must not be empty.")
