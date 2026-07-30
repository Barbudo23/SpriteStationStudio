# Sprite Station Studio v0.10.0 — Post-RC Stabilization

Старт: 2026-07-30.

Ветка: `post-rc/0.10.0-stabilization`.

Опубликованный prerelease: `v0.10.0-rc1`.

Artifact commit: `ae88a25a51376c65ab689647027171ab8a704927`.

Milestone closeout commit: `c1460772448be9d70bf4bd82c694f82078b47665`.

## Цель

Стабилизировать опубликованный Static Sprite и Animation Workflow перед
отдельным решением о Stable, не расширяя пользовательский scope RC1.

## Разрешено

- исправлять только воспроизводимые дефекты;
- добавлять regression test до или вместе с исправлением;
- усиливать no-overwrite, rollback, safe paths и read-only audit;
- повторять clean-install, GUI, Blender и Unity smoke;
- уточнять документацию по фактически выполненным проверкам;
- готовить RC2 только при изменении пользовательского приложения или
  распространяемого ZIP.

## Не входит в scope

- возобновление AI Center;
- платные AI API-вызовы;
- выбор нескольких Blender Actions;
- автоматическое создание Unity AnimationClip;
- AtlasBuilder, MotionLab и CameraLab;
- installer, updater и signing;
- массовый рефакторинг `gui.py`;
- объявление Stable без отдельного решения.

## Обязательный цикл дефекта

1. Зафиксировать воспроизводимый сценарий.
2. Добавить regression test.
3. Выполнить минимальное исправление.
4. Запустить целевые тесты и полный Python regression.
5. Для worker/GUI/Unity изменений повторить соответствующий physical smoke.
6. Проверить активный бренд Sprite Station Studio и legacy allowlist.
7. Создать отдельный коммит и синхронизировать ветку.

## Stable gate

Минимальные условия:

- нет открытых блокирующих дефектов;
- повторяемый запуск RC1 на Windows;
- `172/172` или больше regression tests;
- оба synthetic workflow E2E проходят из clean extraction;
- опубликованный ZIP digest повторно подтверждён;
- ограничения RC документированы;
- принято отдельное решение о Stable.

## Исправленные дефекты

- GUI review state теперь привязан не только к пути, но и к SHA-256
  `animation_manifest.json`; изменение manifest после `VALIDATE` требует
  повторной проверки перед записью решения.
- Final package audit требует точного покрытия всех manifest, review, contact,
  frame и sheet файлов верхнеуровневым artifact list; сокращённый или
  неожиданный список отклоняется.
