from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile

from app.unity_runner import UnityBridgeError, UnityRunner
from app.brand import LEGACY_UNITY_IMPORTS_DIR, UNITY_IMPORTS_DIR


@dataclass(frozen=True)
class UnitySpriteImportResult:
    report_path: Path
    log_path: Path
    report: dict


def _validate_exported_package(path: Path) -> tuple[Path, Path, Path]:
    package_dir = path.expanduser().resolve()
    if not package_dir.is_dir():
        raise UnityBridgeError(f"Exported Unity package not found: {package_dir}")

    try:
        imports_dir = package_dir.parent
        assets_dir = imports_dir.parent
    except IndexError as exc:
        raise UnityBridgeError("Invalid exported Unity package path.") from exc

    if imports_dir.name not in {UNITY_IMPORTS_DIR, LEGACY_UNITY_IMPORTS_DIR} or assets_dir.name.lower() != "assets":
        raise UnityBridgeError(
            "TextureImporter settings can only be applied inside "
            "Assets/SpriteStationImports/<asset> (legacy AssetForgeImports is also supported)."
        )
    project_dir = assets_dir.parent
    if not (project_dir / "ProjectSettings").is_dir():
        raise UnityBridgeError(f"Not a Unity project: {project_dir}")

    preset_path = package_dir / "unity_import_preset.json"
    if not preset_path.is_file():
        raise UnityBridgeError(f"Unity sprite preset not found: {preset_path}")
    return project_dir, package_dir, preset_path


class UnitySpriteImportRunner:
    def __init__(self, unity_runner: UnityRunner | None = None) -> None:
        self.unity_runner = unity_runner or UnityRunner()

    def run(
        self,
        unity_path: Path,
        exported_package_dir: Path,
        timeout: int = 300,
    ) -> UnitySpriteImportResult:
        project_dir, package_dir, preset_path = _validate_exported_package(
            exported_package_dir
        )
        final_report_path = package_dir / "unity_import_apply_report.json"
        final_log_path = package_dir / "unity_import_apply.log"
        if final_report_path.exists() or final_log_path.exists():
            raise UnityBridgeError(
                "TextureImporter settings were already attempted for this package; "
                "existing reports are never overwritten."
            )

        with tempfile.TemporaryDirectory(prefix="sprite-station-unity-import-") as tmp:
            temporary_dir = Path(tmp)
            command_path = temporary_dir / "command.json"
            report_path = temporary_dir / "report.json"
            log_path = temporary_dir / "unity.log"
            command_path.write_text(
                json.dumps(
                    {
                        "operation": "apply_sprite_import",
                        "presetPath": str(preset_path),
                        "packagePath": str(package_dir),
                        "reportPath": str(report_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            self.unity_runner.execute(
                unity_path,
                project_dir,
                "AssetForgeUnityBridge.Execute",
                command_path,
                log_path,
                timeout=timeout,
            )
            if not report_path.is_file():
                raise UnityBridgeError(f"Unity import report was not created: {report_path}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("error"):
                raise UnityBridgeError(str(report["error"]))
            if not report.get("importSettingsApplied"):
                raise UnityBridgeError("Unity did not confirm TextureImporter application.")
            if report.get("warnings"):
                raise UnityBridgeError("Unity applied settings with warnings; inspect the report.")
            with final_report_path.open("x", encoding="utf-8") as destination:
                json.dump(report, destination, ensure_ascii=False, indent=2)
            if log_path.is_file():
                with final_log_path.open("xb") as destination, log_path.open("rb") as source:
                    shutil.copyfileobj(source, destination)
        return UnitySpriteImportResult(final_report_path, final_log_path, report)
