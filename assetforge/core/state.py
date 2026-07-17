"""
AssetForge State
Version 0.1

Shared runtime state passed through the entire production pipeline.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetForgeState:

    project_name: str = ""

    iteration: int = 1

    progress: float = 0.0

    current_step: str = ""

    configs: dict[str, Any] = field(default_factory=dict)

    generated_assets: list[str] = field(default_factory=list)

    reports: list[str] = field(default_factory=list)

    logs: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)

    qa_score: float | None = None

    approved: bool = False

    def log(self, message: str):
        self.logs.append(message)

    def add_asset(self, asset: str):
        self.generated_assets.append(asset)

    def add_report(self, report: str):
        self.reports.append(report)

    def fail(self, message: str):
        self.errors.append(message)
        self.approved = False

    def approve(self):
        self.approved = True
