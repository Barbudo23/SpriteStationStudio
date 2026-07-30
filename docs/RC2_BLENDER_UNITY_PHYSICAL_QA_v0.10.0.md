# Sprite Station Studio v0.10.0 RC2 — Blender and Unity Physical QA

Date: 2026-07-30.

Artifact:
`SpriteStationStudio-v0.10.0rc2-43c63e08.zip`.

Environment:

- Blender `5.1`;
- Unity `6000.4.0f1`;
- Python `3.14`;
- clean-extracted commit-bound RC2 application.

## Static Sprite physical E2E

- two fresh 128×128 Blender Preview renders — `PASS`;
- both items explicitly approved — `PASS`;
- workflow audit before Unity — `PASS`;
- Unity read-only preview — `true`;
- Unity valid Single Sprite assets — `2/2`;
- workflow audit after Unity — `PASS`;
- Unity warnings — `0`.

## Animation physical E2E

The established animated FBX baseline was rendered with Strategy30,
`BLENDER_EEVEE`, 64×64 canvas, four directions and source frames 1 and 3.

- real PNG frames — `8/8`;
- horizontal sprite sheets — `4/4`;
- strict manifest/hash/PNG files checked — `14`;
- Unity preset present inside animation ZIP — `PASS`;
- Unity read-only Multiple Sprite sheets — `4/4 valid`;
- Unity slices — `8/8`;
- Unity version — `6000.4.0f1`;
- Unity warnings — `0`.

Result: **PASS**.
