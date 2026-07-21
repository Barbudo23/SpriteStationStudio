# AssetForge Studio v0.6.1 Stable

This release consolidates the working Pseudo3D Forge, Blender Bridge,
Unity Bridge and Unity Asset Library into one stable baseline.

## Stability fixes

- persistent Blender/Unity/model/output settings;
- atomic settings writes;
- background Unity project discovery;
- stale-window callback protection;
- duplicate bridge-scan prevention;
- explicit bridge-discovery error handling;
- selected Unity version persistence;
- selected Unity project persistence;
- regression tests for settings and task coordination.

## Known limitations

- Real Blender and Unity integration must be validated on the target workstation.
- Unity model preview thumbnails are not yet generated for 3D assets.
- AI generation is not included in the stable production path yet.
- Animation-to-8-direction sprite-sheet generation is planned for the next phase.
