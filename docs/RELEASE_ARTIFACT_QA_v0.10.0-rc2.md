# Sprite Station Studio v0.10.0 RC2 — Release Artifact QA

Status: **PUBLISHED GITHUB PRERELEASE / ALL GATES PASS**.

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
- publication decision — `APPROVED AND COMPLETED`.

RC1 tag and published assets remain immutable.

## GitHub publication

- tag: `v0.10.0-rc2`;
- tag target: `43c63e0882912ed73401dc0bfd646e2154e46542`;
- release: `https://github.com/Barbudo23/SpriteStationStudio/releases/tag/v0.10.0-rc2`;
- prerelease: `true`;
- draft: `false`;
- all three assets: `uploaded`;
- ZIP server digest:
  `sha256:15820aa09bc05723a2ccd6a8731d4dcd8cdab2320873ee675bb5beab62ce32c9`;
- manifest server digest:
  `sha256:2902110b1d08a6a5fb26cb27667773a0e421e0b55b66168d8bad5e11bfbaf797`;
- checksum-file server digest:
  `sha256:4f543d1a689ef55634acf5cc67ca70767d204374cd89ece89d4e1d962be2f070`.

Every server-side digest matches the corresponding local SHA-256.

## Superseded candidate

Artifact `SpriteStationStudio-v0.10.0rc2-2f151a06.zip` is not publishable.
Physical Animation QA found that it rejected the established 64-pixel render
contract. Commit `43c63e08` restored that boundary and passed all gates above.
