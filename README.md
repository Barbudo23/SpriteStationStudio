# AssetForge Studio — v0.8.2 AI Center Dev

Текущая ветка основана на проверенном архиве v0.8.1 и отдельном SQLite hotfix.
Добавлен модуль **AI Center** с провайдерами OpenAI API, Codex Bridge и CloseAI API.
Подробности: `docs/AI_CENTER.md`, план: `docs/DEVELOPMENT_PLAN.md`.

Первая рабочая версия приложения для автоматического создания PNG-превью из 3D-модели через Blender.

## Возможности

- графический интерфейс без сторонних Python-библиотек;
- выбор Blender вручную или автоматический поиск;
- импорт FBX, GLB, GLTF и OBJ;
- очистка временной Blender-сцены;
- вычисление мирового Bounding Box;
- установка модели на землю и центрирование;
- автоматическая ортографическая камера;
- студийное освещение;
- прозрачный фон;
- экспорт `Preview.png`;
- экспорт `import_report.json`;
- журнал выполнения в интерфейсе;
- CLI-режим;
- базовые автоматические тесты без запуска Blender.

## Требования

- Windows 10/11, Linux или macOS;
- Python 3.10 или новее;
- Blender 4.2+ или 5.x.

Blender должен быть установлен отдельно. Программа не включает Blender в архив.

## Быстрый запуск Windows

1. Распакуйте архив.
2. Запустите `run_windows.bat`.
3. В поле Blender укажите `blender.exe`, если он не найден автоматически.
4. Выберите реальную модель `.fbx`, `.glb`, `.gltf` или `.obj`.
5. Выберите папку результата.
6. Нажмите **Создать Preview**.
7. После завершения откройте:
   - `Preview.png`
   - `import_report.json`

## Запуск через Python

```bash
python run.py
```

## CLI

```bash
python run.py --cli \
  --blender "/path/to/blender" \
  --model "/path/to/model.fbx" \
  --output "./output"
```

## Проверка без Blender

```bash
python -m unittest discover -s tests -v
```

## Ограничения MVP

- одна модель за один запуск;
- один ракурс;
- рендер только статического кадра;
- материалы отображаются так, как их импортирует Blender;
- внешние текстуры должны быть доступны модели;
- некоторые FBX могут зависеть от версии экспортёра.

## Структура результата

```text
output/
├── Preview.png
└── import_report.json
```

## Исправление Blender 5.1

Режим `AUTO` определяет доступный идентификатор EEVEE через Blender RNA.
Поддерживаются `BLENDER_EEVEE` и `BLENDER_EEVEE_NEXT`, с резервным выбором
Workbench или Cycles.

## Новый интерфейс

Добавлена расширяемая оболочка AssetForge Studio с реестром модулей, Preview, Inspector и нижней панелью Jobs/Log/Output.


## Image Source — 4 ракурса без Blender

В Inspector → Source выберите `4 изображения`.

Поддерживаемые позиции:

- Front Left
- Front Right
- Back Right
- Back Left

После выбора четырёх файлов и папки результата нажмите
`СОЗДАТЬ IMAGE ASSET ZIP`.

Программа создаст:

```text
<AssetName>_ImageAsset.zip
├── manifest.json
├── README.txt
└── images/
    ├── front_left.*
    ├── front_right.*
    ├── back_right.*
    └── back_left.*
```

Blender для этой операции не используется.

## Hotfix 0.3.1

Исправлена ошибка запуска `AttributeError: render_button`.

## Sprite Bar

В центральном Preview добавлен режим `Sprite Bar`, который показывает последний проверочный лист всех ракурсов. До первого собственного экспорта используется вложенный референс.


## Рендер 8 ракурсов

В Inspector → Render выберите `8 направлений`.

Программа:

1. импортирует модель один раз;
2. создаёт AssetRoot;
3. рендерит модель через каждые 45°;
4. сохраняет восемь PNG;
5. создаёт `contact_sheet.png`;
6. создаёт `manifest.json`;
7. упаковывает всё в `<ModelName>_8dir.zip`;
8. показывает contact sheet во вкладке `Sprite Bar`.

Blender нужен только для режима 3D-модели.


## Unity Bridge v0.1

См. `docs/UNITY_BRIDGE.md`. В Inspector → Bridges укажите Unity.exe, проверьте подключение и запустите анализ выбранной модели.


## Auto Bridge v0.8.1 Core Hotfix

Unity и Blender ищутся автоматически. Вкладка Bridges показывает цветные маркеры состояния и список всех рабочих версий Unity.


## Unity Asset Library v0.1

Кнопка `Unity Asset Library` открывает локальный браузер Unity-проектов и позволяет загрузить модель напрямую в Pseudo3D Forge. См. `docs/UNITY_ASSET_LIBRARY.md`.


## Stable baseline

Версия v0.6.1 сохраняет настройки мостов и последние пути, выполняет поиск Unity-проектов в фоне и защищает интерфейс от повторных долгих задач. См. `RELEASE_NOTES_v0.6.1_STABLE.md`.


## Animation Sprite Renderer v0.1

Добавлен рендер активной анимации в 4/8 направлениях с PNG-кадрами, отдельными sprite sheets, manifest и ZIP. См. `docs/ANIMATION_SPRITES.md`.


## AssetForge Core v0.8

Добавлены `.afs` проекты, Event Bus, Job Queue, SQLite Asset Database и Plugin Registry. См. `docs/CORE_FRAMEWORK.md`.


## v0.8.1 Hotfix

Исправлено падение Tkinter при запуске из-за смешивания `pack` и `grid` в верхней панели.


## Stable Baseline Policy

Эта сборка зафиксирована как базовая точка ZIP-разработки.
Правила находятся в:

- `docs/STABLE_DEVELOPMENT_POLICY.md`
- `docs/FROZEN_CORE_MAP.md`
- `docs/ZIP_RELEASE_WORKFLOW.md`
