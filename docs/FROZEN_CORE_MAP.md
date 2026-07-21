# Frozen Core Map — v0.8.1

## Стабилизированные подсистемы

| Подсистема | Состояние | Правило |
|---|---|---|
| Blender Bridge | Frozen | Только hotfix |
| Unity Bridge | Frozen | Только hotfix |
| Unity Asset Library | Frozen | Расширять отдельными сервисами |
| Settings Store | Frozen | Только совместимые поля |
| Project Manager | Frozen | Сохранять `.afs` schema v1 |
| Event Bus | Frozen | Не ломать публичные события |
| Job Queue | Frozen | Расширять без изменения существующих статусов |
| SQLite Asset Database | Frozen schema v1 | Миграции обязательны |
| Static Direction Renderer | Frozen | Новые режимы — отдельный worker |
| Animation Sprite Renderer | Stable preview | Реальная Blender-проверка обязательна |

## Допустимые новые модули

- Pipeline Engine
- Atlas Builder
- Export Profiles
- Animation Preview Editor
- AI Center
- Batch Factory
- Asset Dependency Graph
- Plugin SDK

Каждый новый модуль сначала создаётся без изменения Frozen Core.
