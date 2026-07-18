import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from assetforge.providers import (
    CodexReviewedProvider,
    GenerationRequest,
    MockProvider,
    OpenAIImageConfig,
    OpenAIImageProvider,
)
import yaml


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


def test_codex_reviewed_provider_returns_only_approved_local_asset(tmp_path):
    project = tmp_path / "project"
    output = project / "canary" / "iteration_02"
    jobs = project / "codex_jobs" / "iteration_02"
    output.mkdir(parents=True)
    jobs.mkdir(parents=True)
    asset = output / "CAM01_codex.png"
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(asset)
    (jobs / "Batch_Plan.yaml").write_text(
        yaml.safe_dump({"status": "APPROVED"}), encoding="utf-8"
    )
    (output / "Canary_Result.yaml").write_text(
        yaml.safe_dump({"status": "APPROVED", "asset": str(asset), "approved_by": "owner"}),
        encoding="utf-8",
    )

    provider = CodexReviewedProvider(project, 2)
    result = provider.generate(
        GenerationRequest(prompt="front view", parameters={"camera_id": "CAM01"})
    )

    assert result.assets == (str(asset),)
    assert result.provider == "codex-reviewed"
    assert provider.is_simulation is False


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


class FakeModels:
    def list(self):
        return SimpleNamespace(
            data=[
                SimpleNamespace(id="text-model"),
                SimpleNamespace(id="gpt-image-1.5"),
                SimpleNamespace(id="glm-image"),
            ]
        )


class DeniedImages:
    def edit(self, **kwargs):
        error = RuntimeError("unsafe raw message")
        error.status_code = 403
        error.body = {"error": {"message": "model is not enabled"}}
        raise error


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


def test_closeai_config_is_separate_and_endpoint_locked():
    config = OpenAIImageConfig.from_closeai_env({"CLOSEAI_API_KEY": "test-key"})
    assert config.provider_name == "closeai"
    assert config.base_url == "https://closeai.com.ru/v1"
    assert config.model == "gpt-image-1.5"
    with pytest.raises(ValueError, match="closeai.com.ru"):
        OpenAIImageConfig.from_closeai_env(
            {"CLOSEAI_API_KEY": "test-key", "CLOSEAI_BASE_URL": "https://example.com/v1"}
        )


def test_provider_probe_filters_image_model_ids():
    provider = OpenAIImageProvider(
        OpenAIImageConfig.from_closeai_env({"CLOSEAI_API_KEY": "test-key"}),
        client=SimpleNamespace(models=FakeModels()),
    )

    assert provider.probe_image_models() == ("glm-image", "gpt-image-1.5")


def test_provider_surfaces_safe_gateway_error_detail(tmp_path):
    reference = tmp_path / "Front.png"
    Image.new("RGB", (2, 2), (255, 255, 255)).save(reference)
    provider = OpenAIImageProvider(
        OpenAIImageConfig.from_closeai_env({"CLOSEAI_API_KEY": "secret-test-key"}),
        client=SimpleNamespace(images=DeniedImages()),
    )

    with pytest.raises(RuntimeError, match="HTTP 403: model is not enabled") as captured:
        provider.generate(
            GenerationRequest(
                prompt="front view",
                reference_paths=(str(reference),),
                parameters={"output_directory": str(tmp_path / "out")},
            )
        )
    assert "secret-test-key" not in str(captured.value)


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
