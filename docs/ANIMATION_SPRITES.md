# Animation Sprite Renderer v0.1

## Workflow

1. Select an animated FBX/GLB model.
2. Open the `Animation` inspector tab.
3. Enable `Создать анимационные спрайты`.
4. Select 4 or 8 directions.
5. Optionally set Frame Start / Frame End.
6. Select Frame Step and Max Frames.
7. Start render.

## Output

- `animation_frames/<direction>/*.png`
- `animation_sheets/<direction>.png`
- `animation_contact_sheet.png`
- `animation_manifest.json`
- `animation_report.json`
- `<model>_8dir_animation.zip`

## Frame sampling

If the sampled frame count exceeds `Max Frames`, the worker selects evenly
distributed frames while preserving the beginning and end of the animation.

## Current limitations

- Uses the active imported animation/action.
- Does not yet expose a list of multiple Actions contained in one source file.
- Sprite sheets are horizontal strips.
- Real Blender validation must be completed on the target workstation.
