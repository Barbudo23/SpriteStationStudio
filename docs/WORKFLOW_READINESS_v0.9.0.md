# Sprite Station Studio v0.9.0 — Workflow Readiness

Дата проверки: 2026-07-22.

## Решение

- Backend workflow: **READY FOR LIMITED GUI INTEGRATION**.
- Версия v0.9.0: **NOT RC / NOT PRODUCTION READY**.
- AI Center: **PAUSED**, в этот gate не входит.

Разрешено подключать новый workflow к отдельной минимальной панели интерфейса без изменения существующих Render, Unity Import и AI Center маршрутов. Объявлять RC или Stable пока нельзя.

## Пройденные gates

| Gate | Статус | Доказательство |
|---|---|---|
| BatchPlan 1.0, максимум 3 операции | `PASS` | атомарное хранилище, resume и state-transition tests |
| Реальный Blender Batch Preview | `PASS` | Blender 5.1.2, последовательный smoke трёх Preview |
| PNG/RGBA validation | `PASS` | CRC, размеры, alpha, bounds, path traversal и decompression limits |
| Contact sheet | `PASS` | read-only сборка, SHA-256 источников, no-overwrite |
| Ручные решения | `PASS` | Batch Review 1.0, только `approved` / `rejected` |
| Approved staging | `PASS` | rejected исключаются, исходники не меняются |
| SpriteBuilder | `PASS` | Static Sprite Set 1.0, pivot `bottom_center`, alpha bounds |
| Unity adapter | `PASS` | переносимый preset, без `.meta`, GUID и записи в Unity-проект |
| Реальный Unity preview | `PASS` | Unity 6000.4.0f1, 2/2 Single Sprite valid, warnings 0 |
| Транзакционный workflow | `PASS` | all-or-nothing coordinator и очистка после искусственного сбоя |
| Финальный аудит | `PASS` | read-only проверка contracts, item IDs, safe paths и вложенных SHA-256 |
| Воспроизводимый synthetic E2E | `PASS` | 3 Preview: 2 approved, 1 rejected, 4 artifacts / 10 checked files |
| Полная Python regression | `PASS` | 122/122 tests на момент readiness review |
| Переименование | `PASS` | Sprite Station Studio/SSS на активных поверхностях; legacy allowlist тестируется |
| GitHub | `PASS` | приватный `Barbudo23/SpriteStationStudio`, рабочая ветка синхронизирована |

## Непройденные release gates

| Gate | Статус | Условие закрытия |
|---|---|---|
| Fresh physical E2E | `PENDING` | одна свежая 3D-модель проходит Blender render → review → workflow audit → Unity read-only preview без повторного использования старых результатов |
| GUI integration | `PENDING` | минимальная отдельная панель запуска/статуса без массового изменения `gui.py` |
| Manual Windows GUI QA | `PENDING` | ручной happy-path, cancel, invalid path, overwrite и restart/resume |
| Clean-install QA | `PENDING` | запуск из чистой копии с документированными Python/Blender/Unity requirements |
| Release artifact | `PENDING` | ZIP, SHA-256 manifest, release notes и tag после закрытия предыдущих gates |

Animation workflow и AI Center не блокируют ограниченное подключение статического workflow к GUI, но остаются вне готовности v1.0.

## Следующая точная задача

Выполнить **fresh physical E2E** на локальной GLB-модели: создать новый временный BatchPlan, получить новые Blender Preview, сформировать review/workflow, выполнить read-only audit и проверить итоговый Unity preset через изолированный Unity Bridge. Пользовательские Unity-проекты не изменять.
