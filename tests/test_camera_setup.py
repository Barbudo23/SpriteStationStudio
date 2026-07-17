from copy import deepcopy
from pathlib import Path

from assetforge.core.config_loader import ConfigLoader
from assetforge.core.state import AssetForgeState
from assetforge.engine.gs003_camera_setup import GS003CameraSetup


def load_camera_library() -> dict:
    root = Path(__file__).parents[1] / "configs" / "core"
    return ConfigLoader(root).load("CameraLibrary.yaml")


def test_camera_setup_locks_all_eight_configured_views():
    state = AssetForgeState(
        configs={"CameraLibrary.yaml": load_camera_library()},
    )

    result = GS003CameraSetup().execute(state)

    profile = result.metadata["active_camera_profile"]
    assert result.errors == []
    assert result.approved is True
    assert result.current_step == "GS003"
    assert profile["status"] == "LOCKED"
    assert tuple(profile["cameras"]) == GS003CameraSetup.CAMERA_IDS
    assert profile["cameras"]["CAM01"] == {"name": "Front", "yaw": 0}
    assert profile["cameras"]["CAM08"] == {"name": "FrontLeft", "yaw": 315}


def test_camera_setup_stops_when_a_camera_is_missing():
    library = deepcopy(load_camera_library())
    del library["cameras"]["CAM08"]
    state = AssetForgeState(configs={"CameraLibrary.yaml": library})

    result = GS003CameraSetup().execute(state)

    assert result.approved is False
    assert result.errors == ["Camera set is incomplete: CAM08"]
    assert "active_camera_profile" not in result.metadata


def test_camera_setup_stops_when_lock_rule_is_disabled():
    library = deepcopy(load_camera_library())
    library["rules"]["preserve_scale"] = False
    state = AssetForgeState(configs={"CameraLibrary.yaml": library})

    result = GS003CameraSetup().execute(state)

    assert result.approved is False
    assert result.errors == ["Camera lock rules are not enabled: preserve_scale"]
