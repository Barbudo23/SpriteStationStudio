# Sprite Station Studio v0.10.0 RC2 — Windows GUI QA

Date: 2026-07-30.

Artifact under test:
`SpriteStationStudio-v0.10.0rc2-43c63e08.zip`.

Environment:

- Windows desktop;
- Python 3.14 `pythonw.exe`;
- Blender 5.1 installation detected by the application;
- Unity 6000.4.0f1 detected by the application.

## Direction no-overwrite scenario

The clean-extracted RC2 application opened with the visible identity
`v0.10.0 RC2 Local Candidate`. A previously populated Direction output folder
was selected and **Create Preview** was invoked.

Observed result:

- the GUI rejected the operation before Blender launch;
- the controlled error listed the occupied `directions` directory, report,
  manifest, contact sheet, Unity preset and Direction ZIP;
- the application remained responsive and the dialog could be dismissed;
- Blender process count was `0` before and after the operation;
- SHA-256 and byte length of all nine existing output files matched before and
  after the repeated attempt.

Representative preserved hashes:

| Artifact | SHA-256 |
|---|---|
| `contact_sheet.png` | `E459589A6E37C41B1237A77F1CF372C293FFDBD79C78D626D7FD399B4A2A300D` |
| `directions_report.json` | `4F90D24BD8C34F76CB2BAC8CFB887040F029F393F31C28CF619DC6BAEA850AC8` |
| `manifest.json` | `10C7CFEEE46D09759567633371C6EE57911B6586A3B6D31BB70C25F586B1CA87` |
| Direction ZIP | `5EF973B5BF291ACB9E059B123B37A87CB253E20B2F1A4E2D4DD0535EB57F188F` |
| `unity_import_preset.json` | `F7D33BBFAF95AB5B8C0173589EAAF2745B29E1A2CE30B978BF81F89A9717728C` |

Result: **PASS**.

This scenario was repeated after the 64-pixel Animation boundary correction;
the hashes, byte lengths and zero-Blender-process result remained identical.
