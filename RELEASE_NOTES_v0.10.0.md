# Sprite Station Studio v0.10.0 Stable

Status: Stable production release.

## Scope

Sprite Station Studio converts supported 3D models into static and animated
2D sprite assets with controlled camera directions. v0.10.0 includes the
verified Static Sprite Workflow and Animation Workflow. AI Center remains
paused and is not part of this Stable release.

## Stable capabilities

- FBX, GLB, GLTF and OBJ input through separately installed Blender;
- orthographic Static Sprite rendering with camera profiles and transparent PNG;
- four- or eight-direction static sprite sets;
- four- or eight-direction animation rendering with bounded frame sampling;
- review, approval and read-only audit contracts bound to SHA-256;
- atomic no-overwrite package publication and rollback-safe staging;
- Unity Single and Multiple Sprite import presets and read-only validation;
- portable ZIP packages with manifest and checksum verification.

## Verification

- full Python regression: `199/199 PASS` before Stable promotion;
- Static Sprite and Animation Workflow synthetic E2E: `PASS`;
- Windows GUI no-overwrite QA: `PASS`;
- Blender 5.1 Static and Animation physical QA: `PASS`;
- Unity 6000.4.0f1 Single/Multiple Sprite QA: `PASS`, zero warnings;
- published RC2 observation: no reproducible blocking defects.

## Known limits

- one active Blender animation/action is used;
- automatic Unity AnimationClip creation is not included;
- AI Center, installer, updater and signing remain outside v0.10.0;
- Blender and Unity must be installed separately.
