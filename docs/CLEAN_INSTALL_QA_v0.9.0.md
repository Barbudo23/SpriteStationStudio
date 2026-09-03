# Sprite Station Studio v0.9.0 — Clean-install QA

Дата проверки: 2026-07-22.

## Метод

1. Последний Git-коммит экспортирован через `git archive`.
2. Архив распакован в новый каталог внутри игнорируемой папки `output`.
3. Все проверки запущены с `python -S`, чтобы не загружать сторонние `site-packages`.
4. Исходная рабочая копия, пользовательские настройки и generated outputs не использовались.

## Результаты

| Проверка | Статус | Результат |
|---|---|---|
| `python -S run.py --help` | `PASS` | точка входа и все базовые импорты загружены |
| `python -S -m unittest discover -s tests -q` | `PASS` | 130/130 tests, включая реальные Tk controller tests |
| `python -S Tools/Invoke-StaticSpriteWorkflowSmoke.py` | `PASS` | 3 Preview, 2 approved, 1 rejected, audit valid, 10 файлов проверено |
| Сторонние runtime-пакеты | `PASS` | базовый GUI и Static Sprite Workflow используют только Python stdlib |
| Переименование | `PASS` | активный бренд Sprite Station Studio; legacy-контракты проверены allowlist-тестом |

Blender и Unity не входят в архив и устанавливаются отдельно. Их проверенные версии зафиксированы в `docs/RC_SCOPE_v0.9.0.md`; реальные Blender/Unity gates были пройдены до этой проверки.

## Решение

Clean-install gate для текущего v0.9.0 scope закрыт. Это не означает RC/Stable: остаётся визуальный ручной Windows file-dialog сценарий и выпуск проверяемого release artifact.
