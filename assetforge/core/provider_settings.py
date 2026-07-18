"""Persistent user-facing generation provider selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


PRODUCTION_PROVIDERS = ("openai", "codex", "closeai")
PROVIDER_LABELS = {
    "openai": "Original OpenAI API",
    "codex": "Codex built-in generator",
    "closeai": "CloseAI API",
}
MENU_CHOICES = {"1": "openai", "2": "codex", "3": "closeai"}


@dataclass(frozen=True)
class ProviderSettings:
    active_provider: str = "codex"
    codex_reference_upload_authorized: bool = False
    max_images_per_run: int = 3

    def __post_init__(self) -> None:
        if self.active_provider not in PRODUCTION_PROVIDERS:
            raise ValueError(
                "active_provider must be one of: " + ", ".join(PRODUCTION_PROVIDERS)
            )
        if not 1 <= self.max_images_per_run <= 8:
            raise ValueError("max_images_per_run must be between 1 and 8.")


class ProviderSettingsStore:
    """Load and save the active provider without storing credentials."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ProviderSettings:
        if not self.path.exists():
            return ProviderSettings()
        data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("Provider settings must contain a YAML mapping.")
        return ProviderSettings(
            active_provider=str(data.get("active_provider", "codex")),
            codex_reference_upload_authorized=bool(
                data.get("codex_reference_upload_authorized", False)
            ),
            max_images_per_run=int(data.get("max_images_per_run", 3)),
        )

    def save(self, settings: ProviderSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": "1.0",
            "active_provider": settings.active_provider,
            "label": PROVIDER_LABELS[settings.active_provider],
            "credentials_stored_here": False,
            "codex_reference_upload_authorized": (
                settings.codex_reference_upload_authorized
            ),
            "codex_upload_scope": "configured project references for prepared jobs",
            "human_review_required": True,
            "max_images_per_run": settings.max_images_per_run,
        }
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)


def provider_from_menu_choice(choice: str) -> str:
    normalized = choice.strip().lower()
    if normalized in MENU_CHOICES:
        return MENU_CHOICES[normalized]
    if normalized in PRODUCTION_PROVIDERS:
        return normalized
    raise ValueError("Choose 1, 2, or 3.")


def provider_menu_text(active_provider: str) -> str:
    lines = ["AssetForge generation provider:"]
    for number, provider in MENU_CHOICES.items():
        marker = " [ACTIVE]" if provider == active_provider else ""
        lines.append(f"  {number}. {PROVIDER_LABELS[provider]}{marker}")
    return "\n".join(lines)
