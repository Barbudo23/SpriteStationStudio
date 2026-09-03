from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json
import subprocess

from app.blender_runner import ForgeError, RenderRequest
from app.camera_profiles import DEFAULT_CAMERA_PROFILE, get_camera_profile


@dataclass(frozen=True)
class DirectionRenderResult:
    zip_path: Path
    contact_sheet_path: Path
    manifest_path: Path
    unity_preset_path: Path
    report: dict


class DirectionRenderRunner:
    def __init__(self, worker_script: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.worker_script = worker_script or root / "worker" / "render_directions.py"

    def build_command(
        self,
        request: RenderRequest,
        direction_count: int,
        camera_profile: str = DEFAULT_CAMERA_PROFILE,
    ) -> list[str]:
        request.validate()
        profile = get_camera_profile(camera_profile)
        if direction_count not in {4, 8}:
            raise ForgeError("Количество направлений должно быть 4 или 8.")
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
            "--directions",
            str(direction_count),
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
        direction_count: int,
        camera_profile: str = DEFAULT_CAMERA_PROFILE,
        on_output: Callable[[str], None] | None = None,
    ) -> DirectionRenderResult:
        command = self.build_command(request, direction_count, camera_profile)
        request.output_dir.mkdir(parents=True, exist_ok=True)

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

        code = process.wait()
        report_path = request.output_dir / "directions_report.json"
        manifest_path = request.output_dir / "manifest.json"
        contact_sheet_path = request.output_dir / "contact_sheet.png"
        zip_path = request.output_dir / f"{request.model_path.stem}_{direction_count}dir.zip"

        if code != 0:
            raise ForgeError(
                f"Blender завершился с кодом {code}.\n\n"
                + "\n".join(lines[-30:])
            )

        for required in (report_path, manifest_path, contact_sheet_path, zip_path):
            if not required.is_file():
                raise ForgeError(f"Не создан обязательный файл: {required}")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "success":
            raise ForgeError(report.get("error", "Ошибка direction render."))

        from app.engine_export import append_preset_to_zip, write_unity_import_preset
        unity_preset_path = write_unity_import_preset(manifest_path)
        append_preset_to_zip(zip_path, unity_preset_path)

        return DirectionRenderResult(
            zip_path=zip_path,
            contact_sheet_path=contact_sheet_path,
            manifest_path=manifest_path,
            unity_preset_path=unity_preset_path,
            report=report,
        )
