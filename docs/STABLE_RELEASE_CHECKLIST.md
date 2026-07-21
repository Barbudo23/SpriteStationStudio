# AssetForge Studio v0.6.1 Stable — Release Checklist

## Automated checks

- Python compilation;
- unit test suite;
- Unity executable discovery tests;
- Unity Asset Library indexing/cache tests;
- settings persistence tests;
- duplicate-task guard tests;
- manifest generation.

## Manual checks required on the target Windows workstation

1. Start `run_gui.bat`.
2. Confirm Blender and Unity bridge markers.
3. Open Unity Asset Library.
4. Select a Unity project.
5. Load an FBX model into Pseudo3D Forge.
6. Run Unity model analysis.
7. Render 8 directions through Blender.
8. Verify contact sheet and ZIP output.

## Stable scope

- model/image source selection;
- Blender rendering;
- 4/8 direction preview package;
- Unity Bridge analysis;
- automatic bridge discovery;
- local Unity Asset Library;
- persistent settings;
- background project discovery and indexing;
- structured logs and reports.

AI generation and animation sprite rendering remain development features and are not marked production-stable in this release.
