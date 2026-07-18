"""Provider-independent generation contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class GenerationRequest:
    """Normalized input passed from the engine to any AI provider."""

    prompt: str
    reference_paths: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Generation prompt must not be empty.")


@dataclass(frozen=True)
class GenerationResult:
    """Provider-neutral generation output."""

    assets: tuple[str, ...]
    provider: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Stable interface implemented by concrete generation providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider identifier used in logs and reports."""

    @property
    def is_simulation(self) -> bool:
        """Return whether outputs are technical fixtures rather than production assets."""

        return False

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate assets for a normalized request."""
