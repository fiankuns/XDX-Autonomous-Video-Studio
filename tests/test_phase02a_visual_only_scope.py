"""Phase 02A scope revision — VISUAL_ONLY_BENCHMARK (audio deferred to Phase 04) + Independent Visual QC."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from engines.web_engines import RemotionEngine
from governance import phase_scope as ps
from intelligence.visual_qc_engine import VisualQualityControlEngine
from intelligence.visual_semantic_qc import (
    REFERENCE_DIMENSIONS,
    SHOT_DIMENSIONS,
    build_visual_review_checklist,
    evaluate_visual_review,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
BENCH = ROOT_DIR / "projects" / "bench_p02a_ac_15s"
EVIDENCE = ROOT_DIR / "docs" / "evidence" / "phase02a_visual_only"
HOOK = ROOT_DIR / "scripts" / "execution_guard_hook.py"
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _mp4(tmp_path: Path, name: str, audio: str | None) -> Path:
    out = tmp_path / name
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=216x384:rate=30:duration=1"]
    if audio == "silent":
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-c:a", "aac"]
    elif audio == "tone":
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    return out


def _hook(event: dict) -> tuple[int, dict]:
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True, cwd=ROOT_DIR)
    return p.returncode, json.loads(p.stdout)


# ----------------------------------------------------------------------------- scope policy
def test_p02a_vo_01_audio_capabilities_deferred_to_phase04() -> None:
    for cap in ps.DEFERRED_AUDIO_CAPABILITIES:
        with pytest.raises(ps.PhaseScopeDeferredError):
            ps.assert_capability_in_scope(cap)
    ps.assert_capability_in_scope("mechanism_visualization")
    ps.assert_capability_in_scope("tts", phase="04")
    pol = ps.audio_policy()
    assert pol["delivery_profile"] == "VISUAL_ONLY_BENCHMARK" and pol["audio_track"] == "OMIT"
    assert pol["missing_audio_is_defect"] is False and pol["captions_represent_narration"] is True
    for tool in ("creative_generate_speech", "text_to_speech", "generate_music", "lip_sync_character", "creative_design_voice"):
        assert ps.classify_audio_tool(tool), tool
    for tool in ("create_primitive", "look", "execute_blender_code"):
        assert not ps.classify_audio_tool(tool), tool
    for cmd in ("rhubarb -o v.json vo.wav", "piper --model id.onnx", "ffmpeg -i a.mp4 -af loudnorm out.mp4",
                "ffmpeg -i x.mp4 -c:a aac y.mp4", "faster-whisper vo.wav"):
        assert ps.classify_audio_command(cmd), cmd
    for cmd in ("ls projects", "ffmpeg -i in.mp4 -an -c:v copy out.mp4", "git status"):
        assert not ps.classify_audio_command(cmd), cmd


def test_p02a_vo_02_guard_hook_blocks_audio_work_and_keeps_render_gate() -> None:
    rc, out = _hook({"tool_name": "creative_generate_speech", "arguments": {}})
    assert rc == 2 and "PhaseScopeDeferredError" in out["reason"]
    rc, out = _hook({"tool_name": "bash", "arguments": {"CommandLine": "rhubarb -o out.json vo.wav"}})
    assert rc == 2 and "Phase 04" in out["reason"]
    rc, _ = _hook({"tool_name": "bash", "arguments": {"command": "ls projects"}})
    assert rc == 0
    # Visual-only scope does NOT open rendering: a muted Remotion render is still guarded by trusted approval.
    rc, out = _hook({"tool_name": "bash", "arguments": {"command": "npx remotion render XDXMaster out.mp4 --muted"}})
    assert rc == 2 and "PhaseScopeDeferredError" not in out["reason"]


def test_p02a_vo_03_remotion_composition_exports_without_audio_track() -> None:
    sb = json.loads((BENCH / "storyboard.json").read_text(encoding="utf-8"))
    cap = json.loads((BENCH / "caption_audio_plan.json").read_text(encoding="utf-8"))
    vo = RemotionEngine().compile_master_composition(sb, cap)
    assert vo["deliveryProfile"] == "VISUAL_ONLY_BENCHMARK" and vo["audioSpec"] is None
    assert vo["renderOptions"]["muted"] is True and "audioCodec" not in vo["renderOptions"]
    assert vo["captionCount"] == len(cap["cues"]) > 0  # captions still carry the narration
    master = RemotionEngine().compile_master_composition(sb, cap, delivery_profile="MASTER_WITH_AUDIO")
    assert master["renderOptions"]["audioCodec"] == "aac" and master["audioSpec"]["targetLufs"] == -15.0


# ----------------------------------------------------------------------------- technical QC audio policy
@needs_ffmpeg
def test_p02a_vo_04_technical_qc_audio_policy(tmp_path: Path) -> None:
    qc = VisualQualityControlEngine()
    no_audio = qc.evaluate_video(_mp4(tmp_path, "na.mp4", None), delivery_profile="VISUAL_ONLY_BENCHMARK")
    assert no_audio["overall_status"] == "PASS" and no_audio["defects"] == []
    assert no_audio["audio_policy"]["audio_track_present"] is False

    silent = qc.evaluate_video(_mp4(tmp_path, "si.mp4", "silent"), delivery_profile="VISUAL_ONLY_BENCHMARK")
    assert silent["overall_status"] == "WARN"
    assert [(d["defect_id"], d["severity"]) for d in silent["defects"]] == [("DEF_UNNECESSARY_SILENT_AUDIO_TRACK", "low")]

    tone = qc.evaluate_video(_mp4(tmp_path, "to.mp4", "tone"), delivery_profile="VISUAL_ONLY_BENCHMARK")
    assert tone["overall_status"] == "WARN" and tone["defects"][0]["defect_id"] == "DEF_AUDIO_OUT_OF_PHASE_SCOPE"

    with pytest.raises(ValueError):
        qc.evaluate_video(tmp_path / "na.mp4", delivery_profile="VISUAL_ONLY_BENCHMARK", require_audio=True)

    # The master profile (Phase 04) keeps the strict audio rules.
    assert qc.evaluate_video(tmp_path / "na.mp4", delivery_profile="MASTER_WITH_AUDIO")["overall_status"] == "HARD_FAIL"
    assert qc.evaluate_video(tmp_path / "si.mp4", delivery_profile="MASTER_WITH_AUDIO")["overall_status"] == "HARD_FAIL"


# ----------------------------------------------------------------------------- independent visual QC
def _good_review(chk: dict, render_sha: str) -> dict:
    return {
        "schema": "xdx.independent-visual-review.v1",
        "project_id": chk["project_id"],
        "reviewer_id": "visual_critic_fresh",
        "reviewer_context": "fresh",
        "render_sha256": render_sha,
        "shots": [
            {
                "shot_id": s["shot_id"],
                "frames_inspected": s["frames_to_inspect"],
                "action_evidence": [
                    {"index": a["index"], "visible": True, "frame": s["frames_to_inspect"][1]} for a in s["required_actions"]
                ],
                "placeholder_assets": [],
                "debug_overlay_visible": False,
                "render_artifacts": [],
                "caption_occludes_subject": False,
                "subject_clipped_by_frame": False,
                "scores": {d: 4.0 for d in SHOT_DIMENSIONS},
                "caption_sync_evidence": [
                    {"cue_id": c["cue_id"], "visible": True, "frame": c["inspect_frame"]} for c in s["caption_sync"]
                ],
            }
            for s in chk["shots"]
        ],
        "reference_comparison": {"reference_id": "REF-002", "scores": {d: 3.5 for d in REFERENCE_DIMENSIONS}},
    }


def test_p02a_vo_05_checklist_derives_caption_to_visual_contract() -> None:
    chk = build_visual_review_checklist(BENCH)
    assert chk["delivery_profile"] == "VISUAL_ONLY_BENCHMARK" and chk["audio_in_scope"] is False
    assert [s["shot_id"] for s in chk["shots"]] == ["S001", "S002", "S003", "S004"]
    assert chk["reference_comparison"]["reference_id"] == "REF-002"
    for s in chk["shots"]:
        lo, hi = s["frame_range"]
        assert s["captions"] and s["required_actions"] and s["required_assets"]
        assert all(lo <= f < hi for f in s["frames_to_inspect"]) and len(s["frames_to_inspect"]) == 3
        assert any(a["clause_text"] for a in s["required_actions"])  # tied to the caption/narration clause
        assert s["caption_sync"] and all(c["text"] in s["captions"] for c in s["caption_sync"])
        for c in s["caption_sync"]:
            wa, wb = c["frame_window"]
            assert lo <= wa < wb <= hi and wa <= c["inspect_frame"] < wb
    assert any("kisi" in a["action"] for a in chk["shots"][1]["required_actions"])


def test_p02a_vo_06_independent_review_rules(tmp_path: Path) -> None:
    chk = build_visual_review_checklist(BENCH)
    render = tmp_path / "r.mp4"
    render.write_bytes(b"fake-render-bytes")
    sha = hashlib.sha256(render.read_bytes()).hexdigest()
    good = _good_review(chk, sha)
    assert evaluate_visual_review(chk, good, producer_ids={"render_agent"}, render_path=render)["status"] == "PASS"

    self_rev = evaluate_visual_review(chk, good, producer_ids={"visual_critic_fresh"}, render_path=render)
    assert self_rev["status"] == "HARD_FAIL" and self_rev["defects"][0]["defect_id"] == "DEF_VQC_SELF_REVIEW"

    other = tmp_path / "other.mp4"
    other.write_bytes(b"different")
    assert evaluate_visual_review(chk, good, producer_ids=set(), render_path=other)["status"] == "HARD_FAIL"

    def mutate(fn):
        r = copy.deepcopy(good)
        fn(r)
        return evaluate_visual_review(chk, r, producer_ids={"render_agent"}, render_path=render)

    res = mutate(lambda r: r["shots"][1]["action_evidence"][0].update(visible=False))
    assert res["status"] == "HARD_FAIL" and any(d["defect_id"] == "DEF_VQC_SEMANTIC_MISMATCH" for d in res["defects"])
    assert mutate(lambda r: r["shots"][0].update(placeholder_assets=["char_bima"]))["status"] == "HARD_FAIL"
    assert mutate(lambda r: r["shots"][2].update(debug_overlay_visible=True))["status"] == "HARD_FAIL"
    assert mutate(lambda r: r["shots"][2].update(render_artifacts=["stray grey plane"]))["status"] == "HARD_FAIL"
    assert mutate(lambda r: r["shots"][3]["scores"].update(lighting_shadow_material_texture=2.0))["status"] == "HARD_FAIL"
    assert mutate(lambda r: r["reference_comparison"]["scores"].update({d: 2.0 for d in REFERENCE_DIMENSIONS}))["status"] == "HARD_FAIL"
    assert mutate(lambda r: r["shots"][0].update(caption_occludes_subject=True))["status"] == "WARN"
    assert mutate(lambda r: r["shots"].pop())["status"] == "INCOMPLETE"
    assert mutate(lambda r: r["shots"][0].update(frames_inspected=[]))["status"] == "INCOMPLETE"
    assert mutate(lambda r: r["shots"][0].pop("debug_overlay_visible"))["status"] == "INCOMPLETE"
    assert mutate(lambda r: r.update(reviewer_context="producer"))["status"] == "INCOMPLETE"
    assert mutate(lambda r: r["reference_comparison"].update(reference_id="REF-001"))["status"] == "INCOMPLETE"
    # caption <-> visual sync (visual may lead its caption by <= 0.3 s and must appear before the caption ends)
    res = mutate(lambda r: r["shots"][1]["caption_sync_evidence"][1].update(visible=False))
    assert res["status"] == "HARD_FAIL" and any(d["defect_id"] == "DEF_VQC_CAPTION_VISUAL_MISMATCH" for d in res["defects"])
    late = chk["shots"][1]["caption_sync"][1]["frame_window"][1] + 2
    res = mutate(lambda r: r["shots"][1]["caption_sync_evidence"][1].update(frame=late))
    assert res["status"] == "HARD_FAIL" and any(d["defect_id"] == "DEF_VQC_CAPTION_SYNC_WINDOW" for d in res["defects"])
    assert mutate(lambda r: r["shots"][2].pop("caption_sync_evidence"))["status"] == "INCOMPLETE"


def test_p02a_vo_07_recorded_review_of_first_test_render_is_hard_fail(tmp_path: Path) -> None:
    """Evidence: the first Phase 02A AC test render (user-supplied) fails the semantic gate, not only by opinion."""
    import shutil

    from intelligence.visual_workflow import retime_package

    old = tmp_path / "bench_p02a_ac_15s_original_timing"            # the review was recorded against the original 15 s timeline
    shutil.copytree(BENCH, old)
    retime_package(old, {"S001": 3.5, "S002": 3.5})
    chk = build_visual_review_checklist(old)
    review = json.loads((EVIDENCE / "independent_visual_review_ac15s.json").read_text(encoding="utf-8"))
    res = evaluate_visual_review(chk, review, producer_ids={"phase02a_render_agent"})
    # The first review predates the v2 caption-sync rule: its only gaps may be missing caption_sync_evidence.
    assert res["status"] == "HARD_FAIL" and all("caption_sync_evidence" in g for g in res["review_gaps"])
    ids = {d["defect_id"] for d in res["defects"]}
    assert {"DEF_VQC_SEMANTIC_MISMATCH", "DEF_VQC_PLACEHOLDER_ASSET", "DEF_VQC_DEBUG_OVERLAY", "DEF_VQC_BELOW_REFERENCE"} <= ids
    stored = json.loads((EVIDENCE / "independent_visual_qc_result_ac15s.json").read_text(encoding="utf-8"))
    assert stored["status"] == "HARD_FAIL" and stored["reference_mean_score"] == res["reference_mean_score"]
