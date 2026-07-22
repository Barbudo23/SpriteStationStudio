# Preview PNG Validation

Статус: **VERIFIED** на PNG из Blender 5.1.2.

Независимый модуль `core.validation.preview_png` проверяет опубликованный одиночный Preview без изменения файлов и без внешних Python-зависимостей.

## Проверяемые условия

- manifest имеет `schemaVersion: 1.1`;
- `canvas` содержит положительные width/height, `transparent: true` и `colorMode: RGBA`;
- путь Sprite не выходит за пределы каталога manifest;
- PNG имеет корректную сигнатуру, структуру chunks и CRC;
- обязательны IHDR, IDAT и IEND без trailing data;
- формат — 8-bit RGBA, color type 6, без interlace;
- IDAT полностью декодируется, поддерживаются PNG filters 0–4;
- фактический размер совпадает с manifest canvas;
- присутствуют видимые и прозрачные пиксели.
- размер стороны ограничен 4096, число пикселей — 4096², размер PNG — 128 MiB.

Отчёт содержит размеры, bit depth, количество видимых/прозрачных пикселей, alpha bounds и coverage ratio. Файл отчёта не создаётся: проверка read-only и возвращает неизменяемый объект Python.

Реальная проверка Preview 128×128 из Blender 5.1.2: RGBA/8-bit, 2607 видимых пикселей, 14645 пикселей с прозрачностью, alpha bounds `(31, 21, 92, 112)`, coverage ratio `0.159119`.

Следующий этап — подключить validator в `BatchPreviewCoordinator` перед публикацией staging-папки.
