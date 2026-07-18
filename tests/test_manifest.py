from pathlib import Path

import pytest

from assetforge.workflow import IterationManifest, IterationManifestLoader


def test_iteration_two_manifest_is_valid_and_approved():
    root = Path(__file__).parents[1]
    manifest = IterationManifestLoader().load(
        root / "configs" / "iterations" / "Iteration_02_Walk.yaml"
    )
    assert manifest.iteration == 2
    assert manifest.name == "Walk"
    assert manifest.progress == 0.2
    assert manifest.package == "Iteration_02_Walk.zip"
    assert manifest.next_iteration == 3


def test_iteration_five_draft_manifest_is_valid_but_awaiting_approval():
    root = Path(__file__).parents[1]
    manifest = IterationManifestLoader().load(
        root / "configs" / "iterations" / "Iteration_05_Aim.yaml"
    )
    assert manifest.iteration == 5
    assert manifest.name == "Aim"
    assert manifest.progress == 0.5
    assert manifest.package == "Iteration_05_Aim.zip"
    assert manifest.next_iteration == 6
    assert manifest.data["status"] == "Awaiting Approval"


def test_manifest_rejects_progress_that_does_not_match_iteration():
    data = {
        "iteration": {"id": 2, "name": "Walk", "progress": "10%"},
        "output": {"package": "Walk.zip"},
        "next_iteration": {"id": 3},
    }
    with pytest.raises(ValueError, match="progress"):
        IterationManifest.from_mapping(data)


def test_manifest_rejects_skipped_next_iteration():
    data = {
        "iteration": {"id": 2, "name": "Walk", "progress": "20%"},
        "output": {"package": "Walk.zip"},
        "next_iteration": {"id": 4},
    }
    with pytest.raises(ValueError, match="next iteration"):
        IterationManifest.from_mapping(data)
