# Sprite Station Studio v0.10.0 RC2 — Local Candidate

Status: post-RC stabilization candidate. This version is not Stable.

## Scope

RC2 preserves the published v0.10.0 RC1 Static Sprite and Animation Workflow
feature scope. AI Center remains paused. No new rendering features are included.

## Stabilization fixes

- bound GUI animation approval to the exact validated manifest bytes;
- hardened animation package artifact coverage, output-path uniqueness, frame
  chronology, direction-camera identity, canvas dimensions and normalized pivot;
- validated Unity direction, frame and source-manifest contracts;
- made Unity preset and ZIP update stages atomic, no-overwrite and rollback-safe;
- added complete output collision preflight to Preview and Direction workflows;
- aligned Preview, Direction and Animation render input validation;
- preserved the established `64..4096` Animation resolution range;
- converted malformed manifest and ZIP failures into controlled workflow errors;
- aligned the root README with the active release line.

## Verification required before publication

- full Python regression from the commit-bound source;
- Static Sprite Workflow and Animation Workflow synthetic E2E;
- release verifier with clean extraction;
- artifact SHA-256, manifest, file-count and safe-path verification;
- affected Windows GUI, Blender and Unity physical smoke confirmation.

## Known limits

- one active Blender animation/action is used;
- automatic Unity AnimationClip creation is not included;
- AI Center, installer, updater and signing remain outside this release scope;
- Blender and Unity are installed separately.
