"""Production Iteration manifest loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class IterationManifest:
    iteration: int
    name: str
    progress: float
    package: str
    next_iteration: int | None
    data: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "IterationManifest":
        iteration_data = data.get("iteration")
        output = data.get("output")
        if not isinstance(iteration_data, dict):
            raise ValueError("Manifest iteration must be a mapping.")
        if not isinstance(output, dict):
            raise ValueError("Manifest output must be a mapping.")
        iteration = int(iteration_data["id"])
        name = str(iteration_data.get("name", "")).strip()
        progress = cls._parse_progress(iteration_data.get("progress"))
        package = str(output.get("package", "")).strip()
        next_data = data.get("next_iteration")
        next_iteration = (
            int(next_data["id"])
            if isinstance(next_data, dict) and next_data.get("id") is not None
            else None
        )
        manifest = cls(iteration, name, progress, package, next_iteration, data)
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if not 1 <= self.iteration <= 10:
            raise ValueError("Manifest iteration must be between 1 and 10.")
        if not self.name:
            raise ValueError("Manifest iteration name is required.")
        if abs(self.progress - self.iteration / 10.0) > 1e-9:
            raise ValueError("Manifest progress does not match iteration.")
        if not self.package.lower().endswith(".zip"):
            raise ValueError("Manifest output package must be a ZIP filename.")
        expected_next = self.iteration + 1 if self.iteration < 10 else None
        if self.next_iteration != expected_next:
            raise ValueError("Manifest next iteration is inconsistent.")

    @staticmethod
    def _parse_progress(value: Any) -> float:
        if isinstance(value, str) and value.endswith("%"):
            return float(value[:-1]) / 100.0
        return float(value)


class IterationManifestLoader:
    def load(self, path: Path) -> IterationManifest:
        if not path.is_file():
            raise FileNotFoundError(f"Manifest not found: {path}")
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError("Manifest must contain a YAML mapping.")
        return IterationManifest.from_mapping(data)
