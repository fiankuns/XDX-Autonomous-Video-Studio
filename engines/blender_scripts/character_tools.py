"""Character modeling helpers for the Blender MCP session (Phase 02B.2 asset work).

Original implementation. The tool names/ideas (create_curve, join_objects, sculpt grab/inflate/
smooth, symmetrize, generate_views, reference compare) were inspired by the public
seehiong/blender-mcp-bridge docs; no code was copied from that repo.

Usage inside `execute_blender_code`:
    import sys; sys.path.insert(0, "<repo>/engines/blender_scripts"); import character_tools as T
Rules: only touch objects whose names start with the given prefix (never Camera/Light);
keep each call < 3.5 s (Vivo X200 Pro ANR budget); temp files go to bpy.app.tempdir.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector


# ----------------------------------------------------------------- helpers
def _obj(name):
    o = bpy.data.objects.get(name)
    if o is None:
        raise KeyError(f"object not found: {name}")
    return o


def _select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def hex_to_linear(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


# ----------------------------------------------------------------- modeling
def create_curve(name, points, bevel=0.01, taper=None, cyclic=False, material=None, parent_collection=None):
    """Bezier curve through `points` [(x,y,z)...] with round bevel; returns the curve object."""
    cu = bpy.data.curves.new(name + "_c", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.resolution_u = 10
    cu.use_fill_caps = True
    if taper is not None:
        cu.taper_object = _obj(taper)
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    (parent_collection or bpy.context.scene.collection).objects.link(ob)
    if material:
        cu.materials.append(material)
    return ob


def convert_to_mesh(name):
    o = _obj(name)
    _select_only([o])
    bpy.ops.object.convert(target="MESH")
    return bpy.context.active_object


def join_objects(names, new_name):
    objs = [_obj(n) for n in names]
    _select_only(objs)
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = o.data.name = new_name
    return o


def apply_all_modifiers(name):
    o = _obj(name)
    _select_only([o])
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return o


def apply_transforms(name):
    o = _obj(name)
    _select_only([o])
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def add_outline(name, thickness=0.0035, ink_material="Ingpoh_m_ink"):
    """Inverted-hull outline (solidify, flipped normals, back faces only)."""
    o = _obj(name)
    ink = bpy.data.materials.get(ink_material)
    if ink is None:
        ink = bpy.data.materials.new(ink_material)
        ink.use_nodes = True
        ink.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hex_to_linear("#3A2548")
        ink.use_backface_culling = True
    if ink not in list(o.data.materials):
        o.data.materials.append(ink)
    mod = o.modifiers.get("ink") or o.modifiers.new("ink", "SOLIDIFY")
    mod.thickness, mod.offset, mod.use_flip_normals = thickness, 1, True
    mod.material_offset = len(o.data.materials) - 1
    return o


# ----------------------------------------------------------------- sculpt-like ops (bmesh, no sculpt mode)
def _falloff(d, r):
    t = max(0.0, 1.0 - d / r)
    return t * t * (3 - 2 * t)


def sculpt_grab(name, center, offset, radius):
    """Pull vertices near world-space `center` by `offset` with smooth falloff."""
    o = _obj(name)
    inv = o.matrix_world.inverted()
    c = inv @ Vector(center)
    off = inv.to_3x3() @ Vector(offset)
    for v in o.data.vertices:
        d = (v.co - c).length
        if d < radius:
            v.co += off * _falloff(d, radius)
    o.data.update()
    return o


def sculpt_inflate(name, center, distance, radius):
    """Push vertices along their normals (distance>0 inflates, <0 deflates)."""
    o = _obj(name)
    c = o.matrix_world.inverted() @ Vector(center)
    for v in o.data.vertices:
        d = (v.co - c).length
        if d < radius:
            v.co += v.normal * distance * _falloff(d, radius)
    o.data.update()
    return o


def smooth_mesh(name, iterations=2, factor=0.5):
    o = _obj(name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for _ in range(iterations - 1):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


def symmetrize_mesh(name, axis="X", direction="POSITIVE_X"):
    o = _obj(name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:],
                         direction={"POSITIVE_X": "+X", "NEGATIVE_X": "-X"}.get(direction, "+X"))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


# ----------------------------------------------------------------- materials
def create_material(name, hex_color, roughness=0.75, emission=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_to_linear(hex_color)
    b.inputs["Roughness"].default_value = roughness
    if emission > 0:
        b.inputs["Emission Color"].default_value = hex_to_linear(hex_color)
        b.inputs["Emission Strength"].default_value = emission
    m.diffuse_color = hex_to_linear(hex_color)
    return m


def assign_material(name, material, slot=0):
    o = _obj(name)
    if material.name not in [m.name for m in o.data.materials if m]:
        o.data.materials.append(material)
    for p in o.data.polygons:
        p.material_index = list(o.data.materials).index(material) if slot is None else slot
    return o


# ----------------------------------------------------------------- verification
def silhouette_bbox(prefix):
    """World-space bbox (min, max) of all MESH objects whose name starts with prefix."""
    pts = []
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(prefix):
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        return None
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def front_view_extent_px(prefix, px_per_m=725.0):
    """Front (XZ) extent in reference-image pixels, to compare with the 2D art (636x844 @ 725 px/m)."""
    r = silhouette_bbox(prefix)
    if r is None:
        return None
    mn, mx = r
    return {"width_px": round((mx.x - mn.x) * px_per_m), "height_px": round((mx.z - mn.z) * px_per_m)}


def set_viewport_view(view="FRONT", target=(0, 0, 0.5), distance=1.5):
    """Orthographic-style viewport move for look(); FRONT looks along +Y (character faces -Y)."""
    from mathutils import Euler
    rot = {"FRONT": (90, 0, 0), "BACK": (90, 0, 180), "SIDE_RIGHT": (90, 0, 90),
           "SIDE_LEFT": (90, 0, -90), "TOP": (0, 0, 0)}[view]
    for w in bpy.context.window_manager.windows:
        for ar in w.screen.areas:
            if ar.type == "VIEW_3D":
                r = ar.spaces[0].region_3d
                r.view_perspective = "PERSP"
                r.view_location = target
                r.view_distance = distance
                r.view_rotation = Euler(tuple(math.radians(a) for a in rot)).to_quaternion()
    return view
