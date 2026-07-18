from pathlib import Path

import yaml

from assetforge.core.config_loader import ConfigLoader
from assetforge.providers import MockProvider
from assetforge.workflow import CanaryRunner


def test_canary_generates_one_view_and_does_not_advance_workflow(tmp_path):
    root = Path(__file__).parents[1]
    configs = ConfigLoader(root / "configs" / "core").load_all()
    project_root = tmp_path / "project"
    references = project_root / "References"
    references.mkdir(parents=True)
    for filename in configs["MPI.yaml"]["input"]["references"].values():
        (references / filename).write_bytes(b"reference fixture")
    workflow_state = project_root / "Workflow_State.yaml"
    workflow_state.write_text("status: SIMULATED\n", encoding="utf-8")
    before = workflow_state.read_bytes()

    result = CanaryRunner().run(
        project_root=project_root,
        iteration=2,
        configs=configs,
        provider=MockProvider(),
        camera_id="CAM01",
    )

    report = yaml.safe_load(result.report.read_text(encoding="utf-8"))
    assert result.status == "REVIEW_REQUIRED"
    assert result.asset.is_file()
    assert report["camera_id"] == "CAM01"
    assert report["workflow_state_advanced"] is False
    assert workflow_state.read_bytes() == before
