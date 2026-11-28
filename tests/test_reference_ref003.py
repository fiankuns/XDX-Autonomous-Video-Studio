"""REF-003 (cinematic documentary): media integrity, registry/routing, technique vs style separation, honest status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from intelligence.reference_database_bridge import ReferenceDatabaseBridge, route_references_for_shots
from intelligence.reference_lifecycle import MultiReferenceFusionEngine

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "reference_database"
SHA = "6763efe27a2f312acedd15cb4f1663413fff533a99a4fd77de3686838d4bec87"
FOLDER = DB / "references/documentary/REF-003-Javan-Rhino-Krakatau"


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_ref003_01_media_hash_size_and_probe_recorded():
    mp4 = FOLDER / "original.mp4"
    h = hashlib.sha256()
    with mp4.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    assert h.hexdigest() == SHA and mp4.stat().st_size == 10302125
    meta = _j(FOLDER / "metadata.json")
    v = meta["ffprobe"]["streams"][0]
    assert (v["width"], v["height"], v["avg_frame_rate"]) == (1280, 720, "30/1") and meta["ffprobe"]["format"]["duration"].startswith("64.36")
    assert "filter=lfs" in (DB / ".gitattributes").read_text(encoding="utf-8")


def test_ref003_02_registry_and_previous_references_unchanged():
    refs = {r["id"]: r for r in _j(DB / "reference_registry.json")["references"]}
    assert set(refs) == {"REF-001", "REF-002", "REF-003"}
    assert refs["REF-001"]["sha256"].startswith("12f9e1d9") and refs["REF-002"]["sha256"].startswith("042ad39d")
    assert refs["REF-003"]["sha256"] == SHA and refs["REF-003"]["profile_id"] == "cinematic_geo_documentary_v1"
    out = ReferenceDatabaseBridge().resolve_context(genres=["documentary"], require_media=True)
    assert out["selected_reference_ids"] == ["REF-003"] and out["all_media_verified"] and out["production_authorized"] is False


def test_ref003_03_genre_routing_keeps_old_defaults():
    b = ReferenceDatabaseBridge()
    assert b.resolve_context(genres=["dokumenter"])["selected_reference_ids"] == ["REF-003"]
    assert b.resolve_context(genres=["explainer"])["selected_reference_ids"] == ["REF-002"]
    assert b.resolve_context(genres=["satir sosial"])["selected_reference_ids"] == ["REF-001"]
    fused = b.resolve_context(genres=["explainer", "documentary"])
    assert set(fused["selected_reference_ids"]) == {"REF-002", "REF-003"}


def test_ref003_04_per_shot_multi_reference_routing():
    r = route_references_for_shots({"A": ["geographic_map", "population_visualization"], "B": ["historical_reconstruction"], "C": ["social_vignette"], "D": ["mystery_need"]})
    assert r["production_authorized"] is False
    assert r["shots"]["A"] == {"primary": "REF-003", "subordinate": [], "unknown_needs": []}
    assert r["shots"]["B"]["primary"] == "REF-003" and r["shots"]["B"]["subordinate"] == ["REF-002"]
    assert r["shots"]["C"]["primary"] == "REF-001"
    assert r["shots"]["D"]["primary"] is None and r["shots"]["D"]["unknown_needs"] == ["mystery_need"]


REQUIRED = {"doc_historical_reconstruction", "doc_geo_terrain_map", "doc_geo_camera_navigation", "doc_geo_boundary_highlight", "doc_population_visualization", "doc_radial_wave", "doc_ocean_large_wave", "doc_volcanic_atmospheric_vfx", "doc_environmental_lighting", "doc_animal_visualization", "doc_object_highlight", "doc_environment_transformation", "doc_symbolic_visualization", "doc_animated_callouts", "doc_time_typography", "doc_narrative_misdirection_reveal_callback"}


def test_ref003_05_all_16_techniques_observed_not_render_tested_and_split_observed_vs_inferred():
    reg = _j(DB / "profiles/reference_technique_registry.json")
    techs = {t["technique_id"]: t for t in reg["techniques"]}
    assert set(techs) == REQUIRED
    for t in techs.values():
        assert t["status"] == "REFERENCE_OBSERVED" and t["promotion"]["promoted_to"] is None
        assert t["observed"] and all(o["t"] and o["what"] for o in t["observed"])
        assert t["inferred_method"]["basis"].startswith("INFERENCE_NOT_VERIFIED") and t["inferred_method"]["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    # reuse, not duplication: callouts/highlight map to the existing RENDER_TESTED callout system
    assert techs["doc_animated_callouts"]["maps_to_existing_capability"].startswith("callout_leader_ring_system")
    existing = {x["technique_id"]: x for x in _j(ROOT / "memory/seed_knowledge/production_techniques_v4.json")["techniques"]}
    assert "callout_leader_ring_system" in existing and not (REQUIRED & set(existing))


def test_ref003_06_technique_profile_is_style_independent():
    reg = _j(DB / "profiles/reference_technique_registry.json")
    assert {"stylized_3d", "diorama", "flat_cartoon", "anime_inspired", "realistic"} <= set(reg["style_adaptation_matrix"])
    rea = _j(FOLDER / "rea_analysis_v3_4.json")
    assert rea["animation_technique_profile"]["style_independent"] is True
    assert rea["visual_style_profile"]["status"] == "OBSERVED_NOT_TO_BE_COPIED"
    blob = json.dumps(reg["techniques"]).lower()
    for banned in ("#", "font-family", "hex"):
        assert banned not in blob, "technique entries must not carry colours/fonts of the reference"
    prof = next(p for p in _j(DB / "profiles/reference_pattern_registry.json")["profiles"] if p["id"] == "cinematic_geo_documentary_v1")
    assert prof["defaults"]["style"]["family"] == "user_selected_or_global_style_bible"
    assert prof["defaults"]["engine_routing"]["geographic_animation_simulation_particles_procedural_effects"] == "threejs"
    assert prof["defaults"]["pacing"]["max_shot_s"] <= 10


def test_ref003_07_honest_analysis_provenance_and_scope():
    rea = _j(FOLDER / "rea_analysis_v3_4.json")
    assert rea["analyzer_provenance"]["asr_transcription"].startswith("NOT_PERFORMED") and rea["analyzer_provenance"]["production_authorized"] is False
    assert rea["ten_dimension_analysis"]["09_narration_audio_and_sfx"]["deferred_to"] == "Phase 04"


def test_ref003_08_fusion_picks_ref003_for_geo_documentary_and_keeps_ref002_mechanism():
    b = ReferenceDatabaseBridge()
    recs = [b.verify_and_load_reference(r, require_media=False) for r in ("REF-002", "REF-003")]
    plan = MultiReferenceFusionEngine().fuse(recs, genres=["documentary", "geography"], chosen_style_profile="stylized_3d")
    assert plan["dimensions"]["camera"]["primary_reference_id"] == "REF-003"
    assert plan["dimensions"]["technical_visualization"]["primary_reference_id"] == "REF-003"
    plan2 = MultiReferenceFusionEngine().fuse(recs, genres=["explainer"], chosen_style_profile="stylized_3d")
    assert plan2["dimensions"]["technical_visualization"]["primary_reference_id"] == "REF-002"


# ---------------------------------------------------------------- Phase 02B.1 evidence honesty
def test_p02b1_evidence_separates_tested_from_detected_and_stores_no_secret():
    ev = _j(ROOT / "docs/evidence/phase02b1/blender_capability_probe.json")
    assert ev["mode"] == "READ_ONLY" and ev["production_authorized"] is False and ev["connection"]["credentials_stored"] is False
    assert ev["tested"] and ev["detected_only_not_exercised"] and ev["not_determined"] and ev["not_done_by_design"]
    assert "CYCLES" not in ev["detected_only_not_exercised"]["render_engines"]
    bench = _j(ROOT / "docs/benchmarks/bench_p02b_char_10s.json")
    assert bench["status"] == "PLANNED_NOT_EXECUTED" and bench["requires_user_approval_before_execution"] is True
    assert bench["total_frames"] == 300 == bench["duration_s"] * bench["fps"] and bench["audio"].startswith("DEFERRED_PHASE_04")
    spans = [s["frames"] for s in bench["shots"]]
    assert spans[0][0] == 0 and spans[-1][1] == 300 and all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
    blob = "".join((ROOT / p).read_text(encoding="utf-8") for p in ("docs/evidence/phase02b1/blender_capability_probe.json", "docs/benchmarks/bench_p02b_char_10s.json", "docs/PHASE_02B1_BLENDER_CAPABILITY_REPORT.md"))
    assert "Bearer" not in blob and "trycloudflare" not in blob


def test_p02b2_script_is_unexecuted_draft_and_not_wired_into_runners():
    import py_compile

    script = ROOT / "engines/blender_scripts/phase02b2_bima_rig.py"
    py_compile.compile(str(script), doraise=True)
    src = script.read_text(encoding="utf-8")
    assert "UNTESTED, NOT EXECUTED" in src and "blender_scene_mutation" in src
    for p in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "engines").glob("*.py")) + list((ROOT / "orchestration").glob("*.py")):
        if p.name == "prepare_phase02b_benchmark.py":  # pins the file's hash only; must not import or run it
            body = p.read_text(encoding="utf-8")
            assert "import phase02b2_bima_rig" not in body and "runpy" not in body and "exec(" not in body
            continue
        assert "phase02b2_bima_rig" not in p.read_text(encoding="utf-8"), f"{p} must not call the 02B.2 draft"
    from governance import trusted_approval as ta

    assert ta.PHASE02_EXECUTION_ENABLED is False


def test_p02b_package_waits_for_approval_and_digest_matches_signing_tool():
    import subprocess
    import sys

    pk = ROOT / "projects/bench_p02b_char_10s"
    st = _j(pk / "project_state.json")
    assert st["current_state"] == "WAITING_APPROVAL" and st["approval_status"]["approved"] is False
    out = subprocess.run([sys.executable, str(ROOT / "scripts/trusted_approval.py"), "digest", "--package", str(pk)], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["manifest_digest"] == st["package_digest"] == _j(pk / "approval_package_manifest.json")["package_digest"]
    sb = _j(pk / "storyboard.json")
    assert sb["total_frames"] == 300 and len(sb["shots"]) == 3
    scope = _j(pk / "delivery_scope.json")
    assert scope["audio"]["deferred_to_phase"] == "04" and scope["blender"]["render_allowed"] is False and scope["blender"]["proposed_signed_scope"] == "blender_scene_mutation"
    assert _j(pk / "reference_adaptation.json") is not None
    assert _j(pk / ".reviews/independent_preproduction_review_v4.json")["verdict"] == "PASS"
