# Архитектура MVP

```text
Tkinter GUI / CLI
        |
        v
BlenderRunner (subprocess)
        |
        v
Blender --background --factory-startup
        |
        v
worker/render_preview.py
        |
        +--> Import
        +--> Bounding Box
        +--> Ground Alignment
        +--> Orthographic Camera
        +--> Studio Lighting
        +--> PNG Render
        +--> JSON Report
```

Главный процесс не импортирует `bpy`. Blender API изолирован в Worker.
Это позволяет запускать GUI обычным Python и обновлять Worker независимо.
