"""XDX visual production workflow (Phase 02A consolidation) — topic-agnostic orchestration helpers.

This module adds only what the repository did not have yet and delegates everything else:

* input validation + environment check      -> ``validate_inputs``
* canonical integer-frame timeline + chapters -> ``canonical_timeline`` / ``plan_chapters`` (one timeline, chapters are a view)
* semantic visual contract per beat          -> ``semantic_contract`` (wraps ``visual_semantic_qc.build_visual_review_checklist``)
* shot evidence (actual frames, hash-bound)  -> ``build_shot_evidence`` / ``verify_shot_evidence``
* selective re-render by hash + dependencies -> ``shot_input_hashes`` / ``plan_selective_rerender``
* caption safe area                          -> ``check_caption_safe_area``
* production delivery validation             -> ``validate_delivery`` (wraps ``VisualQualityControlEngine`` + independent review)

Not duplicated here: Independent Semantic Visual QC (``intelligence/visual_semantic_qc.py``), trusted approval and the
execution guard (``governance/``, ``scripts/execution_guard_hook.py``), the deterministic scene API, style frames and
asset load barrier (``engines/web/xdx_core`` + ``scripts/render_phase02a_visual.py``). Remotion stays the master timeline,
Three.js the visual engine, Blender the modelling/rigging/acting/cinematic engine (Phase 02B+, approval required).
No audio, TTS, music, SFX or lip sync (Phase 04).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from governance.phase_scope import PHASE02A_DELIVERY_PROFILE
from intelligence.visual_semantic_qc import build_visual_review_checklist

ROOT_DIR = Path(__file__).resolve().parent.parent

REQUIRED_PACKAGE_FILES = (
    "storyboard.json",
    "caption_audio_plan.json",
    "semantic_visual_plan.json",
    "character_bible.json",
    "style_bible.json",
    "asset_manifest.json",
    "project_state.json",
)
FINAL_ASSET_STATUSES = frozenset({"PROCEDURAL_IMPLEMENTED", "PROCEDURAL_INLINE", "VERIFIED_EXTERNAL", "AVAILABLE"})
BLOCKING_ASSET_STATUSES = frozenset({"PLACEHOLDER", "PLANNED", "PRIMITIVE_PLACEHOLDER", "MISSING"})
# Same geometry the caption plan declares for 9:16 (intelligence/universal_preproduction.py).
CAPTION_SAFE_AREA_9X16 = {"canvas": [1080, 1920], "horizontal_margin_px": 90, "top_margin_px": 220, "bottom_margin_px": 340}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _load(package_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((Path(package_dir) / name).read_text(encoding="utf-8"))


def _issue(code: str, severity: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **extra}


def _status(issues: list[dict[str, Any]]) -> str:
    return "BLOCKED" if any(i["severity"] in {"critical", "high"} for i in issues) else ("WARN" if issues else "OK")


# --------------------------------------------------------------------------------------------- 1. input validation
def validate_inputs(package_dir: Path, *, root: Path = ROOT_DIR, check_environment: bool = True) -> dict[str, Any]:
    """Fail early (before any render) on missing/inconsistent inputs and an unusable render environment."""
    package_dir = Path(package_dir)
    issues: list[dict[str, Any]] = []
    for name in REQUIRED_PACKAGE_FILES:
        if not (package_dir / name).is_file():
            issues.append(_issue("INPUT_MISSING_FILE", "critical", f"required package file missing: {name}", file=name))
    if issues:
        return {"status": _status(issues), "issues": issues}

    sb, cap, cb, sty = (_load(package_dir, n) for n in ("storyboard.json", "caption_audio_plan.json", "character_bible.json", "style_bible.json"))
    shot_ids = {s["shot_id"] for s in sb["shots"]}
    for c in cap.get("cues", []):
        if c["shot_id"] not in shot_ids:
            issues.append(_issue("INPUT_CUE_UNKNOWN_SHOT", "high", f"caption cue {c.get('cue_id')} references unknown shot {c['shot_id']}"))
    if cb.get("style_bible_id") != sty.get("style_bible_id"):
        issues.append(_issue("INPUT_STYLE_MISMATCH", "high", "character_bible.style_bible_id differs from style_bible.style_bible_id"))
    for ch in cb.get("characters", []):
        pal = ch.get("color_palette") or []
        if not pal or not all(isinstance(c, str) and len(c) == 7 and c.startswith("#") for c in pal):
            issues.append(_issue("INPUT_CHARACTER_PALETTE", "high", f"character {ch.get('character_id')} has no valid locked palette"))
    if not (package_dir / "action_events.json").is_file():
        issues.append(_issue("INPUT_NO_ACTION_EVENTS", "medium", "no action_events.json: important actions cannot be verified geometrically (author one per key action)"))
    if check_environment:
        for tool in ("ffmpeg", "ffprobe"):
            if not shutil.which(tool):
                issues.append(_issue("ENV_TOOL_MISSING", "critical", f"{tool} not found"))
        if not (shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")):
            issues.append(_issue("ENV_TOOL_MISSING", "critical", "no headless Chrome/Chromium found"))
        three = Path(root) / "node_modules/three/package.json"
        if not three.is_file():
            issues.append(_issue("ENV_THREE_MISSING", "critical", "node_modules/three missing (npm ci)"))
        elif json.loads(three.read_text(encoding="utf-8")).get("version") != "0.187.0":
            issues.append(_issue("ENV_THREE_VERSION", "high", "three.js must be pinned at 0.187.0"))
    return {"status": _status(issues), "issues": issues}


# --------------------------------------------------------------------------------------------- 2. canonical timeline
def canonical_timeline(package_dir: Path) -> dict[str, Any]:
    """Integer-frame master timeline derived from storyboard + caption plan. Raises ValueError when inconsistent."""
    sb = _load(package_dir, "storyboard.json")
    cap = _load(package_dir, "caption_audio_plan.json")
    fps = sb["fps"]
    if not isinstance(fps, int) or not isinstance(sb["total_frames"], int):
        raise ValueError("fps and total_frames must be integers")
    shots, expect = [], 0
    for s in sb["shots"]:
        a, b = s["start_frame"], s["end_frame"]
        if not (isinstance(a, int) and isinstance(b, int)) or a != expect or b <= a:
            raise ValueError(f"shot {s['shot_id']} is not contiguous integer frames (start {a}, expected {expect})")
        shots.append({"shot_id": s["shot_id"], "start_frame": a, "end_frame": b})
        expect = b
    if expect != sb["total_frames"]:
        raise ValueError(f"shots end at frame {expect} but total_frames is {sb['total_frames']}")
    by_id = {s["shot_id"]: s for s in shots}
    cues = []
    for c in cap.get("cues", []):
        s = by_id.get(c["shot_id"])
        if s is None:
            raise ValueError(f"cue {c.get('cue_id')} references unknown shot {c['shot_id']}")
        a, b = round(c["start_s"] * fps), round(c["end_s"] * fps)
        if not (s["start_frame"] <= a < b <= s["end_frame"]):
            raise ValueError(f"cue {c.get('cue_id')} frames [{a},{b}) fall outside shot {s['shot_id']}")
        cues.append({"cue_id": c["cue_id"], "shot_id": c["shot_id"], "start_frame": a, "end_frame": b})
    return {"schema": "xdx.canonical-timeline.v1", "fps": fps, "total_frames": sb["total_frames"], "shots": shots, "cues": cues, "chapters": []}


def plan_chapters(timeline: dict[str, Any], max_chapter_seconds: float = 45.0) -> dict[str, Any]:
    """Logical chapter mode for long videos: group consecutive shots; chapters are frame ranges on the SAME timeline."""
    fps, chapters, cur = timeline["fps"], [], []
    for s in timeline["shots"]:
        if cur and (s["end_frame"] - cur[0]["start_frame"]) / fps > max_chapter_seconds:
            chapters.append(cur)
            cur = []
        cur.append(s)
    if cur:
        chapters.append(cur)
    out = [
        {"chapter_id": f"CH{i + 1:02d}", "shot_ids": [s["shot_id"] for s in c], "start_frame": c[0]["start_frame"], "end_frame": c[-1]["end_frame"]}
        for i, c in enumerate(chapters)
    ]
    verify_chapters(timeline, out)
    return {**timeline, "chapters": out}


def verify_chapters(timeline: dict[str, Any], chapters: list[dict[str, Any]]) -> None:
    """Chapters must partition the single timeline exactly (no gap, overlap or second clock)."""
    expect = 0
    for ch in chapters:
        if ch["start_frame"] != expect:
            raise ValueError(f"chapter {ch['chapter_id']} starts at {ch['start_frame']}, expected {expect}")
        expect = ch["end_frame"]
    if expect != timeline["total_frames"]:
        raise ValueError("chapters do not cover the canonical timeline exactly")


# --------------------------------------------------------------------------------------------- 3. semantic contract
def semantic_contract(package_dir: Path) -> dict[str, Any]:
    """Semantic Visual Contract per shot/beat: what must be on screen, with which assets, inside which frame windows.

    Built from the same checklist the independent reviewer uses, so producer and QC share one contract.
    """
    chk = build_visual_review_checklist(Path(package_dir))
    issues = []
    beats = []
    for s in chk["shots"]:
        if not s["required_actions"]:
            issues.append(_issue("CONTRACT_NO_ACTION", "critical", f"shot {s['shot_id']} has no required visual action"))
        if not s["caption_sync"]:
            issues.append(_issue("CONTRACT_NO_CAPTION_WINDOW", "high", f"shot {s['shot_id']} has no caption sync window"))
        beats.append(
            {
                "shot_id": s["shot_id"],
                "frame_range": s["frame_range"],
                "required_actions": [a["action"] for a in s["required_actions"]],
                "required_assets": s["required_assets"],
                "caption_windows": [{"cue_id": c["cue_id"], "frame_window": c["frame_window"], "text": c["text"]} for c in s["caption_sync"]],
                "evidence_frames": s["frames_to_inspect"] + [c["inspect_frame"] for c in s["caption_sync"]],
            }
        )
    return {"schema": "xdx.semantic-visual-contract.v1", "project_id": chk["project_id"], "status": _status(issues), "issues": issues, "beats": beats}


# --------------------------------------------------------------------------------------------- 4. shot evidence
def build_shot_evidence(contract: dict[str, Any], frames_dir: Path, render_sha256: str) -> dict[str, Any]:
    """Hash the actual extracted frames per shot. Evidence frames come from the render, never from the producer's notes."""
    frames_dir = Path(frames_dir)
    shots = []
    for b in contract["beats"]:
        entries = []
        for f in sorted(set(b["evidence_frames"])):
            p = frames_dir / f"f{f:04d}.png"
            entries.append({"frame": f, "file": p.name, "sha256": _sha256_file(p) if p.is_file() else None})
        shots.append({"shot_id": b["shot_id"], "frames": entries})
    return {"schema": "xdx.shot-evidence.v1", "render_sha256": render_sha256, "shots": shots}


def verify_shot_evidence(contract: dict[str, Any], evidence: dict[str, Any], render_sha256: str) -> list[dict[str, Any]]:
    issues = []
    if evidence.get("render_sha256") != render_sha256:
        issues.append(_issue("EVIDENCE_RENDER_HASH", "critical", "shot evidence does not belong to this render"))
    got = {s["shot_id"]: s for s in evidence.get("shots", [])}
    for b in contract["beats"]:
        s = got.get(b["shot_id"])
        if s is None or not s["frames"]:
            issues.append(_issue("EVIDENCE_MISSING_SHOT", "critical", f"no visual evidence for shot {b['shot_id']}", shot_id=b["shot_id"]))
            continue
        if any(e["sha256"] is None for e in s["frames"]):
            issues.append(_issue("EVIDENCE_MISSING_FRAME", "critical", f"evidence frame file missing for shot {b['shot_id']}", shot_id=b["shot_id"]))
        have = {e["frame"] for e in s["frames"]}
        for cw in b["caption_windows"]:
            if not any(cw["frame_window"][0] <= f < cw["frame_window"][1] for f in have):
                issues.append(_issue("EVIDENCE_NO_FRAME_IN_CAPTION_WINDOW", "high", f"no evidence frame inside the window of {cw['cue_id']}", shot_id=b["shot_id"]))
    return issues


# --------------------------------------------------------------------------------------------- 5. selective re-render
def shot_input_hashes(package_dir: Path, deps: dict[str, Any], *, root: Path = ROOT_DIR) -> dict[str, str]:
    """Per-shot input hash = storyboard entry + caption cues + semantic mappings + global files + the assets/files the shot uses."""
    package_dir, root = Path(package_dir), Path(root)
    sb, cap, svp = _load(package_dir, "storyboard.json"), _load(package_dir, "caption_audio_plan.json"), _load(package_dir, "semantic_visual_plan.json")
    glob = {rel: _sha256_file(root / rel) for rel in deps["global"]}
    out: dict[str, str] = {}
    for s in sb["shots"]:
        sid = s["shot_id"]
        parts = {
            "storyboard": s,
            "fps": sb["fps"],
            "cues": [c for c in cap.get("cues", []) if c["shot_id"] == sid],
            "semantic": [m for m in svp.get("clause_to_shot_mappings", []) if m.get("03_shot_id") == sid],
            "global": glob,
            "assets": {aid: _sha256_file(root / a["file"]) for aid, a in deps.get("assets", {}).items() if sid in a["shots"]},
            "shot_files": {rel: _sha256_file(root / rel) for rel in deps.get("shot_files", {}).get(sid, [])},
        }
        out[sid] = _sha256_obj(parts)
    return out


def plan_selective_rerender(current: dict[str, str], previous: dict[str, str] | None) -> dict[str, Any]:
    """Re-render only shots whose input hash changed (or that are new); reuse cached frames for the rest."""
    prev = previous or {}
    rerender = sorted(s for s, h in current.items() if prev.get(s) != h)
    return {"rerender": rerender, "reuse": sorted(set(current) - set(rerender)), "removed": sorted(set(prev) - set(current))}


# --------------------------------------------------------------------------------------------- 6. caption safe area
def check_caption_safe_area(rects: list[dict[str, Any]], safe: dict[str, Any] = CAPTION_SAFE_AREA_9X16) -> list[dict[str, Any]]:
    """rects: [{"frame": int, "x": px, "y": px, "w": px, "h": px}] measured from the real caption element."""
    cw, ch = safe["canvas"]
    left, right = safe["horizontal_margin_px"], cw - safe["horizontal_margin_px"]
    top, bottom = safe["top_margin_px"], ch - safe["bottom_margin_px"] + 200  # the caption block sits INSIDE the bottom band; it must not leave the canvas
    issues = []
    for r in rects:
        if r["x"] < left or r["x"] + r["w"] > right:
            issues.append(_issue("CAPTION_OUTSIDE_HORIZONTAL_SAFE_AREA", "high", f"frame {r['frame']}: caption exceeds horizontal margins", frame=r["frame"]))
        if r["y"] < top or r["y"] + r["h"] > ch - 60:
            issues.append(_issue("CAPTION_OUTSIDE_VERTICAL_SAFE_AREA", "high", f"frame {r['frame']}: caption outside vertical safe area", frame=r["frame"]))
        if r["y"] < ch - safe["bottom_margin_px"] - r["h"] - 60:
            issues.append(_issue("CAPTION_ABOVE_LOWER_THIRD_BAND", "medium", f"frame {r['frame']}: caption is not in the lower caption band", frame=r["frame"]))
    return issues


# --------------------------------------------------------------------------------------------- 7. delivery validation
def _ffprobe(path: Path) -> dict[str, Any]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def validate_delivery(
    mp4: Path,
    *,
    package_dir: Path,
    render_manifest: dict[str, Any],
    asset_bindings: dict[str, Any],
    evidence: dict[str, Any] | None,
    review_result: dict[str, Any] | None,
    safe_area_report: list[dict[str, Any]] | None,
    action_report: dict[str, Any] | None = None,
    callout_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Final gate for a VISUAL_ONLY_BENCHMARK delivery. Every check is evidence-based; nothing is assumed."""
    mp4 = Path(mp4)
    issues: list[dict[str, Any]] = []
    actual = _sha256_file(mp4)
    if render_manifest.get("output_sha256") != actual:
        issues.append(_issue("DELIVERY_HASH_MISMATCH", "critical", "render manifest hash differs from the delivered file"))
    if render_manifest.get("delivery_profile") != PHASE02A_DELIVERY_PROFILE:
        issues.append(_issue("DELIVERY_PROFILE", "high", "render manifest is not VISUAL_ONLY_BENCHMARK"))

    sb = _load(package_dir, "storyboard.json")
    probe = _ffprobe(mp4)
    streams = probe["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    if video is None:
        issues.append(_issue("DELIVERY_NO_VIDEO", "critical", "no video stream"))
    else:
        if (video["width"], video["height"]) != (sb["width"], sb["height"]):
            issues.append(_issue("DELIVERY_RESOLUTION", "high", f"{video['width']}x{video['height']} != {sb['width']}x{sb['height']}"))
        num, den = (int(x) for x in video["avg_frame_rate"].split("/"))
        if den == 0 or num // den != sb["fps"] or num % den:
            issues.append(_issue("DELIVERY_FPS", "high", f"avg_frame_rate {video['avg_frame_rate']} != {sb['fps']}"))
        if int(video.get("nb_read_frames") or video.get("nb_frames") or -1) != sb["total_frames"]:
            issues.append(_issue("DELIVERY_FRAME_COUNT", "high", "frame count differs from the canonical timeline"))
    if any(s["codec_type"] == "audio" for s in streams):
        issues.append(_issue("DELIVERY_UNNECESSARY_AUDIO_TRACK", "low", "Phase 02A exports no audio track"))

    for b in asset_bindings.get("bindings", []):
        if b["status"] in BLOCKING_ASSET_STATUSES or b["status"] not in FINAL_ASSET_STATUSES:
            issues.append(_issue("DELIVERY_PLACEHOLDER_ASSET", "critical", f"asset {b['asset_id']} is {b['status']}; placeholders cannot pass final QC", asset_id=b["asset_id"]))
        if not (ROOT_DIR / b["module"]).is_file():
            issues.append(_issue("DELIVERY_ASSET_MODULE_MISSING", "high", f"asset module missing for {b['asset_id']}"))
    scene_hashes = render_manifest.get("scene_sha256") or {}
    if not scene_hashes:
        issues.append(_issue("DELIVERY_NO_SCENE_HASH", "high", "render manifest has no scene hashes"))

    contract = semantic_contract(package_dir)
    if evidence is None:
        issues.append(_issue("DELIVERY_NO_SHOT_EVIDENCE", "critical", "shot evidence missing"))
    else:
        issues += verify_shot_evidence(contract, evidence, actual)
    if safe_area_report is None:
        issues.append(_issue("DELIVERY_NO_SAFE_AREA_REPORT", "high", "caption safe-area report missing"))
    else:
        issues += safe_area_report
    if (Path(package_dir) / "action_events.json").is_file():
        if action_report is None:
            issues.append(_issue("DELIVERY_NO_ACTION_VERIFICATION", "high", "package declares action events but no geometric verification report was provided"))
        elif action_report.get("status") != "OK":
            issues += [_issue(i["code"], "critical", i["message"]) for i in action_report.get("issues", [])] or [_issue("DELIVERY_ACTION_VERIFICATION", "critical", "action verification not OK")]
    if callout_report is None:
        issues.append(_issue("DELIVERY_NO_CALLOUT_VERIFICATION", "high", "no callout layout verification report (leader lines, overlaps)"))
    elif callout_report.get("status") != "OK":
        issues += [_issue(i["code"], "critical", i["message"]) for i in callout_report.get("issues", [])] or [_issue("DELIVERY_CALLOUT_VERIFICATION", "critical", "callout verification not OK")]
    if review_result is None:
        issues.append(_issue("DELIVERY_NO_INDEPENDENT_REVIEW", "critical", "independent semantic visual review missing"))
    elif review_result.get("overall_status") != "PASS":
        issues.append(_issue("DELIVERY_REVIEW_NOT_PASS", "critical", f"independent visual review is {review_result.get('overall_status')}"))
    return {"schema": "xdx.delivery-validation.v1", "mp4_sha256": actual, "status": _status(issues), "issues": issues}


# ----------------------------------------------------------------------------------------------------------------------
# Content-driven duration: a script action may need more time than the nominal target (a 15 s brief is a default, not a law).
# ``retime_package`` stretches individual shots and rewrites every frame/second field consistently (piecewise-linear map on
# the shot boundaries), so storyboard, camera, motion, engine, narration and caption cues keep describing ONE timeline.
# ----------------------------------------------------------------------------------------------------------------------
_RETIME_FILES = ("storyboard.json", "camera_plan.json", "motion_plan.json", "engine_plan.json", "narration_dialogue.json",
                 "caption_audio_plan.json", "semantic_visual_plan.json", "production_config.json", "project_state.json")
_FRAME_KEYS = {"start_frame", "end_frame", "frame"}
_SEC_KEYS = {"start_s", "end_s", "start_time_s", "end_time_s"}


def retime_package(package_dir: Path, shot_seconds: dict[str, float]) -> dict[str, Any]:
    """Set new durations (seconds) for named shots; later shots shift. Only valid while the package is unapproved."""
    package_dir = Path(package_dir)
    sb = json.loads((package_dir / "storyboard.json").read_text(encoding="utf-8"))
    fps = int(sb["fps"])
    old = [(s["shot_id"], int(s["start_frame"]), int(s["end_frame"])) for s in sb["shots"]]
    new_bounds, cur = [], 0
    for sid, a, b in old:
        n = round(shot_seconds[sid] * fps) if sid in shot_seconds else b - a
        new_bounds.append((sid, cur, cur + n))
        cur += n
    total_new = cur
    segs = [(a, b, na, nb) for (_, a, b), (_, na, nb) in zip(old, new_bounds)]

    def mf(x: float) -> float:
        for a, b, na, nb in segs:
            if a <= x <= b:
                return na + (x - a) * (nb - na) / (b - a)
        return x + (total_new - segs[-1][1])

    def walk(o: Any, fname: str) -> None:
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if k in _FRAME_KEYS:
                        o[k] = int(round(mf(v)))
                    elif k in _SEC_KEYS:
                        o[k] = round(mf(v * fps) / fps, 3)
                    elif k == "total_frames" and fname != "production_config.json" or (k == "total_frames" and v == segs[-1][1]):
                        o[k] = total_new
                else:
                    walk(v, fname)
            if "start_frame" in o and "end_frame" in o:
                n = o["end_frame"] - o["start_frame"]
                if "frame_count" in o: o["frame_count"] = n
                if "duration_frames" in o: o["duration_frames"] = n
                if "duration_s" in o: o["duration_s"] = round(n / fps, 3)
            elif "start_s" in o and "end_s" in o and "duration_s" in o:
                o["duration_s"] = round(o["end_s"] - o["start_s"], 3)
        elif isinstance(o, list):
            for x in o:
                walk(x, fname)

    for fn in _RETIME_FILES:
        p = package_dir / fn
        if not p.is_file():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        walk(d, fn)
        if fn == "storyboard.json":
            d["total_frames"] = total_new
            d["duration_s"] = round(total_new / fps, 3)
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"fps": fps, "total_frames": total_new, "duration_s": round(total_new / fps, 3), "shots": [{"shot_id": s, "start_frame": a, "end_frame": b} for s, a, b in new_bounds]}
