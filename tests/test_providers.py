import pytest

from assetforge.providers import GenerationRequest, MockProvider


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
    assert first.assets[0].startswith("mock://generation/")
    assert first.metadata["deterministic"] is True
