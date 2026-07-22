# План разработки Sprite Station Studio (SSS)

## Контроль версий

- Репозиторий: `Barbudo23/SpriteStationStudio` (переименование из `Barbudo23/AssetForge`).
- Исходная база: ветка `studio/0.8.1-baseline`, тег `studio-v0.8.1-baseline`.
- Hotfix: тег `studio-v0.8.1.1-hotfix`.
- AI Center: ветка `studio/0.8.2-ai-dev`, разработка приостановлена.
- Текущая разработка: ветка `studio/0.8.3-static-sprite-pipeline`.
- `stable` не получает экспериментальный код напрямую.
- Каждая рабочая версия публикуется отдельным коммитом; крупные этапы — отдельными
  ветками и draft PR.

## Этап 1 — v0.8.2 AI Center Foundation (приостановлен)

- [x] Реестр AI Center в UI и Core.
- [x] Переключатель OpenAI / Codex / CloseAI.
- [x] Настройки без хранения секретов.
- [x] Один API-запрос с 1–4 референсами.
- [x] Codex Bridge JSON job.
- [x] Human-review gate.
- [x] Автотесты контрактов.
- [ ] Фоновое выполнение API-запроса через Job Queue.
- [ ] Preview результата внутри AI Center.

## Этап 2 — v0.8.3 Static Sprite Pipeline (текущий)

- [x] Подключить выбор профиля камеры к 4/8-направленному Blender-рендеру.
- [x] Валидировать азимут, высоту камеры и запас кадра.
- [x] Зафиксировать прозрачный RGBA-холст и ортографическую проекцию.
- [x] Добавить в manifest 1.1 камеру, нормализацию, bounds и pivot `bottom_center`.
- [x] Добавить автоматические тесты профилей и контракта.
- [x] Провести визуальный Blender smoke-test на эталонной GLB-модели (Blender 5.1.2, 4 направления, Strategy30).
- [x] Перенести тот же контракт камеры/pivot в анимационный конвейер.
- [x] Выполнить smoke-test анимационного пакета и проверить sprite sheets (4 направления × 2 кадра, Blender 5.1.2).
- [x] Унифицировать Camera Profile, canvas и pivot для режима одного ракурса.
- [x] Выполнить реальный smoke-test одиночного Preview и manifest 1.1 (профиль Diablo, Blender 5.1.2).
- [x] Добавить переносимый `unity_import_preset.json` для Single/Multiple Sprite.
- [x] Включать Unity preset в статические и анимационные ZIP-пакеты.
- [x] Проверить preset на реальных статическом и анимационном пакетах.
- [x] Добавить read-only preview команды импорта в изолированный Unity Bridge.
- [x] Проверить статический пакет в Unity 6000.4.0f1 без импорта в пользовательский проект.
- [x] Проверить 4 animation sheets и 8 slices в Unity 6000.4.0f1.
- [x] Минимизировать зависимости bridge project до необходимых встроенных модулей.
- [x] Добавить кнопку Unity Import Preview и отчёт в интерфейс.
- [x] Автоматически использовать preset последнего успешного рендера.
- [x] Запускать Unity preview в фоне с защитой от дублирования.
- [x] Добавить явный экспорт проверенного пакета в выбранную папку `Assets` с подтверждением пользователя.
- [x] Запретить перезапись, mismatched preview, warnings и invalid assets.
- [x] Проверить транзакционное копирование на временном Unity-проекте.
- [x] Добавить отдельную подтверждаемую команду применения TextureImporter-настроек.
- [x] Проверить применение на 4 статических Sprite и 4 Multiple sheets / 8 slices в Unity 6000.4.0f1.

## Этап 3 — v0.9.0 Production Workflow

- [x] Зафиксировать RC scope и support matrix (`docs/RC_SCOPE_v0.9.0.md`).
- [x] Добавить независимый контракт `BatchPlan 1.0` максимум на три Blender-операции.
- [x] Добавить атомарное JSON-хранилище, resume-переходы и data-safety тесты.
- [x] Подключить BatchPlan к одиночному Preview через изолированный coordinator после contract tests.
- [x] Выполнить реальный Blender smoke Batch Preview и подтвердить checkpoint/result manifest.
- [x] Добавить независимую read-only проверку PNG/alpha и соответствия manifest 1.1.
- [x] Проверить PNG validator на реальном Blender 5.1.2 Preview.
- [x] Подключить PNG validator перед staging-публикацией Batch Preview.
- [x] Выполнить real smoke интегрированной PNG-проверки в Blender 5.1.2.
- [x] Добавить явный последовательный запуск до трёх Preview с остановкой на первой ошибке.
- [x] Выполнить реальный Blender smoke трёхэлементного batch-запуска.
- Пакетная генерация до трёх кадров за запуск.
- Возобновляемый batch plan.
- Проверка PNG, alpha и геометрии объекта.
- [x] Read-only contact sheet и manifest для визуального пакетного согласования без изменения исходных PNG.
- [x] Атомарный контракт ручных решений `approved` / `rejected` с проверкой SHA-256 исходников.
- [x] Изолированный staging-пакет только для `approved` Preview с повторной проверкой целостности.
- [x] Контракт SpriteBuilder для атомарной сборки статического Sprite Set из approved staging.
- [x] Read-only адаптер Static Sprite Set в переносимый Unity preset-пакет без запуска Unity.
- [x] Реальный read-only smoke-test Static Sprite Unity-пакета в Unity 6000.4.0f1: 2/2 valid, warnings отсутствуют.
- [x] Транзакционный end-to-end coordinator review → staging → SpriteBuilder → Unity preview package.
- [x] Read-only аудит опубликованного workflow: контракты, бренд, пути, SHA-256 и идентичность items.
- [x] Воспроизводимый end-to-end smoke на трёх Preview с двумя approved, одним rejected и финальным аудитом.
- [x] Workflow readiness checklist: backend готов к limited GUI integration, продукт остаётся NOT RC.
- Импорт утверждённых кадров в Animation pipeline.

## Этап 4 — v0.9.5 Provider Reliability

- Retry/backoff и отмена задач.
- Probe моделей без платной генерации.
- Локальный журнал стоимости и request ID без секретов.
- Тестирование OpenAI и CloseAI sandbox/mock transport.

## Этап 5 — v1.0 Stable

- Полный production QA.
- Документированный migration path с v0.8.1.
- Проверка Blender и Unity integration.
- Stable ZIP, SHA-256 manifest, release notes и Git tag.

## Ближайшее действие

Выполнить fresh physical E2E на локальной GLB: новые Blender Preview → review → workflow audit → Unity read-only preview. Пользовательские Unity-проекты и AI Center не изменять.
