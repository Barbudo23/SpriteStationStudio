# BatchPlan 1.0

Статус: **IMPLEMENTED_NOT_INTEGRATION_VERIFIED**.

`BatchPlan` — независимый локальный контракт для будущего последовательного выполнения максимум трёх Blender-операций. На текущем этапе модуль не подключён к GUI, `BlenderRunner`, существующей `JobQueue` или AI Center.

## Операции и состояния

Допустимые операции: `preview`, `directions`, `animation`.

Состояния элемента: `pending`, `running`, `completed`, `failed`, `cancelled`. Одновременно выполняться может только один элемент. Завершённый элемент нельзя повторно перевести в `running`; ошибочный элемент разрешено возобновить, при этом увеличивается `attemptCount` и очищается старая ошибка.

## Ограничения безопасности

- план содержит от одного до трёх элементов;
- `itemId` и `outputPath` уникальны;
- `outputPath` не допускает сегмент `..`;
- завершённый элемент обязан иметь `resultManifest`;
- ошибка ограничена 1000 символами и хранится только у `failed`;
- неизвестная `schemaVersion` отклоняется;
- сохранение выполняется во временный файл в том же каталоге, с `fsync`, резервной копией при обновлении и атомарной заменой;
- staging и backup удаляются после успеха или ошибки.

## JSON contract

```json
{
  "schemaVersion": "1.0",
  "planId": "UUID",
  "createdUtc": "ISO-8601 UTC",
  "updatedUtc": "ISO-8601 UTC",
  "items": [
    {
      "itemId": "preview-01",
      "operation": "preview",
      "sourcePath": "models/unit.glb",
      "outputPath": "renders/preview-01",
      "status": "pending",
      "attemptCount": 0,
      "resultManifest": null,
      "error": null
    }
  ]
}
```

Следующий этап: подключить контракт только к одному существующему Blender workflow через отдельный coordinator и выполнить реальный Blender smoke. До этого статус остаётся `IMPLEMENTED_NOT_INTEGRATION_VERIFIED`.

