"""Action choreography contract — geometric proof that an action is performed the way the script says (topic-agnostic).

Every important action in a script is authored as an *action event*: who (actor/part), what (object), toward what
(target), when (a window relative to a caption cue) and how to verify it (constraints on named world-space anchors
that the scene exposes through ``window.__xdxProbe``). Examples of constraint types:

* ``distance_lt`` / ``distance_gt``   a hand is (not) near a target
* ``facing``                          an object's direction vector points at a target (fan face -> face, remote tip -> AC)
* ``not_facing``                      something must NOT point at a target yet (head must not look at the AC before the press)
* ``rigid``                           two anchors keep a constant distance over the window (the fan follows the wrist: a prop is attached)
* ``travel_gt``                       an anchor really MOVES (path length over the window): waving, wiping, pressing are not static poses

An event may also declare ``min_seconds``: the window must be long enough to be seen (content-driven duration; see retime_package).

This replaces guessed joint angles by checks the render pipeline can run in seconds, before any pixel review, and gives the
independent reviewer hard evidence. See schemas/action_events.schema.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "xdx.action-events.v1"
CONSTRAINT_TYPES = frozenset({"distance_lt", "distance_gt", "facing", "not_facing", "rigid", "travel_gt"})
WINDOW_TYPES = frozenset({"rigid", "travel_gt"})  # judged over the whole window, not per frame


def load_action_events(package_dir: Path) -> dict[str, Any] | None:
    p = Path(package_dir) / "action_events.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _vec_to(a: dict[str, Any], b: dict[str, Any]) -> list[float]:
    return [b["p"][i] - a["p"][i] for i in range(3)]


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def evaluate_constraint(c: dict[str, Any], probe: dict[str, Any]) -> tuple[bool, float]:
    t = c["type"]
    if t in {"distance_lt", "distance_gt"}:
        d = math.dist(probe[c["a"]]["p"], probe[c["b"]]["p"])
        return (d < c["value"] if t == "distance_lt" else d > c["value"]), d
    if t in {"facing", "not_facing"}:
        d = _norm(probe[c["dir"]]["d"])
        to = _norm(_vec_to(probe[c["from"]], probe[c["to"]]))
        dot = sum(d[i] * to[i] for i in range(3))
        return (dot >= c["min_dot"] if t == "facing" else dot <= c["max_dot"]), dot
    raise ValueError(f"unknown constraint type {t}")


def evaluate_window_constraint(c: dict[str, Any], probes: list[dict[str, Any]]) -> tuple[bool, float]:
    if c["type"] == "rigid":
        ds = [math.dist(p[c["a"]]["p"], p[c["b"]]["p"]) for p in probes]
        spread = max(ds) - min(ds)
        return spread <= c.get("tol", 0.02), spread
    path = sum(math.dist(probes[i - 1][c["anchor"]]["p"], probes[i][c["anchor"]]["p"]) for i in range(1, len(probes)))
    return path >= c["value"], path


def event_frames(event: dict[str, Any], cues: list[dict[str, Any]], step: int = 3) -> list[int]:
    """Frames of an event window: a fraction range of the n-th caption cue of the event's shot (integer frames)."""
    shot_cues = [c for c in cues if c["shot_id"] == event["shot_id"]]
    w = event["window"]
    cue = shot_cues[w["cue"]]
    a = cue["start_frame"] + round((cue["end_frame"] - cue["start_frame"]) * w["from"])
    b = cue["start_frame"] + round((cue["end_frame"] - cue["start_frame"]) * w["to"])
    return list(range(a, max(a + 1, b), step))


def needed_frames(spec: dict[str, Any], cues: list[dict[str, Any]]) -> list[int]:
    return sorted({f for e in spec["events"] for f in event_frames(e, cues)})


def evaluate_events(spec: dict[str, Any], cues: list[dict[str, Any]], probes: dict[int, dict[str, Any]]) -> dict[str, Any]:
    results, issues = [], []
    for e in spec["events"]:
        frames = event_frames(e, cues)
        per_constraint = []
        for c in e["constraints"]:
            if c["type"] not in CONSTRAINT_TYPES:
                raise ValueError(f"unknown constraint type {c['type']}")
            if c["type"] in WINDOW_TYPES:
                ok, val = evaluate_window_constraint(c, [probes[f] for f in frames])
                per_constraint.append({"constraint": c, "hold": 1.0 if ok else 0.0, "worst_value": round(val, 3), "passed": ok})
                if not ok:
                    issues.append({"code": "ACTION_GEOMETRY_FAIL", "severity": "critical", "event_id": e["event_id"],
                                   "message": f"{e['event_id']}: {c['type']} failed ({val:.3f})"})
                continue
            ok_frames = 0
            worst = None
            for f in frames:
                ok, val = evaluate_constraint(c, probes[f])
                ok_frames += ok
                worst = val if worst is None else (max(worst, val) if c["type"] in {"distance_lt"} else min(worst, val) if c["type"] in {"facing", "distance_gt"} else max(worst, val))
            ratio = ok_frames / len(frames)
            passed = ratio >= e.get("hold_ratio", 0.9)
            per_constraint.append({"constraint": c, "hold": round(ratio, 3), "worst_value": round(worst, 3), "passed": passed})
            if not passed:
                issues.append({"code": "ACTION_GEOMETRY_FAIL", "severity": "critical", "event_id": e["event_id"],
                               "message": f"{e['event_id']}: {c['type']} held on {ratio:.0%} of frames (worst {worst:.3f})"})
        if "min_seconds" in e:
            shot_cues = [c for c in cues if c["shot_id"] == e["shot_id"]]
            cue = shot_cues[e["window"]["cue"]]
            secs = (cue["end_frame"] - cue["start_frame"]) * (e["window"]["to"] - e["window"]["from"]) / 30.0
            if secs + 1e-6 < e["min_seconds"]:
                issues.append({"code": "ACTION_TOO_SHORT", "severity": "critical", "event_id": e["event_id"],
                               "message": f"{e['event_id']}: window {secs:.2f}s < required {e['min_seconds']}s - retime the shot (retime_package)"})
        results.append({"event_id": e["event_id"], "shot_id": e["shot_id"], "frames": [frames[0], frames[-1]], "constraints": per_constraint,
                        "passed": all(x["passed"] for x in per_constraint)})
    return {"schema": "xdx.action-verification.v1", "status": "BLOCKED" if issues else "OK", "events": results, "issues": issues}
