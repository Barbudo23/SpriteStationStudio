"""Official OpenAI GPT Image provider."""

from __future__ import annotations

import base64
import binascii
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from assetforge.providers.base import BaseProvider, GenerationRequest, GenerationResult


OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
CLOSEAI_BASE_URL = "https://closeai.com.ru/v1"


@dataclass(frozen=True)
class OpenAIImageConfig:
    """Validated settings for the official GPT Image endpoint."""

    api_key: str
    base_url: str = OFFICIAL_OPENAI_BASE_URL
    model: str = "gpt-image-2"
    quality: str = "low"
    size: str = "1024x1024"
    background: str = "auto"
    timeout: float = 180.0
    max_retries: int = 2
    provider_name: str = "openai"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OpenAIImageConfig":
        values = os.environ if env is None else env
        key = values.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI image provider.")
        config = cls(
            api_key=key,
            base_url=values.get("OPENAI_BASE_URL", OFFICIAL_OPENAI_BASE_URL).rstrip("/"),
            model=values.get("OPENAI_IMAGE_MODEL", "gpt-image-2").strip(),
            quality=values.get("OPENAI_IMAGE_QUALITY", "low").strip(),
            size=values.get("OPENAI_IMAGE_SIZE", "1024x1024").strip(),
            background=values.get("OPENAI_IMAGE_BACKGROUND", "auto").strip(),
            timeout=float(values.get("OPENAI_IMAGE_TIMEOUT", "180")),
            max_retries=int(values.get("OPENAI_IMAGE_MAX_RETRIES", "2")),
        )
        config.validate()
        return config

    @classmethod
    def from_closeai_env(cls, env: Mapping[str, str] | None = None) -> "OpenAIImageConfig":
        values = os.environ if env is None else env
        key = values.get("CLOSEAI_API_KEY", "").strip()
        if not key:
            raise ValueError("CLOSEAI_API_KEY is required for the CloseAI image provider.")
        config = cls(
            api_key=key,
            base_url=values.get("CLOSEAI_BASE_URL", CLOSEAI_BASE_URL).rstrip("/"),
            model=values.get("CLOSEAI_IMAGE_MODEL", "gpt-image-1.5").strip(),
            quality=values.get("OPENAI_IMAGE_QUALITY", "low").strip(),
            size=values.get("OPENAI_IMAGE_SIZE", "1024x1024").strip(),
            background=values.get("OPENAI_IMAGE_BACKGROUND", "auto").strip(),
            timeout=float(values.get("OPENAI_IMAGE_TIMEOUT", "180")),
            max_retries=int(values.get("OPENAI_IMAGE_MAX_RETRIES", "2")),
            provider_name="closeai",
        )
        config.validate()
        return config

    def validate(self) -> None:
        expected_url = (
            OFFICIAL_OPENAI_BASE_URL if self.provider_name == "openai" else CLOSEAI_BASE_URL
        )
        if self.provider_name not in {"openai", "closeai"}:
            raise ValueError("provider_name must be openai or closeai.")
        if self.base_url != expected_url:
            raise ValueError(f"{self.provider_name} provider requires endpoint {expected_url}.")
        if self.provider_name == "openai" and not self.model.startswith("gpt-image-2"):
            raise ValueError("OPENAI_IMAGE_MODEL must be gpt-image-2 or its dated snapshot.")
        if not self.model:
            raise ValueError("Image model must not be empty.")
        if self.quality not in {"auto", "low", "medium", "high"}:
            raise ValueError("OPENAI_IMAGE_QUALITY must be auto, low, medium, or high.")
        if self.background not in {"auto", "opaque", "transparent"}:
            raise ValueError("OPENAI_IMAGE_BACKGROUND must be auto, opaque, or transparent.")
        if self.timeout <= 0:
            raise ValueError("OPENAI_IMAGE_TIMEOUT must be positive.")
        if not 0 <= self.max_retries <= 5:
            raise ValueError("OPENAI_IMAGE_MAX_RETRIES must be between 0 and 5.")


class OpenAIImageProvider(BaseProvider):
    """Generate one PNG through the official Images edit endpoint."""

    def __init__(self, config: OpenAIImageConfig, client: Any | None = None) -> None:
        config.validate()
        self.config = config
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        self._client = client

    @property
    def name(self) -> str:
        return self.config.provider_name

    def probe_image_models(self) -> tuple[str, ...]:
        """Read model IDs without requesting a paid image generation."""

        try:
            response = self._client.models.list()
        except Exception as error:
            raise RuntimeError(
                f"{self.name} model probe failed ({type(error).__name__})."
            ) from error
        model_ids = sorted(
            str(getattr(model, "id", ""))
            for model in getattr(response, "data", ())
            if "image" in str(getattr(model, "id", "")).lower()
        )
        return tuple(model_id for model_id in model_ids if model_id)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        references = tuple(Path(path) for path in request.reference_paths)
        if not references:
            raise ValueError("At least one reference image is required.")
        missing = [str(path) for path in references if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Reference image not found: {missing[0]}")

        output_directory = request.parameters.get("output_directory")
        if not output_directory:
            raise ValueError("output_directory is required for OpenAI image generation.")
        camera_id = str(request.parameters.get("camera_id", "CAM00"))

        with ExitStack() as stack:
            image_files = [stack.enter_context(path.open("rb")) for path in references]
            try:
                response = self._client.images.edit(
                    model=self.config.model,
                    image=image_files,
                    prompt=request.prompt,
                    quality=self.config.quality,
                    size=self.config.size,
                    background=self.config.background,
                )
            except Exception as error:
                raise RuntimeError(
                    f"OpenAI image request failed ({type(error).__name__})."
                ) from error

        data = getattr(response, "data", None)
        encoded = getattr(data[0], "b64_json", None) if data else None
        if not encoded:
            raise RuntimeError("OpenAI returned no base64 image data.")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise RuntimeError("OpenAI returned invalid base64 image data.") from error
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.verify()
        except Exception as error:
            raise RuntimeError("OpenAI returned an invalid image payload.") from error

        directory = Path(str(output_directory))
        directory.mkdir(parents=True, exist_ok=True)
        fingerprint = sha256(
            "\n".join((request.prompt, *(str(path) for path in references))).encode("utf-8")
        ).hexdigest()[:16]
        asset_path = directory / f"{camera_id}_{fingerprint}.png"
        asset_path.write_bytes(image_bytes)
        metadata = {
            "model": self.config.model,
            "quality": self.config.quality,
            "size": self.config.size,
            "background": self.config.background,
            "review_required": True,
        }
        request_id = getattr(response, "_request_id", None)
        if request_id:
            metadata["request_id"] = request_id
        return GenerationResult(
            assets=(str(asset_path),),
            provider=self.name,
            metadata=metadata,
        )
