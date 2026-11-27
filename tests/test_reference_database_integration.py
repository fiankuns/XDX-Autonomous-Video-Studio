"""Comprehensive integration & regression tests for `reference_database/` (v3.4).

Covers all 9 mandatory verification pillars:
1. Git LFS binary hydration & fail-closed pointer/missing-media rejection (`reference_db.py verify`).
2. Exact SHA-256 & byte size verification of `REF-001` and `REF-002` + preservation of `prior_analysis.*`.
3. Versioned 10-dimension REA-Video v3.4 analysis & analyzer fingerprint integrity.
4. Automatic genre routing (`explainer`, `explainair`, `storytelling`, `satir_sosial`, `"satir sosial"`, related candidates).
5. Explicit single Reference ID selection overriding genre defaults.
6. Multi-reference selection & profile fusion (`["REF-001", "REF-002"]` and multi-genre auto-fusion).
7. Creative Pipeline & `xdx_studio.py` CLI integration (`upload_prompt_suppressed`, 4-layer provenance, shots <= 10s).
8. Fail-closed `ApprovalGate` enforcement (`WAITING_APPROVAL`, `production_authorized == False`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from intelligence.creative_pipeline import PreProductionPackageBuilder
from intelligence.reference_database_bridge import (
    ReferenceDatabaseBridge,
    ReferenceMediaIntegrityError,
)
from intelligence.state_and_approval import (
    ApprovalAuthorizationError,
    ApprovalGate,
    ProjectStateManager,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_ROOT = ROOT_DIR / "reference_database"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_git_lfs_real_binaries_and_cli_verify() -> None:
    proc = subprocess.run(
        [sys.executable, str(DB_ROOT / "scripts" / "reference_db.py"), "verify"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    results = json.loads(proc.stdout)
    by_id = {r["id"]: r for r in results}
    assert set(by_id) == {"REF-001", "REF-002"}

    for rid, expected_bytes, expected_sha in (
        ("REF-001", 27026130, "12f9e1d992fc6f71f56c4c1116a91def3f6ca70bf1c55aa2618281ae4a71879d"),
        ("REF-002", 38669358, "042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01"),
    ):
        assert by_id[rid]["status"] == "VERIFIED"
        assert by_id[rid]["production_authorized"] is False
        assert by_id[rid]["sha256"] == expected_sha
        mp4 = Path(by_id[rid]["path"])
        assert mp4.is_file()
        assert mp4.stat().st_size == expected_bytes
        with mp4.open("rb") as f:
            head = f.read(64)
        assert not head.startswith(b"version https://git-lfs.github.com/spec/v1")
        assert _sha256(mp4) == expected_sha


def test_fail_closed_on_lfs_pointer_or_missing_media(tmp_path: Path) -> None:
    fake_db = tmp_path / "reference_database"
    shutil.copytree(
        DB_ROOT,
        fake_db,
        ignore=shutil.ignore_patterns("original.mp4", ".rea-output", "__pycache__"),
    )
    bridge = ReferenceDatabaseBridge(db_root=fake_db, studio_root=ROOT_DIR)

    # 1. Missing MP4 -> MEDIA_MISSING
    with pytest.raises(ReferenceMediaIntegrityError, match="MEDIA_MISSING"):
        bridge.verify_and_load_reference("REF-002", hydrate=False)

    # 2. Unhydrated Git LFS pointer -> INTEGRITY_FAILED
    ptr_file = fake_db / "references" / "explainer" / "REF-002-Yakhchal" / "original.mp4"
    ptr_file.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01\n"
        "size 38669358\n",
        encoding="utf-8",
    )
    with pytest.raises(ReferenceMediaIntegrityError, match="INTEGRITY_FAILED"):
        bridge.verify_and_load_reference("REF-002", hydrate=False)


def test_prior_analyses_preserved_and_versioned_rea_v3_4_complete() -> None:
    bridge = ReferenceDatabaseBridge()
    required_10_dims = {
        "01_narrative_structure_and_hook",
        "02_shots_timestamps_and_pacing",
        "03_characters_and_acting",
        "04_body_motion_facial_expressions_and_objects",
        "05_camera_and_cinematography",
        "06_environment_assets_materials_and_lighting",
        "07_technical_cutaways_and_demonstrations",
        "08_captions_and_typography",
        "09_narration_audio_and_sfx",
        "10_editing_transitions_and_vfx",
    }

    r1 = bridge.verify_and_load_reference("REF-001")
    r2 = bridge.verify_and_load_reference("REF-002")

    assert r1.prior_analysis_path.name == "prior_analysis.md"
    assert "1001952045.mp4" in r1.prior_analysis_content
    assert r2.prior_analysis_path.name == "prior_analysis.json"
    assert r2.prior_analysis_content["id"] == "ref_1001952305"

    for rec in (r1, r2):
        assert rec.rea_v3_4_data["schema"] == "xdx.rea-video.deep-analysis.v3.4"
        assert rec.rea_v3_4_data["analyzer_provenance"]["production_authorized"] is False
        assert set(rec.rea_v3_4_data["ten_dimension_analysis"]) == required_10_dims
        assert rec.rea_v3_4_md_path.stat().st_size > 1500


def test_automatic_genre_and_alias_routing() -> None:
    bridge = ReferenceDatabaseBridge()

    # Explainer & Explainair -> REF-002 Yakhchal
    for alias in ("explainer", "explainair", "explaner"):
        ctx = bridge.resolve_context(genres=[alias])
        assert ctx["normalized_genres"] == ["explainer"]
        assert ctx["selected_reference_ids"] == ["REF-002"]
        assert ctx["selection_mode"] == "automatic_genre_default"
        assert ctx["upload_prompt_suppressed"] is True
        assert ctx["fused_production_profile"]["profile_ids"] == ["hosted_3d_explainer_cutaway_v1"]

    # Storytelling & Satir Sosial -> REF-001
    for g_in in ("storytelling", "satir_sosial", "social_satire", "satir sosial"):
        ctx = bridge.resolve_context(genres=[g_in])
        assert ctx["selected_reference_ids"] == ["REF-001"]
        assert ctx["selection_mode"] == "automatic_genre_default"
        assert ctx["upload_prompt_suppressed"] is True
        assert ctx["fused_production_profile"]["profile_ids"] == ["satirical_3d_vignette_storytelling_v1"]

    # Unmapped genre preserves existing default; related genre offers optional candidate without forcing
    horor_ctx = bridge.resolve_context(genres=["horor"])
    assert horor_ctx["selected_reference_ids"] == []
    assert horor_ctx["related_candidate_ids"] == []

    edu_ctx = bridge.resolve_context(genres=["edukasi"], include_related=False)
    assert edu_ctx["selected_reference_ids"] == []
    assert edu_ctx["related_candidate_ids"] == ["REF-002"]

    edu_related_ctx = bridge.resolve_context(genres=["edukasi"], include_related=True)
    assert edu_related_ctx["selected_reference_ids"] == ["REF-002"]


def test_specific_id_and_multi_reference_selection() -> None:
    bridge = ReferenceDatabaseBridge()

    # Explicit single ID overrides default
    single = bridge.resolve_context(genres=["horor"], explicit_reference_ids=["REF-002"])
    assert single["selection_mode"] == "explicit_single_reference"
    assert single["selected_reference_ids"] == ["REF-002"]

    # Explicit multi-reference fusion
    multi = bridge.resolve_context(genres=["explainer"], explicit_reference_ids=["REF-001", "REF-002"])
    assert multi["selection_mode"] == "explicit_multi_reference"
    assert multi["selected_reference_ids"] == ["REF-001", "REF-002"]
    fused = multi["fused_production_profile"]
    assert fused["is_multi_reference_blend"] is True
    assert fused["profile_ids"] == [
        "satirical_3d_vignette_storytelling_v1",
        "hosted_3d_explainer_cutaway_v1",
    ]
    assert "TECHNICAL_CUTAWAY" in fused["visual_modes"]
    assert "DIEGETIC_3D_SCOREBOARD_OR_SCALE" in fused["visual_modes"]

    # Automatic multi-genre fusion
    auto_multi = bridge.resolve_context(genres=["explainair", "satir_sosial"])
    assert auto_multi["selection_mode"] == "automatic_multi_genre_reference_fusion"
    assert auto_multi["selected_reference_ids"] == ["REF-002", "REF-001"]


def test_creative_pipeline_and_approval_gate_with_references(tmp_path: Path) -> None:
    builder = PreProductionPackageBuilder()
    gate = ApprovalGate()

    # 1. Explainair -> auto REF-002 Yakhchal
    pkg_exp = tmp_path / "pkg_explainair"
    res_exp = builder.build_waiting_approval_package(
        package_dir=pkg_exp,
        project_id="uji_explainair_ref002",
        genres=["explainair"],
        target_duration_s=60,
    )
    assert res_exp["status"] == "WAITING_APPROVAL"
    assert res_exp["reference_intelligence"]["selected_reference_ids"] == ["REF-002"]
    assert res_exp["reference_intelligence"]["production_authorized"] is False
    assert res_exp["reference_intelligence"]["upload_prompt_suppressed"] is True

    sb_exp = json.loads((pkg_exp / "storyboard.json").read_text(encoding="utf-8"))
    assert sb_exp["total_frames"] == 1800
    assert all(s["duration_s"] <= 10.0 for s in sb_exp["shots"])
    assert "REF-002" in (pkg_exp / "reference_analysis.md").read_text(encoding="utf-8")
    assert gate.inspect_package(pkg_exp)["status"] == "WAITING_APPROVAL"

    # 2. Satir Sosial -> auto REF-001 + ApprovalGate negation rejection
    pkg_sat = tmp_path / "pkg_satir"
    res_sat = builder.build_waiting_approval_package(
        package_dir=pkg_sat,
        project_id="uji_satir_ref001",
        genres=["satir_sosial", "storytelling"],
        target_duration_s=60,
    )
    assert res_sat["status"] == "WAITING_APPROVAL"
    assert res_sat["reference_intelligence"]["selected_reference_ids"] == ["REF-001"]
    assert gate.inspect_package(pkg_sat)["status"] == "WAITING_APPROVAL"

    sm = ProjectStateManager(pkg_sat / "project_state.json")
    with pytest.raises(ApprovalAuthorizationError):
        sm.record_explicit_user_approval(
            package_dir=pkg_sat,
            user_message="Saya tidak setuju paket v1, jangan render",
            actor_role="human_user",
        )

    approved_state = sm.record_explicit_user_approval(
        package_dir=pkg_sat,
        user_message=res_sat["approval_command_example"],
        actor_role="human_user",
    )
    assert approved_state["current_state"] == "APPROVED"

    # 3. CLI multi-reference plan (`--ref-ids REF-001 REF-002`)
    pkg_multi = tmp_path / "pkg_cli_multi"
    cli = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "xdx_studio.py"),
            "plan",
            "--project-id",
            "uji_multi_ref_cli",
            "--genres",
            "explainair",
            "satir_sosial",
            "--ref-ids",
            "REF-001",
            "REF-002",
            "--duration",
            "30",
            "--out",
            str(pkg_multi),
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    cli_out = json.loads(cli.stdout)
    assert cli_out["status"] == "WAITING_APPROVAL"
    assert cli_out["selected_reference_ids"] == ["REF-001", "REF-002"]
    assert cli_out["reference_selection_mode"] == "explicit_multi_reference"
    assert gate.inspect_package(pkg_multi)["status"] == "WAITING_APPROVAL"
