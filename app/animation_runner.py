from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
from typing import Callable

from app.blender_runner import ForgeError


@dataclass(frozen=True)
class AnimationRenderRequest:
    blender_path: Path
    model_path: Path
    output_dir: Path
    resolution: int = 256
    engine: str = "AUTO"
    direction_count: int = 8
    frame_start: int | None = None
    frame_end: int | None = None
    frame_step: int = 2
    max_frames: int = 32


@dataclass(frozen=True)
class AnimationRenderResult:
    zip_path: Path
    manifest_path: Path
    report_path: Path
    contact_sheet_path: Path
    report: dict


class AnimationRenderRunner:
    def __init__(self, worker_script: Path | None = None):
        self.worker_script = (
            worker_script
            or Path(__file__).resolve().parents[1] / "worker" / "render_animation_directions.py"
        )

    def build_command(self, request: AnimationRenderRequest) -> list[str]:
        if not request.blender_path.is_file():
            raise ForgeError(f"Blender executable не найден: {request.blender_path}")
        if not request.model_path.is_file():
            raise ForgeError(f"Файл модели не найден: {request.model_path}")
        if not self.worker_script.is_file():
            raise ForgeError(f"Animation worker не найден: {self.worker_script}")
        if request.direction_count not in {4, 8}:
            raise ForgeError("Количество направлений должно быть 4 или 8.")
        if request.frame_step < 1:
            raise ForgeError("Frame Step должен быть не меньше 1.")
        if not 1 <= request.max_frames <= 128:
            raise ForgeError("Max Frames должен быть от 1 до 128.")

        args = [
            str(request.blender_path),
            "--background",
            "--factory-startup",
            "--python",
            str(self.worker_script),
            "--",
            "--model", str(request.model_path),
            "--output", str(request.output_dir),
            "--resolution", str(request.resolution),
            "--engine", request.engine,
            "--directions", str(request.direction_count),
            "--frame-step", str(request.frame_step),
            "--max-frames", str(request.max_frames),
        ]
        if request.frame_start is not None:
            args.extend(["--frame-start", str(request.frame_start)])
        if request.frame_end is not None:
            args.extend(["--frame-end", str(request.frame_end)])
        return args

    def run(
        self,
        request: AnimationRenderRequest,
        on_output: Callable[[str], None] | None = None,
    ) -> AnimationRenderResult:
        command = self.build_command(request)
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
        report_path = request.output_dir / "animation_report.json"
        manifest_path = request.output_dir / "animation_manifest.json"
        contact_sheet_path = request.output_dir / "animation_contact_sheet.png"
        zip_path = request.output_dir / f"{request.model_path.stem}_{request.direction_count}dir_animation.zip"

        if code != 0:
            raise ForgeError(
                f"Blender animation worker завершился с кодом {code}.\n\n"
                + "\n".join(lines[-40:])
            )

        for required in (report_path, manifest_path, contact_sheet_path, zip_path):
            if not required.is_file():
                raise ForgeError(f"Не создан обязательный файл: {required}")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "success":
            raise ForgeError(report.get("error", "Ошибка animation render."))

        return AnimationRenderResult(
            zip_path=zip_path,
            manifest_path=manifest_path,
            report_path=report_path,
            contact_sheet_path=contact_sheet_path,
            report=report,
        )
