from __future__ import annotations

import base64
from contextlib import ExitStack
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

from app.ai_center.models import AIGenerationRequest, AIProvider, AISettings


OPENAI_BASE_URL = "https://api.openai.com/v1"
CLOSEAI_BASE_URL = "https://closeai.com.ru/v1"


@dataclass(frozen=True)
class ProviderOutput:
    provider: AIProvider
    status: str
    asset: Path | None
    request_id: str | None = None


class ImageAPIProvider:
    """OpenAI-compatible image edit adapter with lazy optional SDK loading."""

    def __init__(
        self,
        provider: AIProvider,
        settings: AISettings,
        env: Mapping[str, str] | None = None,
        client: Any | None = None,
    ) -> None:
        if provider not in {AIProvider.OPENAI, AIProvider.CLOSEAI}:
            raise ValueError("ImageAPIProvider supports OpenAI and CloseAI only.")
        settings.validate()
        self.provider = provider
        self.settings = settings
        values = os.environ if env is None else env
        key_name = "OPENAI_API_KEY" if provider is AIProvider.OPENAI else "CLOSEAI_API_KEY"
        self.api_key = values.get(key_name, "").strip()
        if not self.api_key:
            raise ValueError(f"{key_name} is required for {provider.value} generation.")
        self.base_url = OPENAI_BASE_URL if provider is AIProvider.OPENAI else CLOSEAI_BASE_URL
        self.model = (
            settings.openai_model
            if provider is AIProvider.OPENAI
            else settings.closeai_model
        )
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    "The optional 'openai' package is required for API generation."
                ) from error
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=180.0)
        self.client = client

    def generate(self, request: AIGenerationRequest) -> ProviderOutput:
        request.validate()
        with ExitStack() as stack:
            images = [stack.enter_context(path.open("rb")) for path in request.reference_paths]
            try:
                response = self.client.images.edit(
                    model=self.model,
                    image=images,
                    prompt=request.prompt,
                    quality=self.settings.quality,
                    size=self.settings.size,
                    background=self.settings.background,
                )
            except Exception as error:
                detail = str(error).replace(self.api_key, "[REDACTED]")[:300]
                raise RuntimeError(
                    f"{self.provider.value} image request failed: {detail}"
                ) from error
        data = getattr(response, "data", None)
        encoded = getattr(data[0], "b64_json", None) if data else None
        if not encoded:
            raise RuntimeError(f"{self.provider.value} returned no image data.")
        image_bytes = base64.b64decode(encoded, validate=True)
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"{self.provider.value} returned a non-PNG payload.")
        request.output_directory.mkdir(parents=True, exist_ok=True)
        asset = request.output_directory / f"{request.camera_id}_{self.provider.value}.png"
        if asset.exists():
            raise FileExistsError(f"AI output already exists: {asset}")
        asset.write_bytes(image_bytes)
        return ProviderOutput(
            provider=self.provider,
            status="REVIEW_REQUIRED",
            asset=asset,
            request_id=getattr(response, "_request_id", None),
        )
