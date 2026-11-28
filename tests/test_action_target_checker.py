"""DEF-P016D-028: action targets measured by an independent checker; actor never used as its own target."""
from __future__ import annotations

import json
from pathlib import Path

from intelligence.action_target_checker import check_action_targets
from intelligence.universal_preproduction import CharacterActionPlanner

ROOT = Path(__file__).resolve().parents[1]


def _shot(sid, chars, assets, text, env="env_room"):
    return {"shot_id": sid, "start_frame": 0, "end_frame": 48, "character_ids": chars, "asset_ids": assets,
            "environment_id": env, "semantic_visual_purpose": "character_acting", "beat_id": "B1",
            "action_start": text, "action_mid": text, "action_end": text, "primary_engine": "blender",
            "camera": {"motion_curve": "ease", "target": "x"}, "action_events": [{"concrete_action": text}]}


def _sb(*shots):
    return {"project_id": "p", "fps": 24, "total_frames": 48, "shots": list(shots)}


def test_actor_as_target_is_detected():
    sb = _sb(_shot("S1", ["char_bima"], ["prop_glass"], "Bima mengambil gelas"))
    bad = {"planned_actions": [{"action_id": "A1", "shot_id": "S1", "actor_id": "char_bima", "object_target": "char_bima"}]}
    r = check_action_targets(sb, bad)
    assert r["verdict"] == "FAIL" and r["actor_as_target"] == 1
    assert any(f["rule"] == "interaction_clause_without_object_target" for f in r["failures"])


def test_planner_never_targets_the_actor_even_when_actor_is_the_only_asset():
    sb = _sb(_shot("S1", [], ["char_bima"], "Bima melambai"),             # actor falls back to the asset
             _shot("S2", ["char_bima"], ["char_bima", "prop_glass"], "Bima meminum gelas"))
    plan = CharacterActionPlanner().build_action_plan(storyboard=sb, characters=[{"character_id": "char_bima"}])
    acts = {a["shot_id"]: a for a in plan["planned_actions"]}
    assert acts["S1"]["object_target"] == "env_anchor:env_room" and acts["S1"]["object_interaction"] is False
    assert acts["S2"]["object_target"] == "prop_glass" and acts["S2"]["object_interaction"] is True
    assert check_action_targets(sb, plan)["verdict"] == "PASS"


def test_interaction_clause_needs_a_real_object_not_env_anchor():
    sb = _sb(_shot("S1", ["char_bima"], [], "Bima mengangkat gelas lalu minum"))
    plan = CharacterActionPlanner().build_action_plan(storyboard=sb, characters=[{"character_id": "char_bima"}])
    r = check_action_targets(sb, plan)
    assert r["verdict"] == "FAIL" and r["interaction_clauses_failed"] == 1


def test_target_must_exist_in_shot_and_every_character_needs_an_action():
    sb = _sb(_shot("S1", ["char_bima", "char_ani"], ["prop_glass"], "Bima menunjuk"))
    plan = {"planned_actions": [{"action_id": "A1", "shot_id": "S1", "actor_id": "char_bima", "object_target": "prop_ghost"}]}
    rules = {f["rule"] for f in check_action_targets(sb, plan)["failures"]}
    assert {"target_not_in_shot", "character_without_action"} <= rules


def test_legacy_01_6c_plans_reproduce_the_109_actor_as_target_finding():
    """The carried-forward 109/109 claim: re-measured independently, every legacy action targets its own actor."""
    total = actor_as_target = 0
    for name in ("bench_a_ac_explainer_60s", "bench_b_birokrasi_satir_60s", "bench_c_laut_hilang_hybrid_180s",
                 "bench_d_kaus_kaki_flat_cartoon_45s"):
        d = ROOT / "projects" / name
        sbp = d / "storyboard.json" if (d / "storyboard.json").exists() else d / "semantic_visual_plan.json"
        r = check_action_targets(json.loads(sbp.read_text()), json.loads((d / "motion_plan.json").read_text()))
        total += r["actions"]
        actor_as_target += r["actor_as_target"]
    assert total == 109 and actor_as_target == 109
