from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import yaml

from assetforge.core.state import AssetForgeState
from assetforge.engine.gs007_package import GS007Package


def make_packaging_state(tmp_path: Path) -> AssetForgeState:
    project_root = tmp_path / "project"
    iteration_root = project_root / "iterations" / "iteration_01"
    export_root = iteration_root / "Export"
    for directory in ("PNG", "SpriteSheet", "GIF"):
        (export_root / directory).mkdir(parents=True, exist_ok=True)
        (export_root / directory / f"{directory}.asset").write_text(directory, encoding="utf-8")
    (export_root / "Export_Metadata.yaml").write_text("status: PASS\n", encoding="utf-8")
    (iteration_root / "Production_Report").mkdir()
    (iteration_root / "Production_Report" / "Production_Report.md").write_text(
        "# Production Report\n", encoding="utf-8"
    )
    (iteration_root / "Readme.md").write_text("# Iteration 01\n", encoding="utf-8")
    return AssetForgeState(
        iteration=1,
        configs={"Manifest.yaml": {"output": {"package": "Iteration_01_Base.zip"}}},
        metadata={
            "project_root": str(project_root),
            "stack_revision": "Stack_02_Rev00",
            "export": {"status": "PASS", "root": str(export_root)},
        },
    )


def test_package_contains_required_structure_and_checksum(tmp_path):
    result = GS007Package().execute(make_packaging_state(tmp_path))

    package = result.metadata["package"]
    package_path = Path(package["file"])
    assert result.errors == []
    assert result.approved is True
    assert package_path.name == "Iteration_01_Base_Stack_02_Rev00.zip"
    assert package["sha256"] == sha256(package_path.read_bytes()).hexdigest()
    with ZipFile(package_path) as archive:
        assert set(archive.namelist()) == {
            "PNG/PNG.asset",
            "SpriteSheet/SpriteSheet.asset",
            "GIF/GIF.asset",
            "Export_Metadata.yaml",
            "Production_Report.md",
            "Readme.md",
        }
    metadata = yaml.safe_load(Path(package["metadata_file"]).read_text(encoding="utf-8"))
    assert metadata["sha256"] == package["sha256"]


def test_package_is_reproducible(tmp_path):
    state = make_packaging_state(tmp_path)
    first = GS007Package().execute(state).metadata["package"]["sha256"]
    second = GS007Package().execute(state).metadata["package"]["sha256"]
    assert first == second


def test_package_requires_successful_export(tmp_path):
    state = AssetForgeState(metadata={"project_root": str(tmp_path)})
    result = GS007Package().execute(state)
    assert result.approved is False
    assert result.errors == ["Successful export is required before packaging."]
