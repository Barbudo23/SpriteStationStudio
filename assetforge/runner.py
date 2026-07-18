#!/usr/bin/env python3
"""AssetForge Stack 2 command-line runner."""
from __future__ import annotations
import argparse
from pathlib import Path

from dotenv import load_dotenv

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
from assetforge.providers import MockProvider, OpenAIImageConfig, OpenAIImageProvider
from assetforge.workflow import (
    CanaryRunner,
    IterationManifest,
    IterationManifestLoader,
    ManifestAwaitingApprovalError,
    ManifestCatalog,
    ProductionWorkflowGuard,
    WorkflowAction,
    WorkflowCheckpointStore,
)


def success_message(stack_revision: str, provider: str) -> str:
    return f"{stack_revision} completed successfully with provider: {provider}."

def main() -> int:
    parser = argparse.ArgumentParser(description="Run implemented AssetForge Stack 2 steps")
    parser.add_argument("--project-root", type=Path, default=Path("projects/Soldier_AK47"))
    parser.add_argument("--config-root", type=Path, default=Path("configs/core"))
    manifest_group = parser.add_mutually_exclusive_group()
    manifest_group.add_argument(
        "--manifest",
        type=Path,
        help="Iteration manifest YAML. Defaults to configs/core/Manifest.yaml.",
    )
    manifest_group.add_argument(
        "--next",
        action="store_true",
        help="Run the next approved manifest from the local catalog.",
    )
    parser.add_argument(
        "--manifest-root",
        type=Path,
        default=Path("configs/iterations"),
        help="Directory containing approved iteration manifests.",
    )
    parser.add_argument(
        "--provider",
        choices=("mock", "openai", "closeai"),
        default="mock",
        help="Generation provider. OpenAI is initially restricted to one-view canary mode.",
    )
    parser.add_argument(
        "--canary",
        action="store_true",
        help="Generate exactly one view for human review without advancing workflow state.",
    )
    parser.add_argument(
        "--canary-camera",
        default="CAM01",
        help="Camera ID for the one-view canary (default: CAM01).",
    )
    parser.add_argument(
        "--probe-provider",
        action="store_true",
        help="List image-capable models without generating an image.",
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
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show all ten iteration slots and local manifest readiness.",
    )
    args = parser.parse_args()
    load_dotenv(dotenv_path=Path(".env"), override=False)

    configs = ConfigLoader(args.config_root).load_all()
    checkpoint_store = WorkflowCheckpointStore()
    try:
        checkpoint = checkpoint_store.load(args.project_root)
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: Invalid workflow checkpoint: {error}")
        return 1
    try:
        catalog = ManifestCatalog.discover(
            args.config_root / "Manifest.yaml",
            args.manifest_root,
        )
        if args.next:
            selected_manifest = catalog.next_entry(checkpoint).manifest
            configs["Manifest.yaml"] = dict(selected_manifest.data)
        elif args.manifest:
            selected_manifest = IterationManifestLoader().load(args.manifest)
            configs["Manifest.yaml"] = dict(selected_manifest.data)
        else:
            selected_manifest = IterationManifest.from_mapping(configs["Manifest.yaml"])
    except ManifestAwaitingApprovalError as error:
        print(f"BLOCKED: {error}")
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: Invalid iteration manifest: {error}")
        return 1
    manifest_iteration = selected_manifest.iteration
    if args.status:
        if checkpoint is None:
            print("Workflow has not started.")
        else:
            print(
                f"Iteration {checkpoint.completed_iteration:02d}: {checkpoint.status}; "
                f"mode={checkpoint.mode}; progress={checkpoint.project_progress:.0%}; "
                f"next={checkpoint.next_iteration if checkpoint.next_iteration else 'none'}; "
                f"stack={checkpoint.stack_revision}."
            )
        return 0
    if args.plan:
        print("ID  STATUS             NAME")
        for line in catalog.describe(checkpoint):
            print(line)
        return 0

    if args.provider in {"openai", "closeai"} and args.probe_provider:
        try:
            config = (
                OpenAIImageConfig.from_env()
                if args.provider == "openai"
                else OpenAIImageConfig.from_closeai_env()
            )
            models = OpenAIImageProvider(config).probe_image_models()
        except (OSError, RuntimeError, ValueError) as error:
            print(f"ERROR: Provider probe failed: {error}")
            return 1
        print("Image models: " + (", ".join(models) if models else "none reported"))
        return 0
    if args.provider in {"openai", "closeai"} and not args.canary:
        print(
            "BLOCKED: paid full-batch generation is disabled until a canary image "
            f"has passed human review. Run with --provider {args.provider} --canary."
        )
        return 1
    if args.canary:
        try:
            if args.provider in {"openai", "closeai"}:
                config = (
                    OpenAIImageConfig.from_env()
                    if args.provider == "openai"
                    else OpenAIImageConfig.from_closeai_env()
                )
                provider = OpenAIImageProvider(config)
            else:
                provider = MockProvider()
            canary = CanaryRunner().run(
                project_root=args.project_root,
                iteration=manifest_iteration,
                configs=configs,
                provider=provider,
                camera_id=args.canary_camera,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"ERROR: Canary generation failed: {error}")
            return 1
        print(
            f"{canary.status}: generated one {args.canary_camera} image at {canary.asset}. "
            f"Review record: {canary.report}. Workflow state was not advanced."
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
