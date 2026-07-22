# Sprite Station Studio Brand Migration

- Public product name changed from AssetForge Studio to Sprite Station Studio (SSS).
- Python distribution and new user configuration directory use the new isolated name.
- Unity exports now prefer `Assets/SpriteStationImports`.
- Legacy `.afs` projects, `AssetForgeUnityBridge` commands, settings and Unity import folders remain supported.
- Historical changelog and release-note entries retain the former product name for traceability.
- Added a read-only, atomic Batch Preview contact sheet with source hashes and review manifest.
- Added brand-regression checks to distinguish supported legacy identifiers from stale public naming.
- Added atomic Batch Review 1.0 decisions with contact-sheet and source integrity checks.
- Added an atomic approved-only Preview staging package for the future SpriteBuilder boundary.
- Added Static Sprite Set 1.0 builder with pivot, alpha-bounds and source-integrity validation.
- Added a read-only Static Sprite Set adapter for the existing Unity preset preview workflow.
- Verified the adapter in Unity 6000.4.0f1: 2/2 Single Sprites valid in read-only preview with no warnings.
- Added an all-or-nothing coordinator for review, approved staging, SpriteBuilder and Unity preview preparation.
- Added strict read-only auditing for published workflow contracts, paths, item identities and hashes.
- Added a reproducible three-Preview end-to-end workflow smoke tool with final read-only audit.
- Recorded v0.9.0 backend readiness and the remaining physical E2E, GUI and clean-install gates.
- Closed the fresh physical E2E gate with new Blender renders and Unity 6000.4.0f1 read-only validation (2/2, no warnings).
- Enabled a separate minimal SpriteBuilder workflow window without changing existing Render, Unity or AI Center routes.

# v0.8.3 Static Sprite Pipeline Dev

- Camera Profile в интерфейсе подключён к реальному 4/8-направленному Blender-рендеру.
- Добавлены проверяемые профили Strategy30, XCOM, Commandos и Diablo.
- Параметры ортографической камеры передаются worker-процессу явно.
- Manifest обновлён до 1.1: RGBA-холст, камера, нормализация, bounds и pivot.
- Добавлены тесты профилей камеры и контракта статического спрайта.
- Автообнаружение Blender на Windows дополнено чтением InstallLocation из реестра, включая установку на другом диске.
- Выполнен успешный реальный smoke-test в Blender 5.1.2 на GLB-модели.
- Единый manifest 1.1, Camera Profile и pivot перенесены в анимационный рендер.
- Анимационный пакет проверен реальным Blender smoke-тестом: 4 направления × 2 кадра, sheets, contact sheet и ZIP.
- Режим одиночного Preview переведён на общие Camera Profiles и `preview_manifest.json` 1.1.
- Одиночный Preview проверен реальным рендером профиля Diablo в Blender 5.1.2.
- Добавлен `unity_import_preset.json` для Single Sprite и нарезки анимационных Multiple Sprite.
- Unity preset автоматически включается в ZIP без изменения пользовательских Unity-проектов.
- Unity Bridge получил read-only команду `preview_sprite_import` с проверкой PNG и границ slices.
- Статический пакет успешно проверен в Unity 6000.4.0f1: 4/4 спрайта valid, предупреждений нет.
- Анимационный пакет проверен в Unity: 4/4 sheet и 8/8 slices valid, предупреждений нет.
- Из bridge project удалены несовместимые необязательные IDE/Collaborate/Test зависимости.
- В Integrations добавлена кнопка `UNITY IMPORT PREVIEW (READ-ONLY)`.
- Интерфейс автоматически выбирает preset последнего рендера и показывает assets/slices/warnings.
- Unity preview выполняется в фоновом потоке с защитой от повторного запуска.
- Добавлен подтверждаемый экспорт проверенного пакета в новую папку `Assets/AssetForgeImports`.
- Экспорт запрещает перезапись, mismatched preview, warnings, invalid assets и небезопасные пути.
- После нового рендера старый Unity preview автоматически считается недействительным.
- AI Center оставлен в статусе «в разработке / приостановлен».

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
# v0.8.2 Dev — AI Center

- Добавлен независимый модуль AI Center.
- Добавлены OpenAI API, Codex Bridge и CloseAI API provider contracts.
- API-ключи читаются только из переменных окружения и не сохраняются.
- Добавлены JSON jobs, SHA-256 prompt и обязательный human-review gate.
- Добавлены тесты AI-настроек, Codex job, OpenAI-compatible API и регистрации модуля.
- Обновлены аудит baseline, GitHub workflow и план разработки.

# v0.8.1.1 Hotfix

- SQLite-соединения гарантированно закрываются после операций на Windows.
- Схема базы и публичный API не изменены.
