#!/usr/bin/env python3
"""AssetForge Stack 2 command-line runner."""
from __future__ import annotations
import argparse
from pathlib import Path
from assetforge.core.config_loader import ConfigLoader
from assetforge.core.pipeline import Pipeline
from assetforge.core.state import AssetForgeState
from assetforge.engine.gs001_input_validation import GS001InputValidation
from assetforge.engine.gs002_character_lock import GS002CharacterLock
from assetforge.engine.gs003_camera_setup import GS003CameraSetup
from assetforge.engine.gs004_generation import GS004Generation
from assetforge.engine.gs005_qa import GS005QA
from assetforge.engine.gs006_export import GS006Export
from assetforge.engine.gs007_package import GS007Package
from assetforge.engine.gs008_report import GS008Report
from assetforge.providers import MockProvider

def main() -> int:
    parser = argparse.ArgumentParser(description="Run implemented AssetForge Stack 2 steps")
    parser.add_argument("--project-root", type=Path, default=Path("projects/Soldier_AK47"))
    parser.add_argument("--config-root", type=Path, default=Path("configs/core"))
    parser.add_argument(
        "--provider",
        choices=("mock",),
        default="mock",
        help="Generation provider (Stack 2 currently supplies the deterministic mock).",
    )
    args = parser.parse_args()

    configs = ConfigLoader(args.config_root).load_all()
    manifest = configs["Manifest.yaml"]
    state = AssetForgeState(
        project_name=configs["MPI.yaml"].get("project", {}).get("name", "Character_Project"),
        iteration=int(manifest.get("iteration", {}).get("id", 1)),
        progress=0.10,
        configs=configs,
        metadata={
            "project_root": str(args.project_root),
            "provider": MockProvider(),
            "stack_revision": "Stack_02_Rev00",
        },
    )
    result = Pipeline(
        [
            GS001InputValidation(),
            GS002CharacterLock(),
            GS003CameraSetup(),
            GS004Generation(),
            GS005QA(),
            GS006Export(),
            GS007Package(),
            GS008Report(),
        ]
    ).run(state)
    for line in result.logs:
        print(line)
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Stack 2 completed successfully with provider: {args.provider}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
