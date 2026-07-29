# Animation Workflow v0.10 — Real Blender/Unity Smoke

Дата: 2026-07-30.

Статус: **PASS**.

## Среда

- Blender `5.1.2`;
- Unity `6000.4.0f1`;
- модель: `Meshy_AI_biped_Animation_Running_withSkin.fbx`;
- camera profile: `Strategy30`;
- render engine: `BLENDER_EEVEE`;
- canvas: `64×64`;
- направления: `4`;
- sampled frames: `1, 3`.

## Blender

Новый no-overwrite output:
`output/animation-v010-smoke-20260730`.

- импорт анимированного FBX — `PASS`;
- frames — `8/8`;
- horizontal sprite sheets — `4/4`;
- contact sheet, manifest, report и ZIP — созданы;
- SHA-256 source/frame/sheet/contact — проверены;
- PNG CRC/decompression/RGBA/canvas validation — `PASS`;
- Unity preset добавлен в ZIP;
- общее время runner — около `84` секунд.

## Approval package

Новый atomic output:
`output/animation-v010-approved-20260730`.

- explicit review — `approved`;
- package artifacts — `16`;
- final read-only package audit — `PASS`;
- render output не изменялся при публикации.

## Unity

Read-only preview через `unity_bridge_project`:

- `readOnlyPreview` — `true`;
- sprite sheets — `4/4 valid`;
- sprite mode — `Multiple`;
- slices — `8/8`;
- размер каждого sheet — `128×64`;
- warnings — `0`;
- импорт или изменение пользовательского Unity-проекта не выполнялись.

## Решение

Physical Blender/Unity gate этапа 5 закрыт. Animation Workflow допускается к
подключению через отдельный GUI-модуль без массового рефакторинга `gui.py`.
