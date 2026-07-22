# Unity Sprite Export Preset

Статус: **v0.9.0 RC1 local candidate, безопасный переносимый контракт**.

После успешного рендера Sprite Station Studio создаёт `unity_import_preset.json`. Для пакетов 4/8 направлений и анимаций этот файл также автоматически добавляется в ZIP.

Preset не копирует файлы в пользовательский Unity-проект и не создаёт `.meta` или GUID. Это сделано намеренно: применение настроек остаётся явной операцией и не может незаметно изменить существующие ассеты.

Approved Static Sprite Set также может быть преобразован в отдельный переносимый preview-пакет. Адаптер повторно проверяет SHA-256, RGBA-размеры, alpha bounds, pivot и актуальный бренд Sprite Station Studio, затем копирует спрайты и создаёт preset атомарно. На этом шаге Unity не запускается, пользовательский проект не изменяется.

Реальный smoke-test адаптера выполнен в Unity 6000.4.0f1 через изолированный bridge project: два Single Sprite прошли read-only preview, результат `2/2 valid`, предупреждений нет. Воспроизводимый запуск находится в `Tools/Invoke-StaticSpriteUnitySmoke.py`.

Fresh physical E2E также выполнен на локальной GLB: Blender 5.1 создал два новых Preview 128×128, полный approved workflow прошёл аудит до и после Unity, итоговый Unity read-only preview подтвердил 2/2 valid без предупреждений. Сценарий воспроизводится `Tools/Invoke-PhysicalStaticSpriteE2E.py`.

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

Bridge project использует только необходимые встроенные Unity-модули. Необязательные IDE, Collaborate/Plastic SCM и Test Framework пакеты удалены, чтобы исключить их несовместимость с версиями Unity Editor.

## Запуск из интерфейса

1. Создайте Preview, пакет направлений или анимацию.
2. Откройте панель Integrations и убедитесь, что Unity Bridge подключён.
3. Нажмите **UNITY IMPORT PREVIEW (READ-ONLY)**.
4. Sprite Station Studio автоматически использует preset последнего рендера. Если он не найден, программа предложит выбрать `unity_import_preset.json`.
5. После проверки откроется краткий отчёт: valid assets, slices и warnings. Полный JSON записывается в журнал интерфейса и файл `unity_import_preview_report.json`.

Операция выполняется в фоне. Повторный запуск блокируется до завершения текущей проверки.

## Явный экспорт в Unity Assets

После успешного read-only preview становится доступен путь **EXPORT VERIFIED PACKAGE TO UNITY**:

1. Нажмите кнопку и выберите корень Unity-проекта или его папку `Assets`.
2. Подтвердите операцию в отдельном диалоге.
3. Sprite Station Studio создаст только новую папку `Assets/SpriteStationImports/<asset>`.
4. Туда копируются проверенные PNG, preset, preview report и manifest.

Защита экспорта:

- отчёт обязан принадлежать выбранному preset;
- все assets должны иметь `valid=true`, warnings не допускаются;
- пути проверяются на выход за пределы пакета;
- существующая целевая папка никогда не перезаписывается;
- новый рендер сбрасывает подтверждение старого preview;
- копирование собирается во временной staging-папке и становится видимым только после успеха.

## Подтверждаемое применение TextureImporter

После экспорта становится доступна отдельная команда **APPLY TEXTURE IMPORT SETTINGS**. Перед запуском интерфейс повторно показывает целевую папку и требует подтверждение.

Команда принимает непосредственную папку `Assets/SpriteStationImports/<asset>` (старые `Assets/AssetForgeImports/<asset>` также читаются), повторно проверяет preset и запрещает пути за пределы пакета. Unity применяет Sprite type, alpha, mipmaps, wrap/filter/compression, pixels per unit, pivot и Multiple slices только к PNG, перечисленным в preset. Результат записывается в `unity_import_apply_report.json`; ошибки и предупреждения не считаются успешным завершением.

Существующие ассеты вне новой папки Sprite Station не изменяются. `.meta` внутри экспортированного пакета создаются или обновляются Unity только после явного подтверждения пользователя.

Реальные smoke-тесты применения выполнены в Unity 6000.4.0f1: 4/4 статических Sprite и 4/4 анимационных sheets с 8/8 slices получили TextureImporter-настройки без предупреждений.
