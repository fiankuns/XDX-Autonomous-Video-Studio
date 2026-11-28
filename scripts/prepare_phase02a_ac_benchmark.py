#!/usr/bin/env python3
"""Prepare Phase 02A 15-second 4-shot AC Benchmark Package (Part B).

- Compiles ONLY projects/bench_p02a_ac_15s (does NOT re-run other benchmarks).
- Reuses verified REF-002 (Yakhchal) from reference_database/.
- Pins ALL external production dependencies in production_dependencies.json so they are covered
  by the canonical SHA-256 manifest (governance/canonical_manifest.py).
- Updates approval_package_manifest.json, project_state.json, and project_state_v4.json with the
  exact canonical SHA-256 digest and stops strictly at WAITING_APPROVAL (or BLOCKED when no key).
- Zero rendering, zero Blender MCP calls, zero Phase 02B work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from governance.canonical_manifest import (
    build_canonical_manifest,
    build_production_dependencies_manifest,
    manifest_digest,
)
from intelligence.state_and_approval import ProjectStateManager
from orchestration.preproduction_workflow import PreproductionMultiAgentWorkflow

BENCH_ID = "bench_p02a_ac_15s"
PRODUCTION_DEPENDENCY_FILES = [
    "package.json",
    "package-lock.json",
    "engines/web/three_deterministic_scene.mjs",
    "engines/web/remotion_timeline_spec.mjs",
    "engines/web_engines.py",
    "engines/ffmpeg_engine.py",
    "governance/canonical_manifest.py",
    "governance/trusted_approval.py",
    "scripts/execution_guard_hook.py",
    "governance/phase_scope.py",
    "intelligence/visual_qc_engine.py",
    "intelligence/visual_semantic_qc.py",
    "engines/web/phase02a_ac15s/index.html",
    "engines/web/phase02a_ac15s/scene.js",
    "engines/web/phase02a_ac15s/render_dependencies.json",
    "engines/web/xdx_core/kit.js",
    "engines/web/xdx_core/comets.js",
    "engines/web/xdx_core/timeline.js",
    "engines/web/xdx_core/barrier.js",
    "engines/web/xdx_core/style_binding.js",
    "engines/web/xdx_core/assets/character_bima.js",
    "engines/web/xdx_core/assets/indoor_ac.js",
    "intelligence/visual_workflow.py",
    "scripts/render_phase02a_visual.py",
    "reference_database/profiles/reference_pattern_registry.json",
    "reference_database/references/explainer/REF-002-Yakhchal/rea_analysis_v3_4.json",
]


DELIVERY_SCOPE = {
    "schema": "xdx.delivery-scope.v1",
    "project_id": BENCH_ID,
    "phase": "02A",
    "delivery_profile": "VISUAL_ONLY_BENCHMARK",
    "audio": {
        "in_scope": False,
        "deferred_to_phase": "04",
        "export_audio_track": False,
        "missing_audio_is_qc_failure": False,
        "planning_fields_ignored_in_02A": ["audio_events", "sfx_cues", "audio_master_preset_id", "target_lufs",
                                           "music_direction", "ambience"],
    },
    "captions_represent_narration": True,
    "visual_qc": {
        "technical": "intelligence/visual_qc_engine.py (delivery_profile=VISUAL_ONLY_BENCHMARK)",
        "independent_semantic": "intelligence/visual_semantic_qc.py via scripts/visual_review.py",
        "reference_comparison": "REF-002",
    },
}


def repin(pkg_dir: Path) -> dict:
    """Re-pin dependencies + delivery scope and resync the canonical digest WITHOUT re-running the workflow."""
    (pkg_dir / "delivery_scope.json").write_text(json.dumps(DELIVERY_SCOPE, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    dep_manifest = build_production_dependencies_manifest(ROOT_DIR, PRODUCTION_DEPENDENCY_FILES)
    (pkg_dir / "production_dependencies.json").write_text(
        json.dumps(dep_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    canon_man = build_canonical_manifest(pkg_dir)
    canon_digest = manifest_digest(canon_man)
    app_man_path = pkg_dir / "approval_package_manifest.json"
    app_man = json.loads(app_man_path.read_text(encoding="utf-8"))
    app_man["package_digest"] = canon_digest
    app_man["required_files_sha256"] = {k: v["sha256"] for k, v in canon_man["files"].items()}
    app_man_path.write_text(json.dumps(app_man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state_path = pkg_dir / "project_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("current_state") != "WAITING_APPROVAL" or state.get("approval_status", {}).get("approved"):
        raise SystemExit("Refusing to re-pin: package is not in an unapproved WAITING_APPROVAL state")
    ProjectStateManager(state_path).mark_waiting_approval(canon_digest, package_version=app_man.get("package_version", "v1"))
    return {"project_id": BENCH_ID, "canonical_manifest_digest": canon_digest,
            "canonical_files_covered": len(canon_man["files"]),
            "external_dependencies_pinned": len(dep_manifest["dependencies"])}


def main() -> int:
    pkg_dir = ROOT_DIR / "projects" / BENCH_ID
    if "--repin-only" in sys.argv[1:]:
        print(json.dumps(repin(pkg_dir), indent=2))
        return 0
    (pkg_dir / "delivery_scope.json").write_text(json.dumps(DELIVERY_SCOPE, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    payload_path = pkg_dir / "authored_creative_payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    # 1. Pin all external production dependencies inside package_dir BEFORE canonical digest calculation
    dep_manifest = build_production_dependencies_manifest(ROOT_DIR, PRODUCTION_DEPENDENCY_FILES)
    (pkg_dir / "production_dependencies.json").write_text(
        json.dumps(dep_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 2. Run PreproductionMultiAgentWorkflow for bench_p02a_ac_15s ONLY
    wf = PreproductionMultiAgentWorkflow(root_dir=ROOT_DIR, max_parallel_specialists=2)
    out = wf.run_workflow(
        project_id=BENCH_ID,
        topic=payload["topic_title"],
        genres=payload["genres"],
        target_duration_s=15,
        authored_payload=payload,
        explicit_reference_ids=["REF-002"],
        disable_reference=False,
        execution_mode="sequential_fallback_honest",
    )

    # 3. Recompute exact Phase 01.6D canonical manifest (now including production_dependencies.json!)
    canon_man = build_canonical_manifest(pkg_dir)
    canon_digest = manifest_digest(canon_man)

    # Sync approval_package_manifest.json and v3.4 project_state.json to the exact canonical digest
    app_man_path = pkg_dir / "approval_package_manifest.json"
    app_man = json.loads(app_man_path.read_text(encoding="utf-8"))
    app_man["package_digest"] = canon_digest
    app_man["required_files_sha256"] = {k: v["sha256"] for k, v in canon_man["files"].items()}
    app_man_path.write_text(json.dumps(app_man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sb = json.loads((pkg_dir / "storyboard.json").read_text(encoding="utf-8"))
    v34_mgr = ProjectStateManager(pkg_dir / "project_state.json")
    v34_mgr.initialize(
        project_id=BENCH_ID,
        project_title=payload["topic_title"],
        genres=payload["genres"],
        total_frames=sb["total_frames"],
    )
    v34_mgr.mark_waiting_approval(canon_digest, package_version=app_man.get("package_version", "v1"))

    nar = json.loads((pkg_dir / "narration_dialogue.json").read_text(encoding="utf-8"))
    rev = json.loads((pkg_dir / ".reviews" / "independent_preproduction_review_v4.json").read_text(encoding="utf-8"))

    print(
        json.dumps(
            {
                "project_id": BENCH_ID,
                "status": out["status"],
                "canonical_manifest_digest": canon_digest,
                "canonical_files_covered": len(canon_man["files"]),
                "external_dependencies_pinned": len(dep_manifest["dependencies"]),
                "shot_count": len(sb["shots"]),
                "total_frames": sb["total_frames"],
                "duration_s": sb["duration_s"],
                "narration_estimated_s": nar["estimated_timing"]["estimated_total_s"],
                "narration_fit_status": nar["estimated_timing"]["duration_fit_status"],
                "measured_script_wpm": nar["measured_script_wpm"],
                "verifier_verdict": rev["verdict"],
                "verifier_criteria_count": len(rev["checked_criteria"]),
                "verifier_defects": rev["defects"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
