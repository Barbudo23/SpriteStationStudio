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

## Current v0.11 Action behavior

- Read-only discovery lists the Actions contained in an imported model before
  rendering.
- One exact Action name can be selected for each render and is bound through
  the request, Blender worker, manifest, approval package and Unity clip
  descriptor.
- Timing records FPS, source-frame timestamps, duration and `loop`/`once`
  policy.
- Approved timed packages can produce audited portable native Unity `.anim`
  clips through the isolated Unity bridge.

## Current limitations

- A render operation processes one selected Action at a time; multi-Action QA
  coordinates two independent renders and packages rather than flattening them.
- Sprite sheets are horizontal strips.
- The verified two-Action developer QA remains intentionally two-stage: contact
  sheets are inspected explicitly before `finalize`, while the production GUI
  continues to render one selected Action at a time.
