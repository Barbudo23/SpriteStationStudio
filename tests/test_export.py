from pathlib import Path

from PIL import Image
import yaml

from assetforge.core.state import AssetForgeState
from assetforge.engine.gs006_export import GS006Export


def make_png(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (16, 16), color).save(path, format="PNG")


def test_export_creates_all_required_formats_and_metadata(tmp_path):
    sources = []
    for index in range(8):
        source = tmp_path / f"source_{index}.png"
        make_png(source, (index * 20, 40, 80, 200))
        sources.append(str(source))
    state = AssetForgeState(
        iteration=1,
        generated_assets=sources,
        metadata={
            "project_root": str(tmp_path / "project"),
            "qa": {"status": "APPROVED"},
        },
    )

    result = GS006Export().execute(state)

    export = result.metadata["export"]
    assert result.errors == []
    assert result.approved is True
    assert len(export["png_files"]) == 8
    assert all(Path(path).is_file() for path in export["png_files"])
    assert Path(export["sprite_sheet"]).is_file()
    assert Path(export["gif_preview"]).is_file()
    metadata_path = Path(export["metadata_file"])
    assert metadata_path.is_file()
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "PASS"
    assert metadata["formats"] == ["PNG", "SpriteSheet", "GIF"]


def test_export_requires_qa_approval(tmp_path):
    state = AssetForgeState(
        generated_assets=[],
        metadata={"project_root": str(tmp_path), "qa": {"status": "REWORK"}},
    )

    result = GS006Export().execute(state)

    assert result.approved is False
    assert result.errors == ["QA approval is required before export."]


def test_export_reports_missing_generated_file(tmp_path):
    state = AssetForgeState(
        generated_assets=[str(tmp_path / "missing.png")],
        metadata={"project_root": str(tmp_path), "qa": {"status": "APPROVED"}},
    )

    result = GS006Export().execute(state)

    assert result.approved is False
    assert result.errors[0].startswith("Export failed: Generated assets are missing:")
