from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class TaskToken:
    name: str
    generation: int


class TaskGuard:
    """Prevents duplicate long-running tasks and invalidates stale results."""

    def __init__(self):
        self._lock = Lock()
        self._active: dict[str, int] = {}

    def begin(self, name: str) -> TaskToken | None:
        with self._lock:
            if name in self._active:
                return None
            generation = max(self._active.values(), default=0) + 1
            self._active[name] = generation
            return TaskToken(name, generation)

    def finish(self, token: TaskToken) -> bool:
        with self._lock:
            current = self._active.get(token.name)
            if current != token.generation:
                return False
            del self._active[token.name]
            return True

    def is_active(self, name: str) -> bool:
        with self._lock:
            return name in self._active
