# Sprite Station Studio Core v0.8

## Components

- Project Manager (`.afs`)
- Event Bus
- Job Queue
- SQLite Asset Database
- Plugin Registry
- Core application facade

## Project layout

```text
ProjectName/
├── ProjectName.afs
├── Assets/
├── Source/
├── AI/
├── Sprites/
├── Animations/
├── Atlases/
├── Cache/
├── Export/
├── Database/
└── Logs/
```

## Current integration

The existing UI remains compatible. Opening a project changes the default output
folder to `<project>/Export` and creates `<project>/Database/assets.sqlite3`.

The job queue is operational and exposed in the UI. Existing render workflows
will be migrated to it incrementally in later versions.
