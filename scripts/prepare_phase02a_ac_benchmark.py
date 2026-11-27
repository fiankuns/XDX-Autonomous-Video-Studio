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
    "reference_database/profiles/reference_pattern_registry.json",
    "reference_database/references/explainer/REF-002-Yakhchal/rea_analysis_v3_4.json",
]


def main() -> int:
    pkg_dir = ROOT_DIR / "projects" / BENCH_ID
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
