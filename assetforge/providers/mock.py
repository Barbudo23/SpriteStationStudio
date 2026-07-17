"""Deterministic provider used for local development and tests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw

from assetforge.providers.base import BaseProvider, GenerationRequest, GenerationResult


class MockProvider(BaseProvider):
    """Return stable synthetic asset identifiers without external services."""

    @property
    def name(self) -> str:
        return "mock"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        fingerprint_source = "\n".join(
            (request.prompt, *request.reference_paths)
        ).encode("utf-8")
        fingerprint = sha256(fingerprint_source).hexdigest()[:16]
        output_directory = request.parameters.get("output_directory")
        if output_directory:
            directory = Path(str(output_directory))
            directory.mkdir(parents=True, exist_ok=True)
            camera_id = str(request.parameters.get("camera_id", "CAM00"))
            asset_path = directory / f"{camera_id}_{fingerprint}.png"
            self._write_placeholder(asset_path, fingerprint)
            asset = str(asset_path)
        else:
            asset = f"mock://generation/{fingerprint}.png"
        return GenerationResult(
            assets=(asset,),
            provider=self.name,
            metadata={"deterministic": True},
        )

    @staticmethod
    def _write_placeholder(path: Path, fingerprint: str) -> None:
        """Create a valid deterministic RGBA fixture for downstream pipeline tests."""

        color = tuple(int(fingerprint[index : index + 2], 16) for index in (0, 2, 4))
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 55, 55), fill=(*color, 220))
        draw.line((8, 55, 32, 8, 55, 55), fill=(255, 255, 255, 255), width=2)
        image.save(path, format="PNG")
