"""XDX Character Action Compiler (Phase 02B.4) — engine-agnostic, character-agnostic.

Input: a rig profile (semantic controls -> rig control names + body measurements), a scene description (objects with
named sockets), and an ordered list of action requests. Output: validated ActionSpecs (actor, target object, initial /
key / final poses, contact point, timing, IK target, acceptance criteria) and a compiled channel plan
(control -> [(frame, value, easing)]) plus constraint events (attach / detach) that an engine executor applies.

Natural-animation principles are produced by the recipes, not by generic torso/hand rotation:
anticipation (counter-move before the main move), weight transfer (hips over the support foot), foot planting
(a planted foot's IK target is constant in world space), easing per key, overlapping action (head/eyes lead or lag the
body by a few frames), follow-through/overshoot, secondary motion (breathing, head bob), continuity (each action
starts exactly from the previous action's final pose) and balance (hips stay between the feet).

Coordinates: world metres, Z up. Angles in degrees as (pitch, roll, yaw) in the body frame: pitch > 0 = bend /
nod FORWARD (look down), yaw > 0 = turn towards +X when facing -Y. Face values 0..1.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

ACTION_TYPES = ("idle", "look_at", "walk", "turn", "sit", "stand", "reach", "grasp", "hold", "lift", "drink", "place",
                "release", "facial_reaction")
OBJECT_ACTIONS = {"reach", "grasp", "hold", "lift", "drink", "place", "release", "look_at", "sit"}
REQUIRED_FIELDS = ("action_id", "action_type", "actor", "target_object", "start_frame", "end_frame", "initial_pose",
                   "key_poses", "final_pose", "contact_point", "timing", "ik_target", "acceptance_criteria")


class ActionCompileError(ValueError):
    pass


# ------------------------------------------------------------------ rig profile / scene
@dataclass
class RigProfile:
    actor: str
    controls: dict[str, str]                 # semantic -> rig control name
    shoulder_height: float
    hip_height: float
    arm_reach: float
    hip_width: float
    eye_height: float
    mouth_offset: tuple[float, float, float]  # mouth socket relative to the head control (world, facing -Y)
    stride: float = 0.33
    hand_rest_offset: dict[str, tuple[float, float, float]] = field(default_factory=dict)  # side -> rel. to root

    def ctl(self, key: str) -> str:
        if key not in self.controls:
            raise ActionCompileError(f"rig profile for {self.actor} has no control '{key}'")
        return self.controls[key]


@dataclass
class SceneObject:
    object_id: str
    location: tuple[float, float, float]
    sockets: dict[str, tuple[float, float, float]]   # relative to location
    kind: str = "prop"

    def socket(self, name: str) -> tuple[float, float, float]:
        if name not in self.sockets:
            raise ActionCompileError(f"object '{self.object_id}' has no socket '{name}'")
        return _add(self.location, self.sockets[name])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _len(a):
    return math.sqrt(sum(x * x for x in a))


def _yaw_to(src, dst):
    """Heading (deg) so a character facing -Y at yaw 0 faces from src to dst."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    return math.degrees(math.atan2(dx, -dy))


def _rot(v, yaw_deg):
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


# ------------------------------------------------------------------ pose state
def rest_pose(rig: RigProfile, root=(0.0, 0.0, 0.0), yaw=0.0) -> dict[str, Any]:
    """Full pose: every control has a value, so continuity can be checked exactly."""
    p: dict[str, Any] = {
        "root": {"loc": root, "yaw": yaw},
        "hips": {"loc": (0.0, 0.0, 0.0), "rot": (0.0, 0.0, 0.0)},
        "spine": {"rot": (0.0, 0.0, 0.0)}, "chest": {"rot": (0.0, 0.0, 0.0)},
        "neck": {"rot": (0.0, 0.0, 0.0)}, "head": {"rot": (0.0, 0.0, 0.0)},
        "eye_target": {"loc": _add(root, _rot((0.0, -2.0, rig.eye_height), yaw))},
        "face": {"blink": 0.0, "smile": 0.3, "brow_up": 0.0, "mouth_open": 0.0},
        "attach": {"L": None, "R": None},
    }
    for side, sx in (("L", -1), ("R", 1)):
        p[f"foot_ik.{side}"] = {"loc": _add(root, _rot((sx * rig.hip_width, 0.0, 0.0), yaw)), "yaw": yaw}
        off = rig.hand_rest_offset.get(side, (sx * 0.26, -0.04, 0.86))
        p[f"hand_ik.{side}"] = {"loc": _add(root, _rot(off, yaw)), "rot": (0.0, 0.0, 0.0)}
    return p


def _poses_equal(a: dict, b: dict, tol=1e-6) -> list[str]:
    bad = []
    for k in a:
        if k not in b:
            bad.append(k)
            continue
        va, vb = a[k], b[k]
        if isinstance(va, dict):
            for kk in va:
                x, y = va[kk], vb.get(kk)
                if isinstance(x, (tuple, list)) and isinstance(y, (tuple, list)):
                    if any(abs(i - j) > tol for i, j in zip(x, y)):
                        bad.append(f"{k}.{kk}")
                elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    if abs(x - y) > tol:
                        bad.append(f"{k}.{kk}")
                elif x != y:
                    bad.append(f"{k}.{kk}")
    return bad


# ------------------------------------------------------------------ recipes
class _Builder:
    def __init__(self, start: int, pose: dict):
        self.start = start
        self.pose = copy.deepcopy(pose)
        self.keys: list[dict[str, Any]] = [{"frame": start, "pose": copy.deepcopy(pose), "principle": "hold_from_previous",
                                            "ease": "AUTO_CLAMPED"}]

    def key(self, frame: int, principle: str, ease: str = "EASE_IN_OUT", **changes):
        for path, val in changes.items():
            ctl, _, attr = path.partition("__")
            ctl = ctl.replace("_dot_", ".")
            self.pose.setdefault(ctl, {})[attr] = val
        self.keys.append({"frame": frame, "pose": copy.deepcopy(self.pose), "principle": principle, "ease": ease})


def recipe_look_at(rig, scene, req, pose, b: _Builder):
    tgt = scene[req["target_object"]].socket(req.get("socket", "look"))
    s, e = req["start_frame"], req["end_frame"]
    d = e - s
    yaw = pose["root"]["yaw"]
    head_yaw = max(-35.0, min(35.0, _yaw_to(pose["root"]["loc"], tgt) - yaw))
    # eyes lead (overlap), head follows 3-4 f later with a small overshoot, then settles; blink on the turn.
    b.key(s + 2, "anticipation_blink", face__blink=1.0)
    b.key(s + 4, "eyes_lead", eye_target__loc=tgt, face__blink=0.0)
    b.key(s + 10, "head_follows_overlap", "EASE_OUT", head__rot=(10.0, 0.0, head_yaw * 1.08), neck__rot=(4.0, 0.0, head_yaw * 0.25))
    b.key(s + 16, "settle_follow_through", head__rot=(8.0, 0.0, head_yaw), chest__rot=(0.0, 0.0, head_yaw * 0.12))
    b.key(s + int(d * 0.75), "breathing_secondary", "EASE_IN_OUT", chest__rot=(1.2, 0.0, head_yaw * 0.12))
    b.key(e, "breathing_secondary", chest__rot=(0.0, 0.0, head_yaw * 0.12))
    return {"contact_point": f"gaze:{req['target_object']}:{req.get('socket', 'look')}", "ik_target": rig.ctl("eye_target")}


def recipe_walk(rig, scene, req, pose, b: _Builder):
    """Stance/swing cycle with planted feet, hips over the support foot, bob, arm counter-swing."""
    s, e = req["start_frame"], req["end_frame"]
    goal_obj = scene[req["target_object"]]
    stop = goal_obj.socket(req.get("socket", "stand_spot"))
    start = pose["root"]["loc"]
    yaw = _yaw_to(start, stop)
    dist = _len(_sub((stop[0], stop[1], 0), (start[0], start[1], 0)))
    n_steps = max(2, math.ceil(dist / rig.stride))
    step = dist / n_steps
    fwd = _rot((0.0, -1.0, 0.0), yaw)
    seg = (e - s - 4) / (n_steps + 0.6)   # 4 f anticipation, then n steps + a short closing step
    b.key(s + 4, "anticipation_weight_shift", "EASE_OUT",
          hips__loc=(0.02, 0.0, -0.015), spine__rot=(-3.0, 0.0, 0.0), root__yaw=yaw)
    feet = {"L": pose["foot_ik.L"]["loc"], "R": pose["foot_ik.R"]["loc"]}
    lateral = {"L": _rot((-rig.hip_width, 0, 0), yaw), "R": _rot((rig.hip_width, 0, 0), yaw)}
    swing = "L"
    t0 = s + 4
    for i in range(n_steps):
        travelled = step * (i + 1)
        body = _add(start, _scale(fwd, travelled))
        land = _add(body, lateral[swing])
        land = (land[0], land[1], 0.0)
        support = "R" if swing == "L" else "L"
        f_pass, f_land = int(t0 + seg * (i + 0.5)), int(t0 + seg * (i + 1))
        mid = _lerp(feet[swing], land, 0.5)
        hip_x = 0.025 if support == "R" else -0.025
        pass_root = _add(start, _scale(fwd, travelled - step * 0.5))
        arms = {}
        for hs in ("L", "R"):
            if pose["attach"].get(hs) is None:
                sx = -1 if hs == "L" else 1
                off = rig.hand_rest_offset.get(hs, (sx * 0.26, -0.04, 0.86))
                sw = 0.06 if hs == swing else -0.06          # arm opposite to the swinging leg swings forward
                arms[f"hand_ik_dot_{hs}__loc"] = _add(pass_root, _rot(_add(off, (0.0, sw, 0.01)), yaw))
        # passing pose: swing foot lifted, body up (bob), arms counter-swing; support foot stays planted
        b.key(f_pass, f"passing_{swing}_support_{support}_planted", "EASE_IN_OUT",
              **{f"foot_ik_dot_{swing}__loc": (mid[0], mid[1], 0.06), "root__loc": pass_root,
                 "hips__loc": (hip_x, 0.0, -0.006), "chest__rot": (2.0, 0.0, 6.0 if swing == "L" else -6.0)}, **arms)
        arms_land = {}
        for hs in ("L", "R"):
            if pose["attach"].get(hs) is None:
                sx = -1 if hs == "L" else 1
                off = rig.hand_rest_offset.get(hs, (sx * 0.26, -0.04, 0.86))
                arms_land[f"hand_ik_dot_{hs}__loc"] = _add(body, _rot(off, yaw))
        feet[swing] = land
        b.key(f_land, f"contact_{swing}_heel_strike_weight_transfer", "EASE_OUT",
              # hips drop at heel strike so the extended leg can reach its target (leg-length aware stride)
              **{f"foot_ik_dot_{swing}__loc": land, "root__loc": body, "hips__loc": (0.0, 0.0, -0.03),
                 "chest__rot": (0.0, 0.0, 0.0)}, **arms_land)
        swing = support
    # closing step: the trailing foot is LIFTED and placed level with the leading foot (never slid), hips recentre
    final_root = _add(start, _scale(fwd, dist))
    close = (lambda p: (p[0], p[1], 0.0))(_add(final_root, lateral[swing]))
    f_pass = int(t0 + seg * (n_steps + 0.25))
    mid = _lerp(feet[swing], close, 0.5)
    b.key(f_pass, f"closing_step_passing_{swing}_support_{'R' if swing == 'L' else 'L'}_planted", "EASE_IN_OUT",
          **{f"foot_ik_dot_{swing}__loc": (mid[0], mid[1], 0.04), "hips__loc": (0.02 if swing == "L" else -0.02, 0.0, 0.006)})
    feet[swing] = close
    b.key(e - 2, "settle_overshoot_follow_through", "EASE_OUT",
          **{f"foot_ik_dot_{swing}__loc": close, "hips__loc": (0.0, -0.01, -0.008), "root__loc": final_root})
    b.key(e, "settle_balance", hips__loc=(0.0, 0.0, 0.0), spine__rot=(0.0, 0.0, 0.0),
          **{"foot_ik_dot_L__yaw": yaw, "foot_ik_dot_R__yaw": yaw})
    return {"contact_point": f"floor:{req['target_object']}:{req.get('socket', 'stand_spot')}", "ik_target": rig.ctl("foot_ik.L") + "," + rig.ctl("foot_ik.R")}


def recipe_reach_grasp(rig, scene, req, pose, b: _Builder):
    """Anticipation (small pull back), lean with hips back for balance, hand arc to pre-grasp, contact, attach."""
    s, e = req["start_frame"], req["end_frame"]
    side = req.get("hand", "R")
    obj = scene[req["target_object"]]
    grip = obj.socket(req.get("socket", "grip"))
    hand = f"hand_ik.{side}"
    approach = _add(grip, (0.0, 0.06, 0.04))          # come from above/behind the glass (towards the actor)
    head_yaw = pose["head"]["rot"][2]
    d = e - s
    contact = s + int(d * 0.7)
    b.key(s + int(d * 0.15), "anticipation_pullback", "EASE_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(pose[hand]["loc"], (0.0, 0.03, 0.02)), "chest__rot": (-2.0, 0.0, 0.0)})
    b.key(s + int(d * 0.5), "reach_arc_lean_hips_back_balance", "EASE_IN_OUT",
          **{f"hand_ik_dot_{side}__loc": approach, "spine__rot": (14.0, 0.0, 0.0), "chest__rot": (10.0, 0.0, 0.0),
             "hips__loc": (0.0, 0.03, -0.02), "head__rot": (14.0, 0.0, head_yaw * 0.5)})
    b.key(contact, "contact_ease_in", "EASE_IN", **{f"hand_ik_dot_{side}__loc": grip, f"hand_ik_dot_{side}__rot": (0.0, 0.0, 0.0)})
    b.pose["attach"][side] = req["target_object"]
    b.keys[-1]["pose"]["attach"] = dict(b.pose["attach"])
    b.key(e, "grasp_settle", **{"spine__rot": (12.0, 0.0, 0.0)})
    return {"contact_point": f"{req['target_object']}:{req.get('socket', 'grip')}", "ik_target": rig.ctl(hand),
            "contact_frame": contact, "attach": {"frame": contact, "hand": side, "object": req["target_object"]}}


def recipe_lift_drink(rig, scene, req, pose, b: _Builder):
    """Lift with weight back onto heels, bring rim to the mouth, head tilts back, eyes close, swallow, lower."""
    s, e = req["start_frame"], req["end_frame"]
    side = req.get("hand", "R")
    hand = f"hand_ik.{side}"
    if pose["attach"][side] != req["target_object"]:
        raise ActionCompileError(f"{req['action_id']}: drink requires '{req['target_object']}' held in hand {side}")
    root, yaw = pose["root"]["loc"], pose["root"]["yaw"]
    mouth = _add(root, _rot(rig.mouth_offset, yaw))
    obj = scene[req["target_object"]]
    rim_to_grip = _sub(obj.sockets[req.get("socket", "grip")], obj.sockets.get("rim", obj.sockets[req.get("socket", "grip")]))
    # the rim front edge meets the lips: glass centre sits one glass radius in front of the mouth (never inside the face)
    radius = obj.sockets.get("radius", (0.035, 0.0, 0.0))[0]
    hand_at_mouth = _add(_add(mouth, _rot((0.0, -radius - 0.008, 0.0), yaw)), rim_to_grip)
    d = e - s
    lifted = _add(pose[hand]["loc"], (0.0, 0.06, 0.16))
    b.key(s + int(d * 0.08), "anticipation_dip_before_lift", "EASE_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(pose[hand]["loc"], (0.0, 0.0, -0.012)), "hips__loc": (0.0, 0.03, -0.028)})
    b.key(s + int(d * 0.2), "lift_weight_back_onto_heels", "EASE_OUT",
          **{f"hand_ik_dot_{side}__loc": lifted, "spine__rot": (0.0, 0.0, 0.0), "chest__rot": (0.0, 0.0, 0.0),
             "hips__loc": (0.0, 0.0, 0.0), "head__rot": (4.0, 0.0, 0.0), "neck__rot": (0.0, 0.0, 0.0)})
    b.key(s + int(d * 0.4), "rim_to_mouth_contact", "EASE_IN_OUT",
          **{f"hand_ik_dot_{side}__loc": hand_at_mouth, f"hand_ik_dot_{side}__rot": (-35.0, 0.0, 0.0),
             "head__rot": (-8.0, 0.0, 0.0), "face__mouth_open": 0.2})
    b.key(s + int(d * 0.55), "drink_tilt_eyes_close", "EASE_IN_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(hand_at_mouth, (0.0, 0.0, 0.015)), f"hand_ik_dot_{side}__rot": (-60.0, 0.0, 0.0),
             "head__rot": (-18.0, 0.0, 0.0), "neck__rot": (-6.0, 0.0, 0.0), "face__blink": 1.0, "chest__rot": (-3.0, 0.0, 0.0)})
    b.key(s + int(d * 0.75), "swallow_secondary", **{"face__blink": 1.0, "neck__rot": (-4.0, 0.0, 0.0)})
    b.key(e, "lower_follow_through", "EASE_OUT",
          **{f"hand_ik_dot_{side}__loc": lifted, f"hand_ik_dot_{side}__rot": (0.0, 0.0, 0.0), "head__rot": (6.0, 0.0, 0.0),
             "neck__rot": (0.0, 0.0, 0.0), "chest__rot": (0.0, 0.0, 0.0), "face__blink": 0.0, "face__mouth_open": 0.0})
    return {"contact_point": f"{req['target_object']}:rim->mouth", "ik_target": rig.ctl(hand)}


def recipe_place_release(rig, scene, req, pose, b: _Builder):
    s, e = req["start_frame"], req["end_frame"]
    side = req.get("hand", "R")
    hand = f"hand_ik.{side}"
    obj = scene[req["target_object"]]
    surface = scene[req["surface"]].socket(req.get("surface_socket", "place_spot"))
    grip_off = obj.sockets[req.get("socket", "grip")]
    hand_on = _add(surface, grip_off)
    d = e - s
    contact = s + int(d * 0.5)
    b.key(s + int(d * 0.12), "anticipation_small_rise", "EASE_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(pose[hand]["loc"], (0.0, -0.02, 0.02))})
    b.key(s + int(d * 0.3), "lower_with_lean", "EASE_IN_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(hand_on, (0.0, 0.0, 0.05)), "spine__rot": (16.0, 0.0, 0.0),
             "chest__rot": (8.0, 0.0, 0.0), "hips__loc": (0.0, 0.035, -0.025)})
    b.key(contact, "set_down_contact_ease_in", "EASE_IN", **{f"hand_ik_dot_{side}__loc": hand_on, "spine__rot": (18.0, 0.0, 0.0)})
    b.pose["attach"][side] = None
    b.keys[-1]["pose"]["attach"] = dict(b.pose["attach"])
    rest = rig.hand_rest_offset.get(side, (0.26, -0.04, 0.86))
    b.key(contact + 6, "release_lift_off", "EASE_OUT", **{f"hand_ik_dot_{side}__loc": _add(hand_on, (0.0, 0.05, 0.05))})
    b.key(e, "recover_upright_balance", "EASE_IN_OUT",
          **{f"hand_ik_dot_{side}__loc": _add(pose["root"]["loc"], _rot(rest, pose["root"]["yaw"])),
             "spine__rot": (0.0, 0.0, 0.0), "chest__rot": (0.0, 0.0, 0.0), "hips__loc": (0.0, 0.0, 0.0)})
    return {"contact_point": f"{req['surface']}:{req.get('surface_socket', 'place_spot')}", "ik_target": rig.ctl(hand),
            "contact_frame": contact, "detach": {"frame": contact, "hand": side, "object": req["target_object"],
                                                 "world_location": surface}}


def recipe_facial_reaction(rig, scene, req, pose, b: _Builder):
    s, e = req["start_frame"], req["end_frame"]
    d = e - s
    kind = req.get("reaction", "satisfied")
    look = req.get("look_at_camera_point")
    if look:
        b.key(s + 2, "eyes_lead_to_camera", eye_target__loc=tuple(look))
    b.key(s + int(d * 0.25), "anticipation_squash", "EASE_OUT", face__brow_up=0.0, face__smile=0.2, head__rot=(4.0, 0.0, 0.0))
    b.key(s + int(d * 0.45), f"{kind}_peak_overshoot", "EASE_OUT", face__smile=1.0, face__brow_up=0.8,
          head__rot=(-6.0, 0.0, 5.0), chest__rot=(-3.0, 0.0, 0.0))
    b.key(s + int(d * 0.6), "blink_secondary", face__blink=1.0)
    b.key(s + int(d * 0.66), "blink_secondary", face__blink=0.0)
    b.key(e, f"{kind}_settle_follow_through", face__smile=0.8, face__brow_up=0.3, head__rot=(-3.0, 0.0, 3.0),
          chest__rot=(0.0, 0.0, 0.0))
    return {"contact_point": "none:facial_only", "ik_target": rig.ctl("eye_target")}


def recipe_idle(rig, scene, req, pose, b: _Builder):
    s, e = req["start_frame"], req["end_frame"]
    period = 48
    f = s
    i = 0
    while f + period // 2 <= e:
        f += period // 2
        b.key(f, "breathing_inhale" if i % 2 == 0 else "breathing_exhale",
              chest__rot=(1.2 if i % 2 == 0 else 0.0, 0.0, pose["chest"]["rot"][2]),
              hips__loc=(0.0, 0.0, 0.004 if i % 2 == 0 else 0.0))
        i += 1
    return {"contact_point": "floor:planted_feet", "ik_target": rig.ctl("foot_ik.L") + "," + rig.ctl("foot_ik.R")}


RECIPES = {"look_at": recipe_look_at, "walk": recipe_walk, "reach": recipe_reach_grasp, "grasp": recipe_reach_grasp,
           "lift": recipe_lift_drink, "drink": recipe_lift_drink, "place": recipe_place_release,
           "release": recipe_place_release, "facial_reaction": recipe_facial_reaction, "idle": recipe_idle}
# turn/sit/stand/hold share the same contract and are compiled through the generic recipes below.


def recipe_turn(rig, scene, req, pose, b):
    s, e = req["start_frame"], req["end_frame"]
    tgt = scene[req["target_object"]].socket(req.get("socket", "look"))
    yaw = _yaw_to(pose["root"]["loc"], tgt)
    d = e - s
    b.key(s + int(d * 0.2), "head_leads_turn", head__rot=(0.0, 0.0, max(-35, min(35, yaw - pose["root"]["yaw"]))))
    feet = {k: pose[f"foot_ik.{k}"]["loc"] for k in ("L", "R")}
    root = pose["root"]["loc"]
    for i, side in enumerate(("L", "R")):
        sx = -1 if side == "L" else 1
        land = _add(root, _rot((sx * rig.hip_width, 0, 0), yaw))
        b.key(s + int(d * (0.45 + 0.25 * i)), f"pivot_step_{side}", **{f"foot_ik_dot_{side}__loc": (land[0], land[1], 0.0),
              f"foot_ik_dot_{side}__yaw": yaw, "root__yaw": yaw if i else (pose["root"]["yaw"] + yaw) / 2})
    b.key(e, "turn_settle", head__rot=(0.0, 0.0, 0.0), root__yaw=yaw)
    return {"contact_point": "floor:pivot", "ik_target": rig.ctl("foot_ik.L") + "," + rig.ctl("foot_ik.R")}


def recipe_sit(rig, scene, req, pose, b):
    s, e = req["start_frame"], req["end_frame"]
    seat = scene[req["target_object"]].socket(req.get("socket", "seat"))
    d = e - s
    drop = rig.hip_height - seat[2]
    b.key(s + int(d * 0.3), "anticipation_lean_forward", spine__rot=(18.0, 0.0, 0.0), hips__loc=(0.0, 0.02, -0.05))
    b.key(s + int(d * 0.8), "lower_onto_seat_contact", "EASE_IN", hips__loc=(0.0, seat[1] - pose["root"]["loc"][1], -drop),
          spine__rot=(10.0, 0.0, 0.0))
    b.key(e, "settle_upright", spine__rot=(0.0, 0.0, 0.0))
    return {"contact_point": f"{req['target_object']}:seat", "ik_target": rig.ctl("hips")}


def recipe_stand(rig, scene, req, pose, b):
    s, e = req["start_frame"], req["end_frame"]
    d = e - s
    b.key(s + int(d * 0.3), "anticipation_lean_forward_over_feet", spine__rot=(22.0, 0.0, 0.0))
    b.key(s + int(d * 0.75), "push_up_overshoot", "EASE_OUT", hips__loc=(0.0, 0.0, 0.01), spine__rot=(-2.0, 0.0, 0.0))
    b.key(e, "settle_balance", hips__loc=(0.0, 0.0, 0.0), spine__rot=(0.0, 0.0, 0.0))
    return {"contact_point": "floor:planted_feet", "ik_target": rig.ctl("hips")}


def recipe_hold(rig, scene, req, pose, b):
    side = req.get("hand", "R")
    if pose["attach"][side] != req["target_object"]:
        raise ActionCompileError(f"{req['action_id']}: hold requires '{req['target_object']}' attached to hand {side}")
    s, e = req["start_frame"], req["end_frame"]
    hand = f"hand_ik.{side}"
    b.key((s + e) // 2, "hold_secondary_sway", **{f"hand_ik_dot_{side}__loc": _add(pose[hand]["loc"], (0.0, 0.0, 0.008))})
    b.key(e, "hold_settle", **{f"hand_ik_dot_{side}__loc": pose[hand]["loc"]})
    return {"contact_point": f"{req['target_object']}:grip", "ik_target": rig.ctl(hand)}


RECIPES.update({"turn": recipe_turn, "sit": recipe_sit, "stand": recipe_stand, "hold": recipe_hold})


# ------------------------------------------------------------------ acceptance criteria
def _criteria(atype: str, req: dict, extra: dict) -> list[dict[str, Any]]:
    c = [{"id": "continuity", "rule": "initial pose equals previous final pose", "tolerance": 0.0},
         {"id": "no_mesh_explosion", "rule": "max deformed-vertex displacement per frame <= 0.08 m"}]
    if atype in ("walk", "turn", "idle", "look_at", "reach", "grasp", "lift", "drink", "place", "release", "facial_reaction", "hold"):
        c.append({"id": "foot_sliding", "rule": "planted foot world drift <= 0.01 m during stance", "metric": "m", "max": 0.01})
    if atype in ("reach", "grasp", "lift", "drink", "place", "release", "hold"):
        c.append({"id": "hand_object_contact", "rule": "hand grip socket within 0.02 m of object grip while attached",
                  "metric": "m", "max": 0.02})
        c.append({"id": "object_penetration", "rule": "object never below its support surface by > 0.005 m", "max": 0.005})
    if atype in ("drink",):
        c.append({"id": "rim_to_mouth", "rule": "object rim within 0.04 m of mouth at the drink key", "max": 0.04})
    if atype in ("walk",):
        c.append({"id": "arrival", "rule": "root ends within 0.03 m of the stand spot", "max": 0.03})
    if atype in ("look_at", "facial_reaction"):
        c.append({"id": "gaze", "rule": "eye target on the target socket at the settle key", "max": 0.01})
    c.append({"id": "balance", "rule": "hips XY stays inside the feet support polygon (+0.05 m margin)"})
    return c


# ------------------------------------------------------------------ compiler
def compile_actions(rig: RigProfile, scene_objects: list[SceneObject], requests: list[dict[str, Any]],
                    initial_pose: dict | None = None) -> dict[str, Any]:
    scene = {o.object_id: o for o in scene_objects}
    pose = copy.deepcopy(initial_pose) if initial_pose else rest_pose(rig)
    specs: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    prev_end = None
    for req in requests:
        atype = req.get("action_type")
        if atype not in RECIPES:
            raise ActionCompileError(f"unsupported action_type '{atype}'")
        actor = req.get("actor")
        if actor != rig.actor:
            raise ActionCompileError(f"{req.get('action_id')}: actor '{actor}' does not match rig '{rig.actor}'")
        tgt = req.get("target_object")
        if not tgt:
            raise ActionCompileError(f"{req.get('action_id')}: target_object is required")
        if tgt == actor or str(tgt).startswith(actor + ".") or str(tgt).startswith(actor + ":"):
            raise ActionCompileError(f"{req.get('action_id')}: actor '{actor}' cannot be its own target object")
        if tgt not in scene and not str(tgt).startswith("camera"):
            raise ActionCompileError(f"{req.get('action_id')}: target object '{tgt}' is not in the scene")
        s, e = int(req["start_frame"]), int(req["end_frame"])
        if e - s < 8:
            raise ActionCompileError(f"{req['action_id']}: action shorter than 8 frames")
        if prev_end is not None and s != prev_end:
            raise ActionCompileError(f"{req['action_id']}: starts at {s} but previous action ended at {prev_end} (gap/overlap)")
        initial = copy.deepcopy(pose)
        b = _Builder(s, pose)
        extra = RECIPES[atype](rig, scene, req, pose, b)
        if b.keys[-1]["frame"] != e:
            b.key(e, "hold_to_end")
        pose = copy.deepcopy(b.pose)
        spec = {"action_id": req["action_id"], "action_type": atype, "actor": actor, "target_object": tgt,
                "start_frame": s, "end_frame": e, "initial_pose": initial,
                "key_poses": [{"frame": k["frame"], "principle": k["principle"], "ease": k["ease"]} for k in b.keys[1:]],
                "final_pose": copy.deepcopy(pose), "contact_point": extra["contact_point"], "ik_target": extra["ik_target"],
                "timing": {"frames": e - s, "contact_frame": extra.get("contact_frame"),
                           "anticipation_frames": next((k["frame"] - s for k in b.keys if "anticipation" in k["principle"]), None)},
                "acceptance_criteria": _criteria(atype, req, extra), "_keys": b.keys}
        missing = [f for f in REQUIRED_FIELDS if spec.get(f) in (None, "", [])]
        if missing:
            raise ActionCompileError(f"{req['action_id']}: missing fields {missing}")
        for ev in ("attach", "detach"):
            if extra.get(ev):
                events.append(dict(extra[ev], type=ev, action_id=req["action_id"]))
        specs.append(spec)
        prev_end = e
    for a, b2 in zip(specs, specs[1:]):
        diff = _poses_equal(a["final_pose"], b2["initial_pose"])
        if diff:
            raise ActionCompileError(f"continuity broken between {a['action_id']} and {b2['action_id']}: {diff[:5]}")
    return {"compiler": "xdx_action_compiler_v1", "actor": rig.actor, "actions": specs, "events": events,
            "channels": _channels(rig, specs)}


def _channels(rig: RigProfile, specs: list[dict]) -> dict[str, list]:
    """Flatten keys into per-control channels: {'<rig control>|<attr>': [(frame, value, ease), ...]}."""
    ch: dict[str, list] = {}
    seen: set[tuple[str, int]] = set()
    for sp in specs:
        for k in sp["_keys"]:
            for ctl, attrs in k["pose"].items():
                if ctl == "attach":
                    continue
                name = ctl if ctl == "face" else rig.ctl(ctl)
                for attr, val in attrs.items():
                    key = f"{name}|{attr}"
                    if (key, k["frame"]) in seen:
                        ch[key] = [x for x in ch[key] if x[0] != k["frame"]]
                    seen.add((key, k["frame"]))
                    ch.setdefault(key, []).append((k["frame"], val, k["ease"]))
    for key in ch:
        ch[key].sort(key=lambda x: x[0])
        dedup = []
        for item in ch[key]:
            if dedup and dedup[-1][1] == item[1] and len(dedup) >= 2 and dedup[-2][1] == item[1]:
                dedup[-1] = item          # drop redundant middle holds
            else:
                dedup.append(item)
        ch[key] = dedup
    return ch
