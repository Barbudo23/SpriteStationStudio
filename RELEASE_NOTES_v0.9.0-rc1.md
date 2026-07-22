# Sprite Station Studio v0.9.0 RC1 — Local Candidate

Статус: локальный кандидат для проверки. Git tag и GitHub Release не созданы. Версия не является Stable или production-ready до проверки release artifact.

## Основной результат

Sprite Station Studio преобразует результаты 3D Preview в проверяемые статические 2D Sprite-наборы через явное ручное согласование.

## Добавлено

- BatchPlan 1.0 максимум для трёх Preview с resume и атомарным состоянием.
- Read-only contact sheet и неизменяемый Batch Review 1.0 с SHA-256.
- Approved-only staging, Static Sprite Set 1.0 и переносимый Unity preview package.
- Транзакционный Static Sprite Workflow и строгий read-only аудит всей цепочки.
- Отдельная GUI-панель SpriteBuilder с `approved` / `rejected`, build и audit.
- Synthetic и physical E2E, реальный Blender 5.1 и Unity 6000.4.0f1 smoke.

## Проверено

- 131/131 Python tests, включая проверку неопубликованного no-overwrite release builder.
- Manual Windows GUI QA, включая системный file dialog и три review items.
- Clean-install из Git archive с `python -S` без сторонних runtime-пакетов.
- Переименование активных поверхностей в Sprite Station Studio с контролируемой legacy-совместимостью.

## Ограничения

- AI Center остаётся приостановленным и не входит в текущий release scope.
- Animation workflow не входит в критерии готовности Static Sprite Workflow v0.9.0.
- Blender и Unity устанавливаются отдельно.
- Публичный RC/Stable, installer, updater и signing отсутствуют.
