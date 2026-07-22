# Sprite Station Studio v0.9.0 — RC Scope and Support Matrix

Статус документа: **APPROVED DEVELOPMENT SCOPE**. Статус продукта: **не RC и не production-ready**.

## Цель v0.9.0

Довести основной локальный маршрут до воспроизводимого процесса:

`3D import → camera profile → Blender render → validation → review → Unity export/import`

Версия v0.9.0 расширяет проверенный v0.8.3 Static Sprite Pipeline небольшими возобновляемыми пакетами. Существующие одиночный, направленный и анимационный режимы остаются рабочими и обратно совместимыми.

## Входит в scope

1. Новый версионированный `BatchPlan` для максимум трёх локальных Blender-операций.
2. Явные состояния элементов: `pending`, `running`, `completed`, `failed`, `cancelled`.
3. Атомарное сохранение плана, checkpoint после каждого элемента и безопасное возобновление.
4. Идемпотентность: завершённый элемент не запускается повторно без отдельной команды пользователя.
5. Проверка PNG, alpha, размеров холста и обязательных manifest-полей.
6. Contact sheet для ручного согласования результатов.
7. Передача только утверждённых результатов в существующий Unity export/import workflow.

## Не входит в scope

- возобновление разработки AI Center или платные API-вызовы;
- перенос Blender, Unity, AI и batch на единую новую Job System;
- массовый рефакторинг `gui.py`;
- изменение manifest 1.1 или `unity_import_preset.json` 1.0 без отдельной миграции;
- Godot и Unreal exporters;
- installer, updater, signing и публикация Stable/RC;
- пакет больше трёх операций до подтверждения поведения и производительности.

## Публичные контракты

- Render manifest: `1.1`, чтение и семантика сохраняются.
- Unity import preset: `1.0`, чтение и семантика сохраняются.
- Новый BatchPlan: отдельная схема `1.0`; существующие контракты не расширяются скрыто.
- Batch review decision: отдельная схема `1.0`, только `approved` / `rejected`, с SHA-256 contact sheet и исходных Preview.
- Approved Preview staging: отдельная схема `1.0`; копирует только утверждённые результаты после повторной проверки всей цепочки SHA-256.
- Static Sprite Set: отдельная схема `1.0`, фиксирует RGBA-размеры, alpha bounds, SHA-256 и pivot `bottom_center` каждого утверждённого Sprite.
- Static Sprite Unity preview package: схема `1.0`, переносимый preset для изолированной read-only проверки без записи в пользовательский Unity-проект.
- Approved Static Sprite workflow: схема `1.0`, транзакционно публикует полную цепочку артефактов либо не оставляет частичного результата.
- Workflow audit: строго read-only проверяет опубликованную цепочку, безопасные пути и фактические SHA-256 без автоматического исправления.
- Пути в BatchPlan должны быть относительными к каталогу плана либо явно валидированными абсолютными входами.
- Выходные каталоги не перезаписываются; запись плана выполняется через staging и атомарную замену.

## Support matrix

| Компонент | Минимум | Проверенная конфигурация | Статус |
|---|---:|---|---|
| Windows | Windows 10 x64 | Windows 11 x64, build 10.0.26200 | `VERIFIED` |
| Python | 3.10 | CPython 3.14.6 | `VERIFIED` |
| Blender | 5.1 | Blender 5.1.2 | `VERIFIED` |
| Unity Editor | Unity 6 | 6000.4.0f1 | `VERIFIED` |
| Linux | Python 3.10+ | Реальный GUI/Blender/Unity smoke не выполнен | `UNKNOWN` |
| macOS | Python 3.10+ | Реальный GUI/Blender/Unity smoke не выполнен | `UNKNOWN` |
| Blender 4.x и ниже | Не заявлен | Не проверено на текущем pipeline | `UNKNOWN` |
| Unity 2022/2023 | Не заявлен | TextureImporter/Data Provider не проверены | `UNKNOWN` |

`SUPPORTED` для коммерческого RC будет присвоен только после clean-install и полного release gate на соответствующей конфигурации.

## Release gates

- целевые unit и contract tests;
- полный Python regression-набор;
- реальный Blender smoke затронутого режима;
- реальный Unity smoke статического и анимационного пакета;
- проверка no-overwrite, path traversal, interrupted-write recovery и resume;
- ручная проверка GUI на целевой Windows-машине;
- отсутствие секретов, generated outputs и незаявленных бинарных файлов в diff;
- обновлённые документация, результаты тестов и known limitations.

## Следующая точная задача

Добавить ограниченную GUI-интеграцию Static Sprite Workflow по `docs/WORKFLOW_READINESS_v0.9.0.md`. Статус остаётся `NOT RC` до ручного GUI и clean-install QA.
