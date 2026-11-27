"""Tests for 13-Item Approval Gate, Multi-Genre Preproduction, Project State Machine & REA/Visual QC."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from intelligence.creative_pipeline import PreProductionPackageBuilder
from intelligence.rea_reference_intelligence import REAReferenceIntelligence
from intelligence.state_and_approval import ApprovalGate, ProjectStateManager
from intelligence.visual_qc_engine import VisualQualityControlEngine

ROOT_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_MP4 = ROOT_DIR / "tests" / "fixtures" / "synthetic.mp4"


def test_13_item_approval_gate_and_state_machine_across_hybrid_genres(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "pkg_hybrid"
    builder = PreProductionPackageBuilder()
    result = builder.build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="sejarah_horor_01",
        topic="Misteri Jam Tua di Gedung Arsip 1928",
        genres=["sejarah", "horor", "komedi_absurd"],
        target_duration_s=24,
        package_version="v1",
    )

    assert result["status"] == "WAITING_APPROVAL"
    assert len(result["approval_manifest"]["mandatory_13_items"]) == 13

    gate = ApprovalGate()
    inspected = gate.inspect_package(pkg_dir, check_record=False)
    assert inspected["status"] == "WAITING_APPROVAL"

    # CLI check without approval_record.json MUST return exit code 2 / BLOCKED
    cli_proc = subprocess.run(
        ["python3", "scripts/approval_gate.py", str(pkg_dir), "--check"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    assert cli_proc.returncode == 2
    assert json.loads(cli_proc.stdout)["status"] == "BLOCKED"

    # State machine MUST block entering SHOT_RENDER or MCP_PREFLIGHT before explicit approval
    state_mgr = ProjectStateManager(pkg_dir / "project_state.json")
    with pytest.raises(PermissionError):
        state_mgr.transition("SHOT_RENDER", reason="Attempt unapproved render", package_dir=pkg_dir)

    # Ambiguous phrases like "lanjutkan" or "ok" MUST be rejected
    with pytest.raises(PermissionError):
        state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message="lanjutkan")
    with pytest.raises(PermissionError):
        state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message="ok")

    # Unbound natural-language sentence without project_id/digest/scope MUST also be rejected in v3.4
    with pytest.raises(PermissionError):
        state_mgr.record_explicit_user_approval(
            package_dir=pkg_dir,
            user_message="Saya setujui paket v1 dan izinkan render",
        )

    # Structured explicit versioned + digest-bound approval transitions cleanly to APPROVED -> MCP_PREFLIGHT
    approved_state = state_mgr.record_explicit_user_approval(
        package_dir=pkg_dir,
        user_message=result["approval_command_example"],
    )
    assert approved_state["current_state"] == "APPROVED"

    cli_ok = subprocess.run(
        ["python3", "scripts/approval_gate.py", str(pkg_dir), "--check", "--strict-schema"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    assert cli_ok.returncode == 0
    assert json.loads(cli_ok.stdout)["status"] == "RECORD_MATCH_ONLY"

    preflight_state = state_mgr.transition("MCP_PREFLIGHT", reason="Start preflight", package_dir=pkg_dir)
    assert preflight_state["current_state"] == "MCP_PREFLIGHT"

    # Mutating any file after approval MUST invalidate approval and revert to WAITING_APPROVAL
    (pkg_dir / "script.md").write_text((pkg_dir / "script.md").read_text(encoding="utf-8") + "\nEdit tanpa izin\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        state_mgr.transition("STYLE_FRAME", reason="Render tampered package", package_dir=pkg_dir)
    assert state_mgr.load()["current_state"] == "WAITING_APPROVAL"


def test_rea_video_reference_analysis_and_visual_qc_on_synthetic_mp4(tmp_path: Path) -> None:
    assert SYNTHETIC_MP4.is_file()
    out_dir = tmp_path / "rea_out"
    rea = REAReferenceIntelligence()
    report = rea.analyze_video(SYNTHETIC_MP4, out_dir)

    assert report["measurements"]["duration_s"] == pytest.approx(4.0, abs=0.15)
    # At scene_threshold=0.30 FFmpeg catches the strong 2.0s cut (2 segments), while OpenCV adaptive MAD catches subtle 1s/2s/3s cuts
    assert len(report["ffmpeg_scene_candidates"]) >= 2
    assert len(report["adaptive_opencv_candidates"]["abrupt_candidates"]) >= 2
    assert (out_dir / "contact_sheet.jpg").is_file()
    assert (out_dir / "REPORT_BASELINE.md").is_file()

    qc_engine = VisualQualityControlEngine()
    qc_report = qc_engine.evaluate_video(SYNTHETIC_MP4, require_audio=False, current_attempt=1)
    assert qc_report["technical_qc"]["full_decode_ok"] is True
    assert qc_report["technical_qc"]["has_video_stream"] is True
    assert qc_report["visual_qc"]["sampled_frames"] > 0

    # Verify bounded max-3 self-correction cap when defects occur (e.g. require_audio=True on silent fixture)
    qc_fail_attempt_3 = qc_engine.evaluate_video(SYNTHETIC_MP4, require_audio=True, current_attempt=3)
    assert qc_fail_attempt_3["overall_status"] == "HARD_FAIL"
    assert qc_fail_attempt_3["self_correction_plan"]["requires_re_render"] is False
