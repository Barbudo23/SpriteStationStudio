import pytest
import yaml

from assetforge.core.provider_settings import (
    ProviderSettings,
    ProviderSettingsStore,
    provider_from_menu_choice,
    provider_menu_text,
)


def test_missing_provider_settings_default_to_codex(tmp_path):
    settings = ProviderSettingsStore(tmp_path / "Provider.yaml").load()
    assert settings.active_provider == "codex"
    assert settings.codex_reference_upload_authorized is False


@pytest.mark.parametrize(
    ("choice", "expected"),
    [("1", "openai"), ("2", "codex"), ("3", "closeai"), (" codex ", "codex")],
)
def test_provider_menu_choice_mapping(choice, expected):
    assert provider_from_menu_choice(choice) == expected


def test_provider_menu_rejects_unknown_choice():
    with pytest.raises(ValueError, match="1, 2, or 3"):
        provider_from_menu_choice("4")


def test_provider_settings_are_persisted_without_credentials(tmp_path):
    path = tmp_path / "Provider.yaml"
    store = ProviderSettingsStore(path)
    store.save(ProviderSettings("closeai", True))

    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert store.load().active_provider == "closeai"
    assert saved["credentials_stored_here"] is False
    assert "api_key" not in saved
    assert saved["codex_reference_upload_authorized"] is True
    assert saved["human_review_required"] is True
    assert saved["max_images_per_run"] == 1


def test_menu_marks_the_active_provider():
    menu = provider_menu_text("openai")
    assert "1. Original OpenAI API [ACTIVE]" in menu
    assert "2. Codex built-in generator" in menu
    assert "3. CloseAI API" in menu
