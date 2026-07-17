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
from assetforge.workflow import ProductionWorkflowGuard, WorkflowAction, WorkflowCheckpointStore


def success_message(stack_revision: str, provider: str) -> str:
    return f"{stack_revision} completed successfully with provider: {provider}."

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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly rebuild an iteration already recorded as complete.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show the persisted workflow checkpoint without running the pipeline.",
    )
    args = parser.parse_args()

    configs = ConfigLoader(args.config_root).load_all()
    manifest = configs["Manifest.yaml"]
    manifest_iteration = int(manifest.get("iteration", {}).get("id", 1))
    checkpoint_store = WorkflowCheckpointStore()
    try:
        checkpoint = checkpoint_store.load(args.project_root)
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: Invalid workflow checkpoint: {error}")
        return 1
    if args.status:
        if checkpoint is None:
            print("Workflow has not started.")
        else:
            print(
                f"Iteration {checkpoint.completed_iteration:02d}: {checkpoint.status}; "
                f"progress={checkpoint.project_progress:.0%}; "
                f"next={checkpoint.next_iteration if checkpoint.next_iteration else 'none'}; "
                f"stack={checkpoint.stack_revision}."
            )
        return 0

    decision = ProductionWorkflowGuard().evaluate(
        manifest_iteration,
        checkpoint,
        force=args.force,
    )
    print(decision.message)
    if decision.action == WorkflowAction.ALREADY_COMPLETE:
        return 0
    if decision.action == WorkflowAction.BLOCKED:
        return 1
    state = AssetForgeState(
        project_name=configs["MPI.yaml"].get("project", {}).get("name", "Character_Project"),
        iteration=manifest_iteration,
        progress=0.10,
        configs=configs,
        metadata={
            "project_root": str(args.project_root),
            "provider": MockProvider(),
            "stack_revision": "Stack_03_Rev00",
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
    print(success_message(result.metadata["stack_revision"], args.provider))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
