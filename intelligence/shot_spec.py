"""Shot spec: ONE authoring file per topic (action events + callouts per shot); everything else is compiled or verified from it.

* ``validate_shot_spec``      structure, shot/cue references, anchors, label kinds, ids
* ``compile_action_events``   writes the action_events.json the geometric verifier consumes
* ``suggest_durations``       seconds each shot needs so every event window satisfies its ``min_seconds`` (feed to retime_package)
The scene reads the callouts from the same file (injected as window.__XDX_PACKAGE.callouts), so no label placement lives in scene code.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "xdx.shot-spec.v1"
SPACES = {"world", "ac", "od", "named"}


def load_shot_spec(package_dir: Path) -> dict[str, Any] | None:
    p = Path(package_dir) / "shot_spec.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def validate_shot_spec(spec: dict[str, Any], timeline: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    add = lambda code, msg: issues.append({"code": code, "severity": "critical", "message": msg})  # noqa: E731
    shots = {s["shot_id"] for s in timeline["shots"]}
    cues: dict[str, int] = {}
    for c in timeline["cues"]:
        cues[c["shot_id"]] = cues.get(c["shot_id"], 0) + 1
    seen: set[str] = set()
    for sh in spec["shots"]:
        sid = sh["shot_id"]
        if sid not in shots:
            add("SPEC_UNKNOWN_SHOT", f"shot {sid} is not in the storyboard")
            continue
        if not sh.get("events"):
            add("SPEC_SHOT_WITHOUT_ACTION_EVENT", f"{sid} has no action event: its important action cannot be verified")
        for e in sh.get("events", []):
            if e["window"]["cue"] >= cues.get(sid, 0) or e["window"]["from"] >= e["window"]["to"]:
                add("SPEC_BAD_EVENT_WINDOW", f"{e['event_id']}: window outside the shot's cues or empty")
        for c in sh.get("callouts", []):
            key = f"{sid}/{c['id']}"
            if key in seen:
                add("SPEC_DUPLICATE_CALLOUT", key)
            seen.add(key)
            a = c["anchor"]
            if a["space"] not in SPACES or (a["space"] == "named" and "name" not in a) or (a["space"] != "named" and "p" not in a):
                add("SPEC_BAD_ANCHOR", f"{key}: anchor needs space in {sorted(SPACES)} with p (or name for 'named')")
            for k in ("in", "out"):
                if k in c["show"] and c["show"][k]["cue"] >= cues.get(sid, 0):
                    add("SPEC_BAD_CALLOUT_WINDOW", f"{key}: {k} window references a missing cue")
    return issues


def compile_action_events(spec: dict[str, Any]) -> dict[str, Any]:
    events = [{**{k: v for k, v in e.items()}, "shot_id": sh["shot_id"]} for sh in spec["shots"] for e in sh.get("events", [])]
    return {"schema": "xdx.action-events.v1", "project_id": spec["project_id"], "events": events}


def suggest_durations(spec: dict[str, Any], timeline: dict[str, Any]) -> dict[str, float]:
    """Minimum shot seconds so that every event window is at least its min_seconds long (cue length scales with the shot)."""
    need: dict[str, float] = {}
    fps = timeline["fps"]
    for sh in spec["shots"]:
        shot = next(s for s in timeline["shots"] if s["shot_id"] == sh["shot_id"])
        shot_len = (shot["end_frame"] - shot["start_frame"]) / fps
        scale = 1.0
        for e in sh.get("events", []):
            if "min_seconds" not in e:
                continue
            cue = [c for c in timeline["cues"] if c["shot_id"] == sh["shot_id"]][e["window"]["cue"]]
            have = (cue["end_frame"] - cue["start_frame"]) * (e["window"]["to"] - e["window"]["from"]) / fps
            if have + 1e-6 < e["min_seconds"]:
                scale = max(scale, e["min_seconds"] / have)
        if scale > 1.0:
            need[sh["shot_id"]] = math.ceil(shot_len * scale * 10) / 10
    return need
