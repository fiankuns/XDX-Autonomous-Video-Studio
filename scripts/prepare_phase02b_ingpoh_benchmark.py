#!/usr/bin/env python3
"""Prepare the Phase 02B.2 package for the narrator character Sebatas Ingpoh (replaces Bima). Planning only: stops at WAITING_APPROVAL.

Reuses scripts/prepare_phase02b_benchmark.py (same workflow, same scope: blender_scene_mutation, asset + rig only) with a new project id
so the existing Bima approval stays valid evidence and the new digest must be signed separately by the human.
No Blender call, no render, never sets APPROVED.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
for p in (str(ROOT_DIR), str(ROOT_DIR / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import prepare_phase02b_benchmark as base  # noqa: E402
from orchestration.preproduction_workflow import PreproductionMultiAgentWorkflow  # noqa: E402

BENCH_ID = "bench_p02b_ingpoh_10s"
NAME = "Ingpoh"

CHARACTER = {
    "character_id": "char_sebatas_ingpoh",
    "name": "Sebatas Ingpoh",
    "role": "hero",
    "silhouette_and_proportions": "Siluet chibi stylized 3D sekitar 2.8 kepala tinggi dengan kepala besar, rambut lavender panjang bergelombang sampai pinggang, poni miring, dan satu ahoge melengkung di atas kepala.",
    "facial_design": "Mata ungu besar berkilau dengan bulu mata tebal, alis tipis, pipi merona bergaris, mulut kecil; berubah dari lelah kepanasan saat pembuka menjadi lega saat AC menyala.",
    "wardrobe": "Kaus peach lengan pendek berkerah renda krem dengan sablon 'Sebatas Ingpohh' dan garis merah di bawahnya, celana pendek peach bermotif bulan sabit krem, bertelanjang kaki.",
    "materials": ["soft_jersey_knit_fabric", "matte_plastic_remote_shell", "soft_subsurface_skin_aces"],
    "palette": ["#C9A7EE", "#F29A84", "#FFF1D6", "#E04545"],
    "expressions": ["overheated_exhausted", "focused_remote_press", "relaxed_chilled"],
    "rig_spec": "rig_biped_stylized_v4_ik_fk_hands_facial_visemes",
    "facial_controls": ["jaw_viseme_driver", "sweat_drop_toggle", "brow_furrow_relief"],
    "pose_requirements": ["slumped_fanning_self", "aiming_pressing_ac_remote"],
    "action_requirements": ["mengipasi wajah di kamar panas 32 derajat Celsius",
                            "menekan tombol daya dan suhu 24 derajat pada prop_ac_remote_control ke arah prop_ac_indoor_evaporator_cutaway"],
    "biography_disclaimer": "Karakter narator orisinal Sebatas Ingpoh milik pemilik proyek XDX; bukan individu nyata.",
}


def build_payload() -> dict:
    p = base.build_payload()
    p["project_id"] = BENCH_ID
    p["topic_title"] = "Ingpoh dan AC: Uji Animasi Karakter Blender 10 Detik"
    text = json.dumps(p, ensure_ascii=False).replace("Bima", NAME).replace("Bima dan AC", "Ingpoh dan AC")
    p = json.loads(text)
    p["characters"] = [copy.deepcopy(CHARACTER)]
    p["blueprint"]["premise"] = "Uji animasi karakter 10 detik untuk Blender: Sebatas Ingpoh kepanasan, menoleh ke AC, lalu menekan remot dan merasa lega, dengan penjelasan singkat kalor dipindahkan keluar."
    return p


def main() -> int:
    base.BENCH_ID = BENCH_ID
    old_rig = "engines/blender_scripts/phase02b2_" + "bima" + "_rig.py"  # previous character draft, replaced by the Ingpoh one
    deps = [d for d in base.DEPENDENCIES if d not in (old_rig, "docs/benchmarks/bench_p02b_char_10s.json")]
    deps += ["engines/blender_scripts/phase02b2_ingpoh_rig.py", "docs/benchmarks/bench_p02b_ingpoh_10s.json"]
    base.DEPENDENCIES = deps
    scope = copy.deepcopy(base.DELIVERY_SCOPE)
    scope["project_id"] = BENCH_ID
    scope["blender"]["stage"] = "02B.2 asset+rig only (Sebatas Ingpoh)"
    base.DELIVERY_SCOPE = scope
    pkg = ROOT_DIR / "projects" / BENCH_ID
    pkg.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    (pkg / "authored_creative_payload.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "--repin-only" not in sys.argv[1:]:
        wf = PreproductionMultiAgentWorkflow(root_dir=ROOT_DIR, max_parallel_specialists=2)
        out = wf.run_workflow(project_id=BENCH_ID, topic=payload["topic_title"], genres=payload["genres"], target_duration_s=10, authored_payload=payload,
                              explicit_reference_ids=payload["reference_ids"], disable_reference=False, execution_mode="sequential_fallback_honest")
        print(json.dumps({"workflow_status": out["status"]}))
    print(json.dumps(base.finalize(pkg, payload["topic_title"], payload["genres"]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
