# GitHub workflow

Рабочие версии AssetForge Studio контролируются в приватном репозитории
`Barbudo23/AssetForge`.

## Правила

1. Новая функция начинается от последнего проверенного baseline/hotfix.
2. Frozen Core меняется только отдельным hotfix-коммитом.
3. Перед коммитом запускается `python -m unittest discover -s tests -v`.
4. В коммит не входят API-ключи, `.env`, пользовательские settings, output и cache.
5. Ветка публикуется в GitHub и получает draft PR, если существует отдельная base branch.
6. Stable tag создаётся только после ручной UI/Blender/Unity проверки.

## Активные линии

| Линия | Назначение |
|---|---|
| `studio/0.8.1-baseline` | импорт исходного стабильного архива |
| `studio/0.8.2-ai-dev` | AI Center и связанные тесты |
| `stack/04-rev00` | архивная линия предыдущего AssetForge ProjectOS |

Истории Studio и ProjectOS не смешиваются слиянием без отдельного migration plan.
