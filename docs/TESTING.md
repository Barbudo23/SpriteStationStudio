# Ручное тестирование MVP

## Тест 1 — GLB

1. Запустите приложение.
2. Выберите `blender.exe`.
3. Выберите реальный `.glb`.
4. Укажите пустую папку.
5. Нажмите «Создать Preview».
6. Проверьте PNG и JSON.

Ожидается:

- модель полностью попадает в кадр;
- фон прозрачен;
- модель стоит на уровне Z=0;
- JSON имеет `status: success`.

## Тест 2 — FBX

Повторите тест с `.fbx`.

## Тест 3 — ошибка

Выберите неподдерживаемый файл. GUI должен показать понятную ошибку до запуска Blender.

## Диагностика

Если Blender завершается с ошибкой, скопируйте последние строки из журнала GUI.
Они содержат traceback Blender Worker.

## v0.11 two-Action physical QA (verified)

The gate must be performed in two separate commands. First create a new
workspace and render both contact sheets:

```powershell
python Tools/Invoke-TwoActionPhysicalQA.py prepare `
  --workspace "<new-workspace>" `
  --blender "<path-to-blender.exe>" `
  --unity "<path-to-Unity.exe>" `
  --primary-source "<Running_withSkin.fbx>" `
  --secondary-source "<Walking_withSkin.fbx>"
```

Expected state: `awaiting_visual_review`. Open and inspect both contact-sheet
paths printed by the command. Confirm that the Running and Walking poses are
valid and visibly different. Do not run finalization if either sheet is wrong.

After explicit visual approval, use the same Blender and Unity executables:

```powershell
python Tools/Invoke-TwoActionPhysicalQA.py finalize `
  --workspace "<prepared-workspace>" `
  --blender "<same-path-to-blender.exe>" `
  --unity "<same-path-to-Unity.exe>" `
  --reviewer "<reviewer-name>" `
  --confirm-contact-sheets-approved
```

PASS requires `status=passed`, two Actions with `loop` and `once`, 8 distinct
clips, 8 sheets, 16 keys, 70 bundle artifacts and
`portableReloadVerified=true`. Unity must be `6000.4.0f1`. Any changed source,
fixture, render artifact or repository bridge, any warning, missing paired
`.meta`, name collision or partial output is a failure.

The recorded physical baseline passed with two 17-artifact approved packages
and two 35-artifact Unity `6000.4.0f1` bundles: 8 clips, 8 sheets, 16 keys and
70 bundle artifacts in total. Both portable reload checks are true. The final
schema 1.1 evidence manifest additionally hash-closes 147 artifacts; together
with the self-excluded result manifest, the final directory has 148 files.
Repeating the same `finalize` is an audit-only idempotent operation;
the physical repeat completed in 1.47 seconds without rebuilding the bundles.

Crash recovery is part of the gate: if the atomic `final` rename succeeded but
the state update was interrupted, the next `finalize` must audit that immutable
result and repair the state. It must never overwrite an existing final result.
The final repository regression run completed with 256 of 256 tests passing,
including a real Windows junction escape rejection.
