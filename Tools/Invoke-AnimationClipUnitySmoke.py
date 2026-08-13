from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.unity_animation_clip_bridge import (  # noqa: E402
    UnityAnimationClipBridge,
    audit_unity_animation_clip_bundle,
)
from app.unity_runner import UnityBridgeError, UnityRunner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create and verify portable native AnimationClips in a disposable "
            "Sprite Station Unity Bridge project."
        )
    )
    parser.add_argument(
        "--package",
        required=True,
        type=Path,
        help="Path to approved_animation_package.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New output directory for the audited Unity AnimationClip bundle.",
    )
    parser.add_argument(
        "--unity",
        type=Path,
        help="Unity Editor executable; auto-detected when omitted.",
    )
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    runner = UnityRunner()
    unity = args.unity or runner.find_unity()
    if unity is None:
        raise UnityBridgeError("No Unity Editor installation was detected.")
    result = UnityAnimationClipBridge(runner).run(
        unity,
        args.package,
        args.output,
        timeout=args.timeout,
    )
    audit = audit_unity_animation_clip_bundle(result.manifest_path)
    print(
        json.dumps(
            {
                "application": "Sprite Station Studio",
                "workflow": "Unity AnimationClip physical smoke",
                "unityVersion": result.unity_version,
                "output": str(result.output_dir),
                "clipCount": result.clip_count,
                "spriteSheetCount": audit.sprite_sheet_count,
                "keyframeCount": result.keyframe_count,
                "artifactCount": audit.artifact_count,
                "portableReloadVerified": audit.portable_reload_verified,
                "auditValid": audit.valid,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
