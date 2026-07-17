"""Persistent workflow checkpoints for safe iteration resume."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class WorkflowCheckpoint:
    status: str
    completed_iteration: int
    next_iteration: int | None
    project_progress: float
    package_file: str
    package_sha256: str
    stack_revision: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkflowCheckpoint":
        checkpoint = cls(
            status=str(data["status"]),
            completed_iteration=int(data["completed_iteration"]),
            next_iteration=(
                int(data["next_iteration"])
                if data.get("next_iteration") is not None
                else None
            ),
            project_progress=float(data["project_progress"]),
            package_file=str(data["package_file"]),
            package_sha256=str(data["package_sha256"]),
            stack_revision=str(data["stack_revision"]),
        )
        checkpoint.validate()
        return checkpoint

    def validate(self) -> None:
        if self.status != "COMPLETE":
            raise ValueError("Checkpoint status must be COMPLETE.")
        if not 1 <= self.completed_iteration <= 10:
            raise ValueError("Completed iteration must be between 1 and 10.")
        expected_progress = self.completed_iteration / 10.0
        if abs(self.project_progress - expected_progress) > 1e-9:
            raise ValueError("Checkpoint progress does not match completed iteration.")
        expected_next = self.completed_iteration + 1 if self.completed_iteration < 10 else None
        if self.next_iteration != expected_next:
            raise ValueError("Checkpoint next iteration is inconsistent.")
        if not self.package_file or not self.package_sha256:
            raise ValueError("Checkpoint package identity is required.")


class WorkflowCheckpointStore:
    """Read and atomically replace the current project workflow state."""

    filename = "Workflow_State.yaml"

    def save(self, project_root: Path, checkpoint: WorkflowCheckpoint) -> Path:
        checkpoint.validate()
        project_root.mkdir(parents=True, exist_ok=True)
        destination = project_root / self.filename
        temporary = project_root / f"{self.filename}.tmp"
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(asdict(checkpoint), stream, sort_keys=False)
        temporary.replace(destination)
        return destination

    def load(self, project_root: Path) -> WorkflowCheckpoint | None:
        path = project_root / self.filename
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError("Workflow checkpoint must contain a YAML mapping.")
        return WorkflowCheckpoint.from_mapping(data)
