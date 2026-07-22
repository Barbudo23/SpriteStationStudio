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
| Визуальный file-dialog path | `PASS` | через системный Windows-диалог выбраны BatchPlan и contact manifest; отображены три review items |
| Invalid plan/contact pair | `PASS` | контроллер отклоняет contact manifest, который ссылается на другой BatchPlan |
| Immutable review и restart | `PASS` | повторный контроллер использует совпадающее решение для нового output |
| No-overwrite | `PASS` | повторная публикация в существующий output отклоняется |
| Final audit | `PASS` | исходная и повторно запущенная публикации завершаются статусом `audit valid` |

Итог: Manual Windows GUI QA закрыт. Логика контроллера подтверждена end-to-end, включая mismatch, immutable review, restart и no-overwrite; системный file dialog визуально проверен. RC/Stable автоматически не объявляется. AI Center не изменялся.

Для продолжения ручного QA можно создать новый набор в ранее не существующей папке:

```powershell
python Tools/Invoke-StaticSpriteWorkflowSmoke.py --prepare-gui-fixture output/gui-qa-manual
```

Инструмент намеренно не перезаписывает существующий каталог.
