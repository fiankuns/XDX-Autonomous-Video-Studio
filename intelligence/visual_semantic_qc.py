"""Independent Visual QC for Phase 02A VISUAL_ONLY_BENCHMARK renders.

Technical QC (``VisualQualityControlEngine``) only proves that an MP4 decodes and is not blank. That is how a render
with primitive placeholder props, debug overlays and shots that never show what the caption says could pass. This
module adds the missing semantic gate:

1. ``build_visual_review_checklist(package_dir)`` derives, from the signed package (storyboard + semantic visual plan +
   caption plan), what every shot MUST visibly show: the caption text (the stand-in for the narration in Phase 02A),
   the required actions, the required assets, the camera intent and the frames a reviewer must inspect. It also
   lists the REF-002 comparison dimensions.
2. ``evaluate_visual_review(checklist, review, ...)`` checks a review written by an INDEPENDENT reviewer (fresh
   context, not a producer) against that checklist and returns PASS / WARN / HARD_FAIL / INCOMPLETE.

Audio is out of scope here by design (deferred to Phase 04): no rule in this module looks at sound.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from governance.phase_scope import PHASE02A_DELIVERY_PROFILE, VISUAL_FOCUS_AREAS

CHECKLIST_SCHEMA = "xdx.visual-review-checklist.v2"
REVIEW_SCHEMA = "xdx.independent-visual-review.v1"
REFERENCE_ID = "REF-002"
SYNC_LEAD_S = 0.3  # a visual may lead its caption by at most 0.3 s (and must appear before the caption ends)

# Scored 0–5 by the reviewer for every shot.
SHOT_DIMENSIONS = (
    "character_and_asset_quality",
    "semantic_visual_storytelling",
    "animation_and_object_interaction",
    "mechanism_visualization",
    "camera_and_cinematography",
    "lighting_shadow_material_texture",
    "composition_and_transitions",
)
# Scored 0–5 for the whole render compared side by side with REF-002 (5 = on par with the reference).
REFERENCE_DIMENSIONS = (
    "character_and_asset_quality",
    "mechanism_visualization",
    "camera_and_cinematography",
    "lighting_shadow_material_texture",
    "composition_and_transitions",
    "story_clarity",
)
MIN_DIMENSION_SCORE = 3.0
MIN_SHOT_MEAN_SCORE = 3.5
MIN_REFERENCE_MEAN_SCORE = 3.0

assert set(SHOT_DIMENSIONS) <= set(VISUAL_FOCUS_AREAS)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(package_dir: Path, name: str) -> dict[str, Any]:
    p = package_dir / name
    if not p.is_file():
        raise FileNotFoundError(f"Visual review checklist needs {name} in {package_dir}")
    return json.loads(p.read_text(encoding="utf-8"))


def _sample_frames(start: int, end: int) -> list[int]:
    """Start, middle and end of the shot (inside the shot, away from cut frames)."""
    last = max(start, end - 1)
    span = last - start
    pts = {start + round(span * 0.1), start + round(span * 0.5), start + round(span * 0.9)}
    return sorted(pts)


def build_visual_review_checklist(package_dir: Path) -> dict[str, Any]:
    package_dir = Path(package_dir)
    sb = _load(package_dir, "storyboard.json")
    svp = _load(package_dir, "semantic_visual_plan.json")
    cap = _load(package_dir, "caption_audio_plan.json")

    fps = int(sb["fps"])
    cues_by_shot: dict[str, list[str]] = {}
    cue_windows: dict[str, list[dict[str, Any]]] = {}
    for cue in cap.get("cues", []):
        cues_by_shot.setdefault(cue["shot_id"], []).append(cue["text"])
        cue_windows.setdefault(cue["shot_id"], []).append(cue)
    actions_by_shot: dict[str, list[dict[str, Any]]] = {}
    for m in svp.get("clause_to_shot_mappings", []):
        actions_by_shot.setdefault(m["03_shot_id"], []).append(
            {"clause_id": m["clause_id"], "clause_text": m["clause_text"], "action": m["04_action"]}
        )

    shots = []
    for s in sb["shots"]:
        sid = s["shot_id"]
        required = list(actions_by_shot.get(sid, []))
        for key in ("action_start", "action_mid", "action_end"):
            txt = s.get(key)
            if isinstance(txt, str) and txt.strip() and txt.strip().lower() not in {
                a["action"].strip().lower() for a in required
            }:
                required.append({"clause_id": None, "clause_text": None, "action": txt.strip(), "phase": key})
        if not required:
            raise ValueError(f"Shot {sid} has no required visual action; the package cannot be reviewed semantically")
        shots.append(
            {
                "shot_id": sid,
                "frame_range": [s["start_frame"], s["end_frame"]],
                "captions": cues_by_shot.get(sid, []),
                "required_actions": [{"index": i, **a} for i, a in enumerate(required)],
                "required_assets": sorted(set(s.get("asset_ids", []))),
                "character_ids": list(s.get("character_ids", [])),
                "camera": s.get("camera"),
                "semantic_visual_purpose": s.get("semantic_visual_purpose"),
                "transition_in": s.get("transition_in"),
                "frames_to_inspect": _sample_frames(int(s["start_frame"]), int(s["end_frame"])),
                "caption_sync": [
                    {
                        "cue_id": c["cue_id"],
                        "text": c["text"],
                        "frame_window": [
                            max(int(s["start_frame"]), round((float(c["start_s"]) - SYNC_LEAD_S) * fps)),
                            min(int(s["end_frame"]), round(float(c["end_s"]) * fps)),
                        ],
                        "inspect_frame": min(int(s["end_frame"]) - 1, round((float(c["start_s"]) + float(c["end_s"])) / 2 * fps)),
                    }
                    for c in cue_windows.get(sid, [])
                ],
            }
        )

    return {
        "schema": CHECKLIST_SCHEMA,
        "project_id": sb["project_id"],
        "delivery_profile": PHASE02A_DELIVERY_PROFILE,
        "audio_in_scope": False,
        "fps": sb["fps"],
        "total_frames": sb["total_frames"],
        "resolution": [sb["width"], sb["height"]],
        "shot_dimensions": list(SHOT_DIMENSIONS),
        "reference_comparison": {"reference_id": REFERENCE_ID, "dimensions": list(REFERENCE_DIMENSIONS)},
        "thresholds": {
            "min_dimension_score": MIN_DIMENSION_SCORE,
            "min_shot_mean_score": MIN_SHOT_MEAN_SCORE,
            "min_reference_mean_score": MIN_REFERENCE_MEAN_SCORE,
        },
        "hard_rules": [
            "Every required action must be visibly shown in the inspected frames (caption ↔ visual match).",
            "Caption sync: what each caption says must be on screen inside its window (lead <= 0.3 s, before the caption ends).",
            "No placeholder / primitive stand-in for a required asset or character.",
            "No debug overlay, shot label, frame counter or engine watermark in the final frames.",
            "No render artifacts (stray planes, z-fighting, missing textures, clipping through geometry).",
            "Captions must not cover the subject; subjects must not be cut by the frame edge unintentionally.",
        ],
        "shots": shots,
    }


def _defect(defect_id: str, severity: str, shot_id: str | None, description: str) -> dict[str, Any]:
    return {"defect_id": defect_id, "severity": severity, "shot_id": shot_id, "description": description}


def _score_ok(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 5


def evaluate_visual_review(
    checklist: dict[str, Any],
    review: dict[str, Any],
    *,
    producer_ids: set[str] | frozenset[str],
    render_path: Path | None = None,
    reference_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate an independent visual review against the checklist.

    Status:
      * INCOMPLETE — the review does not cover every shot / action / frame / dimension, or is not independent.
      * HARD_FAIL  — any critical defect (semantic mismatch, placeholder asset, debug overlay, wrong render hash).
      * WARN       — only medium/low defects.
      * PASS       — complete, independent, no defects, all scores above thresholds.
    """
    defects: list[dict[str, Any]] = []
    gaps: list[str] = []

    if review.get("schema") != REVIEW_SCHEMA:
        gaps.append(f"review.schema must be {REVIEW_SCHEMA}")
    reviewer = str(review.get("reviewer_id") or "")
    if not reviewer:
        gaps.append("reviewer_id missing")
    elif reviewer in producer_ids:
        defects.append(_defect("DEF_VQC_SELF_REVIEW", "critical", None,
                               f"Reviewer '{reviewer}' produced the render; independent review required"))
    if review.get("reviewer_context") != "fresh":
        gaps.append("reviewer_context must be 'fresh' (independent clean context)")
    if review.get("project_id") != checklist["project_id"]:
        gaps.append("review.project_id does not match the checklist")

    if render_path is not None:
        actual = _sha256(Path(render_path))
        if review.get("render_sha256") != actual:
            defects.append(_defect("DEF_VQC_RENDER_HASH_MISMATCH", "critical", None,
                                   "Review does not refer to the rendered file being judged (SHA-256 mismatch)"))
    elif not review.get("render_sha256"):
        gaps.append("render_sha256 missing")

    reviewed = {s.get("shot_id"): s for s in review.get("shots", []) if isinstance(s, dict)}
    shot_means: dict[str, float] = {}
    for shot in checklist["shots"]:
        sid = shot["shot_id"]
        r = reviewed.get(sid)
        if r is None:
            gaps.append(f"{sid}: not reviewed")
            continue
        inspected = set(r.get("frames_inspected", []))
        missing_frames = [f for f in shot["frames_to_inspect"] if f not in inspected]
        if missing_frames:
            gaps.append(f"{sid}: frames not inspected {missing_frames}")

        evidence = {e.get("index"): e for e in r.get("action_evidence", []) if isinstance(e, dict)}
        lo, hi = shot["frame_range"]
        for act in shot["required_actions"]:
            e = evidence.get(act["index"])
            if e is None:
                gaps.append(f"{sid}: no evidence for required action #{act['index']}")
                continue
            frame = e.get("frame")
            if e.get("visible") is True:
                if not isinstance(frame, int) or not (lo <= frame < hi):
                    gaps.append(f"{sid}: action #{act['index']} evidence frame must lie inside [{lo},{hi})")
            else:
                defects.append(_defect("DEF_VQC_SEMANTIC_MISMATCH", "critical", sid,
                                       f"Required action not visible: {act['action']}"))

        sync_ev = {e.get("cue_id"): e for e in r.get("caption_sync_evidence", []) if isinstance(e, dict)}
        for cs in shot.get("caption_sync", []):
            e = sync_ev.get(cs["cue_id"])
            if e is None:
                gaps.append(f"{sid}: no caption_sync_evidence for {cs['cue_id']}")
                continue
            if e.get("visible") is not True:
                defects.append(_defect("DEF_VQC_CAPTION_VISUAL_MISMATCH", "critical", sid,
                                       f"{cs['cue_id']} '{cs['text']}' is not shown on screen while it is captioned"))
                continue
            fr = e.get("frame")
            wa, wb = cs["frame_window"]
            if not isinstance(fr, int):
                gaps.append(f"{sid}: {cs['cue_id']} evidence frame missing")
            elif not (wa <= fr < wb):
                defects.append(_defect("DEF_VQC_CAPTION_SYNC_WINDOW", "high", sid,
                                       f"{cs['cue_id']} shown at frame {fr}, outside its window [{wa},{wb})"))

        for asset in r.get("placeholder_assets", []) or []:
            defects.append(_defect("DEF_VQC_PLACEHOLDER_ASSET", "critical", sid,
                                   f"Primitive/placeholder stand-in visible for '{asset}'"))
        if r.get("debug_overlay_visible") is not False:
            if r.get("debug_overlay_visible") is True:
                defects.append(_defect("DEF_VQC_DEBUG_OVERLAY", "critical", sid,
                                       "Debug overlay / shot label / frame counter visible in final frames"))
            else:
                gaps.append(f"{sid}: debug_overlay_visible must be answered true/false")
        for art in r.get("render_artifacts", []) or []:
            defects.append(_defect("DEF_VQC_RENDER_ARTIFACT", "high", sid, f"Render artifact: {art}"))
        for key, did in (("caption_occludes_subject", "DEF_VQC_CAPTION_OCCLUSION"),
                         ("subject_clipped_by_frame", "DEF_VQC_FRAME_EDGE_CLIP")):
            val = r.get(key)
            if val is True:
                defects.append(_defect(did, "medium", sid, key.replace("_", " ")))
            elif val is not False:
                gaps.append(f"{sid}: {key} must be answered true/false")

        scores = r.get("scores", {}) or {}
        vals = []
        for dim in SHOT_DIMENSIONS:
            v = scores.get(dim)
            if not _score_ok(v):
                gaps.append(f"{sid}: score '{dim}' missing or outside 0–5")
                continue
            vals.append(float(v))
            if v < MIN_DIMENSION_SCORE:
                defects.append(_defect("DEF_VQC_LOW_SCORE", "high", sid, f"{dim} scored {v} < {MIN_DIMENSION_SCORE}"))
        if len(vals) == len(SHOT_DIMENSIONS):
            mean = sum(vals) / len(vals)
            shot_means[sid] = round(mean, 3)
            if mean < MIN_SHOT_MEAN_SCORE:
                defects.append(_defect("DEF_VQC_LOW_SHOT_MEAN", "high", sid,
                                       f"Mean visual score {mean:.2f} < {MIN_SHOT_MEAN_SCORE}"))

    ref = review.get("reference_comparison") or {}
    ref_mean = None
    if ref.get("reference_id") != REFERENCE_ID:
        gaps.append(f"reference_comparison must compare against {REFERENCE_ID}")
    if reference_sha256 and ref.get("reference_sha256") != reference_sha256:
        gaps.append("reference_comparison.reference_sha256 does not match the verified REF-002 media")
    ref_scores = ref.get("scores", {}) or {}
    rvals = []
    for dim in REFERENCE_DIMENSIONS:
        v = ref_scores.get(dim)
        if not _score_ok(v):
            gaps.append(f"reference score '{dim}' missing or outside 0–5")
            continue
        rvals.append(float(v))
    if len(rvals) == len(REFERENCE_DIMENSIONS):
        ref_mean = round(sum(rvals) / len(rvals), 3)
        if ref_mean < MIN_REFERENCE_MEAN_SCORE:
            defects.append(_defect("DEF_VQC_BELOW_REFERENCE", "high", None,
                                   f"Render scored {ref_mean} vs {REFERENCE_ID} (< {MIN_REFERENCE_MEAN_SCORE})"))
        for dim in REFERENCE_DIMENSIONS:
            if ref_scores[dim] < MIN_DIMENSION_SCORE:
                defects.append(_defect("DEF_VQC_REFERENCE_GAP", "medium", None,
                                       f"{dim} vs {REFERENCE_ID} scored {ref_scores[dim]}"))

    sev = {d["severity"] for d in defects}
    if "critical" in sev or "high" in sev:
        status = "HARD_FAIL"
    elif gaps:
        status = "INCOMPLETE"
    elif defects:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "schema": "xdx.independent-visual-qc-result.v1",
        "project_id": checklist["project_id"],
        "delivery_profile": checklist["delivery_profile"],
        "status": status,
        "reviewer_id": reviewer or None,
        "shot_mean_scores": shot_means,
        "reference_mean_score": ref_mean,
        "defects": defects,
        "review_gaps": gaps,
        "production_ready": status == "PASS",
    }
