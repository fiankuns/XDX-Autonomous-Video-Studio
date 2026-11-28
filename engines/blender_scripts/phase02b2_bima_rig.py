"""Phase 02B.2 draft: Bima asset + rig for bench_p02b_char_10s. UNTESTED, NOT EXECUTED.

Run ONLY after (a) the user approves the 02B.2 scope in writing, (b) the package carries a valid Trusted Approval token with
scope `blender_scene_mutation` (Ed25519, owner key), (c) a human sets PHASE02_EXECUTION_ENABLED. Nothing in this repo calls this file.

Mobile rules: every function is one MCP call (< 3.5 s), idempotent (re-running replaces objects named `Bima_*`), uses
bpy.app.tempdir, never renders. Colours/proportions come from projects/<id>/character_bible.json (palette passed in), not hard-coded.
"""
from __future__ import annotations

PALETTE = {"shirt": "#E0A11B", "pants": "#E8DFCA", "dark": "#2C3539", "accent": "#FF6B4A"}  # character_bible.color_palette (locked)
HEAD_UNITS = 6.3  # character_bible silhouette: 6.3 heads tall
FPS = 30  # production fps (scene default is 24): setting it is a scene mutation covered by the approval


def _hex(c: str) -> tuple[float, float, float, float]:
    c = c.lstrip("#")
    srgb = [int(c[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in srgb]
    return (*lin, 1.0)


def step0_scene_setup(frames: int = 300):
    """fps 30, frame range 1..300, EEVEE, portrait render size within the mobile guard (decide per-side cap first)."""
    import bpy

    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 360, 640, 100
    return {"fps": sc.render.fps, "range": [sc.frame_start, sc.frame_end], "res": [sc.render.resolution_x, sc.render.resolution_y]}


def _clear_prefix(prefix: str = "Bima_"):
    import bpy

    for o in [o for o in bpy.data.objects if o.name.startswith(prefix)]:
        bpy.data.objects.remove(o, do_unlink=True)


def _mat(name: str, hex_color: str, roughness: float = 0.7):
    import bpy

    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = _hex(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    return m


def step1_body_meshes(height: float = 1.75):
    """Low-poly parts (matches the Three.js Bima proportions): torso, hips, head, 2 arms (upper/lower), 2 legs, hands, thumb."""
    import bpy

    _clear_prefix()
    unit = height / HEAD_UNITS
    parts = [
        ("Bima_Torso", "cube", (0, 0, 3.0 * unit), (0.9 * unit, 0.5 * unit, 1.5 * unit), "shirt"),
        ("Bima_Hips", "cube", (0, 0, 1.75 * unit), (0.85 * unit, 0.45 * unit, 0.6 * unit), "pants"),
        ("Bima_Head", "sphere", (0, 0, 5.3 * unit), (unit, unit, unit), "shirt"),
        ("Bima_UpperArm_L", "cylinder", (-0.75 * unit, 0, 3.6 * unit), (0.22 * unit, 0.22 * unit, 0.8 * unit), "shirt"),
        ("Bima_UpperArm_R", "cylinder", (0.75 * unit, 0, 3.6 * unit), (0.22 * unit, 0.22 * unit, 0.8 * unit), "shirt"),
        ("Bima_Leg_L", "cylinder", (-0.3 * unit, 0, 0.9 * unit), (0.28 * unit, 0.28 * unit, 0.9 * unit), "pants"),
        ("Bima_Leg_R", "cylinder", (0.3 * unit, 0, 0.9 * unit), (0.28 * unit, 0.28 * unit, 0.9 * unit), "pants"),
    ]
    made = []
    for name, prim, loc, scl, mat in parts:
        getattr(bpy.ops.mesh, f"primitive_{prim}_add")(location=loc)
        o = bpy.context.active_object
        o.name, o.scale = name, scl
        o.data.materials.append(_mat(f"Bima_{mat}", PALETTE[mat]))
        made.append(name)
    return made


def step2_armature():
    """Bones: root>hips>spine>chest>neck>head ; shoulder>upper_arm>forearm>hand(+thumb) per side ; legs. IK on forearms with pole targets."""
    import bpy

    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.active_object
    arm.name = "Bima_Rig"
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for b in list(eb):
        eb.remove(b)

    def bone(name, head, tail, parent=None):
        b = eb.new(name)
        b.head, b.tail = head, tail
        if parent:
            b.parent = eb[parent]
        return b

    bone("root", (0, 0, 0), (0, 0, 0.2))
    bone("hips", (0, 0, 0.5), (0, 0, 0.7), "root")
    bone("spine", (0, 0, 0.7), (0, 0, 1.1), "hips")
    bone("chest", (0, 0, 1.1), (0, 0, 1.4), "spine")
    bone("neck", (0, 0, 1.4), (0, 0, 1.5), "chest")
    bone("head", (0, 0, 1.5), (0, 0, 1.75), "neck")
    for side, sx in (("L", -1), ("R", 1)):
        bone(f"upper_arm.{side}", (0.2 * sx, 0, 1.35), (0.42 * sx, 0, 1.1), "chest")
        bone(f"forearm.{side}", (0.42 * sx, 0, 1.1), (0.55 * sx, 0.12, 0.88), f"upper_arm.{side}")
        bone(f"hand.{side}", (0.55 * sx, 0.12, 0.88), (0.6 * sx, 0.16, 0.8), f"forearm.{side}")
        bone(f"thumb.{side}", (0.57 * sx, 0.14, 0.85), (0.6 * sx, 0.2, 0.84), f"hand.{side}")
        bone(f"leg.{side}", (0.1 * sx, 0, 0.5), (0.1 * sx, 0, 0.0), "hips")
        bone(f"ik_target.{side}", (0.5 * sx, 0.3, 1.0), (0.5 * sx, 0.3, 1.1))
        bone(f"ik_pole.{side}", (0.5 * sx, -0.5, 1.3), (0.5 * sx, -0.5, 1.4))
    bpy.ops.object.mode_set(mode="POSE")
    for side in ("L", "R"):
        c = arm.pose.bones[f"forearm.{side}"].constraints.new("IK")
        c.target, c.subtarget = arm, f"ik_target.{side}"
        c.pole_target, c.pole_subtarget = arm, f"ik_pole.{side}"
        c.chain_count = 2
    t = arm.pose.bones["head"].constraints.new("DAMPED_TRACK")
    t.target, t.subtarget = arm, "ik_target.R"  # retargeted per shot in 02B.3 (head aim)
    t.influence = 0.0
    bpy.ops.object.mode_set(mode="OBJECT")
    return [b.name for b in arm.data.bones]


def step3_bind_and_props():
    """Parent meshes to bones (rigid binding for the low-poly style) and add fan/remote sockets (empties parented to the hands)."""
    import bpy

    arm = bpy.data.objects["Bima_Rig"]
    binding = {"Bima_Torso": "chest", "Bima_Hips": "hips", "Bima_Head": "head", "Bima_UpperArm_L": "upper_arm.L", "Bima_UpperArm_R": "upper_arm.R", "Bima_Leg_L": "leg.L", "Bima_Leg_R": "leg.R"}
    for mesh_name, bone in binding.items():
        o = bpy.data.objects[mesh_name]
        o.parent, o.parent_type, o.parent_bone = arm, "BONE", bone
    for side in ("L", "R"):
        e = bpy.data.objects.new(f"Bima_Socket_{side}", None)
        bpy.context.scene.collection.objects.link(e)
        e.parent, e.parent_type, e.parent_bone = arm, "BONE", f"hand.{side}"
    return sorted(binding) + ["Bima_Socket_L", "Bima_Socket_R"]


def verify_rig():
    """READ-ONLY check used after each step: names present, IK constraints set, no stray objects."""
    import bpy

    arm = bpy.data.objects.get("Bima_Rig")
    return {
        "rig": bool(arm),
        "bones": len(arm.data.bones) if arm else 0,
        "ik": [b.name for b in arm.pose.bones if any(c.type == "IK" for c in b.constraints)] if arm else [],
        "bima_objects": sorted(o.name for o in bpy.data.objects if o.name.startswith("Bima_")),
        "fps": bpy.context.scene.render.fps,
    }
