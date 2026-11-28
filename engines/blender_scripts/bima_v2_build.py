"""Reproducible build of the Bima v2 production character (style bible ``xdx_pixar_stylized_3d_v1``).

Blueprint: ``assets/characters/bima_v2/blueprint`` (six ortho views of the owner's GLB).
Height 1.6 m, front faces -Y, Z up. Run stage by stage over MCP (each stage < 3.5 s on Vivo X200 Pro):

    import bima_v2_build as B
    M = B.materials()
    B.stage_body(); B.stage_head(M); B.stage_face_integrate(M); B.stage_hair(M, proxy_npz); B.stage_shoes(M)
    B.stage_materials_assign(M, with_print=False); B.stage_rig(); B.stage_weights(); B.stage_sleeve_fix()
    B.stage_print_live(M); B.stage_finish()

Requires ``style_preset_pixar`` importable (materials + kelvin colours). Only touches ``PFX`` objects.
Techniques here were verified on device (see SKILL.md "Bima v2"):
- one skin-modifier body (torso+arms+hands+fingers+legs), bisect hems for clean material lines;
- Pixar head from a deformed UV sphere + separate eye/iris/pupil/glint, D-shaped smile;
- hair = metaball clumps seeded by farthest-point sampling of the blueprint hair region + inner cap;
- weights computed by distance-to-bone with geodesic arm/torso regions (Bone Heat fails on this mesh);
- colour management Standard, exposure -1.05 (AgX desaturates the saturated yellow shirt).
"""
from __future__ import annotations

import heapq
import math
import os
import sys

import bpy  # type: ignore
import bmesh  # type: ignore
import numpy as np
from mathutils import Vector  # type: ignore

PFX = "Bima_"

BODY = dict(pel=(0.165, 0.115), bel=(0.168, 0.12), che=(0.168, 0.122), upc=(0.15, 0.105), sh=(0.08, 0.075),
            sl=(0.068, 0.066), palm=(0.05, 0.022), fr=0.0135, leg=(0.072, 0.066, 0.06, 0.062, 0.066))
COLORS = {"skin": "#B97650", "shirt": "#F0A20E", "pants": "#E4DED6", "hair": "#15100E", "eyewhite": "#F4F1EC",
          "iris": "#4A2A18", "pupil": "#080506", "mouth": "#5A1A1A", "tongue": "#C8605E", "glint": "#FFFFFF",
          "shoe_canvas": "#5B6478", "shoe_sole": "#E9E6E1", "lace": "#EDEBE6", "print_white": "#FBF7F0",
          "print_coral": "#E0503F", "print_ink": "#3B2A55"}


def _sp():
    return sys.modules["style_preset_pixar"]


def _link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def _select_only(o):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def _skin_obj(name, verts, edges, radii, root=0, levels=2, smoothing=0.4):
    me = bpy.data.meshes.new(name + "Skel")
    me.from_pydata(verts, edges, [])
    o = _link(bpy.data.objects.new(name, me))
    sk = o.modifiers.new("Skin", "SKIN")
    sk.branch_smoothing = smoothing
    sk.use_smooth_shade = True
    for i, r in enumerate(radii):
        me.skin_vertices[0].data[i].radius = r
    me.skin_vertices[0].data[root].use_root = True
    o.modifiers.new("Sub", "SUBSURF").levels = levels
    return o


def _sphere(name, loc, scale, seg=24, ring=16, fn=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        if fn:
            x, y, z = fn(x, y, z)
        v.co = (x * scale[0], y * scale[1], z * scale[2])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = _link(bpy.data.objects.new(name, me))
    o.location = loc
    return o


def materials():
    sp, L = _sp(), _sp().srgb_hex_to_linear
    kinds = {"skin": "skin", "shirt": "cotton", "pants": "twill", "hair": "hair", "eyewhite": "eye_white", "iris": "iris",
             "pupil": "glossy_dark", "mouth": "lip", "tongue": "lip", "glint": "eye_white", "shoe_canvas": "canvas",
             "shoe_sole": "rubber", "lace": "cotton", "print_white": "cotton", "print_coral": "cotton", "print_ink": "cotton"}
    M = {k: sp.make_material(PFX + k, kinds[k], L(COLORS[k])) for k in kinds}
    M["blush"] = sp.make_material(PFX + "blush", "skin", (0.62, 0.24, 0.17))
    for k, sheen in (("shirt", 0.1), ("pants", 0.08), ("print_white", 0.05), ("print_coral", 0.05), ("print_ink", 0.05)):
        M[k].node_tree.nodes["Principled BSDF"].inputs["Sheen Weight"].default_value = sheen
    g = M["glint"].node_tree.nodes["Principled BSDF"]
    g.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    g.inputs["Emission Strength"].default_value = 3.0
    _hair_strands(M["hair"])
    return M


def _hair_strands(mat):
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Coat Weight"].default_value = 0.12
    b.inputs["Specular IOR Level"].default_value = 0.4
    if any(n.type == "TEX_WAVE" for n in nt.nodes):
        return
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "RINGS"
    w.inputs["Scale"].default_value = 45
    w.inputs["Distortion"].default_value = 12
    w.inputs["Detail"].default_value = 4
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    bp.inputs["Distance"].default_value = 0.003
    nt.links.new(w.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.004
    mr.inputs["To Max"].default_value = 0.016
    nt.links.new(w.outputs["Fac"], mr.inputs["Value"])
    cc = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(mr.outputs["Result"], cc.inputs[i])
    nt.links.new(cc.outputs["Color"], b.inputs["Base Color"])


# ------------------------------------------------------------------ stages
def stage_body(P=BODY):
    V, E, R = [], [], []

    def v(p, r):
        V.append(p)
        R.append(r)
        return len(V) - 1

    def ln(*ids):
        E.extend(zip(ids, ids[1:]))

    pel = v((0, 0, 0.70), P["pel"]); bel = v((0, -0.008, 0.84), P["bel"]); che = v((0, -0.01, 1.00), P["che"])
    upc = v((0, 0, 1.12), P["upc"]); nkb = v((0, 0.005, 1.21), (0.05, 0.05)); nkt = v((0, 0.01, 1.31), (0.046, 0.046))
    ln(pel, bel, che, upc, nkb, nkt)
    for s in (-1, 1):
        sh = v((s * 0.15, 0, 1.15), P["sh"]); sl = v((s * 0.2, 0, 1.01), P["sl"]); ua = v((s * 0.203, 0, 0.99), (0.043, 0.043))
        el = v((s * 0.207, 0.005, 0.90), (0.036, 0.036)); fa = v((s * 0.21, 0, 0.81), (0.035, 0.033))
        wr = v((s * 0.212, -0.005, 0.725), (0.029, 0.025)); pa = v((s * 0.214, -0.006, 0.675), P["palm"])
        ln(upc, sh, sl, ua, el, fa, wr, pa)
        for i, dy in enumerate((-0.027, -0.009, 0.009, 0.026)):
            length = 0.06 - abs(i - 1.3) * 0.008
            k1 = v((s * 0.214, -0.006 + dy, 0.645), (P["fr"], P["fr"]))
            k2 = v((s * 0.212, -0.008 + dy * 1.1, 0.645 - length), (P["fr"] * 0.9, P["fr"] * 0.9))
            E.extend(((pa, k1), (k1, k2)))
        t1 = v((s * 0.2, -0.04, 0.68), (P["fr"] * 1.15,) * 2); t2 = v((s * 0.19, -0.06, 0.65), (P["fr"],) * 2)
        E.extend(((pa, t1), (t1, t2)))
        L = P["leg"]; hx = 0.086
        hp = v((s * hx, 0, 0.64), (L[0],) * 2); th = v((s * hx, 0, 0.53), (L[1],) * 2)
        kn = v((s * hx, -0.004, 0.38), (L[2],) * 2); ca = v((s * hx, 0, 0.24), (L[3],) * 2); an = v((s * hx, 0, 0.09), (L[4],) * 2)
        ln(pel, hp, th, kn, ca, an)
    o = _skin_obj(PFX + "Body", V, E, R, root=pel)
    _select_only(o)
    bpy.ops.object.convert(target="MESH")
    # torso depth +20 % (side-view match) and pant hems flared + flattened above the shoe
    for vt in o.data.vertices:
        c = vt.co
        if abs(c.x) < 0.185 and 0.62 < c.z < 1.24:
            w = min(1, (c.z - 0.62) / 0.08) * min(1, (1.24 - c.z) / 0.06)
            c.y *= 1 + 0.2 * w
        if c.z < 0.17 and abs(c.x) > 0.02:
            cx = 0.086 if c.x > 0 else -0.086
            f = 1 + 0.12 * (0.17 - c.z) / 0.1
            c.x = cx + (c.x - cx) * f
            c.y *= f
            c.z = max(c.z, 0.085)
    return o


def stage_head(M):
    C = (0, 0, 1.39); RX, RY, RZ = 0.135, 0.125, 0.142
    h = _sphere(PFX + "Head", C, (RX, RY, RZ), 40, 28)
    for vt in h.data.vertices:
        x, y, z = vt.co
        t = -z / RZ
        if t > 0:
            k = 1 - 0.30 * t ** 1.6
            vt.co.x = x * k
            vt.co.y = y * (1 - 0.12 * t ** 2)
            if y < 0:
                vt.co.y -= 0.018 * t ** 2
        elif y > 0:
            vt.co.y = y * (1 + 0.06 * (-t))
        if y < 0 and -0.4 < t < 0.45:
            vt.co.x *= 1.04
        if y > 0 and t < -0.2:
            vt.co.y += 0.01 * (-t)
    parts = {PFX + "Head": "skin", PFX + "Nose": "skin"}
    for s, sd in ((-1, "L"), (1, "R")):
        _sphere(f"{PFX}Eye_{sd}", (s * 0.05, -0.088, 1.405), (0.036, 0.036, 0.038))
        _sphere(f"{PFX}Iris_{sd}", (s * 0.05, -0.1205, 1.405), (0.0253, 0.0065, 0.027))
        _sphere(f"{PFX}Pupil_{sd}", (s * 0.05, -0.1262, 1.405), (0.01265, 0.0025, 0.0132))
        _sphere(f"{PFX}Glint_{sd}", (s * 0.05 - 0.009, -0.1285, 1.415), (0.0045, 0.002, 0.0045), 12, 8)
        _sphere(f"{PFX}Ear_{sd}", (s * 0.128, 0.012, 1.375), (0.016, 0.03, 0.04))
        brow = _skin_obj(f"{PFX}Brow_{sd}", [(s * 0.02, -0.121, 1.447), (s * 0.05, -0.124, 1.455), (s * 0.082, -0.111, 1.448)],
                         [(0, 1), (1, 2)], [(0.012, 0.0074), (0.0125, 0.0078), (0.009, 0.0056)])
        parts.update({f"{PFX}Eye_{sd}": "eyewhite", f"{PFX}Iris_{sd}": "iris", f"{PFX}Pupil_{sd}": "pupil",
                      f"{PFX}Glint_{sd}": "glint", f"{PFX}Ear_{sd}": "skin", brow.name: "hair"})
    _sphere(PFX + "Nose", (0, -0.132, 1.35), (0.023, 0.0198, 0.0187))

    def smile(k, flat):
        return lambda x, y, z: (x, y, (z * 0.3 if flat and z > 0 else z) / 1.0 + 0)

    def mouth(name, loc, sc, bend, flat):
        def fn(x, y, z):
            if flat and z > 0:
                z *= 0.3
            return x, y, z + bend * x * x / sc[2]
        return _sphere(name, loc, sc, 32, 16, fn)

    mouth(PFX + "MouthIn", (0, -0.099, 1.292), (0.044, 0.012, 0.021), 0.014, True)
    mouth(PFX + "Teeth", (0, -0.1105, 1.2975), (0.036, 0.006, 0.006), 0.012, False)
    mouth(PFX + "Tongue", (0, -0.107, 1.279), (0.024, 0.006, 0.008), 0.004, False)
    parts.update({PFX + "MouthIn": "mouth", PFX + "Teeth": "eyewhite", PFX + "Tongue": "tongue"})
    for n, k in parts.items():
        o = bpy.data.objects[n]
        o.data.materials.clear()
        o.data.materials.append(M[k])


def stage_hair(M, proxy_npz: str, seed: int = 7, count: int = 96):
    """Metaball clumps seeded from the blueprint proxy's hair region (dark vertices), plus an inner cap."""
    d = np.load(proxy_npz)
    P = d["pos"].astype(np.float64)
    col = d["col"].astype(np.float64) / 255.0   # glTF COLOR_0 is linear
    co = np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)  # glTF -> Blender
    dark = (col.max(1) < 0.05) & (co[:, 2] > 1.33)
    face = (co[:, 1] < -0.06) & (co[:, 2] < 1.475) & (np.abs(co[:, 0]) < 0.12)
    pts = co[dark & ~face]
    rng = np.random.default_rng(seed)
    idx = [int(rng.integers(len(pts)))]
    dist = np.linalg.norm(pts - pts[idx[0]], axis=1)
    for _ in range(count - 1):
        i = int(dist.argmax())
        idx.append(i)
        dist = np.minimum(dist, np.linalg.norm(pts - pts[i], axis=1))
    C = np.array([0, 0.01, 1.40])
    S = C + (pts[idx] - C) * 0.86
    mb = bpy.data.metaballs.new(PFX + "HairMB")
    mb.resolution = mb.render_resolution = 0.011
    mb.threshold = 0.6
    for p in S:
        e = mb.elements.new()
        e.co = tuple(p)
        e.radius = float(rng.uniform(0.04, 0.052))
    o = _link(bpy.data.objects.new(PFX + "HairMB", mb))
    mb.materials.append(M["hair"])
    _select_only(o)
    bpy.ops.object.convert(target="MESH")
    hair = bpy.context.view_layer.objects.active
    hair.name = PFX + "Hair"
    for p in hair.data.polygons:
        p.use_smooth = True
    dec = hair.modifiers.new("Dec", "DECIMATE")
    dec.ratio = 0.7
    bpy.ops.object.modifier_apply(modifier="Dec")
    # inner cap so no scalp shows between clumps
    head = bpy.data.objects[PFX + "Head"]
    cap = _link(bpy.data.objects.new(PFX + "HairCap", head.data.copy()))
    cap.location = head.location
    bm = bmesh.new()
    bm.from_mesh(cap.data)
    dl = [f for f in bm.faces if (lambda c: c.z < -0.035 or (c.y < -0.06 and c.z < 0.075) or (c.y < -0.03 and c.z < 0.03))(f.calc_center_median())]
    bmesh.ops.delete(bm, geom=dl, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    for v in bm.verts:
        v.co *= 1.035
    bm.to_mesh(cap.data)
    bm.free()
    cap.data.materials.clear()
    cap.data.materials.append(M["hair"])
    return hair


def stage_shoes(M):
    for s, sd in ((-1, "L"), (1, "R")):
        x = s * 0.093

        def stretch(p):
            return (p[0], 0.02 + (p[1] - 0.02) * 1.2 if p[1] < 0.02 else p[1], p[2])
        shoe = [((x, 0.04, 0.07), (0.038, 0.042)), ((x, 0.0, 0.058), (0.047, 0.05)), ((x, -0.07, 0.042), (0.049, 0.036)), ((x, -0.13, 0.032), (0.04, 0.024))]
        sole = [((x, 0.05, 0.018), (0.044, 0.018)), ((x, -0.03, 0.016), (0.055, 0.017)), ((x, -0.125, 0.018), (0.046, 0.017))]
        for name, pts, mat in ((f"{PFX}Shoe_{sd}", shoe, "shoe_canvas"), (f"{PFX}Sole_{sd}", sole, "shoe_sole")):
            o = _skin_obj(name, [stretch(p) for p, _ in pts], [(i, i + 1) for i in range(len(pts) - 1)], [r for _, r in pts])
            o.data.materials.append(M[mat])
        for k in range(3):
            y = 0.02 + (-0.025 - k * 0.024 - 0.02) * 1.2
            o = _skin_obj(f"{PFX}Lace{k}_{sd}", [(x - 0.02, y, 0.1 - k * 0.011), (x + 0.02, y, 0.1 - k * 0.011)], [(0, 1)],
                          [(0.0045, 0.0045)] * 2, levels=1)
            o.data.materials.append(M["lace"])


def stage_print(M):
    body = bpy.data.objects[PFX + "Body"]
    made = []
    for name, text, z, scale, fill, outline in (("PrintA", "kalian", 1.05, 1.1, "print_white", "print_ink"),
                                                ("PrintB", "tau gak?", 0.958, 1.0, "print_coral", "print_white")):
        for k, (mat, off, ex, dy) in enumerate(((outline, 0.004, 0.0015, 0.0), (fill, 0.0, 0.003, -0.0012))):
            cu = bpy.data.curves.new(f"{PFX}{name}{k}", "FONT")
            cu.body, cu.size, cu.align_x, cu.align_y = text, 0.072, "CENTER", "CENTER"
            cu.offset, cu.extrude, cu.bevel_depth, cu.resolution_u = off, ex, 0.0006, 4
            cu.materials.append(M[mat])
            o = _link(bpy.data.objects.new(f"{PFX}{name}_{k}", cu))
            o.rotation_euler = (math.pi / 2, 0, 0)
            o.location = (0, -0.16 + dy, z)
            o.scale = (scale,) * 3
            _select_only(o)
            bpy.ops.object.convert(target="MESH")
            sw = o.modifiers.new("Wrap", "SHRINKWRAP")
            sw.target = body
            sw.wrap_method = "PROJECT"
            sw.use_project_z = True                 # text local +Z points to world -Y after the 90 deg X turn
            sw.use_negative_direction = True
            sw.use_positive_direction = False
            sw.offset = 0.003 + (0.0015 if k else 0)
            bpy.ops.object.convert(target="MESH")
            made.append(o)
    return made


def stage_materials_assign(M, with_print: bool = False):
    o = bpy.data.objects[PFX + "Body"]
    me = o.data
    for k in ("shirt", "skin", "pants"):
        me.materials.append(M[k])
    bm = bmesh.new()
    bm.from_mesh(me)

    def cut(z, sel):
        geom = ([e for e in bm.edges if all(sel(v.co) for v in e.verts)] + [f for f in bm.faces if all(sel(v.co) for v in f.verts)]
                + [v for v in bm.verts if sel(v.co)])
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1))
    cut(0.75, lambda c: abs(c.x) < 0.185 and 0.6 < c.z < 0.9)
    cut(0.985, lambda c: abs(c.x) > 0.15 and 0.9 < c.z < 1.1)
    cut(1.235, lambda c: abs(c.x) < 0.09 and 1.18 < c.z < 1.3)
    for f in bm.faces:
        c = f.calc_center_median()
        ax = abs(c.x)
        f.material_index = 1 if (c.z > 1.235 or (ax > 0.17 and c.z < 0.985)) else (2 if (c.z < 0.75 and ax < 0.185) else 0)
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    # collar rib, then join print + collar into the body
    cm = bpy.data.meshes.new(PFX + "Collar")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=1, segments=32)
    bm.to_mesh(cm)
    bm.free()
    col = _link(bpy.data.objects.new(PFX + "Collar", cm))
    col.location, col.scale = (0, 0.004, 1.228), (0.058, 0.056, 1)
    col.modifiers.new("Skin", "SKIN")
    for d in cm.skin_vertices[0].data:
        d.radius = (0.009, 0.009)
    col.modifiers.new("Sub", "SUBSURF").levels = 1
    cm.materials.append(M["shirt"])
    _select_only(col)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.select_all(action="DESELECT")
    for ob in bpy.data.objects:
        if ob.name.startswith((PFX + "Collar",)) or (with_print and ob.name.startswith(PFX + "Print")):
            ob.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.join()
    # decimate dense text only, then clean
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in o.data.polygons:
        p.select = p.material_index >= 3
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.decimate(ratio=0.25)
    bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    for ob in list(bpy.data.objects):
        if ob.name.startswith((PFX + "Shoe_", PFX + "Sole_", PFX + "Lace", PFX + "Brow_")) and ob.modifiers:
            _select_only(ob)
            bpy.ops.object.convert(target="MESH")


BONES = [
    ("root", (0, 0, 0), (0, 0.15, 0), None, False, False),
    ("hips", (0, 0, 0.70), (0, 0, 0.84), "root", False, True), ("spine", (0, 0, 0.84), (0, 0, 1.0), "hips", True, True),
    ("chest", (0, 0, 1.0), (0, 0, 1.17), "spine", True, True), ("neck", (0, 0, 1.17), (0, 0, 1.27), "chest", True, True),
    ("head", (0, 0, 1.27), (0, 0, 1.6), "neck", True, False),
]
for _s, _sd in ((-1, "L"), (1, "R")):
    BONES += [
        (f"shoulder.{_sd}", (_s * 0.03, 0, 1.15), (_s * 0.14, 0, 1.15), "chest", False, True),
        (f"upper_arm.{_sd}", (_s * 0.15, 0, 1.15), (_s * 0.207, 0.005, 0.90), f"shoulder.{_sd}", True, True),
        (f"forearm.{_sd}", (_s * 0.207, 0.005, 0.90), (_s * 0.212, -0.005, 0.725), f"upper_arm.{_sd}", True, True),
        (f"hand.{_sd}", (_s * 0.212, -0.005, 0.725), (_s * 0.214, -0.006, 0.61), f"forearm.{_sd}", True, True),
        (f"thigh.{_sd}", (_s * 0.086, 0, 0.66), (_s * 0.086, -0.004, 0.38), "hips", False, True),
        (f"shin.{_sd}", (_s * 0.086, -0.004, 0.38), (_s * 0.088, 0, 0.09), f"thigh.{_sd}", True, True),
        (f"foot.{_sd}", (_s * 0.088, 0, 0.09), (_s * 0.093, -0.11, 0.03), f"shin.{_sd}", True, False),
    ]


def stage_rig():
    arm = bpy.data.armatures.new(PFX + "Rig")
    rig = _link(bpy.data.objects.new(PFX + "Rig", arm))
    _select_only(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    for n, h, t, p, conn, deform in BONES:
        b = arm.edit_bones.new(n)
        b.head, b.tail, b.use_deform = h, t, deform
        if p:
            b.parent = arm.edit_bones[p]
            b.use_connect = conn
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def _segd(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def stage_weights():
    """Distance-to-bone weights, arm vs torso separated by geodesic regions (Bone Heat fails on this mesh)."""
    rig, body = bpy.data.objects[PFX + "Rig"], bpy.data.objects[PFX + "Body"]
    me = body.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(float)
    ed = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    adj = [[] for _ in range(len(co))]
    for (a, b), l in zip(ed, np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1)):
        adj[a].append((b, l))
        adj[b].append((a, l))
    bn = {b.name: (np.array(b.head_local), np.array(b.tail_local)) for b in rig.data.bones}
    lab = np.full(len(co), -1)
    dist = np.full(len(co), np.inf)
    heap = []
    seeds = {0: np.abs(co[:, 0]) < 0.03,
             1: (_segd(co, *bn["forearm.L"]) < 0.05) & (co[:, 0] < -0.17),
             2: (_segd(co, *bn["forearm.R"]) < 0.05) & (co[:, 0] > 0.17)}
    for k, m in seeds.items():
        for i in np.nonzero(m)[0]:
            dist[i] = 0
            lab[i] = k
            heapq.heappush(heap, (0.0, int(i), k))
    while heap:
        d, i, k = heapq.heappop(heap)
        if d > dist[i]:
            continue
        for j, l in adj[i]:
            if d + l < dist[j]:
                dist[j] = d + l
                lab[j] = k
                heapq.heappush(heap, (d + l, j, k))
    deform = {n: v for n, v in bn.items() if rig.data.bones[n].use_deform}
    names = list(deform)
    D = np.stack([_segd(co, *deform[n]) for n in names], 1)
    x, z = co[:, 0], co[:, 2]
    armL, armR = lab == 1, lab == 2
    torso = ~(armL | armR)
    allow = np.zeros_like(D, bool)
    for j, n in enumerate(names):
        if n.startswith(("upper_arm", "forearm", "hand")):
            allow[:, j] = armL if n.endswith("L") else armR
        elif n.startswith("shoulder"):
            allow[:, j] = (((armL | torso) & (x < 0)) if n.endswith("L") else ((armR | torso) & (x > 0))) & (z > 1.0)
        elif n.startswith(("thigh", "shin")):
            allow[:, j] = torso & (z < 0.78) & ((x < 0) if n.endswith("L") else (x >= 0))
        else:
            allow[:, j] = torso | ((armL | armR) & (z > 1.08) & (n == "chest"))
            if n == "neck":
                allow[:, j] &= z > 1.12
            if n == "hips":
                allow[:, j] &= z < 0.95
    W = np.where(allow, 1.0 / np.maximum(D, 0.004) ** 4, 0)
    np.put_along_axis(W, np.argsort(-W, 1)[:, 3:], 0, 1)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    body.vertex_groups.clear()
    for j, n in enumerate(names):
        g = body.vertex_groups.new(name=n)
        for i in np.nonzero(W[:, j] > 0.01)[0]:
            g.add([int(i)], float(W[i, j]), "REPLACE")
    body.modifiers.new("Armature", "ARMATURE").object = rig
    body.parent = rig
    return int((W.sum(1) < 0.99).sum())


def stage_finish():
    rig = bpy.data.objects[PFX + "Rig"]
    vl = bpy.context.view_layer
    for o in list(bpy.data.objects):
        n = o.name
        if not n.startswith(PFX) or o.type != "MESH" or n == PFX + "Body":
            continue
        if n.startswith(PFX + "Print"):
            continue
        bone = ("foot." + n[-1]) if n.startswith((PFX + "Shoe_", PFX + "Sole_", PFX + "Lace")) else "head"
        mw = o.matrix_world.copy()
        o.parent, o.parent_type, o.parent_bone = rig, "BONE", bone
        vl.update()
        o.matrix_world = mw
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = -1.05
    if hasattr(sc.eevee, "use_raytracing"):
        sc.eevee.use_raytracing = False
    sc.eevee.taa_render_samples = 16


def stage_face_integrate(M):
    """Owner request: blush and mouth are part of the face asset (nothing floating).
    Blush = vertex-colour gradient painted on the head skin; mouth = smile-shaped hole carved into the head with an
    inward lip rim, cavity/teeth/tongue behind the surface; nose, ears and mouth parts joined into ``Face``."""
    h = bpy.data.objects[PFX + "Head"]
    O = Vector(h.location)
    bm = bmesh.new()
    bm.from_mesh(h.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=1, use_grid_fill=True, smooth=1.0)

    def inside(c):
        w = c + O
        if w.y > -0.05:
            return False
        u = w.x / 0.042
        if abs(u) >= 1:
            return False
        return 1.292 + 0.014 * u * u - 0.02 * math.sqrt(1 - u * u) < w.z < 1.2975 + 0.014 * u * u
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if inside(f.calc_center_median())], context="FACES")
    ret = bmesh.ops.extrude_edge_only(bm, edges=[e for e in bm.edges if e.is_boundary])
    nv = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    cen = sum((v.co for v in nv), Vector()) / len(nv)
    for v in nv:
        v.co = cen + (v.co - cen) * 0.85
        v.co.y += 0.011
    bm.to_mesh(h.data)
    bm.free()
    me = h.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(O)
    w = np.zeros(len(co))
    for s in (-1, 1):
        d = np.sqrt((co[:, 0] - s * 0.083) ** 2 + ((co[:, 2] - 1.335) / 0.8) ** 2)
        t = np.clip(1 - d / 0.042, 0, 1)
        w = np.maximum(w, t * t * (3 - 2 * t) * (co[:, 1] < -0.02))
    ca = me.color_attributes.new("Blush", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.repeat(w, 4).astype(np.float32))
    face = M["skin"].copy()
    face.name = PFX + "skin_face"
    nt = face.node_tree
    b = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Blush"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = b.inputs["Base Color"].default_value[:]
    mix.inputs["B"].default_value = (0.78, 0.24, 0.2, 1)
    nt.links.new(at.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    for name, y, z in ((PFX + "MouthIn", -0.081, None), (PFX + "Teeth", -0.0918, 1.2928), (PFX + "Tongue", -0.0885, None)):
        o = bpy.data.objects[name]
        o.location.y = y
        if z:
            o.location.z = z
    bpy.data.objects[PFX + "MouthIn"].scale = (1.08, 1.0, 1.15)
    bpy.data.objects[PFX + "Teeth"].scale = (0.95, 1.0, 1.25)
    me.materials.clear()
    me.materials.append(face)
    bpy.ops.object.select_all(action="DESELECT")
    for n in ("MouthIn", "Teeth", "Tongue", "Nose", "Ear_L", "Ear_R"):
        bpy.data.objects[PFX + n].select_set(True)
    h.select_set(True)
    bpy.context.view_layer.objects.active = h
    bpy.ops.object.join()
    h.name = PFX + "Face"
    skin_i = [m.name for m in h.data.materials].index(M["skin"].name) if M["skin"].name in h.data.materials else None
    if skin_i is not None:
        for p in h.data.polygons:
            if p.material_index == skin_i:
                p.material_index = 0
    return h


def stage_sleeve_fix():
    """Sleeve hem by bone ownership, not by x: inner-arm faces below the hem become skin (fixes orange spill)."""
    b = bpy.data.objects[PFX + "Body"]
    me = b.data
    armg = {g.index for g in b.vertex_groups if g.name.startswith(("upper_arm", "forearm", "hand"))}
    aw = np.array([sum(g.weight for g in v.groups if g.group in armg) for v in me.vertices])
    mats = [m.name for m in me.materials]
    SH, SK = mats.index(PFX + "shirt"), mats.index(PFX + "skin")
    for p in me.polygons:
        if p.material_index in (SH, SK) and aw[list(p.vertices)].mean() > 0.5:
            p.material_index = SK if p.center.z < 0.985 else SH


def stage_print_live(M):
    """Raised print as separate objects on the chest bone with a LIVE shrinkwrap to the deforming body, sized to stay
    inside the chest (|x| < 0.1); fill sits 1.8 mm above its outline."""
    vl = bpy.context.view_layer
    body, rig = bpy.data.objects[PFX + "Body"], bpy.data.objects[PFX + "Rig"]
    for name, text, z, size, fill, outline in (("A", "kalian", 1.045, 0.066, "print_white", "print_ink"),
                                                ("B", "tau gak?", 0.962, 0.058, "print_coral", "print_white")):
        for k, (mat, off, ex) in enumerate(((outline, 0.0035, 0.0012), (fill, 0.0, 0.0025))):
            cu = bpy.data.curves.new(f"{PFX}Print{name}{k}", "FONT")
            cu.body, cu.size, cu.align_x, cu.align_y = text, size, "CENTER", "CENTER"
            cu.offset, cu.extrude, cu.bevel_depth, cu.resolution_u = off, ex, 0.0005, 2
            cu.materials.append(M[mat])
            o = _link(bpy.data.objects.new(f"{PFX}Print{name}_{'fill' if k else 'outline'}", cu))
            o.rotation_euler = (math.pi / 2, 0, 0)
            o.location = (0, -0.17, z)
            _select_only(o)
            bpy.ops.object.convert(target="MESH")
            o = vl.objects.active
            sw = o.modifiers.new("Wrap", "SHRINKWRAP")
            sw.target, sw.wrap_method = body, "PROJECT"
            sw.use_project_z, sw.use_negative_direction, sw.use_positive_direction = True, True, False
            sw.offset = 0.0022 + (0.0018 if k else 0)
            mw = o.matrix_world.copy()
            o.parent, o.parent_type, o.parent_bone = rig, "BONE", "chest"
            vl.update()
            o.matrix_world = mw
