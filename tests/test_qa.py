from copy import deepcopy
from pathlib import Path

from assetforge.core.config_loader import ConfigLoader
from assetforge.core.state import AssetForgeState
from assetforge.engine.gs005_qa import GS005QA


def make_generated_state() -> AssetForgeState:
    root = Path(__file__).parents[1]
    configs = ConfigLoader(root / "configs" / "core").load_all()
    cameras = configs["CameraLibrary.yaml"]["cameras"]
    assets = [f"mock://generation/{camera_id}.png" for camera_id in cameras]
    steps = [
        {"camera_id": camera_id, "provider": "mock", "assets": [asset]}
        for camera_id, asset in zip(cameras, assets)
    ]
    return AssetForgeState(
        configs=configs,
        generated_assets=assets,
        metadata={
            "character_profile": {"status": "LOCKED"},
            "active_camera_profile": {"status": "LOCKED", "cameras": cameras},
            "generation": {"status": "PASS", "provider": "mock", "steps": steps},
        },
    )


def test_qa_approves_complete_traceable_generation():
    result = GS005QA().execute(make_generated_state())

    assert result.errors == []
    assert result.approved is True
    assert result.qa_score == 100.0
    assert result.metadata["qa"]["status"] == "APPROVED"
    assert result.metadata["qa"]["mode"] == "structural"
    assert result.reports == ["QA_Report.md"]


def test_qa_requires_rework_for_duplicate_assets():
    state = make_generated_state()
    state.generated_assets[-1] = state.generated_assets[0]

    result = GS005QA().execute(state)

    assert result.approved is False
    assert result.metadata["qa"]["status"] == "REWORK"
    assert result.qa_score < 95
    assert result.errors == ["QA requires rework: asset_uniqueness."]


def test_qa_requires_successful_generation():
    state = make_generated_state()
    state.metadata["generation"] = deepcopy(state.metadata["generation"])
    state.metadata["generation"]["status"] = "FAILED"

    result = GS005QA().execute(state)

    assert result.approved is False
    assert result.errors == ["Generation must pass before QA."]
