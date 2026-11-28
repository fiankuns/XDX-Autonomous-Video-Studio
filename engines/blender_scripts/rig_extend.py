"""XDX intelligent rig extension (Phase 02B.4) — extends an EXISTING accepted rig, never rebuilds the character.

Adds, from bone names in a rig profile:
- IK targets (world, unparented) for hands and feet copied from the hand/foot rest pose, pole targets, IK on the
  forearm/shin chains (chain 2) with the pole angle SOLVED per side (mirrored rolls need different angles), hands/feet
  follow their IK target rotation (Copy Rotation), IK influence = FK/IK switch;
- eye bones with Damped Track to one world ``eye_target`` (eye tracking), eyelid caps on lid bones (blink),
  brow bones (brow raise), face shape keys ``smile`` and ``mouth_open`` on the face mesh;
- a generic object-attachment helper (Child Of to a hand bone, inverse set at the contact frame).
Android-safe bpy only. Each public function runs well under the 3.5 s MCP budget.
"""
from __future__ import annotations

import math

import bpy  # type: ignore
import bmesh  # type: ignore
from mathutils import Matrix, Vector  # type: ignore


def _edit(rig):
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    return rig.data.edit_bones


def add_control_bones(rig_name: str, sides=("L", "R"), eye_centers=None, brow_centers=None, eye_height=1.4) -> list[str]:
    rig = bpy.data.objects[rig_name]
    eb = _edit(rig)
    made = []

    def new(name, head, tail, parent=None, roll=0.0, deform=False):
        b = eb.get(name) or eb.new(name)
        b.head, b.tail, b.roll, b.use_deform = head, tail, roll, deform
        b.parent = eb[parent] if parent else None
        made.append(name)
        return b

    for s in sides:
        h, f = eb[f"hand.{s}"], eb[f"foot.{s}"]
        new(f"ik_hand.{s}", h.head.copy(), h.tail.copy(), roll=h.roll)
        new(f"ik_foot.{s}", f.head.copy(), f.tail.copy(), roll=f.roll)
        el, kn = eb[f"forearm.{s}"].head.copy(), eb[f"shin.{s}"].head.copy()
        sx = 1 if el.x > 0 else -1
        # poles are children of the root so elbows/knees keep their bend direction while the character travels
        new(f"pole_arm.{s}", el + Vector((sx * 0.1, 0.4, 0)), el + Vector((sx * 0.1, 0.45, 0)), parent="root")
        new(f"pole_leg.{s}", kn + Vector((0, -0.5, 0)), kn + Vector((0, -0.55, 0)), parent="root")
    new("eye_target", Vector((0, -2.0, eye_height)), Vector((0, -2.0, eye_height + 0.05)))
    for s, c in (eye_centers or {}).items():
        c = Vector(c)
        new(f"eye.{s}", c, c + Vector((0, -0.03, 0)), parent="head")
        new(f"lid.{s}", c, c + Vector((0, -0.03, 0)), parent="head")
    for s, c in (brow_centers or {}).items():
        c = Vector(c)
        new(f"brow.{s}", c, c + Vector((0, 0, 0.02)), parent="head")
    bpy.ops.object.mode_set(mode="OBJECT")
    return made


def add_ik(rig_name: str, sides=("L", "R")) -> dict:
    """IK on forearm/shin, solve pole angle so the elbow/knee stays in the plane through its pole at rest."""
    rig = bpy.data.objects[rig_name]
    P = rig.pose.bones
    out = {}
    for s in sides:
        for chain, tgt, pole, ref in ((f"forearm.{s}", f"ik_hand.{s}", f"pole_arm.{s}", f"upper_arm.{s}"),
                                      (f"shin.{s}", f"ik_foot.{s}", f"pole_leg.{s}", f"thigh.{s}")):
            pb = P[chain]
            for c in list(pb.constraints):
                if c.type == "IK":
                    pb.constraints.remove(c)
            c = pb.constraints.new("IK")
            c.target, c.subtarget, c.pole_target, c.pole_subtarget, c.chain_count = rig, tgt, rig, pole, 2
            rest_mid = rig.data.bones[ref].tail_local.copy()
            best = None
            # coarse-to-fine sweep (a 5-degree full sweep took 9.4 s on the phone; this needs ~1/4 of the updates)
            for a in list(range(-180, 180, 30)):
                c.pole_angle = math.radians(a)
                bpy.context.view_layer.update()
                d = (P[ref].tail - rest_mid).length
                if best is None or d < best[0]:
                    best = (d, a)
            for a in range(best[1] - 25, best[1] + 26, 5):
                c.pole_angle = math.radians(a)
                bpy.context.view_layer.update()
                d = (P[ref].tail - rest_mid).length
                if d < best[0]:
                    best = (d, a)
            c.pole_angle = math.radians(best[1])
            out[chain] = {"pole_angle_deg": best[1], "rest_error_m": round(best[0], 5)}
        for bone, tgt in ((f"hand.{s}", f"ik_hand.{s}"), (f"foot.{s}", f"ik_foot.{s}")):
            pb = P[bone]
            for c in list(pb.constraints):
                if c.type == "COPY_ROTATION":
                    pb.constraints.remove(c)
            c = pb.constraints.new("COPY_ROTATION")
            c.target, c.subtarget = rig, tgt
    bpy.context.view_layer.update()
    return out


def add_eye_tracking(rig_name: str, sides=("L", "R")):
    rig = bpy.data.objects[rig_name]
    for s in sides:
        pb = rig.pose.bones[f"eye.{s}"]
        for c in list(pb.constraints):
            pb.constraints.remove(c)
        c = pb.constraints.new("DAMPED_TRACK")
        c.target, c.subtarget, c.track_axis = rig, "eye_target", "TRACK_Y"


def reparent_to_bone(obj_names, rig_name, bone):
    rig = bpy.data.objects[rig_name]
    vl = bpy.context.view_layer
    for n in obj_names:
        o = bpy.data.objects[n]
        mw = o.matrix_world.copy()
        o.parent, o.parent_type, o.parent_bone = rig, "BONE", bone
        vl.update()
        o.matrix_world = mw


def make_eyelid(name, rig_name, side, center, radius, material, open_deg=80.0):
    """Upper-hemisphere skin cap on the lid bone (lid bone points -Y, so its local X is world -X):
    rotation X = +80 deg hides the cap behind the eye (open), -90 deg covers the front (closed).
    Radius must exceed the iris/pupil/glint protrusion (Bima: 1.15 x eyeball radius)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=radius)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z < -1e-6], context="FACES")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material)
    rig = bpy.data.objects[rig_name]
    rig.pose.bones[f"lid.{side}"].rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    o.matrix_world = Matrix.Translation(center)
    bpy.context.view_layer.update()          # matrix_world must be current before re-parenting
    reparent_to_bone([name], rig_name, f"lid.{side}")
    rig = bpy.data.objects[rig_name]
    pb = rig.pose.bones[f"lid.{side}"]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(open_deg), 0, 0)
    return o


def add_face_shape_keys(face_name: str, smile_material: str, mouth_center, cheek_centers):
    """smile: corners up/out + cheeks lifted; mouth_open: lower the smile centre into a small 'o' (drinking)."""
    o = bpy.data.objects[face_name]
    me = o.data
    if not me.shape_keys:
        o.shape_key_add(name="Basis")
    mats = [m.name for m in me.materials]
    smile_idx = mats.index(smile_material)
    smile_verts = {v for p in me.polygons if p.material_index == smile_idx for v in p.vertices}
    mc = Vector(mouth_center)
    for kname in ("smile", "mouth_open"):
        k = me.shape_keys.key_blocks.get(kname) or o.shape_key_add(name=kname)
        for i, v in enumerate(me.vertices):
            co = v.co.copy()
            w = o.matrix_world @ co
            if kname == "smile":
                if i in smile_verts:
                    t = (w.x - mc.x) / 0.035
                    co.z += 0.004 * t * t
                    co.x += 0.002 * t
                for cc in cheek_centers:
                    d = (w - Vector(cc)).length
                    if d < 0.04 and w.y < -0.02:
                        co.z += 0.003 * (1 - d / 0.04)
            else:
                if i in smile_verts:
                    t = abs(w.x - mc.x) / 0.035
                    co.z -= 0.004 * max(0.0, 1 - t)
                    co.x -= (w.x - mc.x) * 0.25
            k.data[i].co = co
    return [kb.name for kb in me.shape_keys.key_blocks]


def attach_child_of(obj_name, rig_name, bone, frame, detach_frame=None, detach_world_location=None):
    """Object follows the hand from ``frame``; at ``detach_frame`` it is released and keyed at its world pose,
    snapped to ``detach_world_location`` (the support surface) so it never floats or sinks after the release."""
    o = bpy.data.objects[obj_name]
    rig = bpy.data.objects[rig_name]
    sc = bpy.context.scene
    for c in list(o.constraints):
        if c.type == "CHILD_OF":
            o.constraints.remove(c)
    c = o.constraints.new("CHILD_OF")
    c.target, c.subtarget = rig, bone
    sc.frame_set(frame)
    bm = rig.matrix_world @ rig.pose.bones[bone].matrix
    c.inverse_matrix = bm.inverted()
    c.influence = 0.0
    c.keyframe_insert("influence", frame=frame - 1)
    c.influence = 1.0
    c.keyframe_insert("influence", frame=frame)
    o.keyframe_insert("location", frame=frame - 1)
    o.keyframe_insert("rotation_euler", frame=frame - 1)
    if detach_frame:
        sc.frame_set(detach_frame)
        world = o.matrix_world.copy()
        c.keyframe_insert("influence", frame=detach_frame - 1)
        c.influence = 0.0
        c.keyframe_insert("influence", frame=detach_frame)
        loc, rot, _ = world.decompose()
        if detach_world_location is not None:
            loc = Vector(detach_world_location)
            rot = rot.to_euler()
            rot = type(rot)((0.0, 0.0, rot.z)).to_quaternion()   # upright on the surface, keep its heading
        o.location = loc
        o.rotation_euler = rot.to_euler()
        o.keyframe_insert("location", frame=detach_frame)
        o.keyframe_insert("rotation_euler", frame=detach_frame)
    from action_executor import action_fcurves  # noqa: E402  (same folder / sys.modules)
    for fc in action_fcurves(o):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    return {"object": obj_name, "attach": frame, "detach": detach_frame}
