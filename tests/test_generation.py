from pathlib import Path

from assetforge.core.config_loader import ConfigLoader
from assetforge.core.state import AssetForgeState
from assetforge.engine.gs004_generation import GS004Generation
from assetforge.providers import MockProvider


def make_ready_state(project_root: Path) -> AssetForgeState:
    root = Path(__file__).parents[1]
    configs = ConfigLoader(root / "configs" / "core").load_all()
    cameras = configs["CameraLibrary.yaml"]["cameras"]
    return AssetForgeState(
        project_name="Character_Project",
        iteration=1,
        configs=configs,
        metadata={
            "project_root": str(project_root),
            "provider": MockProvider(),
            "character_profile": {"status": "LOCKED"},
            "active_camera_profile": {
                "status": "LOCKED",
                "cameras": cameras,
            },
        },
    )


def test_generation_dispatches_one_deterministic_asset_per_camera(tmp_path):
    result = GS004Generation().execute(make_ready_state(tmp_path))

    assert result.errors == []
    assert result.approved is True
    assert len(result.generated_assets) == 8
    assert len(set(result.generated_assets)) == 8
    assert result.metadata["generation"]["provider"] == "mock"
    assert result.metadata["generation"]["simulation"] is True
    assert [step["camera_id"] for step in result.metadata["generation"]["steps"]] == [
        f"CAM{index:02d}" for index in range(1, 9)
    ]


def test_generation_requires_locked_character_profile(tmp_path):
    state = make_ready_state(tmp_path)
    state.metadata["character_profile"]["status"] = "DRAFT"

    result = GS004Generation().execute(state)

    assert result.approved is False
    assert result.errors == ["Character profile must be locked before generation."]
    assert result.generated_assets == []


def test_generation_requires_provider_contract(tmp_path):
    state = make_ready_state(tmp_path)
    state.metadata["provider"] = object()

    result = GS004Generation().execute(state)

    assert result.approved is False
    assert result.errors == ["A valid BaseProvider is required."]
