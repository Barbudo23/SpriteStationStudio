# Sprite Station Studio v0.9.0 RC1 — Release Artifact QA

Дата проверки: 2026-07-22.

Статус: **VERIFIED / PUBLISHED AS GITHUB PRERELEASE**.

## Artifact

| Поле | Значение |
|---|---|
| Source commit | `df8613c5d44be876672273692c32520e0631b59d` |
| ZIP | `SpriteStationStudio-v0.9.0rc1-df8613c5.zip` |
| Размер | 44,211,717 bytes |
| SHA-256 | `b1ec23daae4dc18548cbd85b6cfb4254ceb2c8808f686b72e1cefccc135756cb` |
| Tracked files | 160 |
| Artifact manifest `published` | `false` — фиксирует состояние на момент локальной сборки |
| GitHub prerelease | `true`, опубликован 2026-07-22 |

Локальные файлы находятся в `output/release-candidate/` и намеренно не добавлены в Git.

## Проверки

- ZIP создан только из tracked-файлов через `git archive`.
- Все пути внутри ZIP проверены на absolute path и `..` traversal.
- В архиве присутствуют `run.py`, `pyproject.toml` и `RELEASE_NOTES_v0.9.0-rc1.md`.
- SHA-256 ZIP повторно вычислен после сборки и совпал с manifest.
- ZIP распакован в новый одноразовый каталог.
- `python -S run.py --help` — `PASS`.
- `python -S -m unittest discover -s tests -q` — `PASS`, 131/131.
- `python -S Tools/Invoke-StaticSpriteWorkflowSmoke.py` — `PASS`, audit valid, 10 файлов проверено.
- `Tools/Verify-ReleaseCandidate.py` повторно проверяет manifest, размер, SHA-256, single-root ZIP, path traversal, версию и file count до извлечения.
- Verifier отклоняет symlink, encrypted и duplicate members, отдельный файл больше 1 GiB, суммарный распакованный размер больше 2 GiB и коэффициент сжатия выше 250:1.
- Manifest проходит строгую проверку типов и форматов: версия, release channel, 40-символьный commit, basename ZIP, SHA-256, положительные размеры/count и boolean published.
- Portable-path gate отклоняет backslash paths, Windows reserved names, trailing dots/spaces, colon и case-insensitive Unicode collisions до распаковки.
- Автоматизированный `--run-clean-checks` — `PASS`; опубликованный ZIP распакован во временный каталог, внутри повторены entry point, 131 tests и synthetic E2E.
- Release builder создаёт ZIP, manifest и checksum в staging-каталоге и публикует их транзакционно; искусственный сбой подтверждает rollback без частичного набора.
- Публикация использует same-volume hard links вместо overwrite-capable replace: поздняя коллизия атомарно отклоняется, внешний файл сохраняется, собственные частичные outputs откатываются.
- Clean-check extraction повторно сверяет SHA-256 и распаковывает через тот же открытый handle; подмена ZIP после первичной проверки отклоняется.

## Решение

Artifact опубликован как GitHub prerelease `v0.9.0-rc1`. Тег разрешается в `df8613c5d44be876672273692c32520e0631b59d`; три assets имеют статус `uploaded`, а GitHub digest ZIP совпадает с локальным SHA-256. Stable-статус не присваивался.

Повторная локальная проверка:

```powershell
python Tools/Verify-ReleaseCandidate.py <ZIP> <MANIFEST.json> --checksum <SHA256-file> --run-clean-checks
```
