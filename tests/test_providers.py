import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from assetforge.providers import (
    GenerationRequest,
    MockProvider,
    OpenAIImageConfig,
    OpenAIImageProvider,
)


def test_generation_request_rejects_empty_prompt():
    with pytest.raises(ValueError, match="must not be empty"):
        GenerationRequest(prompt="   ")


def test_mock_provider_is_deterministic_and_provider_neutral():
    provider = MockProvider()
    request = GenerationRequest(
        prompt="medium rifleman turnaround",
        reference_paths=("Front.png", "Back.png"),
    )

    first = provider.generate(request)
    second = provider.generate(request)

    assert first == second
    assert first.provider == "mock"
    assert provider.is_simulation is True
    assert first.assets[0].startswith("mock://generation/")
    assert first.metadata["deterministic"] is True


class FakeImages:
    def __init__(self, encoded_image: str):
        self.encoded_image = encoded_image
        self.calls = []

    def edit(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=self.encoded_image)],
            _request_id="req_test",
        )


def encoded_test_png() -> str:
    buffer = BytesIO()
    Image.new("RGBA", (2, 2), (20, 40, 60, 255)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_openai_config_requires_key_and_official_endpoint():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIImageConfig.from_env({})
    with pytest.raises(ValueError, match="api.openai.com"):
        OpenAIImageConfig.from_env(
            {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://example.com/v1"}
        )


def test_openai_provider_sends_all_references_and_writes_review_asset(tmp_path):
    reference_paths = []
    for name in ("Front.png", "Back.png", "Left.png", "Right.png"):
        path = tmp_path / name
        Image.new("RGB", (2, 2), (255, 255, 255)).save(path)
        reference_paths.append(str(path))
    images = FakeImages(encoded_test_png())
    provider = OpenAIImageProvider(
        OpenAIImageConfig(api_key="test-key"),
        client=SimpleNamespace(images=images),
    )

    result = provider.generate(
        GenerationRequest(
            prompt="preserve identity; front view",
            reference_paths=tuple(reference_paths),
            parameters={"camera_id": "CAM01", "output_directory": str(tmp_path / "out")},
        )
    )

    assert Path(result.assets[0]).is_file()
    assert result.metadata["review_required"] is True
    assert result.metadata["request_id"] == "req_test"
    assert len(images.calls) == 1
    assert len(images.calls[0]["image"]) == 4
    assert images.calls[0]["model"] == "gpt-image-2"
    assert "input_fidelity" not in images.calls[0]
