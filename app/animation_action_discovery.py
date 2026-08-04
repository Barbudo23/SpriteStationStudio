from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess

from app.blender_runner import ForgeError, SUPPORTED_EXTENSIONS


RESULT_PREFIX = "[SSS_ACTIONS] "
MAX_ACTIONS = 256


@dataclass(frozen=True)
class AnimationActionInfo:
    name: str
    frame_start: float
    frame_end: float
    active: bool


class AnimationActionDiscovery:
    def __init__(self, worker_script: Path | None = None) -> None:
        self.worker_script = worker_script or (
            Path(__file__).resolve().parents[1]
            / "worker"
            / "inspect_animation_actions.py"
        )

    def build_command(self, blender_path: Path, model_path: Path) -> list[str]:
        if not blender_path.is_file():
            raise ForgeError(f"Blender executable not found: {blender_path}")
        if not model_path.is_file():
            raise ForgeError(f"Model file not found: {model_path}")
        if model_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ForgeError(f"Unsupported model format: {model_path.suffix}")
        if not self.worker_script.is_file():
            raise ForgeError(f"Animation Action discovery worker not found: {self.worker_script}")
        return [
            str(blender_path),
            "--background",
            "--factory-startup",
            "--python",
            str(self.worker_script),
            "--",
            "--model",
            str(model_path),
        ]

    def discover(
        self,
        blender_path: Path,
        model_path: Path,
        *,
        timeout_seconds: int = 120,
    ) -> tuple[AnimationActionInfo, ...]:
        command = self.build_command(blender_path, model_path)
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ForgeError("Animation Action discovery timed out.") from exc
        lines = completed.stdout.splitlines()
        if completed.returncode != 0:
            raise ForgeError(
                "Blender Animation Action discovery failed.\n\n"
                + "\n".join(lines[-40:])
            )
        payload_lines = [line[len(RESULT_PREFIX):] for line in lines if line.startswith(RESULT_PREFIX)]
        if len(payload_lines) != 1:
            raise ForgeError("Blender did not return exactly one Animation Action report.")
        try:
            payload = json.loads(payload_lines[0])
        except json.JSONDecodeError as exc:
            raise ForgeError("Blender Animation Action report is malformed.") from exc
        return self._validate_payload(payload)

    @staticmethod
    def _validate_payload(payload: object) -> tuple[AnimationActionInfo, ...]:
        if not isinstance(payload, dict) or payload.get("schemaVersion") != "1.0":
            raise ForgeError("Animation Action report schema is invalid.")
        raw_actions = payload.get("actions")
        if not isinstance(raw_actions, list) or len(raw_actions) > MAX_ACTIONS:
            raise ForgeError("Animation Action report list is invalid.")
        result: list[AnimationActionInfo] = []
        names: set[str] = set()
        for item in raw_actions:
            if not isinstance(item, dict):
                raise ForgeError("Animation Action report item is invalid.")
            name = item.get("name")
            frame_range = item.get("frameRange")
            active = item.get("active")
            if (
                not isinstance(name, str)
                or not name.strip()
                or name != name.strip()
                or len(name) > 128
                or any(ord(character) < 32 or ord(character) == 127 for character in name)
                or name in names
                or not isinstance(frame_range, list)
                or len(frame_range) != 2
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in frame_range)
                or not all(math.isfinite(float(value)) for value in frame_range)
                or float(frame_range[0]) > float(frame_range[1])
                or not isinstance(active, bool)
            ):
                raise ForgeError("Animation Action report item contract is invalid.")
            names.add(name)
            result.append(AnimationActionInfo(
                name=name,
                frame_start=float(frame_range[0]),
                frame_end=float(frame_range[1]),
                active=active,
            ))
        if [item.name for item in result] != sorted(names, key=str.casefold):
            raise ForgeError("Animation Action report must be sorted by name.")
        return tuple(result)
