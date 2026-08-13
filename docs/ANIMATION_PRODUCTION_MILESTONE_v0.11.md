# Sprite Station Studio v0.11 — Animation Production Milestone

Status: active development.

Branch: `codex/v0.11-animation-production`.

Stable baseline: tag `v0.10.0`, artifact commit `b8d4c923`.

## Goal

Turn the verified directional animation renderer into a production-oriented
animation pipeline while preserving v0.10.0 package safety and read-only Unity
validation. AI Center remains paused and outside this milestone.

## Planned vertical slices

- [x] Explicit Blender Action name in request, worker, manifest, report and GUI.
- [x] Read-only Action discovery before a render operation.
- [x] Stable animation timing contract (FPS, duration and loop policy).
- [x] Unity AnimationClip descriptor generated from approved sprite slices.
- [x] Transactional Unity AnimationClip creation in the isolated bridge project.
- [x] Physical Blender and Unity QA for at least two Actions from one model.
- [ ] Commit-bound v0.11 release candidate and clean-extraction gate.

## Slice 1 contract

An empty Action Name preserves the v0.10 behavior and uses the imported active
animation. A non-empty name is passed exactly to Blender, must match an imported
Action, and is recorded as `actionName` in `animation_manifest.json` and the
render report. The application validates the name before Blender launch and
binds the completed manifest back to the requested name.

The common single-armature FBX/GLB case is supported. If the requested Action is
not already active and the imported scene does not contain exactly one armature,
the worker stops with an ambiguity error instead of guessing a target.

## Slice 2 contract

`DISCOVER ACTIONS (READ-ONLY)` starts Blender in background/factory mode, imports
the selected model and returns one bounded JSON report through stdout. No render
is started and no output path is supplied. The application validates unique,
sorted names, finite frame ranges and active-state flags before updating the
editable Action selector. Discovery and animation rendering cannot run at the
same time.

## Slice 2 physical QA

Blender `5.1` read-only discovery was run against the animated FBX used by the
v0.10 physical Animation baseline. The probe completed without a render or an
output argument and returned exactly one active Action:

- name: `Armature|Armature|Armature|running|baselayer`;
- frame range: `1..20`;
- active: `true`.

Automated closeout: `209/209` tests, Static Sprite synthetic E2E and Animation
Workflow synthetic E2E all pass.

## Slice 3 contract

New animation manifests contain a `timing` object with effective FPS, whether
that FPS came from the Blender scene or an explicit override, source-frame step,
sample timestamps, full selected-range duration and `loop`/`once` policy.
Timestamps are derived from source-frame identity rather than output-array
position, so bounded sampling preserves the original motion timing. The same
validated contract is copied into `unity_import_preset.json` as
`animationTiming` for the next AnimationClip descriptor slice. Legacy v0.10
manifests without timing remain readable.

## Slice 3 physical QA

Blender `5.1` rendered the established animated FBX with the explicitly selected
`running|baselayer` Action, four directions, source frames `1` and `3`, 64px
canvas, FPS override `20` and `once` policy. Eight frames, four sheets, contact
sheet, ZIP and Unity preset were created successfully. Manifest, report and
Unity preset agreed on timestamps `[0.0, 0.1]` and duration `0.15` seconds.

## Slice 4 contract

An approved timed animation package now contains
`unity_animation_clip_descriptor.json`. It is generated inside the same
transactional staging directory as the approved package, included in the
package artifact/hash list and revalidated by the package audit. Rejected,
tampered, untimed or preset-less inputs cannot produce the descriptor.

The descriptor contains one clip per direction. Each clip is bound to the exact
sheet SHA-256, canonical Unity preset and slice rectangles, source frames and
timing. Clip identity includes asset, Action, direction and a stable identity
hash, preventing safe-name and case-insensitive collisions when multiple Actions
of one model are exported. The terminal key is placed at
`duration - 1/FPS`: Unity holds that sprite for the final frame and reports the
requested full duration for both `loop` and `once` policies. A duplicate is only
needed when bounded sampling omitted that terminal source frame.
The target binding is explicitly `SpriteRenderer.m_Sprite`; no Unity project is
modified in this slice.

## Slice 4 physical QA

The real Blender 5.1 Slice 3 output was reviewed, approved and published into a
new package on 2026-08-13. Package audit verified 17 integrity-bound artifacts,
four `once` clips and eight source-frame keyframes. Clip names include the imported
`running|baselayer` Action and remain distinct across all four directions. The
render output and user Unity projects were not modified.

## Slice 5 contract

`UnityAnimationClipBridge` accepts only the exact
`approved_animation_package.json` entry point and runs the complete package
audit before and after making a private snapshot. It copies the minimal bridge
project into an operating-system temporary directory and requires the pinned
Unity `6000.4.0f1`; neither the repository bridge nor a user Unity project is
opened for writing.

Unity independently verifies the package artifact list, hashes, safe paths,
canonical preset and descriptor. It imports each sheet with the exact slice
rectangles and pivots, creates `.anim` through Unity's native
`AnimationUtility.SetObjectReferenceCurve` API, then reloads and verifies the
binding, keyframes, FPS, length, loop policy and Sprite GUID/local file IDs.
Hand-written Unity YAML is not used.

The portable result is a new atomic, no-overwrite bundle containing its complete
approved source snapshot, build report and immutable pairs of sheet PNG/meta and
AnimationClip/meta files. Unity proves portability by preserving those pairs,
deleting the job assets, restoring them, refreshing the AssetDatabase and
verifying all curves and identities again. Only after that succeeds does Python
hash every artifact, audit the staged bundle and publish it with one directory
rename. The existing TextureImporter apply command must not be run over this
bundle because regenerating slice identities would invalidate clip references.

The hashes prove bundle consistency, not cryptographic authorship of the human
approval decision.

## Slice 5 physical QA

The current real Blender 5.1 `running|baselayer` approved package was processed
by Unity `6000.4.0f1` on 2026-08-13. Unity created four `once` native `.anim`
assets with eight keyframes, preserved four sprite sheets and all paired `.meta`
files, deleted and restored its isolated job, and verified portability without
warnings. Final Python audit passed for all 35 bundle artifacts. The repository
bridge, render source and user Unity projects remained unchanged.

## Slice 6 contract

The physical two-Action gate is intentionally split into `prepare` and
`finalize`. It uses the real Running and Walking FBX sources, verifies that both
armatures have the same set of 24 bones, and creates a new no-overwrite FBX
fixture containing both Actions. The two source FBX files are never modified.

The exported fixture is reopened through the production read-only Action
discovery path. The current physical fixture exposes exactly these Actions:

- `Armature|Armature|SSS QA Run`, frame range `1..20`, active, rendered as
  `loop`;
- `Armature|Armature|SSS_QA_Run`, frame range `1..32`, inactive, rendered as
  `once`.

These two names intentionally collapse to the same filesystem-safe slug. The
gate therefore proves that the Action-aware identity hash keeps all eight clip
names distinct even under a case-insensitive comparison. Both Actions are
rendered from the same fixture SHA-256 with four directions, source frames
`1, 3`, 20 FPS and a 64px canvas. Their contact sheets must also have different
hashes.

`prepare` stops with `status=awaiting_visual_review`. It hashes the two source
models, fixture and all prepared render artifacts, prints both contact-sheet
paths and creates no approval package or Unity bundle. A person must inspect
both sheets before continuing. Preparation is run with:

```powershell
python Tools/Invoke-TwoActionPhysicalQA.py prepare `
  --workspace "<new-workspace>" `
  --blender "<path-to-blender.exe>" `
  --unity "<path-to-Unity.exe>" `
  --primary-source "<Running_withSkin.fbx>" `
  --secondary-source "<Walking_withSkin.fbx>"
```

`finalize` accepts only that unchanged prepared workspace and requires both a
reviewer identity and the explicit `--confirm-contact-sheets-approved` flag:

```powershell
python Tools/Invoke-TwoActionPhysicalQA.py finalize `
  --workspace "<prepared-workspace>" `
  --blender "<same-path-to-blender.exe>" `
  --unity "<same-path-to-Unity.exe>" `
  --reviewer "<reviewer-name>" `
  --confirm-contact-sheets-approved
```

Finalization rechecks every prepared hash, publishes both approved packages and
runs Unity `6000.4.0f1` twice in disposable bridge copies. The complete result
is published by one no-overwrite rename only after both Actions pass. Failure
must not expose a partial `final` directory. The repository bridge, prepared
renders, fixture and both source FBX files must remain byte-identical.

## Slice 6 physical QA

The complete Blender-to-Unity gate passed on 2026-08-13. The `prepare` stage
created one compatible 24-bone fixture from the real Running and Walking FBX
sources, discovered exactly two Actions with one active Action and produced two
different contact sheets. Both sheets were inspected and explicitly approved
before `finalize` was allowed to run.

The physical result contains:

- `Armature|Armature|SSS QA Run` with `loop` policy;
- `Armature|Armature|SSS_QA_Run` with `once` policy;
- two audited approved packages with 17 artifacts each;
- four clips, four sheets and eight keyframes per Action;
- eight case-insensitively distinct clip names despite the identical safe slug;
- two Unity `6000.4.0f1` bundles with 35 artifacts each;
- totals of 8 clips, 8 sprite sheets, 16 keyframes and 70 bundle artifacts;
- `portableReloadVerified=true` and zero Unity warnings for both bundles;
- unchanged source FBX files, fixture, prepared artifacts and repository bridge.

Before review, every prepared file is copied into a private snapshot and
rehashed. The final schema 1.1 evidence manifest binds the prepared-state hash,
visual review, both approved manifests and both bundle manifests, and closes
the exact final file set with SHA-256 and file sizes. The physical final contains
147 hash-listed artifacts plus the self-excluded result manifest itself (148
files total); this is separate from the 70 artifacts counted inside the two
portable Unity bundles.

Completion publication is crash-recoverable: an already published, fully
audited `final` directory is authoritative if the mutable state update was
interrupted. A repeated `finalize` audited the existing result and returned the
same successful outcome in 1.47 seconds without rebuilding either Unity bundle.
No existing final output is overwritten.

The repository regression suite passed all 256 tests after the final
review-to-package-to-Unity hash-chain and Windows junction defenses were added.
