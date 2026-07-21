from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.blender_runner import BlenderRunner, RenderRequest
from app.gui import launch_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pseudo3D Forge MVP")
    parser.add_argument("--cli", action="store_true", help="Запустить без GUI")
    parser.add_argument("--blender", help="Путь к Blender executable")
    parser.add_argument("--model", help="Путь к FBX/GLB/GLTF/OBJ")
    parser.add_argument("--output", default=str(ROOT / "output"), help="Папка результата")
    parser.add_argument("--resolution", type=int, default=512, help="Размер PNG")
    parser.add_argument("--engine", default="AUTO",
                        choices=["AUTO", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES"])
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.cli:
        launch_gui()
        return 0

    missing = [name for name in ("blender", "model") if not getattr(args, name)]
    if missing:
        print("Ошибка: для CLI нужны --blender и --model", file=sys.stderr)
        return 2

    request = RenderRequest(
        blender_path=Path(args.blender),
        model_path=Path(args.model),
        output_dir=Path(args.output),
        resolution=args.resolution,
        engine=args.engine,
    )
    runner = BlenderRunner()
    result = runner.run(request, on_output=print)
    print(f"Preview: {result.preview_path}")
    print(f"Report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
