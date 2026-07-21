from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from threading import Event, Lock, Thread
from typing import Any, Callable
import time
import uuid


class JobStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    name: str
    action: Callable[[], Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.WAITING
    result: Any = None
    error: str | None = None
    created_utc: float = field(default_factory=time.time)
    started_utc: float | None = None
    finished_utc: float | None = None


class JobQueue:
    def __init__(self, on_changed: Callable[[Job], None] | None = None):
        self._queue: Queue[Job] = Queue()
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()
        self._stop = Event()
        self._on_changed = on_changed
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, job: Job) -> str:
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put(job)
        self._notify(job)
        return job.id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_utc)

    def cancel_waiting(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.WAITING:
                return False
            job.status = JobStatus.CANCELLED
            job.finished_utc = time.time()
        self._notify(job)
        return True

    def shutdown(self) -> None:
        self._stop.set()

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except Empty:
                continue

            if job.status == JobStatus.CANCELLED:
                self._queue.task_done()
                continue

            job.status = JobStatus.RUNNING
            job.started_utc = time.time()
            self._notify(job)
            try:
                job.result = job.action()
                job.status = JobStatus.FINISHED
            except Exception as exc:
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = JobStatus.FAILED
            finally:
                job.finished_utc = time.time()
                self._notify(job)
                self._queue.task_done()

    def _notify(self, job: Job) -> None:
        if self._on_changed:
            self._on_changed(job)
