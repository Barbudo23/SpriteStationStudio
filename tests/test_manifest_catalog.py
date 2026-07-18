from pathlib import Path

import pytest

from assetforge.workflow import (
    ManifestAwaitingApprovalError,
    ManifestCatalog,
    WorkflowCheckpoint,
)


def project_catalog() -> ManifestCatalog:
    root = Path(__file__).parents[1]
    return ManifestCatalog.discover(
        root / "configs" / "core" / "Manifest.yaml",
        root / "configs" / "iterations",
    )


def checkpoint(iteration: int) -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        status="SIMULATED",
        completed_iteration=iteration,
        next_iteration=iteration + 1 if iteration < 10 else None,
        project_progress=iteration / 10.0,
        package_file=f"Iteration_{iteration:02d}.zip",
        package_sha256="abc123",
        stack_revision="Stack_03_Rev00",
        mode="simulation",
    )


def test_catalog_discovers_only_approved_local_manifests():
    catalog = project_catalog()
    assert [entry.manifest.iteration for entry in catalog.entries] == [1, 2]


def test_catalog_selects_iteration_two_after_iteration_one():
    entry = project_catalog().next_entry(checkpoint(1))
    assert entry.manifest.iteration == 2
    assert entry.manifest.name == "Walk"


def test_catalog_blocks_when_next_manifest_is_not_approved():
    with pytest.raises(ManifestAwaitingApprovalError, match="awaiting an approved manifest"):
        project_catalog().next_entry(checkpoint(2))


def test_catalog_plan_marks_next_missing_manifest():
    lines = project_catalog().describe(checkpoint(2))
    assert lines[0].startswith("01  SIMULATED")
    assert lines[1].startswith("02  SIMULATED")
    assert lines[2].startswith("03  AWAITING_MANIFEST")


def test_catalog_rejects_duplicate_iteration(tmp_path):
    root = Path(__file__).parents[1]
    duplicate = tmp_path / "Duplicate.yaml"
    duplicate.write_text(
        (root / "configs" / "core" / "Manifest.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate manifest"):
        ManifestCatalog.discover(
            root / "configs" / "core" / "Manifest.yaml",
            tmp_path,
        )
