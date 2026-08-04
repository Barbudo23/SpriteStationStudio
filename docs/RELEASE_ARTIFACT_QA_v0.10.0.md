# Sprite Station Studio v0.10.0 — Stable Release Artifact QA

Status: **PUBLISHED GITHUB STABLE RELEASE / ALL GATES PASS**.

## Artifact identity

| Field | Value |
|---|---|
| Version | `0.10.0` |
| Artifact commit | `b8d4c9230a1d781d8f2d7380474ea111318745f2` |
| Tag | `v0.10.0` |
| ZIP | `SpriteStationStudio-v0.10.0-b8d4c923.zip` |
| ZIP bytes | `44273119` |
| ZIP SHA-256 | `8b6416439aabebe8b25e54a8f489997880bdf45bd30acae029d8f0366a869866` |
| Tracked files | `188` |
| Release channel | `stable` |

## Clean-extraction gate

- archive checksum, manifest identity and size: `PASS`;
- portable path, collision and bounded extraction checks: `PASS`;
- application entry-point help: `PASS`;
- full Python regression: `201/201 PASS`;
- Static Sprite Workflow synthetic E2E: `PASS`;
- Animation Workflow synthetic E2E: `PASS`;
- verifier result: `valid: true`, `cleanChecks: PASS`.

The same checks passed before publication and after downloading all three
published assets into a new isolated directory.

## Physical production baseline

- Windows GUI no-overwrite QA: `PASS`;
- Blender 5.1 Static Sprite physical E2E: `PASS`;
- Blender 5.1 Animation physical E2E: `PASS`;
- Unity 6000.4.0f1 Single and Multiple Sprite read-only QA: `PASS`;
- Unity warnings: `0`.

Stable contains only release-identity changes relative to the observed RC2
code line; the physical workflow implementation is unchanged.

## GitHub publication

- release: `https://github.com/Barbudo23/SpriteStationStudio/releases/tag/v0.10.0`;
- draft: `false`;
- prerelease: `false`;
- annotated tag resolves to artifact commit `b8d4c9230a1d781d8f2d7380474ea111318745f2`;
- ZIP server digest:
  `sha256:8b6416439aabebe8b25e54a8f489997880bdf45bd30acae029d8f0366a869866`;
- manifest server digest:
  `sha256:69f597d1de77436593aee75a2aed6bff38d7e7d7cda239d0114a701302d51a83`;
- checksum-file server digest:
  `sha256:06349466d68384aabf93b8cc0bd8c2bff26c0e8db171639894ad9abd322cc7fd`.

Every server-side digest matches its local source file. RC1 and RC2 tags and
assets remain unchanged.
