from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
from typing import Callable


class UnityBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class UnityInstallation:
    executable: Path
    version: str | None = None


@dataclass(frozen=True)
class UnityCommandResult:
    returncode: int
    stdout: str
    stderr: str
    report_path: Path | None = None


class UnityRunner:
    """Runs Unity Editor as an isolated batch-mode subprocess.

    Sprite Station Studio never imports Unity assemblies into the Python process.
    Communication is performed through command JSON and report JSON files.
    """

    def __init__(self, run_process: Callable[..., subprocess.CompletedProcess] | None = None):
        self._run_process = run_process or subprocess.run

    @staticmethod
    def common_install_roots() -> tuple[Path, ...]:
        roots: list[Path] = []
        program_files = os.environ.get("ProgramFiles")
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        if program_files:
            roots.extend([
                Path(program_files) / "Unity" / "Hub" / "Editor",
                Path(program_files) / "Unity",
            ])
        if program_files_x86:
            roots.append(Path(program_files_x86) / "Unity")
        return tuple(roots)

    def find_installations(self) -> list[Path]:
        """Return all detected Unity Editor executables, newest first."""
        candidates: set[Path] = set()

        for name in ("Unity", "Unity.exe"):
            value = shutil.which(name)
            if value:
                candidates.add(Path(value).expanduser().resolve())

        for root in self.common_install_roots():
            if not root.exists():
                continue
            candidates.update(path.resolve() for path in root.glob("*/Editor/Unity.exe"))
            candidates.update(path.resolve() for path in root.glob("Editor/Unity.exe"))

        # Additional common locations and Unity Hub metadata.
        home = Path.home()
        app_data = os.environ.get("APPDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        program_data = os.environ.get("PROGRAMDATA")

        extra_roots = [
            home / "Unity" / "Hub" / "Editor",
            home / "AppData" / "Local" / "Programs" / "Unity" / "Hub" / "Editor",
        ]
        if local_app_data:
            extra_roots.append(Path(local_app_data) / "Programs" / "Unity" / "Hub" / "Editor")

        for root in extra_roots:
            if root.exists():
                candidates.update(path.resolve() for path in root.glob("*/Editor/Unity.exe"))

        hub_files: list[Path] = []
        if app_data:
            hub_files.extend([
                Path(app_data) / "UnityHub" / "editors-v2.json",
                Path(app_data) / "UnityHub" / "editors.json",
            ])
        if program_data:
            hub_files.append(Path(program_data) / "Unity" / "hubInfo.json")

        for hub_file in hub_files:
            if not hub_file.is_file():
                continue
            try:
                raw = hub_file.read_text(encoding="utf-8", errors="replace")
                for value in re.findall(r'"location"\s*:\s*"([^"]+)"', raw, re.I):
                    location = Path(value.replace("\\\\", "\\"))
                    for candidate in (location / "Editor" / "Unity.exe", location / "Unity.exe"):
                        if candidate.is_file():
                            candidates.add(candidate.resolve())
            except OSError:
                continue

        return sorted(candidates, key=self._version_sort_key, reverse=True)

    def find_unity(self) -> Path | None:
        installations = self.find_installations()
        return installations[0] if installations else None

    def find_working_installations(
        self,
        timeout_per_version: int = 90,
    ) -> list[UnityInstallation]:
        working: list[UnityInstallation] = []
        for executable in self.find_installations():
            try:
                version = self.query_version(executable, timeout=timeout_per_version)
                working.append(UnityInstallation(executable=executable, version=version))
            except (UnityBridgeError, OSError, subprocess.SubprocessError):
                continue
        return working

    @staticmethod
    def _version_sort_key(path: Path) -> tuple[int, ...]:
        parts = re.findall(r"\d+", str(path.parent.parent.name))
        return tuple(int(p) for p in parts[:4]) or (0,)

    @staticmethod
    def validate_executable(path: Path) -> Path:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise UnityBridgeError(f"Unity executable not found: {path}")
        if path.name.lower() not in {"unity.exe", "unity"}:
            raise UnityBridgeError(
                "Select Unity Editor executable (Unity.exe), not Unity Hub.exe."
            )
        return path

    def query_version(self, unity_path: Path, timeout: int = 90) -> str:
        unity = self.validate_executable(unity_path)
        result = self._run_process(
            [str(unity), "-version", "-batchmode", "-quit"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        text = "\n".join(filter(None, [result.stdout, result.stderr])).strip()
        if result.returncode != 0 and not text:
            raise UnityBridgeError(
                f"Unity version check failed with code {result.returncode}."
            )
        match = re.search(r"\b\d{4}\.\d+\.\d+[a-z]\d+\b|\b\d+\.\d+\.\d+[a-z]\d+\b", text)
        return match.group(0) if match else (text.splitlines()[0] if text else "unknown")

    def execute(
        self,
        unity_path: Path,
        project_path: Path,
        method: str,
        command_path: Path,
        log_path: Path,
        timeout: int = 900,
    ) -> UnityCommandResult:
        unity = self.validate_executable(unity_path)
        project_path = project_path.expanduser().resolve()
        if not project_path.is_dir():
            raise UnityBridgeError(f"Unity bridge project not found: {project_path}")
        command_path = command_path.expanduser().resolve()
        log_path = log_path.expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            str(unity),
            "-batchmode",
            "-nographics",
            "-quit",
            "-projectPath", str(project_path),
            "-executeMethod", method,
            "-assetForgeCommand", str(command_path),
            "-logFile", str(log_path),
        ]
        result = self._run_process(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        report_path = None
        try:
            command = json.loads(command_path.read_text(encoding="utf-8"))
            candidate = command.get("reportPath")
            if candidate:
                report_path = Path(candidate)
        except (OSError, ValueError):
            pass

        if result.returncode != 0:
            log_tail = ""
            if log_path.is_file():
                log_tail = "\n".join(
                    log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
                )
            raise UnityBridgeError(
                f"Unity batch command failed with code {result.returncode}.\n{log_tail}"
            )

        return UnityCommandResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            report_path=report_path,
        )
