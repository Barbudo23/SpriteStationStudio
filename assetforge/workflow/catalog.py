"""Discover approved Production Iteration manifests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from assetforge.workflow.checkpoint import WorkflowCheckpoint
from assetforge.workflow.manifest import IterationManifest, IterationManifestLoader


@dataclass(frozen=True)
class ManifestCatalogEntry:
    manifest: IterationManifest
    path: Path


class ManifestAwaitingApprovalError(ValueError):
    """Raised when the next workflow slot has no approved local manifest."""


class ManifestCatalog:
    """Validated index of explicitly approved iteration manifests."""

    def __init__(self, entries: dict[int, ManifestCatalogEntry]) -> None:
        self._entries = dict(sorted(entries.items()))

    @classmethod
    def discover(cls, core_manifest: Path, iterations_root: Path) -> "ManifestCatalog":
        loader = IterationManifestLoader()
        candidates = [core_manifest]
        if iterations_root.is_dir():
            candidates.extend(sorted(iterations_root.glob("*.yaml")))

        entries: dict[int, ManifestCatalogEntry] = {}
        for path in candidates:
            manifest = loader.load(path)
            status = str(manifest.data.get("status", "")).strip().casefold()
            is_frozen_foundation = manifest.iteration == 1 and status == "frozen"
            if status != "approved" and not is_frozen_foundation:
                continue
            if manifest.iteration in entries:
                previous = entries[manifest.iteration].path
                raise ValueError(
                    f"Duplicate manifest for iteration {manifest.iteration:02d}: "
                    f"{previous} and {path}."
                )
            entries[manifest.iteration] = ManifestCatalogEntry(manifest, path)
        if 1 not in entries:
            raise ValueError("Manifest catalog must contain iteration 01.")
        return cls(entries)

    @property
    def entries(self) -> tuple[ManifestCatalogEntry, ...]:
        return tuple(self._entries.values())

    def get(self, iteration: int) -> ManifestCatalogEntry | None:
        return self._entries.get(iteration)

    def next_entry(self, checkpoint: WorkflowCheckpoint | None) -> ManifestCatalogEntry:
        iteration = 1 if checkpoint is None else checkpoint.next_iteration
        if iteration is None:
            raise ValueError("All ten Production Iterations are complete.")
        entry = self.get(iteration)
        if entry is None:
            raise ManifestAwaitingApprovalError(
                f"Iteration {iteration:02d} is awaiting an approved manifest."
            )
        return entry

    def describe(self, checkpoint: WorkflowCheckpoint | None) -> tuple[str, ...]:
        completed = checkpoint.completed_iteration if checkpoint else 0
        lines: list[str] = []
        for iteration in range(1, 11):
            entry = self.get(iteration)
            if iteration <= completed:
                status = checkpoint.status if checkpoint else "COMPLETE"
            elif entry is not None:
                status = "APPROVED"
            elif iteration == completed + 1:
                status = "AWAITING_MANIFEST"
            else:
                status = "NOT_CONFIGURED"
            name = entry.manifest.name if entry else "—"
            lines.append(f"{iteration:02d}  {status:<18} {name}")
        return tuple(lines)
