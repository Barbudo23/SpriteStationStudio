from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from app.ai_center.models import AIGenerationRequest, AIProvider, AISettings
from app.ai_center.providers import ImageAPIProvider


@dataclass(frozen=True)
class AIGenerationResult:
    status: str
    provider: AIProvider
    job_file: Path
    asset: Path | None


class AICenterService:
    def __init__(
        self,
        settings: AISettings,
        env: Mapping[str, str] | None = None,
        client: Any | None = None,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.env = env
        self.client = client

    def execute(self, request: AIGenerationRequest) -> AIGenerationResult:
        request.validate()
        request.output_directory.mkdir(parents=True, exist_ok=True)
        job_file = request.output_directory / f"{request.camera_id}_ai_job.json"
        if job_file.exists():
            raise FileExistsError(f"AI job already exists: {job_file}")
        if self.settings.provider is AIProvider.CODEX:
            result = AIGenerationResult(
                status="AWAITING_CODEX", provider=AIProvider.CODEX,
                job_file=job_file, asset=None,
            )
            self._write_job(job_file, request, result)
            return result
        output = ImageAPIProvider(
            self.settings.provider, self.settings, self.env, self.client
        ).generate(request)
        result = AIGenerationResult(
            status=output.status,
            provider=output.provider,
            job_file=job_file,
            asset=output.asset,
        )
        self._write_job(job_file, request, result, request_id=output.request_id)
        return result

    def _write_job(
        self,
        path: Path,
        request: AIGenerationRequest,
        result: AIGenerationResult,
        request_id: str | None = None,
    ) -> None:
        references = [str(item.expanduser().resolve()) for item in request.reference_paths]
        payload = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": result.status,
            "provider": result.provider.value,
            "camera_id": request.camera_id,
            "prompt": request.prompt,
            "prompt_sha256": sha256(request.prompt.encode("utf-8")).hexdigest(),
            "references": references,
            "asset": str(result.asset) if result.asset else None,
            "request_id": request_id,
            "review_required": True,
            "api_key_stored": False,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
