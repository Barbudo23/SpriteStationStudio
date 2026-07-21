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

Провести Blender smoke-test статических 4/8-направленных спрайтов на реальной модели и проверить одинаковый масштаб, прозрачность и положение pivot. После этого распространить контракт manifest 1.1 на анимационный конвейер. AI Center не развивать до отдельного решения пользователя.
