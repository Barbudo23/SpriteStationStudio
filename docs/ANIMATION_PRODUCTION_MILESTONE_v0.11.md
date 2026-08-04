# Sprite Station Studio v0.11 — Animation Production Milestone

Status: active development.

Branch: `codex/v0.11-animation-production`.

Stable baseline: tag `v0.10.0`, artifact commit `b8d4c923`.

## Goal

Turn the verified directional animation renderer into a production-oriented
animation pipeline while preserving v0.10.0 package safety and read-only Unity
validation. AI Center remains paused and outside this milestone.

## Planned vertical slices

- [x] Explicit Blender Action name in request, worker, manifest, report and GUI.
- [x] Read-only Action discovery before a render operation.
- [x] Stable animation timing contract (FPS, duration and loop policy).
- [ ] Unity AnimationClip descriptor generated from approved sprite slices.
- [ ] Transactional Unity AnimationClip creation in the isolated bridge project.
- [ ] Physical Blender and Unity QA for at least two Actions from one model.
- [ ] Commit-bound v0.11 release candidate and clean-extraction gate.

## Slice 1 contract

An empty Action Name preserves the v0.10 behavior and uses the imported active
animation. A non-empty name is passed exactly to Blender, must match an imported
Action, and is recorded as `actionName` in `animation_manifest.json` and the
render report. The application validates the name before Blender launch and
binds the completed manifest back to the requested name.

The common single-armature FBX/GLB case is supported. If the requested Action is
not already active and the imported scene does not contain exactly one armature,
the worker stops with an ambiguity error instead of guessing a target.

## Slice 2 contract

`DISCOVER ACTIONS (READ-ONLY)` starts Blender in background/factory mode, imports
the selected model and returns one bounded JSON report through stdout. No render
is started and no output path is supplied. The application validates unique,
sorted names, finite frame ranges and active-state flags before updating the
editable Action selector. Discovery and animation rendering cannot run at the
same time.

## Slice 2 physical QA

Blender `5.1` read-only discovery was run against the animated FBX used by the
v0.10 physical Animation baseline. The probe completed without a render or an
output argument and returned exactly one active Action:

- name: `Armature|Armature|Armature|running|baselayer`;
- frame range: `1..20`;
- active: `true`.

Automated closeout: `209/209` tests, Static Sprite synthetic E2E and Animation
Workflow synthetic E2E all pass.

## Slice 3 contract

New animation manifests contain a `timing` object with effective FPS, whether
that FPS came from the Blender scene or an explicit override, source-frame step,
sample timestamps, full selected-range duration and `loop`/`once` policy.
Timestamps are derived from source-frame identity rather than output-array
position, so bounded sampling preserves the original motion timing. The same
validated contract is copied into `unity_import_preset.json` as
`animationTiming` for the next AnimationClip descriptor slice. Legacy v0.10
manifests without timing remain readable.

## Slice 3 physical QA

Blender `5.1` rendered the established animated FBX with the explicitly selected
`running|baselayer` Action, four directions, source frames `1` and `3`, 64px
canvas, FPS override `20` and `once` policy. Eight frames, four sheets, contact
sheet, ZIP and Unity preset were created successfully. Manifest, report and
Unity preset agreed on timestamps `[0.0, 0.1]` and duration `0.15` seconds.
