from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from assetforge.core.state import AssetForgeState
from assetforge.engine.gs008_report import GS008Report
from assetforge.exporters import AssetPackager


def make_finalization_state(tmp_path: Path) -> AssetForgeState:
    project_root = tmp_path / "project"
    iteration_root = project_root / "iterations" / "iteration_01"
    export_root = iteration_root / "Export"
    for directory in ("PNG", "SpriteSheet", "GIF"):
        (export_root / directory).mkdir(parents=True, exist_ok=True)
        (export_root / directory / f"{directory}.asset").write_text(directory, encoding="utf-8")
    (export_root / "Export_Metadata.yaml").write_text("status: PASS\n", encoding="utf-8")
    (iteration_root / "Production_Report").mkdir()
    (iteration_root / "Production_Report" / "Production_Report.md").write_text(
        "Pending\n", encoding="utf-8"
    )
    (iteration_root / "Readme.md").write_text("Iteration\n", encoding="utf-8")
    initial = AssetPackager().package(
        export_root=export_root,
        iteration_root=iteration_root,
        package_directory=project_root / "packages",
        package_name="Iteration_01_Base_Stack_02_Rev00.zip",
    )
    return AssetForgeState(
        iteration=1,
        qa_score=100.0,
        metadata={
            "project_root": str(project_root),
            "generation": {"provider": "mock"},
            "qa": {"status": "APPROVED"},
            "export": {
                "status": "PASS",
                "root": str(export_root),
                "png_files": ["one", "two"],
            },
            "package": {
                "status": "PASS",
                "file": str(initial.package_file),
                "metadata_file": str(initial.metadata_file),
                "sha256": initial.checksum,
            },
        },
    )


def test_report_completes_iteration_and_rebuilds_final_package(tmp_path):
    state = make_finalization_state(tmp_path)
    old_checksum = state.metadata["package"]["sha256"]

    result = GS008Report().execute(state)

    package_path = Path(result.metadata["package"]["file"])
    report_path = Path(result.metadata["reporting"]["production_report"])
    assert result.errors == []
    assert result.approved is True
    assert result.progress == 0.1
    assert result.metadata["iteration_status"] == "COMPLETE"
    assert result.metadata["next_iteration"] == 2
    assert result.metadata["reporting"]["status"] == "COMPLETE"
    assert "Status: COMPLETE" in report_path.read_text(encoding="utf-8")
    assert result.metadata["package"]["sha256"] != old_checksum
    assert result.metadata["package"]["sha256"] == sha256(package_path.read_bytes()).hexdigest()
    with ZipFile(package_path) as archive:
        report = archive.read("Production_Report.md").decode("utf-8")
        assert "Status: COMPLETE" in report


def test_report_requires_package(tmp_path):
    state = AssetForgeState(metadata={"project_root": str(tmp_path)})
    result = GS008Report().execute(state)
    assert result.approved is False
    assert result.errors == ["Successful package is required before reporting."]
