"""AssetForge Core Pipeline."""
from __future__ import annotations
from typing import Protocol, TypeVar

T = TypeVar("T")

class GenerationStep(Protocol[T]):
    step_id: str
    name: str
    def execute(self, context: T) -> T: ...

class Pipeline:
    def __init__(self, steps: list[GenerationStep[T]]):
        self.steps = steps

    def run(self, context: T) -> T:
        for step in self.steps:
            print(f"[PIPELINE] {step.step_id} - {step.name}")
            context = step.execute(context)
            if getattr(context, "errors", None):
                break
        return context
