# Rigged 3D character (event uniform)

| File | Use it in |
|---|---|
| `character.blend` | Blender (editable, with rig) |
| `character.fbx` | Maya, 3ds Max, Cinema 4D, Unity, Unreal, Mixamo |
| `character.glb` | Web/three.js, Unity, Unreal, After Effects (Element 3D / Plexus) |
| `renders/*.png` | Transparent preview images |

- Height ≈ 1.80 m, faces the front (-Y in Blender, +Z in glTF).
- Rig bones: `root, hips, spine, chest, neck, head`, plus `upper_arm / forearm / hand / thigh / shin / foot` with `.L` / `.R`.
- Rebuild from source: `python src/build_character.py` (requires the `bpy` package, Blender 5.2).
