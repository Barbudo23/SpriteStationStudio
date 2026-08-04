# Sprite Station Studio v0.10.0 — Stable Decision

Decision date: 2026-08-04.

Decision: **APPROVED FOR STABLE PACKAGING AND PUBLICATION**.

This decision authorizes the final commit-bound Stable packaging iteration. It
does not itself create a Stable tag or GitHub release.

## Evidence

- Published RC2 tag `v0.10.0-rc2` still resolves to immutable artifact commit
  `43c63e0882912ed73401dc0bfd646e2154e46542`.
- GitHub RC2 remains published as a prerelease with all three assets present;
  their server-side SHA-256 digests are unchanged.
- Open GitHub issues: `0`.
- Re-downloaded published RC2 ZIP, manifest and checksum passed independent
  clean extraction and verification on 2026-08-04.
- Full Python regression: `199/199 PASS`.
- Static Sprite Workflow synthetic E2E: `PASS`.
- Animation Workflow synthetic E2E: `PASS`.
- Windows GUI no-overwrite physical QA: `PASS`.
- Blender 5.1 Static and Animation physical QA: `PASS`.
- Unity 6000.4.0f1 Single/Multiple read-only QA: `PASS`, zero warnings.
- RC2 observation found no reproducible blocking defect.

## Stable packaging constraints

- Promote only release identity and Stable documentation from the verified RC2
  code line; do not add product features.
- Keep AI Center paused and outside v0.10.0 Stable scope.
- Build from one exact commit and verify the resulting ZIP from clean extraction.
- Publish ZIP, manifest and checksum without overwriting RC1 or RC2 assets.
- Create a new immutable `v0.10.0` tag only after all Stable checks pass.
- Re-download published Stable assets and compare their hashes before closeout.

## Remaining action

Build, verify, tag and publish the commit-bound v0.10.0 Stable release, then
record the uploaded asset digests and final repository state.
