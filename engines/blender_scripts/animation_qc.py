"""XDX numeric animation QC (Phase 02B.4) — measured on the evaluated Blender scene, frame by frame.

collect(...) samples bone/object world positions in chunks (each MCP call < 3.5 s) into bpy.app.tempdir;
metrics(...) turns them into the acceptance numbers used by the action compiler criteria:
foot sliding while planted, IK reach error (hands/feet), hand-object contact while attached, object vs support
surface (penetration / floating) when free, rim-to-mouth distance and object-head clearance while drinking, balance.
These numbers gate the render; the independent critic still judges real frames and the motion preview.
"""
from __future__ import annotations

import json
import math
import os

import bpy  # type: ignore

FILE = "xdx_anim_qc_rows.json"


def collect(rig_name: str, obj_name: str, start: int, end: int, *, reset: bool = False, bones=None) -> int:
    path = os.path.join(bpy.app.tempdir, FILE)
    rows = [] if reset or not os.path.exists(path) else json.load(open(path))
    sc = bpy.context.scene
    r = bpy.data.objects[rig_name]
    P = r.pose.bones
    o = bpy.data.objects[obj_name] if obj_name else None
    bones = bones or {"footL": "foot.L", "footR": "foot.R", "handL": "hand.L", "handR": "hand.R", "head": "head", "hips": "hips",
                      "ikfL": "ik_foot.L", "ikfR": "ik_foot.R", "ikhL": "ik_hand.L", "ikhR": "ik_hand.R"}
    for f in range(start, end + 1):
        sc.frame_set(f)
        mw = r.matrix_world
        row = {"f": f}
        for k, b in bones.items():
            row[k] = tuple(mw @ P[b].head)
        if o:
            row["obj"] = tuple(o.matrix_world.translation)
            row["obj_up"] = tuple(o.matrix_world.to_3x3().col[2])
        rows.append(row)
    json.dump(rows, open(path, "w"))
    return len(rows)


def metrics(*, foot_target_offset_z: float, attach=None, detach=None, surface_z=None, obj_height=0.11,
            mouth_offset=(0.0, -0.11, 0.02), head_clear_offset=0.12, drink_window=None, planted_eps=0.002) -> dict:
    rows = json.load(open(os.path.join(bpy.app.tempdir, FILE)))
    rows.sort(key=lambda r: r["f"])
    out = {"frames": [rows[0]["f"], rows[-1]["f"]]}
    slide = {}
    for s in "LR":
        worst = (0.0, None)
        for a, b in zip(rows, rows[1:]):
            if a["ikf" + s][2] <= foot_target_offset_z + planted_eps and b["ikf" + s][2] <= foot_target_offset_z + planted_eps:
                d = math.dist(a["foot" + s][:2], b["foot" + s][:2])
                if d > worst[0]:
                    worst = (round(d, 4), b["f"])
        slide[s] = worst
    out["foot_slide_max_m"] = slide
    for k, t in (("handL", "ikhL"), ("handR", "ikhR"), ("footL", "ikfL"), ("footR", "ikfR")):
        out[f"ik_reach_error_{k}"] = max((round(math.dist(r[k], r[t]), 4), r["f"]) for r in rows)
    if attach and detach and "obj" in rows[0]:
        d = [round(math.dist(r["handR"], r["obj"]), 4) for r in rows if attach <= r["f"] < detach]
        out["hand_object_offset_range_m"] = [min(d), max(d)]          # constant offset == rigid contact
    if surface_z is not None and "obj" in rows[0]:
        free = [r for r in rows if (attach is None or r["f"] < attach) or (detach is not None and r["f"] >= detach)]
        out["object_below_surface_max_m"] = round(max(surface_z - r["obj"][2] for r in free), 4)
        out["object_above_surface_max_m"] = round(max(r["obj"][2] - surface_z for r in free), 4)
    if drink_window and "obj" in rows[0]:
        win = [r for r in rows if drink_window[0] <= r["f"] <= drink_window[1]]

        def along(r, k):
            return tuple(r["obj"][i] + k * r["obj_up"][i] for i in range(3))
        rim = [(round(math.dist(along(r, obj_height), (r["head"][0] + mouth_offset[0], r["head"][1] + mouth_offset[1],
                                                          r["head"][2] + mouth_offset[2])), 3), r["f"]) for r in win]
        clr = [(round(math.dist(along(r, obj_height / 2), (r["head"][0], r["head"][1], r["head"][2] + head_clear_offset)), 3), r["f"])
               for r in win]
        out["rim_to_mouth_min_m"] = min(rim)
        out["object_to_head_centre_min_m"] = min(clr)
    return out
