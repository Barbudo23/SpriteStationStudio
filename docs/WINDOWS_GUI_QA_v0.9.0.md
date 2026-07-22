# Sprite Station Studio v0.9.0 — Windows GUI QA

Дата проверки: 2026-07-22.

Среда: Windows 11, Python 3.14, запуск через `run_windows.bat`.

| Сценарий | Результат | Наблюдение |
|---|---|---|
| Запуск главного окна | `PASS` | окно `Sprite Station Studio v0.8.3 Dev — Static Sprite Pipeline` открылось без ошибки |
| Открытие SpriteBuilder | `PASS` | отдельное окно `Sprite Station Studio — Static Sprite Workflow v0.9` открылось корректно |
| Компоновка панели | `PASS` | видимы BatchPlan, Contact manifest, explicit decisions, output, build и audit |
| Пустые пути | `PASS AFTER FIX` | вместо разрешения `Path("")` в рабочую папку выводится явное требование выбрать JSON-файл |
| Disposable fixture | `PASS` | `Tools/Invoke-StaticSpriteWorkflowSmoke.py --prepare-gui-fixture <DIR>` создаёт новую plan/contact-пару без Blender, Unity и API |
| Tk controller happy-path | `PASS` | реальное Tk-окно загрузило три Preview, опубликовало workflow и прошло финальный audit |
| Rejected item | `PASS` | один из трёх Preview оставлен `rejected` и исключён из опубликованного набора |
| Визуальный happy-path мышью | `PENDING` | требуется ручной выбор plan/contact через системный файловый диалог |
| Invalid plan/contact pair | `PASS` | контроллер отклоняет contact manifest, который ссылается на другой BatchPlan |
| Immutable review и restart | `PASS` | повторный контроллер использует совпадающее решение для нового output |
| No-overwrite | `PASS` | повторная публикация в существующий output отклоняется |
| Final audit | `PASS` | исходная и повторно запущенная публикации завершаются статусом `audit valid` |

Итог: логика GUI-контроллера подтверждена end-to-end, включая mismatch, immutable review, restart и no-overwrite. Визуальный ручной gate системного file dialog остаётся `PARTIAL`; RC/Stable не объявляется. AI Center не изменялся.

Для продолжения ручного QA можно создать новый набор в ранее не существующей папке:

```powershell
python Tools/Invoke-StaticSpriteWorkflowSmoke.py --prepare-gui-fixture output/gui-qa-manual
```

Инструмент намеренно не перезаписывает существующий каталог.
