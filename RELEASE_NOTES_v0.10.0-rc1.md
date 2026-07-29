# Sprite Station Studio v0.10.0 RC1 — Local Candidate

Статус: кандидат Animation Workflow. Версия не является Stable.

## Основной результат

Sprite Station Studio преобразует анимированную 3D-модель в проверяемые
последовательности 2D-кадров и Unity-ready Multiple Sprite sheets с явным
согласованием результата.

## Добавлено

- no-overwrite preflight до запуска Blender;
- строгая проверка animation manifest и safe paths;
- CRC/decompression/8-bit RGBA validation кадров и sheets;
- SHA-256 исходной модели, каждого frame, sheet и contact sheet;
- неизменяемое решение `approved/rejected`;
- атомарная публикация approved animation package;
- финальный read-only package audit;
- отдельное окно Animation Workflow;
- воспроизводимый synthetic E2E.

## Проверено

- реальный Blender 5.1.2: анимированный FBX, 4 направления × 2 кадра;
- approved package: 16 integrity-bound артефактов;
- Unity 6000.4.0f1: 4/4 Multiple Sprite sheets, 8/8 slices, warnings 0;
- полный Python regression и реальное открытие Tk-окна.
- clean-extraction gate запускает Static Sprite и Animation Workflow synthetic E2E.

## Ограничения

- используется активная animation/action импортированной модели;
- выбор одной из нескольких Actions пока не предоставляется;
- sheets создаются горизонтальными полосами;
- AI Center остаётся в разработке;
- Blender и Unity устанавливаются отдельно.
