# Unity Sprite Export Preset

Статус: **v0.8.3, безопасный переносимый контракт**.

После успешного рендера AssetForge Studio создаёт `unity_import_preset.json`. Для пакетов 4/8 направлений и анимаций этот файл также автоматически добавляется в ZIP.

Preset не копирует файлы в пользовательский Unity-проект и не создаёт `.meta` или GUID. Это сделано намеренно: применение настроек остаётся явной операцией и не может незаметно изменить существующие ассеты.

## Записываемые настройки

- `Texture Type`: Sprite;
- прозрачность alpha;
- mipmaps выключены;
- `Wrap Mode`: Clamp;
- `Filter Mode`: Bilinear;
- compression: Uncompressed;
- `Pixels Per Unit`: 100;
- pivot из manifest 1.1, сейчас `[0.5, 0.0]`;
- режим `Single` для отдельных PNG;
- режим `Multiple` и точные прямоугольники нарезки для animation sheet.

## Виды пакетов

- одиночный Preview — один Single Sprite;
- 4/8 направлений — отдельный Single Sprite для каждого направления;
- анимация — Multiple Sprite для каждого горизонтального sheet, имена и исходные номера кадров сохранены.

## Следующий этап

Изолированный Unity Bridge поддерживает команду `preview_sprite_import`. Она напрямую читает PNG, проверяет размеры и границы всех slices, формирует `unity_import_preview_report.json` и не вызывает импорт в пользовательский проект.

Реальные smoke-тесты выполнены в Unity 6000.4.0f1:

- четыре статических PNG 256×256 — 4/4 `valid=true`;
- четыре анимационных sheet 512×256 и восемь slices — 4/4 sheet и 8/8 slices корректны;
- предупреждений нет, оба отчёта имеют `readOnlyPreview=true`.

Bridge project использует только необходимые встроенные Unity-модули. Необязательные IDE, Collaborate/Plastic SCM и Test Framework пакеты удалены, чтобы исключить их несовместимость с версиями Unity Editor. Следующий шаг — вывести запуск preview и его отчёт в интерфейс AssetForge Studio.
