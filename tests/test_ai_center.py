from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
import unittest

from app.ai_center.models import AIGenerationRequest, AIProvider, AISettings
from app.ai_center.service import AICenterService
from app.ai_center.settings_store import AISettingsStore
from app.ui.module_registry import create_default_registry
from core.app_core import AssetForgeCore


PNG = b"\x89PNG\r\n\x1a\n" + b"test-payload"


class FakeImages:
    def __init__(self):
        self.calls = []

    def edit(self, **kwargs):
        self.calls.append(kwargs)
        item = type("ImageData", (), {"b64_json": base64.b64encode(PNG).decode("ascii")})()
        return type("Response", (), {"data": [item], "_request_id": "req-test"})()


class FakeClient:
    def __init__(self):
        self.images = FakeImages()


class AICenterTests(unittest.TestCase):
    def _request(self, root: Path) -> AIGenerationRequest:
        reference = root / "front.png"
        reference.write_bytes(PNG)
        return AIGenerationRequest(
            prompt="Preserve the character and create an aiming pose.",
            reference_paths=(reference,),
            output_directory=root / "jobs",
            camera_id="CAM01",
        )

    def test_settings_round_trip_without_api_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ai.json"
            settings = AISettings(provider=AIProvider.CLOSEAI, max_images_per_run=2)
            store = AISettingsStore(path)
            store.save(settings)
            self.assertEqual(store.load(), settings)
            payload = path.read_text(encoding="utf-8")
            self.assertNotIn("api_key", payload.lower())

    def test_codex_bridge_prepares_reviewable_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = AICenterService(AISettings()).execute(self._request(root))
            self.assertEqual(result.status, "AWAITING_CODEX")
            self.assertIsNone(result.asset)
            payload = json.loads(result.job_file.read_text(encoding="utf-8"))
            self.assertTrue(payload["review_required"])
            self.assertFalse(payload["api_key_stored"])

    def test_openai_adapter_writes_png_and_review_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeClient()
            settings = AISettings(provider=AIProvider.OPENAI)
            result = AICenterService(
                settings, env={"OPENAI_API_KEY": "secret"}, client=client
            ).execute(self._request(root))
            self.assertEqual(result.status, "REVIEW_REQUIRED")
            self.assertEqual(result.asset.read_bytes(), PNG)
            self.assertEqual(client.images.calls[0]["model"], "gpt-image-2")
            self.assertNotIn("secret", result.job_file.read_text(encoding="utf-8"))

    def test_ai_center_registered_in_shell_and_core(self):
        modules = {module.id: module for module in create_default_registry().all()}
        self.assertTrue(modules["ai_center"].enabled)
        core = AssetForgeCore()
        try:
            self.assertTrue(core.plugins.get("ai_center").enabled)
        finally:
            core.close()


if __name__ == "__main__":
    unittest.main()
