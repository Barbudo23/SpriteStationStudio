# Sprite Station Studio v0.9.0 — Post-RC Closeout

Дата повторной проверки: 2026-07-30.

Статус технической стабилизации: **COMPLETE**.

Статус релиза: **v0.9.0-rc1 остаётся prerelease**. Перевод в Stable требует отдельного продуктового решения.

## Проверенный опубликованный артефакт

| Поле | Значение |
|---|---|
| Tag | `v0.9.0-rc1` |
| Source commit | `df8613c5d44be876672273692c32520e0631b59d` |
| ZIP | `SpriteStationStudio-v0.9.0rc1-df8613c5.zip` |
| Размер | `44,211,717` bytes |
| SHA-256 | `b1ec23daae4dc18548cbd85b6cfb4254ceb2c8808f686b72e1cefccc135756cb` |
| Tracked files | `160` |

## Финальная повторная проверка

Команда `Tools/Verify-ReleaseCandidate.py ... --run-clean-checks` завершилась с кодом `0`:

- manifest, размер, SHA-256 и file count — `PASS`;
- безопасная структура ZIP и portable paths — `PASS`;
- clean extraction — `PASS`;
- `python -S run.py --help` — `PASS`;
- встроенная regression архива — `131/131 PASS`;
- synthetic Static Sprite Workflow E2E — `PASS`;
- read-only Unity preparation audit — `PASS`;
- текущая regression ветки стабилизации — `153/153 PASS`.

## Результат стабилизации

После публикации RC1 усилены только тесты, документация, builder и внешний verifier:

- автоматическая повторная проверка release artifact;
- защита от symlink, encrypted/duplicate members, traversal и zip bombs;
- строгий manifest contract и переносимые имена;
- транзакционная no-overwrite публикация с rollback;
- защита от поздней коллизии и подмены ZIP;
- ограничения размеров входа;
- контролируемые CLI-ошибки без traceback.

Пользовательские файлы приложения, Blender/Unity worker и содержимое опубликованного ZIP после artifact commit не менялись. Поэтому технической необходимости выпускать RC2 нет.

## Следующее решение

Допустимы два отдельных направления:

1. выдержать дополнительный период пользовательского тестирования RC1 и затем отдельно одобрить Stable;
2. открыть новый milestone после v0.9.0 для Animation Workflow либо возобновления AI Center.

До такого решения post-RC scope считается закрытым, а новые функции в ветку стабилизации не добавляются.
