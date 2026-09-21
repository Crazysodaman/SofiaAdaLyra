"""PKG-AVATAR A0: fully dressed, editable Blender *blockout* (not final art).

Run via Blender Scripting > Open > Run Script. Optional background export:
    blender --background --python tools/avatar/blender_blockout.py -- /absolute/path/sofia_blockout.blend

This script does not clear the scene or overwrite existing output. It is an
art-authoring utility, NOT a runtime model-created script executor or a rig.
Blender Python has normal user-process permissions: run only reviewed scripts.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path


def build() -> None:
    import bpy  # available only inside Blender; no pip bpy dependency for Sofía

    if bpy.data.collections.get("SOFIA_A0_BLOCKOUT"):
        raise RuntimeError("SOFIA_A0_BLOCKOUT already exists; use a new scene or rename it")
    parent = bpy.data.collections.new("SOFIA_A0_BLOCKOUT")
    bpy.context.scene.collection.children.link(parent)
    body = bpy.data.collections.new("01_body_proportions_placeholder")
    clothes = bpy.data.collections.new("02_dressed_outfit_proxy")
    anchors = bpy.data.collections.new("03_clothing_slot_anchors")
    parent.children.link(body)
    parent.children.link(clothes)
    parent.children.link(anchors)

    def material(name: str, color: tuple[float, float, float, float]):
        mat = bpy.data.materials.new("SOFIA_A0_" + name)
        mat.diffuse_color = color
        mat.use_nodes = True
        principled = mat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = color
        return mat

    dark = material("dark_fabric", (0.065, 0.055, 0.09, 1))
    crimson = material("crimson_hair", (0.50, 0.045, 0.18, 1))
    violet = material("violet_ears_tail", (0.26, 0.065, 0.46, 1))
    cyan = material("cyan_details", (0.0, 0.65, 0.85, 1))
    lounge = material("lounge_tee", (0.18, 0.15, 0.26, 1))
    sweat = material("sweatpants", (0.11, 0.105, 0.145, 1))
    leather = material("gauntlet_proxy", (0.12, 0.075, 0.058, 1))
    skin = material("neutral_placeholder", (0.48, 0.35, 0.42, 1))

    def move(obj, target):
        for source in tuple(obj.users_collection):
            source.objects.unlink(obj)
        target.objects.link(obj)
        return obj

    def cube(name, loc, scale, mat, target):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = move(bpy.context.object, target)
        obj.name = name
        obj.dimensions = scale
        obj.data.materials.append(mat)
        obj["sofia_asset_stage"] = "placeholder_not_renderer_verified"
        return obj

    def oval(name, loc, radius, mat, target, rotation=None):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=1, location=loc)
        obj = move(bpy.context.object, target)
        obj.name = name
        obj.scale = radius
        if rotation:
            obj.rotation_euler = rotation
        obj.data.materials.append(mat)
        obj["sofia_asset_stage"] = "placeholder_not_renderer_verified"
        return obj

    def cone(name, loc, radius1, depth, mat, rotation=(0, 0, 0)):
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=radius1, radius2=0.0, depth=depth, location=loc, rotation=rotation)
        obj = move(bpy.context.object, body)
        obj.name = name
        obj.data.materials.append(mat)
        return obj

    def anchor(slot, location):
        empty = bpy.data.objects.new("SLOT_" + slot, None)
        anchors.objects.link(empty)
        empty.location = location
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.045
        empty["sofia_clothing_slot"] = slot
        empty["prototype_only"] = True
        return empty

    # Adult-styled silhouette guide. These are arbitrary blockout proportions,
    # NOT verified canonical anatomy, a final unclothed base, or deformation rig.
    oval("BODY_head_guide", (0, 0, 1.91), (0.13, 0.11, 0.17), skin, body)
    oval("HAIR_crimson_cap", (0, 0.013, 2.03), (0.145, 0.13, 0.08), crimson, body)
    oval("HAIR_back_guide", (0, 0.12, 1.79), (0.14, 0.06, 0.28), crimson, body)
    cone("EAR_left_violet", (-0.088, 0, 2.15), 0.067, 0.22, violet, rotation=(0, -0.10, 0))
    cone("EAR_right_violet", (0.088, 0, 2.15), 0.067, 0.22, violet, rotation=(0, 0.10, 0))
    oval("TAIL_violet_guide", (0, 0.21, 1.10), (0.09, 0.30, 0.10), violet, body, rotation=(math.radians(25), 0, 0))
    # Dressed at creation. No nude/underwear mesh preview is generated.
    cube("GARMENT_oversized_tee_torso", (0, 0, 1.38), (0.57, 0.29, 0.59), lounge, clothes)
    for side, x in (("left", -0.33), ("right", 0.33)):
        cube("GARMENT_tee_sleeve_" + side, (x, 0, 1.55), (0.20, 0.31, 0.17), lounge, clothes)
        oval("BODY_hand_guide_" + side, (x * 1.14, 0, 1.06), (0.055, 0.065, 0.095), skin, body)
        cube("GARMENT_leather_gauntlet_" + side, (x * 1.1, 0, 1.25), (0.13, 0.15, 0.23), leather, clothes)
        anchor(side + "_forearm", (x * 1.1, 0, 1.25))
        anchor(side + "_wrist", (x * 1.14, 0, 1.11))
        anchor(side + "_hand", (x * 1.14, 0, 1.06))
        cube("GARMENT_sweatpants_leg_" + side, (x * 0.49, 0, 0.64), (0.24, 0.26, 0.82), sweat, clothes)
        cube("GARMENT_shoe_" + side, (x * 0.49, -0.05, 0.14), (0.25, 0.36, 0.16), dark, clothes)
    cube("GARMENT_sweatpants_waist", (0, 0, 1.10), (0.41, 0.28, 0.20), sweat, clothes)
    cube("DETAIL_tee_cyan_trim", (0, -0.153, 1.29), (0.50, 0.015, 0.018), cyan, clothes)
    anchor("torso", (0, -0.20, 1.42))
    anchor("pelvis", (0, -0.16, 1.1))
    anchor("ears", (0, 0, 2.15))
    anchor("tail", (0, 0.21, 1.10))
    anchor("back", (0, 0.18, 1.44))
    parent["status"] = "A0 visual blockout only; not a rig or approved body asset"
    parent["canonical_avatar_verified"] = False
    parent["public_display_authorized"] = False
    parent["mesh_licensed_and_reviewed"] = False
    print("SOFIA_A0_BLOCKOUT built: fully dressed placeholders and slot anchors only")

    # Explicit output path only; no implicit home/repository write and no overwrite.
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if len(args) != 1:
            raise ValueError("one explicit .blend output path required after --")
        path = Path(args[0]).expanduser().resolve()
        if path.suffix.lower() != ".blend" or path.exists() or not path.parent.is_dir():
            raise ValueError("output must be a new .blend in an existing directory")
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=True)
        print("Saved blockout to", path)


if __name__ == "__main__":
    build()
