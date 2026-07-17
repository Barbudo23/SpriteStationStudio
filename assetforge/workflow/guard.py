"""Decide whether a manifest may run against persisted workflow state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from assetforge.workflow.checkpoint import WorkflowCheckpoint


class WorkflowAction(str, Enum):
    RUN = "RUN"
    ALREADY_COMPLETE = "ALREADY_COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class WorkflowDecision:
    action: WorkflowAction
    message: str


class ProductionWorkflowGuard:
    """Protect completed iterations from accidental local reruns."""

    def evaluate(
        self,
        manifest_iteration: int,
        checkpoint: WorkflowCheckpoint | None,
        *,
        force: bool = False,
    ) -> WorkflowDecision:
        if not 1 <= manifest_iteration <= 10:
            return WorkflowDecision(
                WorkflowAction.BLOCKED,
                "Manifest iteration must be between 1 and 10.",
            )
        if force:
            return WorkflowDecision(
                WorkflowAction.RUN,
                f"Forced rebuild of iteration {manifest_iteration:02d}.",
            )
        if checkpoint is None:
            return WorkflowDecision(
                WorkflowAction.RUN,
                f"Starting iteration {manifest_iteration:02d}.",
            )
        if checkpoint.completed_iteration == manifest_iteration:
            return WorkflowDecision(
                WorkflowAction.ALREADY_COMPLETE,
                (
                    f"Iteration {manifest_iteration:02d} is already complete. "
                    f"Next iteration: {self._format_next(checkpoint.next_iteration)}."
                ),
            )
        if checkpoint.completed_iteration > manifest_iteration:
            return WorkflowDecision(
                WorkflowAction.BLOCKED,
                (
                    f"Manifest iteration {manifest_iteration:02d} is older than checkpoint "
                    f"iteration {checkpoint.completed_iteration:02d}."
                ),
            )
        if checkpoint.next_iteration != manifest_iteration:
            return WorkflowDecision(
                WorkflowAction.BLOCKED,
                (
                    f"Checkpoint expects iteration {self._format_next(checkpoint.next_iteration)}, "
                    f"not {manifest_iteration:02d}."
                ),
            )
        return WorkflowDecision(
            WorkflowAction.RUN,
            f"Resuming with iteration {manifest_iteration:02d}.",
        )

    @staticmethod
    def _format_next(iteration: int | None) -> str:
        return f"{iteration:02d}" if iteration is not None else "none"
