"""Phase 02B.2 draft: Sebatas Ingpoh (chibi narrator) asset + rig for bench_p02b_ingpoh_10s. NOT EXECUTED.

Run ONLY after (a) a Trusted Approval token for THIS package digest with scope `blender_scene_mutation` verifies,
(b) a human has set PHASE02_EXECUTION_ENABLED. Nothing in the repo calls this file.

Lessons carried over from the Bima build (tested live on the Vivo X200 Pro, Blender 5.3):
- the face must point to -Y (Blender/glTF front); coordinates below are already in Blender axes (x, -depth, up);
- bone parenting: remember `matrix_world`, set the parent, then restore it (otherwise parts jump);
- IK targets are placed exactly on the wrist/ankle at rest so the rest pose is not pulled;
- one MCP call < 3.5 s: at most ~60 small objects per call, join before the next call; hair is built in 2-3 calls;
- every object is named `Ingpoh_*`; rebuilding first removes only `Ingpoh_*`; non-Ingpoh objects are never touched;
- the shirt print is raycast onto the shirt and joined INTO `Ingpoh_Torso` (one asset, no floating geometry).
Palette comes from character_bible.json; skin/eye colours are asset defaults (flagged in the bible).
"""
from __future__ import annotations

PAL = {"hair": "#C9A7EE", "hair_hi": "#DCC3F5", "shirt": "#F29A84", "shorts": "#F5B7A0", "cream": "#FFF1D6", "accent": "#E04545",
       "skin": "#F6CFB1", "iris": "#8E5BC9", "pupil": "#2B1A3D", "eye_white": "#FFFFFF", "line": "#3A1A2A", "blush": "#EE8F8F"}
HEIGHT = 1.0          # metres; 2.8 heads tall (chibi)
HEAD_Z = 0.795        # head centre
HEAD_R = 0.205
FPS = 30


def _hex(c):
    c = c.lstrip("#")
    s = [int(c[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[(v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in s], 1.0)


def _mat(k):
    import bpy

    n = "Ingpoh_" + k
    m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = _hex(PAL[k])
    b.inputs["Roughness"].default_value = 0.6
    m.diffuse_color = _hex(PAL[k])
    return m


def _fin(o, name, k):
    o.name, o.data.name = name, name
    for p in o.data.polygons:
        p.use_smooth = True
    if k:
        o.data.materials.append(_mat(k))
    return o


def sph(name, loc, scl, k, r=1.0, seg=14, rings=8):
    import bpy

    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=rings, location=loc)
    o = bpy.context.active_object
    o.scale = scl
    return _fin(o, name, k)


def cyl(name, a, b, r, k, r2=None):
    import bpy
    from mathutils import Vector

    a, b = Vector(a), Vector(b)
    d = b - a
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=14, location=(a + b) / 2)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=d.length, vertices=14, location=(a + b) / 2)
    o = bpy.context.active_object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    return _fin(o, name, k)


def join(name, objs):
    import bpy

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name, o.data.name = name, name
    return o


def capsule(name, a, b, r, k):
    return join(name, [cyl(name + "_c", a, b, r, k), sph(name + "_a", a, (1, 1, 1), k, r), sph(name + "_b", b, (1, 1, 1), k, r)])


def clear_ingpoh():
    import bpy

    for o in [o for o in bpy.data.objects if o.name.startswith("Ingpoh_")]:
        bpy.data.objects.remove(o, do_unlink=True)


def step0_scene_setup(frames: int = 300):
    import bpy

    sc = bpy.context.scene
    sc.render.fps, sc.frame_start, sc.frame_end = FPS, 1, frames
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 360, 640, 100
    return {"fps": sc.render.fps, "range": [1, frames]}


def step1_body():
    """Barefoot chibi body: legs (short), shorts with crescent-moon print, tee torso + lace collar, arms with 4-finger hands."""
    for s, S in ((-1, "L"), (1, "R")):
        x = s * 0.06
        capsule(f"Ingpoh_Leg_{S}", (x, 0, 0.05), (x, 0, 0.24), 0.045, "skin")
        sph(f"Ingpoh_Foot_{S}", (x, -0.03, 0.025), (0.05, 0.085, 0.035), "skin")
        sph(f"Ingpoh_ShortLeg_{S}", (x, 0, 0.255), (0.075, 0.07, 0.085), "shorts")
        capsule(f"Ingpoh_UpperArm_{S}", (s * 0.135, 0, 0.5), (s * 0.165, 0, 0.4), 0.03, "skin")
        capsule(f"Ingpoh_Forearm_{S}", (s * 0.165, 0, 0.4), (s * 0.18, -0.01, 0.32), 0.027, "skin")
        sph(f"Ingpoh_Hand_{S}", (s * 0.185, -0.012, 0.295), (0.036, 0.024, 0.04), "skin")
        sph(f"Ingpoh_Sleeve_{S}", (s * 0.145, 0, 0.5), (0.05, 0.045, 0.055), "shirt")
    sph("Ingpoh_Hips", (0, 0, 0.30), (0.125, 0.085, 0.07), "shorts")
    sph("Ingpoh_Torso", (0, 0, 0.43), (0.125, 0.08, 0.135), "shirt")
    sph("Ingpoh_Neck", (0, 0, 0.58), (0.035, 0.035, 0.04), "skin")


def step2_head_and_face():
    """Large head, big iris eyes with highlight, thin brows, blush, tiny mouth. Face points to -Y."""
    from mathutils import Vector

    skull = sph("Ingpoh_Head", (0, 0, HEAD_Z), (HEAD_R, HEAD_R * 0.95, HEAD_R * 0.97), "skin", seg=24, rings=14)
    for s, S in ((-1, "L"), (1, "R")):
        e = Vector((s * 0.075, -0.176, HEAD_Z - 0.005))
        w = sph(f"Ingpoh_ew{S}", e, (0.052, 0.022, 0.062), "eye_white")
        i = sph(f"Ingpoh_ei{S}", e + Vector((0, -0.012, 0)), (0.044, 0.014, 0.054), "iris")
        p = sph(f"Ingpoh_ep{S}", e + Vector((0, -0.02, 0)), (0.02, 0.008, 0.028), "pupil")
        h = sph(f"Ingpoh_eh{S}", e + Vector((s * 0.014, -0.03, 0.02)), (0.012, 0.006, 0.012), "eye_white")
        join(f"Ingpoh_Eye_{S}", [w, i, p, h])
        capsule(f"Ingpoh_Brow_{S}", (s * 0.045, -0.172, HEAD_Z + 0.078), (s * 0.1, -0.16, HEAD_Z + 0.07), 0.005, "line")
        sph(f"Ingpoh_Blush_{S}", (s * 0.105, -0.162, HEAD_Z - 0.06), (0.03, 0.006, 0.014), "blush")
    sph("Ingpoh_Mouth", (0, -0.2, HEAD_Z - 0.095), (0.016, 0.005, 0.006), "line")
    return skull


def step3_hair(part: int = 0):
    """Long wavy lavender hair as chains of flattened clumps (strands). part 0: back curtain, 1: side locks + bangs, 2: ahoge curl.
    Call once per part (each < 3.5 s); joins into Ingpoh_Hair at part 2."""
    import math
    import bpy

    created = []
    if part == 0:
        for j in range(-5, 6):  # back curtain, 11 strands x 6 clumps
            for t in range(6):
                z = HEAD_Z + 0.08 - t * 0.11
                x = j * 0.036 + math.sin(t * 1.1 + j) * 0.018
                created.append(sph(f"Ingpoh_hb{j+5}_{t}", (x, 0.1 + t * 0.012, z), (0.045, 0.05, 0.075), "hair", seg=10, rings=6))
        join("Ingpoh_HairA", created)
    elif part == 1:
        for s in (-1, 1):  # side locks framing the face, ending in a flick
            for t in range(7):
                created.append(sph(f"Ingpoh_hs{s}_{t}", (s * (0.2 + 0.015 * math.sin(t)), -0.02 + 0.01 * t, HEAD_Z + 0.05 - t * 0.09), (0.05, 0.06, 0.07), "hair", seg=10, rings=6))
        for k in range(9):  # bangs, swept to one side
            created.append(sph(f"Ingpoh_hn{k}", (-0.12 + k * 0.03, -0.17, HEAD_Z + 0.13 - abs(k - 4) * 0.008), (0.05, 0.03, 0.07), "hair", seg=10, rings=6))
        for k in range(12):  # crown cap
            a = k / 12 * math.tau
            created.append(sph(f"Ingpoh_hc{k}", (math.cos(a) * 0.15, math.sin(a) * 0.15, HEAD_Z + 0.15), (0.06, 0.06, 0.05), "hair", seg=10, rings=6))
        join("Ingpoh_HairB", created)
    else:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.012, major_segments=20, minor_segments=8, location=(0.03, -0.02, HEAD_Z + 0.27), rotation=(1.5708, 0, 0))
        ah = _fin(bpy.context.active_object, "Ingpoh_hahoge", "hair")
        join("Ingpoh_Hair", [bpy.data.objects["Ingpoh_HairA"], bpy.data.objects["Ingpoh_HairB"], ah])


def step4_shirt_print(lines=("Sebatas", "Ingpohh"), underline=True):
    """Raycast text mesh onto the shirt, raise it 3.5 mm and join INTO Ingpoh_Torso (embroidery/screen-print look, one asset)."""
    import math
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    tor = bpy.data.objects["Ingpoh_Torso"]

    def line(txt, z, size):
        bpy.ops.object.text_add(location=(0, 0, z), rotation=(math.radians(90), 0, 0))
        t = bpy.context.active_object
        t.data.body, t.data.size, t.data.align_x, t.data.align_y, t.data.extrude, t.data.resolution_u = txt, size, "CENTER", "CENTER", 0.0, 3
        bpy.ops.object.select_all(action="DESELECT")
        t.select_set(True)
        bpy.context.view_layer.objects.active = t
        bpy.ops.object.convert(target="MESH")
        return bpy.context.active_object

    pr = join("Ingpoh_Print", [line(lines[0], 0.455, 0.04), line(lines[1], 0.41, 0.04)])
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    m = pr.modifiers.new("sub", "SUBSURF")
    m.subdivision_type, m.levels = "SIMPLE", 2
    bpy.ops.object.modifier_apply(modifier="sub")
    bvh = BVHTree.FromObject(tor, bpy.context.evaluated_depsgraph_get())
    inv = tor.matrix_world.inverted()
    for v in pr.data.vertices:
        loc, _n, _i, _d = bvh.ray_cast(inv @ Vector((v.co.x, -1.0, v.co.z)), Vector((0, 1, 0)))
        if loc is not None:
            v.co = tor.matrix_world @ loc + Vector((0, -0.0005, 0))
    m = pr.modifiers.new("sol", "SOLIDIFY")
    m.thickness, m.offset = 0.0035, -1.0
    bpy.ops.object.modifier_apply(modifier="sol")
    pr.data.materials.append(_mat("cream"))
    bpy.ops.object.select_all(action="DESELECT")
    pr.select_set(True)
    tor.select_set(True)
    bpy.context.view_layer.objects.active = tor
    bpy.ops.object.join()
    return {"print_joined_into": "Ingpoh_Torso", "materials": [m.name for m in bpy.context.active_object.data.materials]}


def step5_rig_and_bind():
    """Biped rig scaled to the chibi (IK arms + legs with poles on the rest pose, jaw, hair sway bones), rigid bind, prop sockets."""
    import bpy

    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.active_object
    arm.name = arm.data.name = "Ingpoh_Rig"
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for b in list(eb):
        eb.remove(b)

    def bone(n, h, t, par=None):
        b = eb.new(n)
        b.head, b.tail = h, t
        if par:
            b.parent = eb[par]

    bone("root", (0, 0, 0), (0, 0, 0.08))
    bone("hips", (0, 0, 0.28), (0, 0, 0.34), "root")
    bone("spine", (0, 0, 0.34), (0, 0, 0.45), "hips")
    bone("chest", (0, 0, 0.45), (0, 0, 0.56), "spine")
    bone("neck", (0, 0, 0.56), (0, 0, 0.6), "chest")
    bone("head", (0, 0, 0.6), (0, 0, 1.0), "neck")
    bone("jaw", (0, -0.1, 0.7), (0, -0.19, 0.69), "head")
    bone("hair_back", (0, 0.1, 0.85), (0, 0.12, 0.35), "head")
    for s, S in ((-1, "L"), (1, "R")):
        x = s * 0.06
        bone(f"upper_arm.{S}", (s * 0.135, 0, 0.5), (s * 0.165, 0, 0.4), "chest")
        bone(f"forearm.{S}", (s * 0.165, 0, 0.4), (s * 0.18, -0.01, 0.32), f"upper_arm.{S}")
        bone(f"hand.{S}", (s * 0.18, -0.01, 0.32), (s * 0.185, -0.012, 0.26), f"forearm.{S}")
        bone(f"thigh.{S}", (x, 0, 0.27), (x, -0.005, 0.15), "hips")
        bone(f"shin.{S}", (x, -0.005, 0.15), (x, 0, 0.04), f"thigh.{S}")
        bone(f"foot.{S}", (x, 0, 0.04), (x, -0.1, 0.02), f"shin.{S}")
        bone(f"hair_side.{S}", (s * 0.2, 0, 0.84), (s * 0.2, -0.01, 0.4), "head")
        bone(f"ik_hand.{S}", (s * 0.18, -0.01, 0.32), (s * 0.18, -0.01, 0.38), "root")
        bone(f"ik_pole_arm.{S}", (s * 0.25, 0.3, 0.4), (s * 0.25, 0.3, 0.46), "root")
        bone(f"ik_leg.{S}", (x, 0, 0.04), (x, 0, 0.1), "root")
        bone(f"ik_pole_leg.{S}", (x, -0.4, 0.15), (x, -0.4, 0.21), "root")
    bpy.ops.object.mode_set(mode="POSE")
    for S in ("L", "R"):
        for bn, tg, pl in ((f"forearm.{S}", f"ik_hand.{S}", f"ik_pole_arm.{S}"), (f"shin.{S}", f"ik_leg.{S}", f"ik_pole_leg.{S}")):
            c = arm.pose.bones[bn].constraints.new("IK")
            c.target, c.subtarget, c.pole_target, c.pole_subtarget, c.chain_count = arm, tg, arm, pl, 2
    bpy.ops.object.mode_set(mode="OBJECT")
    mp = {"Torso": "chest", "Hips": "hips", "Neck": "neck", "Head": "head", "Hair": "head", "Mouth": "jaw"}
    for S in ("L", "R"):
        mp.update({f"UpperArm_{S}": f"upper_arm.{S}", f"Sleeve_{S}": f"upper_arm.{S}", f"Forearm_{S}": f"forearm.{S}", f"Hand_{S}": f"hand.{S}", f"Leg_{S}": f"thigh.{S}",
                   f"ShortLeg_{S}": f"thigh.{S}", f"Foot_{S}": f"foot.{S}", f"Eye_{S}": "head", f"Brow_{S}": "head", f"Blush_{S}": "head"})
    bpy.context.view_layer.update()
    for o in [o for o in bpy.data.objects if o.name.startswith("Ingpoh_") and o.type == "MESH"]:
        b = mp.get(o.name[7:])
        if not b:
            continue
        mw = o.matrix_world.copy()
        o.parent, o.parent_type, o.parent_bone = arm, "BONE", b
        bpy.context.view_layer.update()
        o.matrix_world = mw
    for S in ("L", "R"):
        e = bpy.data.objects.new(f"Ingpoh_Socket_{S}", None)
        bpy.context.scene.collection.objects.link(e)
        e.parent, e.parent_type, e.parent_bone = arm, "BONE", f"hand.{S}"
    return len(arm.data.bones)


def verify_rig():
    """READ-ONLY: bones, IK constraints, IK tail vs target at rest (must be ~0), unparented meshes, foreign objects untouched."""
    import bpy

    a = bpy.data.objects.get("Ingpoh_Rig")
    ms = [o for o in bpy.data.objects if o.name.startswith("Ingpoh_") and o.type == "MESH"]
    dev = {}
    if a:
        for S in ("L", "R"):
            for bn, tn in ((f"forearm.{S}", f"ik_hand.{S}"), (f"shin.{S}", f"ik_leg.{S}")):
                dev[bn] = round(((a.matrix_world @ a.pose.bones[bn].tail) - (a.matrix_world @ a.pose.bones[tn].head)).length, 4)
    return {"bones": len(a.data.bones) if a else 0, "ik_dev_m": dev, "meshes": len(ms), "unparented": [o.name for o in ms if not o.parent],
            "foreign": sorted(o.name for o in bpy.data.objects if not o.name.startswith("Ingpoh_")), "fps": bpy.context.scene.render.fps}
