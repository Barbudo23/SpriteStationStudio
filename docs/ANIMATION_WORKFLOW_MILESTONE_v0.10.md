# Sprite Station Studio — Animation Workflow milestone v0.10

Старт: 2026-07-30.

Ветка: `milestone/0.10-animation-workflow`.

Статус: **COMPLETE / PUBLISHED AS v0.10.0-rc1 PRERELEASE**.

## Цель

Довести существующий Animation Sprite Renderer v0.1 до проверяемого workflow:
анимированная 3D-модель → направления камеры → последовательности PNG →
sprite sheets → review/audit → Unity-ready package.

## Границы

- переиспользовать camera profiles, PNG validation, safe paths, atomic
  publication и Unity contracts статического workflow;
- сохранять одинаковый canvas и pivot между кадрами и направлениями;
- не переписывать массово `gui.py`;
- не возобновлять AI Center;
- не изменять опубликованный `v0.9.0-rc1`.

## Этапы

1. Закрыть no-overwrite и валидацию входного диапазона до запуска Blender.
2. Ввести строгую проверку animation manifest, PNG frames и sprite sheets.
3. Добавить read-only audit и source/output hashes.
4. Добавить явный review/approval и атомарную публикацию approved package.
5. [x] Подтвердить synthetic E2E, реальный Blender smoke и Unity Multiple Sprite.
6. [x] Подключить завершённый workflow к отдельному GUI-модулю.

## GUI integration

В оболочку добавлена отдельная плитка `Animation Workflow`. Окно позволяет
выбрать manifest и исходную модель, выполнить strict validation, явно выбрать
approved/rejected, атомарно опубликовать approved package и повторно проверить
существующий package. Массовый рефакторинг `gui.py` не выполнялся.

## Первый дефект

Существующий worker удалял `animation_frames` и `animation_sheets`, если они
уже находились в output-каталоге, а runner мог принять старые result-файлы.
Milestone начинается с no-overwrite preflight полного набора outputs до запуска
Blender.

## Manifest validation

Runner теперь до Unity export проверяет schema/application/module, число и
уникальность направлений, точную последовательность sampled frames, наличие
всех кадров и sheets, а также запрещает absolute и escaping paths.
Кадры проходят CRC/decompression/8-bit RGBA validation, обязаны совпадать с
canvas и содержать видимые и прозрачные пиксели. Horizontal sheets обязаны
иметь размер `canvas.width × frameCount` на `canvas.height`; для них разрешена
длина больше 4096 px, но общий decoded-pixel budget ограничен 16 Mi pixels.

## Integrity audit

Manifest содержит SHA-256 исходной модели, каждого frame, каждого sheet и
contact sheet. Read-only validator сверяет hashes и пиксельные контракты до
создания Unity preset; изменение output после Blender render отклоняется.

## Approval package

Решение `approved` или `rejected` записывается один раз и связано с SHA-256
animation manifest и исходной модели. Только approved review может создать
новый изолированный package. Публикация выполняется через sibling staging и
atomic directory rename; render outputs остаются read-only, overwrite запрещён.

Опубликованный package имеет отдельный read-only audit: повторно проверяются
artifact list, safe paths, SHA-256 каждого файла, approved review → manifest
связь, counts и вложенный PNG/animation contract.

## Synthetic E2E

`python -S Tools/Invoke-AnimationWorkflowSmoke.py` воспроизводит полный контур
4 направления × 2 кадра: render fixture → validation → approval → atomic
package → final read-only audit. Инструмент не требует Blender и пишет только
во временный каталог.

## Physical E2E

Blender 5.1.2 создал 4 направления × 2 реальных кадра из анимированного FBX.
Approved package прошёл final audit. Unity 6000.4.0f1 read-only preview
подтвердил 4/4 Multiple Sprite sheets, 8/8 slices и 0 warnings.
Подробности: `ANIMATION_WORKFLOW_REAL_SMOKE_v0.10.md`.

## Release closeout

Tag `v0.10.0-rc1` указывает на artifact commit `ae88a25a`. Проверенный ZIP,
manifest и checksum опубликованы как GitHub prerelease; GitHub digest ZIP
совпадает с локальным SHA-256. Stable остаётся отдельным решением.
