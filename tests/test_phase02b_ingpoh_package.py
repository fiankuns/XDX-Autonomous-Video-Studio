"""Sebatas Ingpoh (replaces Bima) 02B.2 package: waits for approval, digest matches the signing tool, draft script is unexecuted and wired nowhere."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK = ROOT / "projects/bench_p02b_ingpoh_10s"


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_ingpoh_package_waits_for_approval_and_digest_matches_signing_tool():
    st = _j(PK / "project_state.json")
    assert st["project_id"] == "bench_p02b_ingpoh_10s" and st["current_state"] == "WAITING_APPROVAL" and st["approval_status"]["approved"] is False
    out = subprocess.run([sys.executable, str(ROOT / "scripts/trusted_approval.py"), "digest", "--package", str(PK)], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["manifest_digest"] == st["package_digest"] == _j(PK / "approval_package_manifest.json")["package_digest"]
    scope = _j(PK / "delivery_scope.json")
    assert scope["project_id"] == "bench_p02b_ingpoh_10s" and scope["blender"]["render_allowed"] is False and scope["blender"]["proposed_signed_scope"] == "blender_scene_mutation"
    assert _j(PK / ".reviews/independent_preproduction_review_v4.json")["verdict"] == "PASS"


def test_ingpoh_character_replaces_bima_and_keeps_style_bible():
    cb = _j(PK / "character_bible.json")
    assert [c["character_id"] for c in cb["characters"]] == ["char_sebatas_ingpoh"] and cb["modeling_executed"] is False
    assert not any("Bima" in p.read_text(encoding="utf-8") for p in PK.glob("*.json")) 
    assert _j(PK / "style_bible.json")["style_bible_id"] == "xdx_stylized_3d_v4_0"
    assert _j(ROOT / "projects/bench_p02b_char_10s/project_state.json")["project_id"] == "bench_p02b_char_10s"  # Bima package untouched


def test_ingpoh_rig_draft_is_pinned_but_not_wired_into_runners():
    dep = _j(PK / "production_dependencies.json")
    pinned = dep["dependencies"]
    names = [d["path"] if isinstance(d, dict) else d for d in (pinned if isinstance(pinned, list) else pinned.keys())]
    assert "engines/blender_scripts/phase02b2_ingpoh_rig.py" in names
    src = (ROOT / "engines/blender_scripts/phase02b2_ingpoh_rig.py").read_text(encoding="utf-8")
    assert "NOT EXECUTED" in src and "bpy.app.tempdir" not in src or "/tmp" not in src
    for p in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "engines").glob("*.py")) + list((ROOT / "orchestration").glob("*.py")):
        if p.name in ("prepare_phase02b_ingpoh_benchmark.py", "prepare_phase02b_benchmark.py"):
            continue
        assert "phase02b2_ingpoh_rig" not in p.read_text(encoding="utf-8"), p
