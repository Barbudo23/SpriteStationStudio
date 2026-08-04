from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import subprocess
from typing import Callable

from app.blender_runner import ForgeError, SUPPORTED_EXTENSIONS
from app.camera_profiles import DEFAULT_CAMERA_PROFILE, get_camera_profile


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
    camera_profile: str = DEFAULT_CAMERA_PROFILE
    action_name: str | None = None
    playback_fps: float | None = None
    loop_policy: str = "loop"


@dataclass(frozen=True)
class AnimationRenderResult:
    zip_path: Path
    manifest_path: Path
    report_path: Path
    contact_sheet_path: Path
    unity_preset_path: Path
    report: dict


class AnimationRenderRunner:
    def __init__(self, worker_script: Path | None = None):
        self.worker_script = (
            worker_script
            or Path(__file__).resolve().parents[1] / "worker" / "render_animation_directions.py"
        )

    def build_command(self, request: AnimationRenderRequest) -> list[str]:
        profile = get_camera_profile(request.camera_profile)
        if not request.blender_path.is_file():
            raise ForgeError(f"Blender executable не найден: {request.blender_path}")
        if not request.model_path.is_file():
            raise ForgeError(f"Файл модели не найден: {request.model_path}")
        if request.model_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ForgeError(
                f"Unsupported model format: {request.model_path.suffix}"
            )
        if not self.worker_script.is_file():
            raise ForgeError(f"Animation worker не найден: {self.worker_script}")
        if (
            isinstance(request.direction_count, bool)
            or not isinstance(request.direction_count, int)
            or request.direction_count not in {4, 8}
        ):
            raise ForgeError("Количество направлений должно быть 4 или 8.")
        if (
            isinstance(request.resolution, bool)
            or not isinstance(request.resolution, int)
            or not 64 <= request.resolution <= 4096
        ):
            raise ForgeError("Animation resolution must be from 64 to 4096.")
        if not isinstance(request.engine, str) or request.engine not in {
            "AUTO",
            "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT",
            "BLENDER_WORKBENCH",
            "CYCLES",
        }:
            raise ForgeError(f"Unsupported render engine: {request.engine}")
        if (
            isinstance(request.frame_step, bool)
            or not isinstance(request.frame_step, int)
            or request.frame_step < 1
        ):
            raise ForgeError("Frame Step должен быть не меньше 1.")
        if (
            isinstance(request.max_frames, bool)
            or not isinstance(request.max_frames, int)
            or not 1 <= request.max_frames <= 128
        ):
            raise ForgeError("Max Frames должен быть от 1 до 128.")
        for label, value in (
            ("Frame Start", request.frame_start),
            ("Frame End", request.frame_end),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ForgeError(f"{label} must be an integer.")
        if (
            request.frame_start is not None
            and request.frame_end is not None
            and request.frame_start > request.frame_end
        ):
            raise ForgeError("Frame Start не должен быть больше Frame End.")
        if request.action_name is not None and (
            not isinstance(request.action_name, str)
            or not request.action_name.strip()
            or request.action_name != request.action_name.strip()
            or len(request.action_name) > 128
            or any(ord(character) < 32 or ord(character) == 127 for character in request.action_name)
        ):
            raise ForgeError("Animation Action name must be a trimmed non-empty string up to 128 characters.")
        if request.playback_fps is not None and (
            isinstance(request.playback_fps, bool)
            or not isinstance(request.playback_fps, (int, float))
            or not math.isfinite(float(request.playback_fps))
            or not 1.0 <= float(request.playback_fps) <= 240.0
        ):
            raise ForgeError("Animation playback FPS must be from 1 to 240.")
        if request.loop_policy not in {"loop", "once"}:
            raise ForgeError("Animation loop policy must be loop or once.")

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
            "--camera-profile", profile.profile_id,
            "--camera-azimuth", str(profile.azimuth_degrees),
            "--camera-elevation", str(profile.elevation_degrees),
            "--framing-margin", str(profile.framing_margin),
            "--pivot-mode", profile.pivot_mode,
        ]
        if request.frame_start is not None:
            args.extend(["--frame-start", str(request.frame_start)])
        if request.frame_end is not None:
            args.extend(["--frame-end", str(request.frame_end)])
        if request.action_name is not None:
            args.extend(["--action-name", request.action_name])
        if request.playback_fps is not None:
            args.extend(["--playback-fps", str(float(request.playback_fps))])
        args.extend(["--loop-policy", request.loop_policy])
        return args

    @staticmethod
    def output_contract_paths(request: AnimationRenderRequest) -> tuple[Path, ...]:
        zip_path = (
            request.output_dir
            / f"{request.model_path.stem}_{request.direction_count}dir_animation.zip"
        )
        return (
            request.output_dir / "animation_frames",
            request.output_dir / "animation_sheets",
            request.output_dir / "animation_report.json",
            request.output_dir / "animation_manifest.json",
            request.output_dir / "animation_contact_sheet.png",
            request.output_dir / "unity_import_preset.json",
            zip_path,
            zip_path.with_suffix(zip_path.suffix + ".updating"),
        )

    def run(
        self,
        request: AnimationRenderRequest,
        on_output: Callable[[str], None] | None = None,
    ) -> AnimationRenderResult:
        command = self.build_command(request)
        collisions = [
            path for path in self.output_contract_paths(request) if path.exists()
        ]
        if collisions:
            formatted = "\n".join(f"- {path}" for path in collisions)
            raise ForgeError(
                "Animation output уже существует; удалите его или выберите "
                f"новую папку:\n{formatted}"
            )
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

        from app.animation_validation import validate_animation_manifest
        manifest_report = validate_animation_manifest(manifest_path, request.model_path)
        if (
            request.action_name is not None
            and manifest_report.action_name != request.action_name
        ):
            raise ForgeError("Rendered Animation Action does not match the request.")
        timing = manifest_report.timing
        if timing is None or timing.loop_policy != request.loop_policy:
            raise ForgeError("Rendered animation timing does not match the request.")
        if (
            request.playback_fps is not None
            and not math.isclose(timing.fps, float(request.playback_fps), abs_tol=1e-6)
        ):
            raise ForgeError("Rendered animation FPS does not match the request.")

        from app.engine_export import append_preset_to_zip, write_unity_import_preset
        unity_preset_path = write_unity_import_preset(manifest_path)
        append_preset_to_zip(zip_path, unity_preset_path)

        return AnimationRenderResult(
            zip_path=zip_path,
            manifest_path=manifest_path,
            report_path=report_path,
            contact_sheet_path=contact_sheet_path,
            unity_preset_path=unity_preset_path,
            report=report,
        )
