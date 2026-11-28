#!/usr/bin/env python3
"""Prepare the Phase 02B 10-second character-animation benchmark PACKAGE (planning only, stops at WAITING_APPROVAL).

No Blender call, no render, no approval: it builds the package through the existing preproduction workflow, pins its
dependencies and prints the canonical digest that the human signs with scripts/trusted_approval.py.
Scope proposed for the signature: blender_scene_mutation (02B.2 asset + rig) only.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from governance.canonical_manifest import build_canonical_manifest, build_production_dependencies_manifest, manifest_digest
from intelligence.state_and_approval import ProjectStateManager
from orchestration.preproduction_workflow import PreproductionMultiAgentWorkflow

BENCH_ID = "bench_p02b_char_10s"
SRC_PAYLOAD = ROOT_DIR / "projects" / "bench_p02a_ac_15s" / "authored_creative_payload.json"
DEPENDENCIES = [
    "package.json", "package-lock.json",
    "engines/blender_xdx_engine.py", "engines/blender_scripts/phase02b2_bima_rig.py",
    "engines/web/remotion_timeline_spec.mjs", "engines/ffmpeg_engine.py",
    "engines/web/xdx_core/callouts.js", "engines/web/xdx_core/rig_ik.js",
    "governance/canonical_manifest.py", "governance/trusted_approval.py", "governance/phase_scope.py", "scripts/execution_guard_hook.py",
    "intelligence/visual_qc_engine.py", "intelligence/visual_semantic_qc.py", "intelligence/visual_workflow.py",
    "intelligence/action_choreography.py", "intelligence/shot_spec.py",
    "docs/benchmarks/bench_p02b_char_10s.json", "docs/PHASE_02B1_BLENDER_CAPABILITY_REPORT.md",
    "reference_database/profiles/reference_pattern_registry.json", "reference_database/profiles/reference_technique_registry.json",
    "reference_database/references/social_satire/REF-001/rea_analysis_v3_4.json",
    "reference_database/references/explainer/REF-002-Yakhchal/rea_analysis_v3_4.json",
    "reference_database/references/documentary/REF-003-Javan-Rhino-Krakatau/rea_analysis_v3_4.json",
]
DELIVERY_SCOPE = {
    "schema": "xdx.delivery-scope.v1", "project_id": BENCH_ID, "phase": "02B", "delivery_profile": "VISUAL_ONLY_BENCHMARK",
    "audio": {"in_scope": False, "deferred_to_phase": "04", "export_audio_track": False, "missing_audio_is_qc_failure": False,
              "planning_fields_ignored_in_02A": ["audio_events", "sfx_cues", "audio_master_preset_id", "target_lufs", "music_direction", "ambience"]},
    "captions_represent_narration": True,
    "blender": {"proposed_signed_scope": "blender_scene_mutation", "stage": "02B.2 asset+rig only", "render_allowed": False,
                "mobile_guard": {"max_render_resolution": 640, "max_render_samples": 32, "anr_budget_ms": 3500, "engine": "BLENDER_EEVEE"}},
    "visual_qc": {"technical": "intelligence/visual_qc_engine.py", "independent_semantic": "intelligence/visual_semantic_qc.py via scripts/visual_review.py",
                  "reference_comparison": ["REF-001", "REF-002", "REF-003"]},
}


def build_payload() -> dict:
    p = copy.deepcopy(json.loads(SRC_PAYLOAD.read_text(encoding="utf-8")))
    p["project_id"] = BENCH_ID
    p["topic_title"] = "Bima dan AC: Uji Animasi Karakter Blender 10 Detik"
    p["reference_ids"] = ["REF-001", "REF-002", "REF-003"]
    p["target_duration_s"] = 10
    p["blueprint"]["premise"] = "Uji animasi karakter 10 detik untuk Blender: Bima kepanasan, menoleh ke AC, lalu menekan remot dan merasa lega, dengan penjelasan singkat kalor dipindahkan keluar."
    b = {x["beat_id"]: x for x in p["narrative_beats"]}
    b1, b2 = copy.deepcopy(b["B01"]), copy.deepcopy(b["B02"])
    b3 = copy.deepcopy(b["B03"])
    for beat, bid, dur, role in ((b1, "B01", 3.5, "hook_overheated_character"), (b2, "B02", 3.0, "turn_to_ac_then_cut"), (b3, "B03", 3.5, "macro_remote_press_relief")):
        beat["beat_id"], beat["target_duration_s"], beat["beat_role"] = bid, dur, role
        beat["act"], beat["sequence_id"], beat["scene_id"] = {"B01": ("ACT_1", "SEQ_01", "SCN_01"), "B02": ("ACT_2", "SEQ_01", "SCN_01"), "B03": ("ACT_3", "SEQ_02", "SCN_02")}[bid]
        beat["environment_id"] = "env_bedroom_tropical_sealed_3d"
        beat["shot_blueprints"][0]["preferred_engine"] = "blender"
        beat["shot_blueprints"][0]["is_cutaway"] = False
    b1["narration_vo"] = "AC tidak menciptakan dingin melainkan memindahkan panas kamarmu."
    b1["shot_blueprints"][0]["concrete_action"] = ("Bima mengipasi wajah dengan kipas lipat yang bergerak mengikuti pergelangan tangan kanan, tangan kiri "
        "menyeka dahi dengan siku terangkat, bulir keringat terlihat, di kamar tertutup 32 derajat Celsius di bawah prop_ac_indoor_evaporator_cutaway.")
    b2["narration_vo"] = "Saat tombol remot ditekan, kisi AC terbuka."
    b2["claim_refs"] = ["CLM_03"]
    b2["shot_blueprints"][0].update({"visual_purpose": "character_acting", "shot_size": "medium", "visual_subject": "Kepala Bima menoleh ke unit AC lalu bertahan sejenak sebelum cut pada aksi",
        "concrete_action": "Bima berhenti mengipasi, kepala menoleh ke prop_ac_indoor_evaporator_cutaway dan tangan kanan mengangkat prop_ac_remote_control, lalu jeda singkat sebelum cut.",
        "interaction_target_object_id": "prop_ac_remote_control", "props": ["prop_ac_remote_control", "prop_ac_indoor_evaporator_cutaway"], "scientific_labels": []})
    b3["narration_vo"] = "Panasnya dipindahkan keluar, kamar jadi sejuk."
    b3["claim_refs"] = ["CLM_01"]
    b3["emotion"] = "relieved"
    b3["shot_blueprints"][0].update({"visual_purpose": "character_acting", "shot_size": "medium", "focal_length_mm": 85,
        "visual_subject": "Close-up ibu jari Bima menekan tombol 24 derajat pada remot, label sinyal inframerah, ekspresi lega",
        "concrete_action": "Ibu jari kanan menekan tombol suhu 24 derajat pada prop_ac_remote_control, tombol menyala, label sinyal inframerah dengan garis dan cincin menunjuk sensor AC, cahaya bergeser dari hangat ke sejuk dan wajah Bima menjadi lega.",
        "interaction_target_object_id": "prop_ac_remote_control", "props": ["prop_ac_remote_control", "prop_ac_indoor_evaporator_cutaway"],
        "scientific_labels": ["Sinyal inframerah", "Setelan Target: 24°C"]})
    p["narrative_beats"] = [b1, b2, b3]
    return p


def finalize(pkg: Path, payload_title: str, genres: list[str]) -> dict:
    (pkg / "delivery_scope.json").write_text(json.dumps(DELIVERY_SCOPE, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dep = build_production_dependencies_manifest(ROOT_DIR, DEPENDENCIES)
    (pkg / "production_dependencies.json").write_text(json.dumps(dep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    man = build_canonical_manifest(pkg)
    digest = manifest_digest(man)
    am = json.loads((pkg / "approval_package_manifest.json").read_text(encoding="utf-8"))
    am["package_digest"] = digest
    am["required_files_sha256"] = {k: v["sha256"] for k, v in man["files"].items()}
    (pkg / "approval_package_manifest.json").write_text(json.dumps(am, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sb = json.loads((pkg / "storyboard.json").read_text(encoding="utf-8"))
    mgr = ProjectStateManager(pkg / "project_state.json")
    if not (pkg / "project_state.json").is_file() or json.loads((pkg / "project_state.json").read_text(encoding="utf-8")).get("project_id") != BENCH_ID:
        mgr.initialize(project_id=BENCH_ID, project_title=payload_title, genres=genres, total_frames=sb["total_frames"])
    st = json.loads((pkg / "project_state.json").read_text(encoding="utf-8"))
    if st.get("approval_status", {}).get("approved"):
        raise SystemExit("Refusing: package already approved")
    mgr.mark_waiting_approval(digest, package_version=am.get("package_version", "v1"))
    return {"project_id": BENCH_ID, "canonical_manifest_digest": digest, "files": len(man["files"]), "dependencies_pinned": len(dep["dependencies"]),
            "total_frames": sb["total_frames"], "duration_s": sb["duration_s"], "shots": len(sb["shots"])}


def main() -> int:
    pkg = ROOT_DIR / "projects" / BENCH_ID
    pkg.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    (pkg / "authored_creative_payload.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "--repin-only" not in sys.argv[1:]:
        wf = PreproductionMultiAgentWorkflow(root_dir=ROOT_DIR, max_parallel_specialists=2)
        out = wf.run_workflow(project_id=BENCH_ID, topic=payload["topic_title"], genres=payload["genres"], target_duration_s=10, authored_payload=payload,
                              explicit_reference_ids=payload["reference_ids"], disable_reference=False, execution_mode="sequential_fallback_honest")
        print(json.dumps({"workflow_status": out["status"]}))
    print(json.dumps(finalize(pkg, payload["topic_title"], payload["genres"]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
