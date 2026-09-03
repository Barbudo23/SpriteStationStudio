# Sprite Station Studio — Current Project Report

Generated: 2026-07-22. Repository state: branch `studio/0.8.3-static-sprite-pipeline`, HEAD `d54662e249a7620f6d414c51feaf52dc8471d49c`.

## Executive status

Sprite Station Studio has reached a published **v0.9.0 RC1 prerelease** for its main static-sprite workflow. The verified product path is:

`3D model → camera profile → Blender Preview → validation → manual review → Static Sprite Set → Unity preview package`

The current RC is not Stable or production-ready. The static v0.9 scope is approximately **96% complete**; the wider product vision, including animation, AI, installers and additional game-engine exporters, is approximately **58% complete**. Commercial Stable readiness is estimated at **68%** because post-RC field feedback, installer/updater/signing and a broader operating-system matrix are still absent.

## Release state

| Field | Value |
|---|---|
| Product version | `0.9.0rc1` |
| GitHub status | Published prerelease |
| Tag | `v0.9.0-rc1` |
| Tag commit | `df8613c5d44be876672273692c32520e0631b59d` |
| ZIP | `SpriteStationStudio-v0.9.0rc1-df8613c5.zip` |
| ZIP size | 44,211,717 bytes |
| SHA-256 | `b1ec23daae4dc18548cbd85b6cfb4254ceb2c8808f686b72e1cefccc135756cb` |
| Stable | No |

The artifact was rebuilt after correcting its release-note test count. Its SHA-256 was independently recalculated, the ZIP was extracted into a new directory, and all tests plus synthetic E2E were executed inside the extracted archive with `python -S`.

## Repository measurements

| Metric | Value |
|---|---:|
| Tracked files | 161 |
| Tracked bytes | 50,319,551 |
| Program code lines | 11,542 |
| Measured text lines | 13,297 |
| Python | 97 files / 11,053 lines |
| C# | 1 file / 454 lines |
| Batch and shell | 4 files / 35 lines |
| Documentation | 33 Markdown files / 1,683 lines |
| Git commits | 43 |
| Test files | 37 |
| Test methods | 131 |

LOC means physical text lines, including comments and blank lines. Completion percentages are engineering estimates, not telemetry.

## Module readiness

| Module | Completion | Status |
|---|---:|---|
| Static Sprite Workflow v0.9 | 96% | Published prerelease; all planned gates passed |
| Batch Preview and Review | 94% | Validated, resumable, immutable review |
| Static SpriteBuilder | 95% | Validated approved-only pipeline |
| Blender static rendering | 90% | Physical E2E passed on Blender 5.1.2 |
| Unity sprite integration | 86% | Unity 6000.4.0f1, 2/2 sprites, zero warnings |
| Desktop GUI | 76% | Windows manual and Tk controller QA passed |
| Release engineering | 82% | Reproducible prerelease ZIP and checksums |
| Core framework | 62% | Foundation implemented; workflows not fully unified |
| Animation rendering | 60% | Exists but outside v0.9 acceptance scope |
| Four-image source | 55% | Portable image package implemented |
| Unity Asset Library | 55% | Local discovery workflow implemented |
| AI Center | 35% | Explicitly paused |
| AtlasBuilder | 5% | Placeholder |
| Installer/updater | 10% | ZIP distribution only |
| Godot and Unreal exporters | 0% | Not implemented |

## Verified gates

- 131/131 Python tests pass.
- BatchPlan 1.0 supports at most three operations with atomic state and resume.
- PNG validation checks RGBA, CRC, bounds, dimensions and decompression limits.
- Contact sheets and review decisions are integrity-bound with SHA-256.
- Approved staging excludes rejected Preview files and does not modify sources.
- Static Sprite Set records alpha bounds, bottom-center pivot and source hashes.
- Workflow publication is transactional; failure leaves no partial result.
- Final audit is read-only and verifies paths, identities, contracts and nested hashes.
- Physical Blender 5.1.2 E2E passed with new 128×128 Preview images.
- Unity 6000.4.0f1 preview passed for 2/2 sprites with zero warnings.
- Manual Windows GUI QA passed, including the native file dialog and three review items.
- Clean-install QA passed from `git archive` with `python -S`.
- GitHub prerelease contains the ZIP, JSON manifest and checksum file.

## Architecture

The application is a modular Python/Tkinter desktop monolith with external-process boundaries for Blender and Unity. JSON manifests are treated as public contracts. The current static workflow intentionally avoids a broad rewrite of the legacy GUI and uses a separate SpriteBuilder window over tested backend services.

Important safety properties are no-overwrite output, staging plus atomic publication, path-traversal rejection, immutable reviews, SHA-256 integrity, isolated Unity preview and read-only auditing.

Supported legacy names such as `.afs`, `AssetForgeUnityBridge` and old Unity import locations remain compatibility contracts. Active public surfaces use Sprite Station Studio; rename-regression tests distinguish allowed legacy identifiers from stale branding.

## Known limitations and risks

1. RC1 has not yet accumulated a meaningful period of external field feedback.
2. AI Center is paused and excluded from the RC acceptance scope.
3. Animation exists but has not passed the same v0.9 release gates as the static workflow.
4. There is no installer, updater, code signing, telemetry or crash reporting.
5. Linux and macOS are claimed as Python/Blender possibilities, but real GUI and Blender smoke results are unknown.
6. Unity support is validated on Unity 6000.4.0f1; older Unity versions are not claimed.
7. Line and branch coverage percentages are unknown because no coverage run is recorded.

## Recommended next development point

Use a limited post-RC cycle. Accept only reproducible v0.9.0-rc1 defects, add a failing regression test first, and issue RC2 only if a real defect requires code or contract changes. Do not resume AI Center or broaden the scope during RC stabilization. Stable should require a separate decision after a field-test period.

## Codex statistics note

Historical Codex input, cached and output token telemetry is not available from the repository or current tools. The companion JSON therefore records `0` in the requested numeric token fields and explicitly marks those values as unavailable rather than claiming that no tokens were used.
