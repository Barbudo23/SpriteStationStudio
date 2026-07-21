# v0.8.1 Core Hotfix

- Fixed Tkinter startup crash caused by mixing pack and grid in the top bar.
- Added a regression test for top-bar geometry managers.

# v0.8.0 Core Framework

- Added .afs project system and project folder layout.
- Added Event Bus.
- Added background Job Queue.
- Added SQLite Asset Database.
- Added Plugin Registry.
- Added Project Manager and Job Queue UI.
- Added last project persistence.
- Added core regression tests.

# v0.7.0 Animation Sprites

- Added animated model frame rendering for 4/8 directions.
- Added per-direction horizontal sprite sheets.
- Added animation contact sheet, report, manifest and ZIP.
- Added configurable frame range, step and maximum sampled frames.
- Added duplicate animation-render task protection.
- Fixed settings restoration before Tk variables were initialized.
- Added animation runner and initialization regression tests.

# v0.6.1 Stable

- Added persistent atomic application settings.
- Added last Unity project and editor persistence.
- Moved Unity project discovery off the UI thread.
- Added closed-window callback protection.
- Added duplicate bridge scan protection.
- Added explicit bridge discovery error handling.
- Added settings and task coordination regression tests.
- Added stable release checklist and release notes.

# v0.6.0 Unity Asset Browser

- Added local Unity project discovery.
- Added Unity Assets filesystem indexer and persistent JSON cache.
- Added model, prefab, animation, texture, material and scene filters.
- Added asset search and details panel.
- Added texture thumbnail preview.
- Added direct model loading into Pseudo3D Forge.
- Added one-click Unity Bridge analysis for selected models.
- Added Unity GUID extraction from .meta files.
- Added four Unity Asset Library tests.

# v0.5.1 Auto Bridge

- Automatic discovery of Unity Editors installed through Unity Hub.
- Batch-mode verification of every detected Unity version.
- Automatic connection to the first working Unity version.
- Dropdown for switching between working Unity versions.
- Green/red/yellow bridge status markers for Unity and Blender.
- Fixed missing Unity event handling in the GUI.
- Added discovery and fallback tests.

# v0.5.0 Unity Bridge

- Added Unity.exe selection and auto-detection.
- Added batch-mode version check.
- Added isolated JSON command/report protocol.
- Added Unity Editor asset analyzer.
- Added Bridges inspector tab and Settings dialog.
- Added UnityRunner unit tests.

# Changelog

## 0.4.0-eight-directions

- Добавлен Blender Worker для 4/8 ракурсов.
- Добавлен поворот AssetRoot с шагом 45°.
- Добавлены 8 PNG, contact sheet, manifest и ZIP.
- Sprite Bar автоматически показывает последний пакет.
- Добавлены тесты DirectionRenderRunner.


## 0.3.2-sprite-bar

- Добавлен режим Preview: Sprite Bar.
- Добавлен референсный contact sheet.
- Добавлен контракт для показа последнего выполненного набора ракурсов.


## 0.3.1-hotfix

- Исправлен запуск GUI: source mode теперь инициализируется после render_button.
- Добавлена защита hasattr для обновления текста основной кнопки.
- Добавлен regression-тест порядка инициализации Inspector.


## 0.3.0-ui-image-source

- Добавлен выбор источника: 3D-модель или четыре изображения.
- Добавлены поля Front Left, Front Right, Back Right, Back Left.
- Добавлена упаковка Image Asset без Blender.
- Добавлен manifest.json и ZIP в выбранной директории.
- Добавлены тесты Image Source.


## 0.1.1-mvp-fix — 2026-07-17

- Исправлена ошибка Blender 5.1.2: `BLENDER_EEVEE_NEXT` отсутствует.
- Добавлен автоматический выбор `BLENDER_EEVEE`/`BLENDER_EEVEE_NEXT`.
- Добавлен fallback на Workbench и Cycles.
- Реальный выбранный движок сохраняется в JSON-отчёте.
- Добавлены regression-тесты.


## 0.1.0-mvp — 2026-07-17

- Добавлен рабочий Tkinter GUI.
- Добавлен поиск Blender.
- Добавлен background worker для Blender.
- Реализован импорт FBX, GLB, GLTF и OBJ.
- Реализованы центрирование, выравнивание по земле и Bounding Box.
- Реализованы автоматическая камера и студийное освещение.
- Реализован прозрачный PNG-рендер.
- Добавлен JSON-отчёт.
- Добавлен CLI.
- Добавлены unit-тесты командной строки и валидации.
