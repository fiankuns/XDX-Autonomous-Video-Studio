"""Apply a compiled XDX action plan (intelligence/action_compiler.py) to a Blender rig. Generic via a rig profile.

Control spaces (rig profile ``control_spaces``; defaults below):
- root_world:   root bone, world location + yaw (bone rests at the origin pointing +Y)
- body_fk:      vertical FK bones (hips/spine/chest/neck/head): body (pitch, roll, yaw) -> bone euler (pitch, yaw, -roll);
                hips also take a body-frame offset (dx right, dy back, dz up) -> bone local (dx, dz, -dy)
- world_target: unparented IK / eye targets, world location (+ optional pitch tilt for hands, yaw for feet)
- face:         blink -> lid bones X rotation, brow_up -> brow bones local Y, smile / mouth_open -> shape keys
Easing: the compiler's ease on a key shapes the segment INTO that key (SINE + EASE_IN / EASE_OUT / EASE_IN_OUT,
AUTO_CLAMPED -> BEZIER auto-clamped).
"""
from __future__ import annotations

import math

import bpy  # type: ignore
from mathutils import Euler, Matrix, Vector  # type: ignore

DEFAULT_SPACES = {"root": "root_world", "hips": "body_fk", "spine": "body_fk", "chest": "body_fk", "neck": "body_fk",
                  "head": "body_fk", "ik_hand.L": "world_target", "ik_hand.R": "world_target", "ik_foot.L": "world_target",
                  "ik_foot.R": "world_target", "eye_target": "world_target"}


def _body_euler(rot):
    p, r, y = (math.radians(v) for v in rot)
    return (p, y, -r)


def apply_plan(rig_name: str, plan: dict, *, face_object: str, foot_offset_z: float = 0.0, lid_open_deg: float = -80.0,
               lid_closed_deg: float = 90.0, brow_raise_m: float = 0.012, spaces: dict | None = None,
               clear: bool = True) -> dict:
    rig = bpy.data.objects[rig_name]
    P = rig.pose.bones
    spaces = {**DEFAULT_SPACES, **(spaces or {})}
    face = bpy.data.objects[face_object]
    if clear:
        if rig.animation_data:
            rig.animation_data_clear()
        if face.data.shape_keys and face.data.shape_keys.animation_data:
            face.data.shape_keys.animation_data_clear()
    rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    eases: dict[tuple[str, int], str] = {}
    nkeys = 0
    for key, seq in plan["channels"].items():
        ctl, attr = key.split("|")
        for frame, val, ease in seq:
            if ctl == "face":
                if attr == "blink":
                    for s in ("L", "R"):
                        pb = P.get(f"lid.{s}")
                        if pb:
                            pb.rotation_mode = "XYZ"
                            pb.rotation_euler = (math.radians(lid_open_deg + (lid_closed_deg - lid_open_deg) * val), 0, 0)
                            pb.keyframe_insert("rotation_euler", frame=frame, group="face")
                            eases[(f'pose.bones["lid.{s}"].rotation_euler', frame)] = ease
                elif attr == "brow_up":
                    for s in ("L", "R"):
                        pb = P.get(f"brow.{s}")
                        if pb:
                            pb.location = (0, brow_raise_m * val, 0)
                            pb.keyframe_insert("location", frame=frame, group="face")
                            eases[(f'pose.bones["brow.{s}"].location', frame)] = ease
                else:
                    kb = face.data.shape_keys.key_blocks.get(attr) if face.data.shape_keys else None
                    if kb:
                        kb.value = val
                        kb.keyframe_insert("value", frame=frame)
                nkeys += 1
                continue
            pb = P[ctl]
            space = spaces.get(ctl, "body_fk")
            if space == "root_world":
                pb.rotation_mode = "XYZ"
                if attr == "loc":
                    pb.location = Vector(val)
                    pb.keyframe_insert("location", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].location', frame)] = ease
                elif attr == "yaw":
                    pb.rotation_euler = (0, 0, math.radians(val))
                    pb.keyframe_insert("rotation_euler", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].rotation_euler', frame)] = ease
            elif space == "body_fk":
                pb.rotation_mode = "XYZ"
                if attr == "rot":
                    pb.rotation_euler = _body_euler(val)
                    pb.keyframe_insert("rotation_euler", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].rotation_euler', frame)] = ease
                elif attr == "loc":
                    dx, dy, dz = val
                    pb.location = (dx, dz, -dy)
                    pb.keyframe_insert("location", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].location', frame)] = ease
            elif space == "world_target":
                pb.rotation_mode = "QUATERNION"
                if attr == "loc":
                    t = Vector(val)
                    if ctl.startswith("ik_foot"):
                        t.z += foot_offset_z
                    m = pb.matrix.copy()
                    m.translation = t
                    pb.matrix = m
                    pb.keyframe_insert("location", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].location', frame)] = ease
                elif attr in ("rot", "yaw"):
                    r0 = rest[ctl].to_3x3()
                    if attr == "rot":
                        rw = Euler((math.radians(val[0]), 0, 0)).to_matrix() @ r0
                    else:
                        rw = Euler((0, 0, math.radians(val))).to_matrix() @ r0
                    m = rw.to_4x4()
                    m.translation = pb.matrix.translation
                    pb.matrix = m
                    pb.keyframe_insert("rotation_quaternion", frame=frame, group=ctl)
                    eases[(f'pose.bones["{ctl}"].rotation_quaternion', frame)] = ease
            nkeys += 1
    _apply_easing(rig, eases)
    if face.data.shape_keys and face.data.shape_keys.animation_data and face.data.shape_keys.animation_data.action:
        for fc in face.data.shape_keys.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation, kp.easing = "SINE", "EASE_IN_OUT"
    sc = bpy.context.scene
    sc.frame_start = min(min(f for f, _, _ in seq) for seq in plan["channels"].values())
    sc.frame_end = max(max(f for f, _, _ in seq) for seq in plan["channels"].values())
    return {"keys": nkeys, "frame_range": [sc.frame_start, sc.frame_end]}


def _apply_easing(rig, eases):
    act = rig.animation_data.action if rig.animation_data else None
    if not act:
        return
    for fc in act.fcurves:
        kps = sorted(fc.keyframe_points, key=lambda k: k.co.x)
        for prev, nxt in zip(kps, kps[1:]):
            ease = eases.get((fc.data_path, int(round(nxt.co.x))), "EASE_IN_OUT")
            if ease == "AUTO_CLAMPED":
                prev.interpolation = "BEZIER"
                prev.handle_right_type = nxt.handle_left_type = "AUTO_CLAMPED"
            else:
                prev.interpolation, prev.easing = "SINE", ease
