# План разработки AssetForge Studio

## Контроль версий

- Репозиторий: `Barbudo23/AssetForge` (private).
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
- [ ] Добавить кнопку Unity Import Preview и отчёт в интерфейс.

## Этап 3 — v0.9.0 Production Workflow

- Пакетная генерация до трёх кадров за запуск.
- Возобновляемый batch plan.
- Проверка PNG, alpha и геометрии объекта.
- Contact sheet и визуальное пакетное согласование.
- Импорт утверждённых кадров в SpriteBuilder/Animation pipeline.

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

Добавить кнопку Unity Import Preview и показ read-only отчёта в интерфейсе, не копируя файлы в пользовательский проект. AI Center не развивать до отдельного решения пользователя.
