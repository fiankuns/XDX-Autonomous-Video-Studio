"""Phase 02B.4 Character Action Compiler: contract, actor != target, continuity, contact, foot planting, principles."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.action_compiler import (ActionCompileError, RigProfile, SceneObject, REQUIRED_FIELDS, compile_actions)

ROOT = Path(__file__).resolve().parents[1]


def _load():
    R = json.loads((ROOT / "rig_profiles" / "bima_v2.json").read_text())
    rig = RigProfile(actor=R["actor"], controls=R["controls"], shoulder_height=R["shoulder_height"], hip_height=R["hip_height"],
                     arm_reach=R["arm_reach"], hip_width=R["hip_width"], eye_height=R["eye_height"],
                     mouth_offset=tuple(R["mouth_offset"]), stride=R["stride"],
                     hand_rest_offset={k: tuple(v) for k, v in R["hand_rest_offset"].items()})
    d = json.loads((ROOT / "projects" / "bench_p02b4_glass_10s" / "action_requests.json").read_text())
    objs = [SceneObject(x["object_id"], tuple(x["location"]), {k: tuple(v) for k, v in x["sockets"].items()}, x["kind"])
            for x in d["scene"]["objects"]]
    return rig, objs, d["requests"]


def test_benchmark_compiles_with_every_required_field_and_real_targets():
    rig, objs, reqs = _load()
    out = compile_actions(rig, objs, reqs)
    assert [a["action_type"] for a in out["actions"]] == ["look_at", "walk", "grasp", "drink", "place", "facial_reaction"]
    for a in out["actions"]:
        assert all(a.get(f) not in (None, "", []) for f in REQUIRED_FIELDS), a["action_id"]
        assert a["target_object"] != a["actor"]
        assert a["acceptance_criteria"] and any(c["id"] == "continuity" for c in a["acceptance_criteria"])
    assert out["actions"][-1]["end_frame"] == 240


@pytest.mark.parametrize("bad_target", ["char_bima_v2", "char_bima_v2.hand_R", "char_bima_v2:head", "", "prop_missing"])
def test_actor_or_missing_object_is_rejected_as_target(bad_target):
    rig, objs, reqs = _load()
    reqs = json.loads(json.dumps(reqs))
    reqs[0]["target_object"] = bad_target
    with pytest.raises(ActionCompileError):
        compile_actions(rig, objs, reqs)


def test_gaps_and_overlaps_and_short_actions_are_rejected():
    rig, objs, reqs = _load()
    gap = json.loads(json.dumps(reqs)); gap[1]["start_frame"] = 50
    with pytest.raises(ActionCompileError, match="gap/overlap"):
        compile_actions(rig, objs, gap)
    short = json.loads(json.dumps(reqs)); short[0]["end_frame"] = 4; short[1]["start_frame"] = 4
    with pytest.raises(ActionCompileError, match="shorter"):
        compile_actions(rig, objs, short)


def test_drink_without_holding_the_glass_is_rejected():
    rig, objs, reqs = _load()
    r = json.loads(json.dumps(reqs))
    r[2]["action_type"] = "look_at"          # never grasped
    with pytest.raises(ActionCompileError, match="held in hand"):
        compile_actions(rig, objs, r)


def test_continuity_contact_and_attach_detach():
    rig, objs, reqs = _load()
    out = compile_actions(rig, objs, reqs)
    acts = out["actions"]
    for a, b in zip(acts, acts[1:]):
        assert a["final_pose"] == b["initial_pose"]
    ev = {e["type"]: e for e in out["events"]}
    assert ev["attach"]["frame"] < ev["detach"]["frame"] and ev["attach"]["object"] == "prop_glass"
    grip = (0.08, -1.31, 0.68 + 0.055)
    hand = dict((f, v) for f, v, _ in out["channels"]["ik_hand.R|loc"])
    assert max(abs(x - y) for x, y in zip(hand[ev["attach"]["frame"]], grip)) < 1e-9   # hand on the grip at contact


def test_walk_plants_feet_and_arrives_on_the_stand_spot():
    rig, objs, reqs = _load()
    out = compile_actions(rig, objs, reqs)
    walk = out["actions"][1]
    root = walk["final_pose"]["root"]["loc"]
    assert abs(root[1] - (-1.35 + 0.36)) < 0.03 and abs(root[0]) < 0.03
    for side in ("L", "R"):
        keys = [(f, v) for f, v, _ in out["channels"][f"ik_foot.{side}|loc"] if 48 <= f <= 96]
        lifted = [f for f, v in keys if v[2] > 0.0]
        assert lifted, "each foot must swing at least once"
        # a planted foot never changes position between two planted keys unless a swing key lies between them
        planted = [(f, v) for f, v in keys if v[2] == 0.0]
        for (f1, v1), (f2, v2) in zip(planted, planted[1:]):
            swung = any(f1 < f < f2 for f in lifted)
            assert swung or max(abs(a - b) for a, b in zip(v1, v2)) < 1e-9, (side, f1, f2)


def test_principles_present_not_generic_rotation():
    rig, objs, reqs = _load()
    out = compile_actions(rig, objs, reqs)
    principles = " ".join(k["principle"] for a in out["actions"] for k in a["key_poses"])
    for p in ("anticipation", "overlap", "weight", "planted", "follow_through", "overshoot", "secondary", "balance", "contact"):
        assert p in principles, p
    # more than torso + hand channels are animated
    animated = {c for c, keys in out["channels"].items() if len({str(v) for _, v, _ in keys}) > 1}
    assert {"ik_foot.L|loc", "ik_foot.R|loc", "root|loc", "eye_target|loc", "face|blink", "face|smile", "head|rot"} <= animated


def test_compiler_is_character_agnostic():
    rig, objs, reqs = _load()
    other = RigProfile(actor="char_other", controls={**rig.controls, "hand_ik.R": "CTRL_hand_r"}, shoulder_height=1.4,
                       hip_height=0.9, arm_reach=0.6, hip_width=0.1, eye_height=1.7, mouth_offset=(0, -0.12, 1.6))
    r2 = [dict(r, actor="char_other") for r in reqs]
    out = compile_actions(other, objs, r2)
    assert "CTRL_hand_r|loc" in out["channels"] and out["actor"] == "char_other"
