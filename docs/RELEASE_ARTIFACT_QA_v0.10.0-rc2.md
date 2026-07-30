# Sprite Station Studio v0.10.0 RC2 — Release Artifact QA

Status: **LOCAL CANDIDATE / ALL AUTOMATED AND PHYSICAL GATES PASS / NOT PUBLISHED**.

## Artifact identity

| Field | Value |
|---|---|
| Version | `0.10.0rc2` |
| Artifact commit | `43c63e0882912ed73401dc0bfd646e2154e46542` |
| ZIP | `SpriteStationStudio-v0.10.0rc2-43c63e08.zip` |
| ZIP bytes | `44269101` |
| SHA-256 | `15820aa09bc05723a2ccd6a8731d4dcd8cdab2320873ee675bb5beab62ce32c9` |
| Tracked files in archive | `184` |
| Release channel | `local-rc-candidate` |

Companion files:

- `SpriteStationStudio-v0.10.0rc2-43c63e08.manifest.json`
- `SpriteStationStudio-v0.10.0rc2-43c63e08.sha256`

## Automated clean-extraction gate

Executed with `Tools/Verify-ReleaseCandidate.py --run-clean-checks`.

- archive checksum, manifest identity and declared size — `PASS`;
- portable paths, collision checks and bounded extraction — `PASS`;
- application entry-point help from clean extraction — `PASS`;
- full Python regression from clean extraction — `199/199 PASS`;
- Static Sprite Workflow synthetic E2E — `PASS`;
- Animation Workflow synthetic E2E — `PASS`;
- final verifier result — `valid: true`, `cleanChecks: PASS`.

## Publication blockers

Before GitHub prerelease publication:

- affected Windows GUI no-overwrite scenario — `PASS`;
- Blender 5.1 Static and Animation physical baseline — `PASS`;
- Unity 6000.4 Single/Multiple Sprite read-only baseline — `PASS`;
- make an explicit publication decision.

RC1 tag and published assets remain immutable.

## Superseded candidate

Artifact `SpriteStationStudio-v0.10.0rc2-2f151a06.zip` is not publishable.
Physical Animation QA found that it rejected the established 64-pixel render
contract. Commit `43c63e08` restored that boundary and passed all gates above.
