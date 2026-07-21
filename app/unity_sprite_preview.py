from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.unity_runner import UnityBridgeError, UnityRunner


@dataclass(frozen=True)
class UnitySpritePreviewResult:
    report_path: Path
    log_path: Path
    report: dict


class UnitySpritePreviewRunner:
    def __init__(
        self,
        unity_runner: UnityRunner | None = None,
        bridge_project: Path | None = None,
    ) -> None:
        self.unity_runner = unity_runner or UnityRunner()
        self.bridge_project = bridge_project or (
            Path(__file__).resolve().parents[1] / "unity_bridge_project"
        )

    def run(
        self,
        unity_path: Path,
        preset_path: Path,
        timeout: int = 300,
    ) -> UnitySpritePreviewResult:
        preset_path = preset_path.expanduser().resolve()
        if not preset_path.is_file():
            raise UnityBridgeError(f"Unity sprite preset not found: {preset_path}")

        output_dir = preset_path.parent
        command_path = output_dir / "unity_preview_command.json"
        report_path = output_dir / "unity_import_preview_report.json"
        log_path = output_dir / "unity_import_preview.log"
        command_path.write_text(
            json.dumps({
                "operation": "preview_sprite_import",
                "presetPath": str(preset_path),
                "reportPath": str(report_path),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.unity_runner.execute(
            unity_path,
            self.bridge_project,
            "AssetForgeUnityBridge.Execute",
            command_path,
            log_path,
            timeout=timeout,
        )
        if not report_path.is_file():
            raise UnityBridgeError(f"Unity preview report was not created: {report_path}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("error"):
            raise UnityBridgeError(str(report["error"]))
        if not report.get("readOnlyPreview"):
            raise UnityBridgeError("Unity report is not marked as read-only preview.")
        return UnitySpritePreviewResult(report_path, log_path, report)
