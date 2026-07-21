# Unity Bridge v0.1

Unity Bridge запускает установленный Unity Editor как изолированный subprocess:

```text
AssetForge Studio
  -> Unity.exe -batchmode -nographics
  -> AssetForgeUnityBridge.Execute
  -> unity_asset_report.json
```

## Настройка

Укажите именно `Unity.exe`, обычно:

```text
C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe
```

Не выбирайте `Unity Hub.exe`.

## Первая команда

`analyze_asset` импортирует FBX/OBJ и возвращает:

- Unity version;
- тип импортированного ассета;
- Transform/bone names;
- количество SkinnedMeshRenderer;
- количество материалов;
- AnimationClip, FPS и длину;
- наличие Animator/Avatar;
- Humanoid/valid Humanoid status.

## Изоляция

Python-процесс не загружает Unity DLL. Обмен выполняется через JSON. Поэтому сбой Unity не должен разрушать GUI AssetForge.

## Ограничения текущей версии

- Unity может обновить временный bridge project при первом запуске.
- GLB требует отдельного Unity importer package.
- Ретаргетинг и SpriteAtlas будут добавлены следующими командами.


## Автоматический поиск и подключение

AssetForge сканирует:

- PATH;
- стандартные папки Unity Hub;
- дополнительные пользовательские каталоги;
- конфигурационные файлы Unity Hub.

Все найденные редакторы проверяются через batch mode. Первая рабочая версия подключается автоматически, остальные доступны в выпадающем списке.

## Цветные маркеры

- зелёный — мост подключён;
- красный — мост не подключён;
- жёлтый — идёт проверка.
