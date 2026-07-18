from pathlib import Path

from PIL import Image
import pytest
import yaml

from assetforge.core.config_loader import ConfigLoader
from assetforge.workflow import CodexBridge


def make_project(tmp_path):
    root = Path(__file__).parents[1]
    configs = ConfigLoader(root / "configs" / "core").load_all()
    project_root = tmp_path / "project"
    references = project_root / "References"
    references.mkdir(parents=True)
    for filename in configs["MPI.yaml"]["input"]["references"].values():
        Image.new("RGB", (4, 4), "white").save(references / filename)
    return project_root, configs


def test_codex_bridge_prepares_one_view_job_without_advancing_state(tmp_path):
    project_root, configs = make_project(tmp_path)
    state_path = project_root / "Workflow_State.yaml"
    state_path.write_text("status: SIMULATED\n", encoding="utf-8")
    before = state_path.read_bytes()

    job = CodexBridge().prepare(
        project_root=project_root,
        iteration=2,
        configs=configs,
        camera_id="CAM01",
    )

    request = yaml.safe_load(job.request.read_text(encoding="utf-8"))
    assert request["status"] == "AWAITING_CODEX"
    assert request["provider"] == "codex-built-in"
    assert len(request["reference_images"]) == 4
    assert "#ff00ff" in request["prompt"]
    assert state_path.read_bytes() == before


def test_codex_bridge_imports_valid_alpha_png_for_review(tmp_path):
    project_root, configs = make_project(tmp_path)
    bridge = CodexBridge()
    job = bridge.prepare(
        project_root=project_root,
        iteration=2,
        configs=configs,
        camera_id="CAM01",
    )
    source = tmp_path / "generated.png"
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(2, 6):
        for y in range(1, 7):
            image.putpixel((x, y), (80, 90, 60, 255))
    image.save(source)

    result = bridge.import_result(
        job=job,
        source_image=source,
        iteration=2,
        camera_id="CAM01",
    )

    report = yaml.safe_load(result.report.read_text(encoding="utf-8"))
    assert result.status == "REVIEW_REQUIRED"
    assert result.asset.is_file()
    assert report["alpha_validated"] is True
    assert report["workflow_state_advanced"] is False


def test_codex_bridge_rejects_png_without_alpha(tmp_path):
    project_root, configs = make_project(tmp_path)
    bridge = CodexBridge()
    job = bridge.prepare(project_root=project_root, iteration=2, configs=configs)
    source = tmp_path / "opaque.png"
    Image.new("RGB", (8, 8), "white").save(source)

    with pytest.raises(ValueError, match="RGBA alpha"):
        bridge.import_result(
            job=job,
            source_image=source,
            iteration=2,
            camera_id="CAM01",
        )


def make_imported_canary(tmp_path):
    project_root, configs = make_project(tmp_path)
    bridge = CodexBridge()
    job = bridge.prepare(project_root=project_root, iteration=2, configs=configs)
    source = tmp_path / "generated.png"
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(2, 6):
        for y in range(1, 7):
            image.putpixel((x, y), (80, 90, 60, 255))
    image.save(source)
    bridge.import_result(
        job=job,
        source_image=source,
        iteration=2,
        camera_id="CAM01",
    )
    return project_root, configs, bridge


def test_codex_canary_requires_explicit_approval_before_batch(tmp_path):
    project_root, configs, bridge = make_imported_canary(tmp_path)

    with pytest.raises(ValueError, match="APPROVED canary"):
        bridge.prepare_batch(project_root=project_root, iteration=2, configs=configs)


def test_codex_canary_approval_records_reviewer_time_and_checksum(tmp_path):
    project_root, _, bridge = make_imported_canary(tmp_path)

    result = bridge.approve_canary(
        project_root=project_root,
        iteration=2,
        approved_by="project-owner",
        approved_at="2026-07-18T12:00:00+00:00",
    )

    report = yaml.safe_load(result.report.read_text(encoding="utf-8"))
    assert result.status == "APPROVED"
    assert report["approved_by"] == "project-owner"
    assert report["approved_at"] == "2026-07-18T12:00:00+00:00"
    assert len(report["asset_sha256"]) == 64
    assert report["workflow_state_advanced"] is False


def test_codex_batch_prepares_only_remaining_seven_cameras(tmp_path):
    project_root, configs, bridge = make_imported_canary(tmp_path)
    bridge.approve_canary(
        project_root=project_root,
        iteration=2,
        approved_at="2026-07-18T12:00:00+00:00",
    )

    batch = bridge.prepare_batch(project_root=project_root, iteration=2, configs=configs)

    plan = yaml.safe_load(batch.plan.read_text(encoding="utf-8"))
    assert batch.status == "READY"
    assert len(batch.jobs) == 7
    assert plan["completed_cameras"] == ["CAM01"]
    assert plan["pending_cameras"] == [f"CAM{index:02d}" for index in range(2, 9)]
    assert plan["generation_started"] is False
    assert plan["workflow_state_advanced"] is False


def test_codex_batch_import_preserves_canary_and_updates_plan(tmp_path):
    project_root, configs, bridge = make_imported_canary(tmp_path)
    bridge.approve_canary(
        project_root=project_root,
        iteration=2,
        approved_at="2026-07-18T12:00:00+00:00",
    )
    batch = bridge.prepare_batch(project_root=project_root, iteration=2, configs=configs)
    canary_report = project_root / "canary" / "iteration_02" / "Canary_Result.yaml"
    canary_before = canary_report.read_bytes()
    source = tmp_path / "cam02.png"
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(2, 6):
        for y in range(1, 7):
            image.putpixel((x, y), (80, 90, 60, 255))
    image.save(source)

    result = bridge.import_batch_result(
        job=batch.jobs[0],
        source_image=source,
        project_root=project_root,
        iteration=2,
        camera_id="CAM02",
    )

    plan = yaml.safe_load(batch.plan.read_text(encoding="utf-8"))
    report = yaml.safe_load(result.report.read_text(encoding="utf-8"))
    assert result.status == "REVIEW_REQUIRED"
    assert result.report.name == "CAM02_Result.yaml"
    assert report["camera_id"] == "CAM02"
    assert plan["status"] == "IN_PROGRESS"
    assert plan["review_required_cameras"] == ["CAM02"]
    assert "CAM02" not in plan["pending_cameras"]
    assert canary_report.read_bytes() == canary_before
