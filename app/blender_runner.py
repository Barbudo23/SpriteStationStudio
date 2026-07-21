from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json
import os
import shutil
import subprocess
import sys


SUPPORTED_EXTENSIONS = {".fbx", ".glb", ".gltf", ".obj"}


class ForgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderRequest:
    blender_path: Path
    model_path: Path
    output_dir: Path
    resolution: int = 512
    engine: str = "AUTO"
    camera_profile: str = "Strategy30"

    def validate(self) -> None:
        if not self.blender_path.is_file():
            raise ForgeError(f"Blender не найден: {self.blender_path}")
        if not self.model_path.is_file():
            raise ForgeError(f"Модель не найдена: {self.model_path}")
        if self.model_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ForgeError(
                f"Неподдерживаемый формат {self.model_path.suffix}. "
                f"Разрешены: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        if not 128 <= self.resolution <= 4096:
            raise ForgeError("Разрешение должно быть от 128 до 4096 пикселей.")
        if self.engine not in {"AUTO", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES"}:
            raise ForgeError(f"Неподдерживаемый render engine: {self.engine}")


@dataclass(frozen=True)
class RenderResult:
    preview_path: Path
    report_path: Path
    manifest_path: Path
    report: dict


class BlenderRunner:
    def __init__(self, worker_script: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.worker_script = worker_script or root / "worker" / "render_preview.py"

    @staticmethod
    def _windows_registry_candidates() -> list[Path]:
        """Return Blender executables registered by Windows Installer."""
        try:
            import winreg
        except ImportError:
            return []

        candidates: list[Path] = []
        uninstall_paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for uninstall_path in uninstall_paths:
                try:
                    root_key = winreg.OpenKey(hive, uninstall_path)
                except OSError:
                    continue
                with root_key:
                    index = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(root_key, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root_key, subkey_name) as subkey:
                                display_name = str(
                                    winreg.QueryValueEx(subkey, "DisplayName")[0]
                                )
                                if "blender" not in display_name.lower():
                                    continue
                                install_location = str(
                                    winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                ).strip()
                        except OSError:
                            continue
                        if install_location:
                            candidates.append(Path(install_location) / "blender.exe")
        return candidates

    @staticmethod
    def find_blender() -> Path | None:
        env = os.environ.get("BLENDER_PATH")
        candidates: list[Path] = []
        if env:
            candidates.append(Path(env))

        found = shutil.which("blender")
        if found:
            candidates.append(Path(found))

        if sys.platform.startswith("win"):
            candidates.extend(BlenderRunner._windows_registry_candidates())
            program_files = [
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            ]
            for root in program_files:
                foundation = root / "Blender Foundation"
                if foundation.exists():
                    candidates.extend(sorted(foundation.glob("Blender */blender.exe"), reverse=True))
        elif sys.platform == "darwin":
            candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
        else:
            candidates.extend([Path("/usr/bin/blender"), Path("/snap/bin/blender")])

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def build_command(self, request: RenderRequest) -> list[str]:
        from app.camera_profiles import get_camera_profile

        request.validate()
        profile = get_camera_profile(request.camera_profile)
        if not self.worker_script.is_file():
            raise ForgeError(f"Worker script не найден: {self.worker_script}")

        return [
            str(request.blender_path),
            "--background",
            "--factory-startup",
            "--python",
            str(self.worker_script),
            "--",
            "--model",
            str(request.model_path),
            "--output",
            str(request.output_dir),
            "--resolution",
            str(request.resolution),
            "--engine",
            request.engine,
            "--camera-profile",
            profile.profile_id,
            "--camera-azimuth",
            str(profile.azimuth_degrees),
            "--camera-elevation",
            str(profile.elevation_degrees),
            "--framing-margin",
            str(profile.framing_margin),
            "--pivot-mode",
            profile.pivot_mode,
        ]

    def run(
        self,
        request: RenderRequest,
        on_output: Callable[[str], None] | None = None,
    ) -> RenderResult:
        command = self.build_command(request)
        request.output_dir.mkdir(parents=True, exist_ok=True)

        preview_path = request.output_dir / "Preview.png"
        report_path = request.output_dir / "import_report.json"
        manifest_path = request.output_dir / "preview_manifest.json"

        for stale in (preview_path, report_path, manifest_path):
            try:
                stale.unlink()
            except FileNotFoundError:
                pass

        if on_output:
            on_output("Запуск Blender Worker...")
            on_output(" ".join(f'"{x}"' if " " in x else x for x in command))

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert process.stdout is not None
        lines: list[str] = []
        for raw in process.stdout:
            line = raw.rstrip()
            lines.append(line)
            if on_output:
                on_output(line)

        return_code = process.wait()
        if return_code != 0:
            tail = "\n".join(lines[-30:])
            raise ForgeError(
                f"Blender завершился с кодом {return_code}.\n\nПоследние сообщения:\n{tail}"
            )

        if not preview_path.is_file():
            raise ForgeError("Blender завершился без Preview.png")
        if not report_path.is_file():
            raise ForgeError("Blender завершился без import_report.json")
        if not manifest_path.is_file():
            raise ForgeError("Blender завершился без preview_manifest.json")

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ForgeError(f"Не удалось прочитать отчёт: {exc}") from exc

        if report.get("status") != "success":
            raise ForgeError(report.get("error", "Worker вернул неизвестную ошибку."))

        return RenderResult(
            preview_path=preview_path,
            report_path=report_path,
            manifest_path=manifest_path,
            report=report,
        )
