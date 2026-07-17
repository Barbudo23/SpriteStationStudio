from pathlib import Path

import pytest

from assetforge.workflow import WorkflowCheckpoint, WorkflowCheckpointStore


def make_checkpoint() -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        status="COMPLETE",
        completed_iteration=1,
        next_iteration=2,
        project_progress=0.1,
        package_file="packages/Iteration_01.zip",
        package_sha256="abc123",
        stack_revision="Stack_03_Rev00",
    )


def test_checkpoint_round_trip_is_atomic(tmp_path):
    store = WorkflowCheckpointStore()
    path = store.save(tmp_path, make_checkpoint())

    assert path == tmp_path / "Workflow_State.yaml"
    assert not (tmp_path / "Workflow_State.yaml.tmp").exists()
    assert store.load(tmp_path) == make_checkpoint()


def test_checkpoint_returns_none_when_workflow_has_not_started(tmp_path):
    assert WorkflowCheckpointStore().load(tmp_path) is None


def test_checkpoint_rejects_inconsistent_progress():
    checkpoint = WorkflowCheckpoint(
        status="COMPLETE",
        completed_iteration=2,
        next_iteration=3,
        project_progress=0.1,
        package_file="package.zip",
        package_sha256="abc123",
        stack_revision="Stack_03_Rev00",
    )

    with pytest.raises(ValueError, match="progress"):
        checkpoint.validate()


def test_checkpoint_rejects_inconsistent_next_iteration():
    checkpoint = WorkflowCheckpoint(
        status="COMPLETE",
        completed_iteration=1,
        next_iteration=4,
        project_progress=0.1,
        package_file="package.zip",
        package_sha256="abc123",
        stack_revision="Stack_03_Rev00",
    )

    with pytest.raises(ValueError, match="next iteration"):
        checkpoint.validate()
