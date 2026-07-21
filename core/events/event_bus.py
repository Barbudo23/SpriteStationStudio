from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    name: str
    payload: Any = None
    source: str | None = None


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        with self._lock:
            callbacks = self._subscribers.get(event_name, [])
            if callback in callbacks:
                callbacks.remove(callback)

    def publish(self, event_name: str, payload: Any = None, source: str | None = None) -> None:
        event = Event(event_name, payload, source)
        with self._lock:
            callbacks = list(self._subscribers.get(event_name, []))
        for callback in callbacks:
            callback(event)
