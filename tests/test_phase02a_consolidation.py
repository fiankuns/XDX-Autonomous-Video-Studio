"""Phase 02A consolidation: reusable assets, style binding, workflow modules, delivery gate (no render needed)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest

from intelligence import visual_workflow as vw

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "projects" / "bench_p02a_ac_15s"
SCENE = ROOT / "engines/web/phase02a_ac15s/scene.js"
DEPS = ROOT / "engines/web/phase02a_ac15s/render_dependencies.json"


def _copy_pkg(tmp_path: Path) -> Path:
    dst = tmp_path / "pkg"
    shutil.copytree(PKG, dst, ignore=shutil.ignore_patterns(".*", "renders"))
    return dst


def test_p02a_cons_01_scene_uses_core_modules_and_bible_palette() -> None:
    src = SCENE.read_text(encoding="utf-8")
    assert "xdx_core/kit.js" in src and "bindCharacterPalette" in src and "createAssetLoadBarrier" in src
    bible = json.loads((PKG / "character_bible.json").read_text(encoding="utf-8"))
    for colour in bible["characters"][0]["color_palette"]:
        assert colour.lower() not in src.lower(), f"locked palette colour {colour} must come from the bible, not the scene"
    assert not re.search(r"function make(Bima|IndoorAC)\(", src)
    for f in ("kit", "comets", "timeline", "barrier", "style_binding"):
        assert (ROOT / f"engines/web/xdx_core/{f}.js").is_file()
    binding = (ROOT / "engines/web/xdx_core/style_binding.js").read_text(encoding="utf-8")
    assert "throw new Error" in binding  # fail closed when the palette is missing


def test_p02a_cons_02_asset_registry_and_bindings() -> None:
    reg = json.loads((ROOT / "registry/asset_registry.json").read_text(encoding="utf-8"))
    jsonschema.validate(reg, json.loads((ROOT / "schemas/asset_registry.schema.json").read_text(encoding="utf-8")))
    by_id = {a["asset_id"]: a for a in reg["assets"]}
    bind = json.loads((PKG / "asset_bindings.json").read_text(encoding="utf-8"))
    for b in bind["bindings"]:
        assert b["status"] in vw.FINAL_ASSET_STATUSES and (ROOT / b["module"]).is_file()
        if b["registry"]:
            a = by_id[b["asset_id"]]
            assert a["is_placeholder"] is False and a["origin_type"] == "procedural_generated"
    deps = json.loads(DEPS.read_text(encoding="utf-8"))
    for a in deps["assets"].values():
        assert (ROOT / a["file"]).is_file()


def test_p02a_cons_03_input_validation(tmp_path: Path) -> None:
    assert vw.validate_inputs(PKG)["status"] == "OK"
    bad = _copy_pkg(tmp_path)
    (bad / "style_bible.json").unlink()
    r = vw.validate_inputs(bad, check_environment=False)
    assert r["status"] == "BLOCKED" and r["issues"][0]["code"] == "INPUT_MISSING_FILE"
    cb = json.loads((bad / "character_bible.json").read_text(encoding="utf-8"))
    (bad / "style_bible.json").write_text(json.dumps({"style_bible_id": "other"}), encoding="utf-8")
    cb["characters"][0]["color_palette"] = ["red"]
    (bad / "character_bible.json").write_text(json.dumps(cb), encoding="utf-8")
    codes = {i["code"] for i in vw.validate_inputs(bad, check_environment=False)["issues"]}
    assert {"INPUT_STYLE_MISMATCH", "INPUT_CHARACTER_PALETTE"} <= codes


def test_p02a_cons_04_canonical_timeline_and_chapters(tmp_path: Path) -> None:
    tl = vw.canonical_timeline(PKG)
    assert tl["total_frames"] == 450 and tl["shots"][-1]["end_frame"] == 450 and len(tl["cues"]) == 8
    ch = vw.plan_chapters(tl, max_chapter_seconds=8)
    assert len(ch["chapters"]) >= 2 and ch["total_frames"] == tl["total_frames"] and "timeline_2" not in ch
    with pytest.raises(ValueError):
        vw.verify_chapters(tl, [{"chapter_id": "X", "start_frame": 0, "end_frame": 100}, {"chapter_id": "Y", "start_frame": 120, "end_frame": 450}])
    bad = _copy_pkg(tmp_path)
    sb = json.loads((bad / "storyboard.json").read_text(encoding="utf-8"))
    sb["shots"][1]["start_frame"] += 3
    (bad / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    with pytest.raises(ValueError):
        vw.canonical_timeline(bad)


def test_p02a_cons_05_semantic_contract_and_shot_evidence(tmp_path: Path) -> None:
    c = vw.semantic_contract(PKG)
    assert c["status"] == "OK" and len(c["beats"]) == 4 and all(b["required_actions"] and b["caption_windows"] for b in c["beats"])
    frames = tmp_path / "frames"
    frames.mkdir()
    for b in c["beats"]:
        for f in b["evidence_frames"]:
            (frames / f"f{f:04d}.png").write_bytes(b"png%d" % f)
    ev = vw.build_shot_evidence(c, frames, "abc")
    assert vw.verify_shot_evidence(c, ev, "abc") == []
    assert vw.verify_shot_evidence(c, ev, "other")[0]["code"] == "EVIDENCE_RENDER_HASH"
    ev["shots"][0]["frames"][0]["sha256"] = None
    assert any(i["code"] == "EVIDENCE_MISSING_FRAME" for i in vw.verify_shot_evidence(c, ev, "abc"))
    ev["shots"][1]["frames"] = []
    assert any(i["code"] == "EVIDENCE_MISSING_SHOT" for i in vw.verify_shot_evidence(c, ev, "abc"))


def test_p02a_cons_06_selective_rerender(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    for n in ("glob.js", "bima.js", "ac.js"):
        (root / "a" / n).write_text(n, encoding="utf-8")
    deps = {"global": ["a/glob.js"], "assets": {"bima": {"file": "a/bima.js", "shots": ["S001", "S002"]}, "ac": {"file": "a/ac.js", "shots": ["S001", "S002", "S003", "S004"]}}, "shot_files": {}}
    base = vw.shot_input_hashes(PKG, deps, root=root)
    assert vw.plan_selective_rerender(base, base)["rerender"] == []
    (root / "a/bima.js").write_text("changed", encoding="utf-8")
    assert vw.plan_selective_rerender(vw.shot_input_hashes(PKG, deps, root=root), base)["rerender"] == ["S001", "S002"]
    (root / "a/glob.js").write_text("changed", encoding="utf-8")
    assert len(vw.plan_selective_rerender(vw.shot_input_hashes(PKG, deps, root=root), base)["rerender"]) == 4
    pkg2 = _copy_pkg(tmp_path)
    cap = json.loads((pkg2 / "caption_audio_plan.json").read_text(encoding="utf-8"))
    next(c for c in cap["cues"] if c["shot_id"] == "S003")["text"] += " ya"
    (pkg2 / "caption_audio_plan.json").write_text(json.dumps(cap), encoding="utf-8")
    (root / "a/bima.js").write_text("bima.js", encoding="utf-8")
    (root / "a/glob.js").write_text("glob.js", encoding="utf-8")
    assert vw.plan_selective_rerender(vw.shot_input_hashes(pkg2, deps, root=root), base)["rerender"] == ["S003"]


def test_p02a_cons_07_caption_safe_area() -> None:
    ok = {"frame": 10, "x": 90, "y": 1400, "w": 900, "h": 160}
    assert vw.check_caption_safe_area([ok]) == []
    assert vw.check_caption_safe_area([{**ok, "x": 20}])[0]["code"] == "CAPTION_OUTSIDE_HORIZONTAL_SAFE_AREA"
    assert any(i["code"] == "CAPTION_OUTSIDE_VERTICAL_SAFE_AREA" for i in vw.check_caption_safe_area([{**ok, "y": 1850}]))


def test_p02a_cons_08_delivery_blocks_placeholder_and_missing_evidence(tmp_path: Path) -> None:
    mp4 = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=64x64:r=30:d=1", "-pix_fmt", "yuv420p", "-an", str(mp4)], check=True)
    sha = vw._sha256_file(mp4)
    manifest = {"output_sha256": sha, "delivery_profile": "VISUAL_ONLY_BENCHMARK", "scene_sha256": {"scene.js": "x"}}
    bindings = {"bindings": [{"asset_id": "prop_x", "module": "engines/web/phase02a_ac15s/scene.js", "status": "PLACEHOLDER"}]}
    r = vw.validate_delivery(mp4, package_dir=PKG, render_manifest=manifest, asset_bindings=bindings, evidence=None, review_result=None, safe_area_report=None)
    codes = {i["code"] for i in r["issues"]}
    assert r["status"] == "BLOCKED"
    assert {"DELIVERY_PLACEHOLDER_ASSET", "DELIVERY_NO_SHOT_EVIDENCE", "DELIVERY_NO_INDEPENDENT_REVIEW", "DELIVERY_RESOLUTION", "DELIVERY_FRAME_COUNT", "DELIVERY_NO_SAFE_AREA_REPORT"} <= codes
    manifest["output_sha256"] = "0" * 64
    r2 = vw.validate_delivery(mp4, package_dir=PKG, render_manifest=manifest, asset_bindings={"bindings": []}, evidence=None, review_result={"overall_status": "HARD_FAIL"}, safe_area_report=[])
    assert {"DELIVERY_HASH_MISMATCH", "DELIVERY_REVIEW_NOT_PASS"} <= {i["code"] for i in r2["issues"]}


def test_p02a_cons_09_guard_covers_preview_modes() -> None:
    from scripts.execution_guard_hook import decide

    for flag in ("--animatic", "--shot S002", "--preview", "--frames 1,2"):
        ok, reason = decide({"tool_name": "bash", "arguments": {"command": f"python3 scripts/render_phase02a_visual.py projects/bench_p02a_ac_15s --prototype --out /tmp/x {flag}"}})
        assert ok is False, f"{flag} must stay behind the execution guard ({reason})"
    ok, _ = decide({"tool_name": "bash", "arguments": {"command": "python3 scripts/visual_workflow.py validate-inputs projects/bench_p02a_ac_15s"}})
    assert ok is True  # read-only checks are not render commands


def _can_render() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return bool((shutil.which("google-chrome") or shutil.which("chromium")) and shutil.which("ffmpeg")
                and (ROOT / "node_modules" / "three").is_dir() and (ROOT / "node_modules" / "@fontsource" / "plus-jakarta-sans").is_dir())


@pytest.mark.skipif(not _can_render(), reason="headless Chrome/Playwright not available")
def test_p02a_cons_10_pixel_regression_against_latest_benchmark(tmp_path: Path) -> None:
    bench = json.loads((ROOT / "docs/evidence/phase02a_visual_only/regression_benchmark_v7.json").read_text(encoding="utf-8"))
    frames = [10, 140, 260, 400]
    out = tmp_path / "frames"
    res = subprocess.run(["python3", str(ROOT / "scripts/render_phase02a_visual.py"), str(PKG), "--prototype", "--out", str(out),
                          "--frames", ",".join(map(str, frames))], capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr[-500:]
    for f in frames:
        assert vw._sha256_file(out / f"bench_p02a_ac_15s_f{f:04d}.png") == bench["frame_sha256"][str(f)], f"frame {f} drifted from the latest benchmark"


def test_p02a_cons_11_production_and_error_memory_seed(tmp_path: Path) -> None:
    from memory.persistent_memory import SixPartitionMemoryStore
    from memory.seed_loader import load_production_seed

    store = SixPartitionMemoryStore(tmp_path / "m.sqlite3")
    n = load_production_seed(store)
    assert n["techniques"] >= 15 and n["errors"] >= 12
    t = store.production.get_technique("level_camera_cut_on_action", "v4.0")
    assert t and t["test_status"] == "RENDER_TESTED" and t["payload"]["topic_agnostic"] is True
    errs = store.error.list_errors("xdx_global")
    assert {"p02a_camera_roll_from_up_lerp", "p02a_first_render_primitive_assets"} <= {e["error_id"] for e in errs}
    seeds = (ROOT / "memory/seed_knowledge")
    text = (seeds / "production_techniques_v4.json").read_text(encoding="utf-8") + (seeds / "error_lessons_v4.json").read_text(encoding="utf-8")
    assert "topic_agnostic" in text
    for t_ in json.loads((seeds / "production_techniques_v4.json").read_text(encoding="utf-8"))["techniques"]:
        for ref in t_["tests"]:
            f, _, fn = ref.partition("::")
            assert fn in (ROOT / f).read_text(encoding="utf-8"), f"technique {t_['technique_id']} cites a missing test {ref}"


def test_p02a_cons_12_action_choreography_constraints_catch_wrong_acting() -> None:
    from intelligence import action_choreography as ac

    spec = ac.load_action_events(PKG)
    jsonschema.validate(spec, json.loads((ROOT / "schemas/action_events.schema.json").read_text(encoding="utf-8")))
    cues = vw.canonical_timeline(PKG)["cues"]
    fan = next(e for e in spec["events"] if e["event_id"] == "AE-S001-FAN")
    frames = ac.event_frames(fan, cues)

    def probe(fan_dir, fan_pos=(0.0, 0.0, 0.3), head_dir=(0.0, 0.0, 1.0)):
        return {"fan_center": {"p": list(fan_pos), "d": list(fan_dir)}, "face_center": {"p": [0.0, 0.0, 0.0]},
                "head_pos": {"p": [0.0, 0.0, 0.0], "d": list(head_dir)}, "ac_sensor": {"p": [-2.0, 0.0, 0.0]}}

    good = {f: probe((0.0, 0.0, -1.0)) for f in frames}                      # blade face points back at the face
    assert ac.evaluate_events({"events": [fan]}, cues, good)["status"] == "OK"
    wrong_dir = {f: probe((0.0, 0.0, 1.0)) for f in frames}                   # blade face points away from the face (the v6 bug)
    assert ac.evaluate_events({"events": [fan]}, cues, wrong_dir)["status"] == "BLOCKED"
    far = {f: probe((0.0, 0.0, -1.0), fan_pos=(0.0, 0.0, 1.5)) for f in frames}  # fan nowhere near the face
    assert ac.evaluate_events({"events": [fan]}, cues, far)["status"] == "BLOCKED"
    early_turn = {f: probe((0.0, 0.0, -1.0), head_dir=(-1.0, 0.0, 0.0)) for f in frames}  # head already looks at the AC in S001
    assert ac.evaluate_events({"events": [fan]}, cues, early_turn)["status"] == "BLOCKED"


@pytest.mark.skipif(not _can_render(), reason="headless Chrome/Playwright not available")
def test_p02a_cons_13_actions_verified_on_the_real_scene() -> None:
    from intelligence import action_choreography as ac
    from scripts.render_phase02a_visual import load_package_data, probe_frames

    spec = ac.load_action_events(PKG)
    tl = vw.canonical_timeline(PKG)
    rep = ac.evaluate_events(spec, tl["cues"], probe_frames(load_package_data(PKG), ac.needed_frames(spec, tl["cues"])))
    assert rep["status"] == "OK", rep["issues"]
