# Unity Asset Library v0.1

Unity Asset Library allows AssetForge Studio to browse assets stored in local Unity projects.

## Features

- automatic discovery of recent/common Unity projects;
- manual Unity project selection;
- recursive indexing of `Assets/`;
- support for models, prefabs, animations, textures, materials and scenes;
- search by name/path;
- type filters;
- persistent JSON cache;
- GUID extraction from `.meta`;
- texture thumbnails;
- load selected model directly into Pseudo3D Forge;
- analyze selected model through Unity Bridge.

## Supported model source types

- FBX
- OBJ
- BLEND
- GLTF
- GLB
- DAE
- 3DS

Blender Bridge currently determines which source types can be rendered directly.

## Safety

The browser reads project files and `.meta` metadata. It does not modify the original Unity project.
Unity analysis copies the selected file into the isolated bridge project.
