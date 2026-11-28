"""Native bpy/bmesh geometry QC for XDX character/prop assets (original code, MIT-compatible).

Concepts (validation checklist, curvature, gap analysis) follow common practice and the audited
Mesh Workbench / blend-ai feature lists; no upstream code is copied. Mesh Workbench (MIT) was found to
import on Android ARM64 / Blender 5.3 but its quality functions need its own baked-mesh pipeline, so
these checks are implemented natively.

Run inside the XDX Blender MCP via execute_blender_code. Read-only: nothing here mutates scene data.
Keep each call < 3.5 s on the Vivo X200 Pro (use `prefix` to limit objects).
"""
import math

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _meshes(prefix, exclude=()):
    return [o for o in bpy.data.objects
            if o.type == "MESH" and o.name.startswith(prefix) and not any(x in o.name for x in exclude)]


def validate_mesh(obj, area_eps=1e-10, dup_eps=1e-6):
    """Non-manifold edges, loose verts, zero-area faces, duplicate verts, ngons, tris/quads."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    out = {
        "object": obj.name,
        "verts": len(bm.verts), "faces": len(bm.faces),
        "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary),
        "boundary_edges": sum(1 for e in bm.edges if e.is_boundary),
        "loose_verts": sum(1 for v in bm.verts if not v.link_edges),
        "zero_area_faces": sum(1 for f in bm.faces if f.calc_area() < area_eps),
        "ngons": sum(1 for f in bm.faces if len(f.verts) > 4),
        "tris": sum(1 for f in bm.faces if len(f.verts) == 3),
    }
    seen, dups = {}, 0
    for v in bm.verts:
        k = (round(v.co.x / dup_eps), round(v.co.y / dup_eps), round(v.co.z / dup_eps))
        dups += k in seen
        seen[k] = 1
    out["duplicate_verts"] = dups
    bm.free()
    return out


def validate_prefix(prefix, max_tris=60000, exclude=()):
    reports = [validate_mesh(o) for o in _meshes(prefix, exclude)]
    tris_total = sum(r["tris"] + 2 * (r["faces"] - r["tris"]) for r in reports)  # rough: quads=2 tris
    bad = [r for r in reports if r["loose_verts"] or r["zero_area_faces"] or r["duplicate_verts"] > r["verts"] * 0.5]
    return {"objects": len(reports), "approx_tris": tris_total, "within_budget": tris_total <= max_tris,
            "needs_attention": [r["object"] for r in bad], "reports": reports}


def curvature_stats(obj):
    """Vertex-normal deviation vs neighbours as a cheap curvature proxy (0 flat .. ~1 sharp)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    vals = []
    for v in bm.verts:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if nbrs:
            vals.append(sum(1 - max(-1.0, min(1.0, v.normal.dot(n.normal))) for n in nbrs) / len(nbrs))
    bm.free()
    if not vals:
        return {"object": obj.name, "mean": 0.0, "max": 0.0, "sharp_fraction": 0.0}
    return {"object": obj.name, "mean": round(sum(vals) / len(vals), 4), "max": round(max(vals), 4),
            "sharp_fraction": round(sum(v > 0.15 for v in vals) / len(vals), 4)}


def _bvh(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [obj.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    ev.to_mesh_clear()
    return tree, verts


def gap_analysis(name_a, name_b, samples=200):
    """Minimum sampled distance between two objects' surfaces (0 = touching/overlapping)."""
    a, b = bpy.data.objects[name_a], bpy.data.objects[name_b]
    ta, va = _bvh(a)
    tb, _ = _bvh(b)
    step = max(1, len(va) // samples)
    best = math.inf
    for p in va[::step]:
        hit = tb.find_nearest(p)
        if hit and hit[3] is not None:
            best = min(best, hit[3])
    return {"a": name_a, "b": name_b, "min_gap_m": None if best is math.inf else round(best, 5)}


def part_proportions(prefix, parts, exclude=()):
    """World-space bbox size of named parts, plus ratios to total height (for head-unit checks)."""
    def bbox(objs):
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return mn, mx
    allo = _meshes(prefix, exclude)
    mn, mx = bbox(allo)
    total_h = mx.z - mn.z
    out = {"total_height_m": round(total_h, 4), "total_width_m": round(mx.x - mn.x, 4), "parts": {}}
    for label, names in parts.items():
        objs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
        if objs:
            a, b = bbox(objs)
            out["parts"][label] = {"w": round(b.x - a.x, 4), "h": round(b.z - a.z, 4), "h_ratio": round((b.z - a.z) / total_h, 4)}
    return out


def landmark_positions(camera, names):
    """Normalised (0..1, y down) screen position of object origins/centres seen by `camera`."""
    scene = bpy.context.scene
    out = {}
    for n in names:
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        c = o.matrix_world @ (sum((Vector(p) for p in o.bound_box), Vector()) / 8)
        uv = world_to_camera_view(scene, camera, c)
        out[n] = (round(uv.x, 4), round(1 - uv.y, 4))
    return out
