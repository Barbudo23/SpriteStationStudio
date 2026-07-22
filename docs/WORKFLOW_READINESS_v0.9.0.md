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
| Fresh physical E2E | `PASS` | локальная 49-МБ GLB, Blender 5.1, 2 новых Preview 128×128, audit до/после Unity, Unity 6000.4.0f1: 2/2 valid, warnings 0 |
| GUI integration | `PASS` | отдельное окно SpriteBuilder, выбор plan/contact, explicit decisions, transactional build и audit |
| Windows GUI launch | `PASS` | реальный запуск Python 3.14, главное окно и отдельная панель открываются без ошибок |
| Полная Python regression | `PASS` | 144/144 tests, включая portable Windows ZIP paths и case-insensitive collision checks |
| Переименование | `PASS` | Sprite Station Studio/SSS на активных поверхностях; legacy allowlist тестируется |
| GitHub | `PASS` | приватный `Barbudo23/SpriteStationStudio`, рабочая ветка синхронизирована |
| Clean-install QA | `PASS` | Git archive, Python `-S`, CLI help, 130 tests с Tk и synthetic E2E без site-packages |
| Manual Windows GUI QA | `PASS` | системный file dialog, два JSON-пути и три review items визуально подтверждены |

## Непройденные release gates

| Gate | Статус | Условие закрытия |
|---|---|---|
| Release artifact | `PASS` | локальный v0.9.0rc1 ZIP, SHA-256 manifest, clean extraction, 131 tests и synthetic E2E |
| GitHub prerelease | `PASS` | tag `v0.9.0-rc1` → `df8613c5`, 3 uploaded assets, ZIP digest совпадает |
| Automated artifact re-verification | `PASS` | manifest/hash/version/file-count/safe-path validation и clean checks |

Animation workflow и AI Center не блокируют ограниченное подключение статического workflow к GUI, но остаются вне готовности v1.0.

## Следующая точная задача

Начать ограниченный post-RC цикл: собирать только воспроизводимые дефекты v0.9.0-rc1 и выпускать rc2 лишь при необходимости. Stable не объявлять без отдельного решения и периода проверки. AI Center не изменять.
