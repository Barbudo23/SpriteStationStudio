# Sprite Station Studio v0.10.0 RC2 — Release Artifact QA

Status: **LOCAL CANDIDATE / AUTOMATED GATE PASS / NOT PUBLISHED**.

## Artifact identity

| Field | Value |
|---|---|
| Version | `0.10.0rc2` |
| Artifact commit | `2f151a06df8756bdb470a02ff8715a3d0ac6b29e` |
| ZIP | `SpriteStationStudio-v0.10.0rc2-2f151a06.zip` |
| ZIP bytes | `44265488` |
| SHA-256 | `7107bb19d6ba6987baa719bea89b58af581393519c0509c5ae8d3d33ad791e2d` |
| Tracked files in archive | `182` |
| Release channel | `local-rc-candidate` |

Companion files:

- `SpriteStationStudio-v0.10.0rc2-2f151a06.manifest.json`
- `SpriteStationStudio-v0.10.0rc2-2f151a06.sha256`

## Automated clean-extraction gate

Executed with `Tools/Verify-ReleaseCandidate.py --run-clean-checks`.

- archive checksum, manifest identity and declared size — `PASS`;
- portable paths, collision checks and bounded extraction — `PASS`;
- application entry-point help from clean extraction — `PASS`;
- full Python regression from clean extraction — `197/197 PASS`;
- Static Sprite Workflow synthetic E2E — `PASS`;
- Animation Workflow synthetic E2E — `PASS`;
- final verifier result — `valid: true`, `cleanChecks: PASS`.

## Publication blockers

Before GitHub prerelease publication:

- affected Windows GUI no-overwrite scenario — `PASS`;
- confirm the existing Blender physical Static/Animation render baseline;
- confirm the existing Unity 6000.4 read-only import baseline;
- make an explicit publication decision.

RC1 tag and published assets remain immutable.
