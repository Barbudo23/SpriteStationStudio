from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Callable
from uuid import uuid4

from core.batch.model import BatchPlan, BatchPlanError


class BatchPlanStore:
    def __init__(self, replace_file: Callable[[Path, Path], None] | None = None) -> None:
        self._replace_file = replace_file or os.replace

    def load(self, path: Path) -> BatchPlan:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise BatchPlanError(f"BatchPlan not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BatchPlanError(f"Cannot read BatchPlan: {exc}") from exc
        return BatchPlan.from_dict(payload)

    def save(self, plan: BatchPlan, path: Path) -> Path:
        plan.validate()
        path = path.expanduser().resolve()
        if path.suffix.lower() != ".json":
            raise BatchPlanError("BatchPlan path must use the .json extension.")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.staging-{uuid4().hex}"
        backup = path.parent / f".{path.name}.backup-{uuid4().hex}"
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(plan.to_dict(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                shutil.copy2(path, backup)
            self._replace_file(temporary, path)
        except Exception:
            if backup.is_file() and not path.is_file():
                shutil.copy2(backup, path)
            raise
        finally:
            temporary.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
        return path
