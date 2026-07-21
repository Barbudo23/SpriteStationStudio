# План разработки AssetForge Studio

## Контроль версий

- Репозиторий: `Barbudo23/AssetForge` (private).
- Исходная база: ветка `studio/0.8.1-baseline`, тег `studio-v0.8.1-baseline`.
- Hotfix: тег `studio-v0.8.1.1-hotfix`.
- Текущая разработка: ветка `studio/0.8.2-ai-dev`.
- `stable` не получает экспериментальный код напрямую.
- Каждая рабочая версия публикуется отдельным коммитом; крупные этапы — отдельными
  ветками и draft PR.

## Этап 1 — v0.8.2 AI Center Foundation

- [x] Реестр AI Center в UI и Core.
- [x] Переключатель OpenAI / Codex / CloseAI.
- [x] Настройки без хранения секретов.
- [x] Один API-запрос с 1–4 референсами.
- [x] Codex Bridge JSON job.
- [x] Human-review gate.
- [x] Автотесты контрактов.
- [ ] Фоновое выполнение API-запроса через Job Queue.
- [ ] Preview результата внутри AI Center.

## Этап 2 — v0.9.0 Production Workflow

- Пакетная генерация до трёх кадров за запуск.
- Возобновляемый batch plan.
- Проверка PNG, alpha и геометрии объекта.
- Contact sheet и визуальное пакетное согласование.
- Импорт утверждённых кадров в SpriteBuilder/Animation pipeline.

## Этап 3 — v0.9.5 Provider Reliability

- Retry/backoff и отмена задач.
- Probe моделей без платной генерации.
- Локальный журнал стоимости и request ID без секретов.
- Тестирование OpenAI и CloseAI sandbox/mock transport.

## Этап 4 — v1.0 Stable

- Полный production QA.
- Документированный migration path с v0.8.1.
- Проверка Blender и Unity integration.
- Stable ZIP, SHA-256 manifest, release notes и Git tag.

## Ближайшее действие

Провести ручную проверку окна AI Center, затем вынести сетевую генерацию в Job Queue.
До ручного подтверждения версия остаётся `v0.8.2 Dev`.
