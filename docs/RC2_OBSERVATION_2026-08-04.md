# v0.10.0 RC2 Observation — 2026-08-04

## Result

The published `v0.10.0-rc2` prerelease remains eligible for the separate Stable
decision. No reproducible blocking defect was found during this observation.

## GitHub observation

- Open issues: `0`.
- RC2 asset downloads at observation time: `0` for each published asset.
- Three open draft pull requests predate RC2 and target historical v0.8.x work;
  they are not RC2 defect reports.
- Release remains a published prerelease with ZIP, manifest and checksum assets.

## Independent published-asset verification

All three assets were downloaded again from GitHub into an isolated local
observation directory. The ZIP had the expected size of `44,269,101` bytes and
SHA-256 `15820aa09bc05723a2ccd6a8731d4dcd8cdab2320873ee675bb5beab62ce32c9`.

`Tools/Verify-ReleaseCandidate.py --run-clean-checks` reported:

- release manifest and checksum: `PASS`;
- safe archive structure and clean extraction: `PASS`;
- `199/199` Python regression tests: `PASS`;
- Static Sprite synthetic E2E: `PASS`;
- Animation Workflow synthetic E2E: `PASS`.

## Decision boundary

This closes the planned RC2 observation iteration. It does not declare or
publish Stable. The next iteration is an explicit Stable decision followed by
final production QA. AI Center remains paused and outside this release scope.
