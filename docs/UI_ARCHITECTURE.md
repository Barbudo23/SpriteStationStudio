# AssetForge Studio UI Architecture — Pseudo3D Forge

## Reference analysis

The original MVP interface is functional and stable, but intentionally linear:

- three path inputs;
- two render options;
- one action row;
- one log panel.

This is ideal for validating the Blender worker but cannot scale to multiple AssetForge modules.

## New shell structure

```text
Top Bar
├── Product identity
├── Active module
└── Version/status

Left Sidebar
├── Module Registry
├── Installed modules
└── Settings / installer

Center Workspace
├── Pipeline stages
├── Main preview
├── View modes
└── Log / Jobs / Output

Right Inspector
├── Source
├── Render
├── Export
└── Primary actions

Bottom Status
├── Current state
└── Progress
```

## Extensibility contract

New modules register through `ModuleDescriptor` and appear in the sidebar without changing shell layout.

Future milestone:
- module-specific workspace providers;
- module-specific inspector providers;
- command registry;
- persisted panel layout;
- localization resources;
- Basic / Advanced / Developer modes.


## Image Source mode

The Source inspector supports two input strategies:

1. `3D Model` — existing Blender worker pipeline.
2. `4 Images` — Front Left, Front Right, Back Right, Back Left.

Image Source mode:

- does not require Blender;
- validates all four files;
- copies images into a normalized package structure;
- writes a versioned manifest;
- creates `<AssetName>_ImageAsset.zip` in the selected directory;
- marks normalization, pivot alignment, background removal, and animation as future stages.

This creates a stable extension point for later image-only workflows such as:
background removal, canvas normalization, pivot alignment, MotionLab, frame generation,
sprite sheet assembly, and engine export.
