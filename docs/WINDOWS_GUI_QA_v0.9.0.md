# Sprite Station Studio v0.9.0 — Windows GUI QA

Дата проверки: 2026-07-22.

Среда: Windows 11, Python 3.14, запуск через `run_windows.bat`.

| Сценарий | Результат | Наблюдение |
|---|---|---|
| Запуск главного окна | `PASS` | окно `Sprite Station Studio v0.8.3 Dev — Static Sprite Pipeline` открылось без ошибки |
| Открытие SpriteBuilder | `PASS` | отдельное окно `Sprite Station Studio — Static Sprite Workflow v0.9` открылось корректно |
| Компоновка панели | `PASS` | видимы BatchPlan, Contact manifest, explicit decisions, output, build и audit |
| Пустые пути | `PASS AFTER FIX` | вместо разрешения `Path("")` в рабочую папку выводится явное требование выбрать JSON-файл |
| Happy-path на реальном plan/contact | `PENDING` | требуется подготовленный незаписанный output-каталог |
| Rejected item | `PENDING` | требуется реальная пара plan/contact |
| Invalid plan/contact pair | `PENDING` | требуется отдельная безопасная fixture-пара |
| Immutable review и overwrite | `PENDING` | проверять только на disposable output |
| Audit existing | `PENDING` | требуется завершённый disposable workflow |

Итог: GUI gate остаётся `PARTIAL`; RC/Stable не объявляется. AI Center не изменялся.
