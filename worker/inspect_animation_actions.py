from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import clear_scene, import_model


RESULT_PREFIX = "[SSS_ACTIONS] "


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        clear_scene()
        import_model(Path(args.model).expanduser().resolve())
        active_names = {
            animation_data.action.name
            for obj in bpy.context.scene.objects
            if (animation_data := getattr(obj, "animation_data", None)) is not None
            and getattr(animation_data, "action", None) is not None
        }
        actions = [
            {
                "name": action.name,
                "frameRange": [float(action.frame_range[0]), float(action.frame_range[1])],
                "active": action.name in active_names,
            }
            for action in sorted(bpy.data.actions, key=lambda item: item.name.casefold())
        ]
        print(RESULT_PREFIX + json.dumps({
            "schemaVersion": "1.0",
            "actions": actions,
        }, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
