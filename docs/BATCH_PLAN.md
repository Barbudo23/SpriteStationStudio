# BatchPlan 1.0

Статус контракта: **VERIFIED**. Интеграция Preview: **VERIFIED** в Blender 5.1.2.

`BatchPlan` — локальный контракт последовательного выполнения максимум трёх Blender-операций. Отдельный `BatchPreviewCoordinator` подключает только операцию `preview` к существующему `BlenderRunner`. GUI, `JobQueue`, направления, анимация и AI Center не подключены.

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

## Preview coordinator

Coordinator принимает путь к плану и выполняет ровно один следующий `failed` или `pending` элемент. Перед Blender-вызовом состояние `running` атомарно сохраняется. Рендер выполняется в уникальной staging-папке; проверяются `preview_manifest.json` версии 1.1, PNG chunks/CRC, RGBA/8-bit, размеры canvas, alpha и нахождение Sprite внутри staging. Только проверенная папка атомарно становится конечным результатом.

Существующая конечная папка никогда не перезаписывается. При ошибке staging удаляется, а диагностированное состояние `failed` сохраняется. Повторный вызов возобновляет failed-элемент. Если процесс прервался после публикации результата, следующий запуск распознаёт валидный manifest и восстанавливает `completed` без повторного Blender-рендера.

Повреждённый, полностью пустой, полностью непрозрачный или не соответствующий manifest PNG блокирует публикацию и сохраняет понятную диагностику в BatchPlan.

Интегрированный real smoke в Blender 5.1.2 завершён без предупреждений: PNG 128×128 прошёл CRC/RGBA/alpha-проверку до публикации, элемент получил `completed`, attempt 1, staging был удалён.

## Явный batch-запуск

`run_batch` последовательно вызывает проверенный Preview workflow максимум для трёх элементов. После каждого элемента BatchPlan уже содержит атомарный checkpoint. При первой ошибке запуск завершается без вызова оставшихся элементов: успешные сохраняют `completed`, ошибочный — `failed`, остальные — `pending`. Результат запуска содержит список завершённых item ID, failed item ID и диагностику без исключения из coordinator API.

Real smoke в Blender 5.1.2 подтвердил один явный запуск из трёх Preview: три независимых staging-каталога, три PNG-проверки, состояния `completed/completed/completed`, attempt 1 и три корректных result manifest. Общее время контрольного запуска при 128×128 составило около 54 секунд.

Реальный smoke выполнен в Blender 5.1.2 на эталонной GLB-модели: `pending → running → completed`, attempt 1, `preview_manifest.json` 1.1 и PNG опубликованы из staging без перезаписи. Предупреждение устаревшего `World.use_nodes` устранено условной совместимостью и проверяется повторным smoke.
