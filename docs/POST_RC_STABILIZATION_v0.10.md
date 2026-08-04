# Sprite Station Studio v0.10.0 — Post-RC Stabilization

Старт: 2026-07-30.

Ветка: `post-rc/0.10.0-stabilization`.

Опубликованный prerelease: `v0.10.0-rc1`.

Artifact commit: `ae88a25a51376c65ab689647027171ab8a704927`.

Milestone closeout commit: `c1460772448be9d70bf4bd82c694f82078b47665`.

## Цель

Стабилизировать опубликованный Static Sprite и Animation Workflow перед
отдельным решением о Stable, не расширяя пользовательский scope RC1.

## Разрешено

- исправлять только воспроизводимые дефекты;
- добавлять regression test до или вместе с исправлением;
- усиливать no-overwrite, rollback, safe paths и read-only audit;
- повторять clean-install, GUI, Blender и Unity smoke;
- уточнять документацию по фактически выполненным проверкам;
- готовить RC2 только при изменении пользовательского приложения или
  распространяемого ZIP.

## Не входит в scope

- возобновление AI Center;
- платные AI API-вызовы;
- выбор нескольких Blender Actions;
- автоматическое создание Unity AnimationClip;
- AtlasBuilder, MotionLab и CameraLab;
- installer, updater и signing;
- массовый рефакторинг `gui.py`;
- объявление Stable без отдельного решения.

## Обязательный цикл дефекта

1. Зафиксировать воспроизводимый сценарий.
2. Добавить regression test.
3. Выполнить минимальное исправление.
4. Запустить целевые тесты и полный Python regression.
5. Для worker/GUI/Unity изменений повторить соответствующий physical smoke.
6. Проверить активный бренд Sprite Station Studio и legacy allowlist.
7. Создать отдельный коммит и синхронизировать ветку.

## Stable gate

Минимальные условия:

- нет открытых блокирующих дефектов;
- повторяемый запуск RC1 на Windows;
- `172/172` или больше regression tests;
- оба synthetic workflow E2E проходят из clean extraction;
- опубликованный ZIP digest повторно подтверждён;
- ограничения RC документированы;
- принято отдельное решение о Stable.

## Исправленные дефекты

- GUI review state теперь привязан не только к пути, но и к SHA-256
  `animation_manifest.json`; изменение manifest после `VALIDATE` требует
  повторной проверки перед записью решения.
- Final package audit требует точного покрытия всех manifest, review, contact,
  frame и sheet файлов верхнеуровневым artifact list; сокращённый или
  неожиданный список отклоняется.
- Animation manifest отклоняется, если разные directions/frames/sheets/contact
  ссылаются на один и тот же output-файл.
- `sampledFrames` обязаны строго возрастать и полностью находиться внутри
  корректного `frameRange`; порядок Unity slices больше нельзя переставить
  формально валидным manifest.
- Direction ID, порядок и `yawDegrees` обязаны точно соответствовать
  проверенному camera contract для 4 или 8 направлений.
- Unity preset отклоняет boolean, `NaN`, бесконечные и выходящие за `[0,1]`
  значения normalized pivot во всех sprite workflows.
- Unity canvas принимает только целые размеры `1..4096` без неявного
  преобразования boolean, строк или дробных значений.

### Unity export contract hardening

- Unity preset export rejects incomplete animation directions, empty frame lists,
  duplicate direction IDs or output files, invalid `sourceFrame` values and
  non-increasing frame chronology.
- Unity ZIP updates reserve their `.updating` stage atomically and preserve any
  pre-existing stage and original archive.
- Direction Workflow now rejects every occupied output-contract path before
  Blender starts, matching the Animation Workflow no-overwrite guarantee.
- Preview Workflow no longer deletes prior preview, report or manifest files;
  it rejects occupied output-contract paths before Blender starts.
- Animation Workflow now rejects unsupported model formats and render engines,
  coerced numeric types, and out-of-range render limits before Blender starts.
- Shared Preview and Direction requests now require an exact integer resolution
  and a supported string render-engine identifier.
- Missing, unreadable, malformed or non-object Unity source manifests now fail
  with a controlled workflow error instead of a raw parser/type traceback.
- Unity import presets are flushed to same-volume staging and published through
  an atomic no-overwrite link; late collisions preserve the existing preset.
- Corrupt source archives and missing preset inputs now leave the source ZIP
  byte-identical, clean owned staging and return a controlled workflow error.
- Root README now identifies the published v0.10.0 RC1 line and current
  post-RC stabilization scope; a regression test binds it to runtime metadata.

## RC2 candidate

Local metadata was promoted to `0.10.0rc2` after the regression-backed
stabilization series. RC1 remains the published immutable baseline. RC2 is not
publishable until its commit-bound archive passes full clean-extraction checks.

Automated gate result: commit `2f151a06`, 44,265,488-byte ZIP, SHA-256
`7107bb19d6ba6987baa719bea89b58af581393519c0509c5ae8d3d33ad791e2d`,
`197/197` regression tests and both synthetic workflow E2E passed from clean
extraction. Physical affected-workflow confirmation remains required before
publication.

Windows GUI no-overwrite QA from the clean-extracted RC2 artifact passed:
the occupied Direction output contract was rejected before Blender launch,
all nine existing files retained identical SHA-256 and byte lengths, and
Blender process count remained zero.

RC2 physical Animation QA exposed a stabilization regression: validation had
raised the established Animation minimum from 64 to 128 pixels. The contract
was restored to `64..4096` with an explicit boundary test. Artifact `2f151a06`
is superseded and must not be published.

Corrected artifact commit `43c63e08` passed `199/199` clean-extraction tests,
both synthetic E2E, repeated Windows GUI no-overwrite QA, two fresh Static
Blender previews, real Animation rendering (8 frames / 4 sheets), Unity
read-only Single `2/2` and Multiple `4/4` / `8/8` slices with zero warnings.

## RC2 release closeout

Tag `v0.10.0-rc2` points to corrected artifact commit `43c63e08`. GitHub
prerelease publication completed with ZIP, manifest and checksum assets.
GitHub server-side SHA-256 digests match all local files. RC2 stabilization is
complete; Stable remains a separate decision after observation.

## RC2 observation closeout — 2026-08-04

No open GitHub issues or RC2 defect reports were present. The published ZIP,
manifest and checksum were downloaded again from GitHub. The ZIP size and
SHA-256 matched the release, and the independent verifier passed clean
extraction, `199/199` tests and both synthetic workflow E2E checks. See
`docs/RC2_OBSERVATION_2026-08-04.md`.

The observation iteration is complete. Stable still requires a separate
explicit decision and final production QA.
