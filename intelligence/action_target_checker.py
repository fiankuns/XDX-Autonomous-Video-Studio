"""Independent action-target checker (DEF-P016D-028).

Measures action-target coverage with criteria that do NOT come from the planner that produced the plan:
- an action's object target must never be its actor (or the actor's own rig/parts);
- the target must exist in the shot (asset ids or an explicit ``env_anchor:<environment_id>``);
- a script clause that names a physical interaction (take, hold, drink, put, lift, ...) must have an action with a real
  object target (not an env anchor) whose id or name appears in, or is listed as an asset of, that shot;
- every shot with a character must have at least one planned action for that character.
Coverage is reported as counted failures, never as a self-reported ratio.
"""
from __future__ import annotations

import re
from typing import Any

# Indonesian + English interaction verbs (root forms; prefixes me-/di-/ber- handled by substring search).
INTERACTION_VERBS = (
    "ambil", "angkat", "pegang", "genggam", "minum", "letak", "taruh", "tuang", "buka", "tutup", "tekan",
    "dorong", "tarik", "lempar", "tangkap", "raih", "sentuh", "kipas", "usap", "gelas", "cangkir",
    "take", "grab", "grasp", "hold", "lift", "drink", "place", "put", "pour", "open", "press", "push", "pull",
    "reach", "touch",
)


def _is_actor_part(target: str, actor: str) -> bool:
    t, a = target.lower(), actor.lower()
    return t == a or t.startswith(a + ".") or t.startswith(a + ":") or t.startswith(a + "_part") or t.startswith(a + "/")


def _clause_needs_object(text: str) -> bool:
    low = (text or "").lower()
    return any(re.search(r"\b\w*" + re.escape(v) + r"\w*\b", low) for v in INTERACTION_VERBS)


def check_action_targets(storyboard: dict[str, Any], motion_plan: dict[str, Any]) -> dict[str, Any]:
    shots = {s["shot_id"]: s for s in storyboard.get("shots", [])}
    actions = motion_plan.get("planned_actions") or []
    failures: list[dict[str, Any]] = []
    by_shot: dict[str, list[dict[str, Any]]] = {}
    for a in actions:
        by_shot.setdefault(a.get("shot_id"), []).append(a)
        sid, actor, tgt = a.get("shot_id"), str(a.get("actor_id") or ""), str(a.get("object_target") or "")
        shot = shots.get(sid)
        if shot is None:
            failures.append({"action_id": a.get("action_id"), "rule": "unknown_shot", "shot_id": sid})
            continue
        if not tgt:
            failures.append({"action_id": a.get("action_id"), "rule": "missing_target"})
        elif _is_actor_part(tgt, actor):
            failures.append({"action_id": a.get("action_id"), "rule": "actor_is_target", "actor": actor, "target": tgt})
        else:
            valid = set(shot.get("asset_ids") or []) | {f"env_anchor:{shot.get('environment_id')}", shot.get("environment_id")}
            if tgt not in valid:
                failures.append({"action_id": a.get("action_id"), "rule": "target_not_in_shot", "target": tgt})
    clause_checked = clause_fail = 0
    for sid, shot in shots.items():
        acts = by_shot.get(sid, [])
        for ch in shot.get("character_ids") or []:
            if not any(x.get("actor_id") == ch for x in acts):
                failures.append({"shot_id": sid, "rule": "character_without_action", "actor": ch})
        text = " ".join(str(shot.get(k) or "") for k in ("script_clause", "clause_text", "action_start", "action_mid", "action_end"))
        text += " " + " ".join(str(e.get("concrete_action") or "") for e in shot.get("action_events") or [])
        if _clause_needs_object(text):
            clause_checked += 1
            real = [x for x in acts if str(x.get("object_target", "")).strip()
                    and not str(x["object_target"]).startswith("env_anchor:")
                    and not _is_actor_part(str(x["object_target"]), str(x.get("actor_id") or ""))]
            if not real:
                clause_fail += 1
                failures.append({"shot_id": sid, "rule": "interaction_clause_without_object_target", "clause": text[:120]})
    return {
        "checker": "independent_action_target_checker_v1",
        "actions": len(actions),
        "shots": len(shots),
        "interaction_clauses_checked": clause_checked,
        "interaction_clauses_failed": clause_fail,
        "actor_as_target": sum(1 for f in failures if f["rule"] == "actor_is_target"),
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
    }
