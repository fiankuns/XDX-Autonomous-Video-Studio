"""Phase 01.5 Regression Tests — Fail-Closed Approval Gate, State Machine & MCP Authorization (Categories 1–4)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from adapters.xdx_mcp_adapter import (
    MCPSceneMutationBlockedError,
    UnclassifiedMCPToolError,
    XDXBlenderMCPAdapter,
)
from intelligence.creative_pipeline import PreProductionPackageBuilder
from intelligence.state_and_approval import (
    ApprovalAuthorizationError,
    ApprovalGate,
    ExecutionAuthorizationContext,
    InvalidStateTransitionError,
    ProductionApprovalFrozenError,
    ProjectStateManager,
    atomic_write_json,
    compute_package_digest,
    format_structured_approval_command,
    is_explicit_approval_message,
)


def _forge_approved_state_on_disk(pkg_dir: Path, *, scopes: list[str], ttl_hours: float = 1.0) -> ExecutionAuthorizationContext:
    """Simulate an attacker/agent hand-writing APPROVED state + approval_record.json (bypassing the API).

    Used to prove the Phase 01.6C freeze holds even when on-disk state claims approval, and to keep the
    dormant TTL / revocation / tamper validators (re-enabled in Phase 01.6D) under regression test.
    """
    state_file = pkg_dir / "project_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    digest, _ = compute_package_digest(pkg_dir)
    now = datetime.now(timezone.utc)
    rec = {
        "approval_id": "app-forged000000000",
        "project_id": state["project_id"],
        "package_version": state["package_version"],
        "digest": digest,
        "decision": "approved",
        "actor_role": "human_user",
        "approved_scopes": scopes,
        "project_state_at_approval": "WAITING_APPROVAL",
        "user_message": format_structured_approval_command(
            project_id=state["project_id"],
            package_version=state["package_version"],
            package_digest=digest,
            scopes=scopes,
        ),
        "recorded_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        "revoked": False,
    }
    atomic_write_json(pkg_dir / "approval_record.json", rec)
    state["current_state"] = "APPROVED"
    state["approval_status"] = {
        "approved": True,
        "approval_id": rec["approval_id"],
        "actor_role": "human_user",
        "approved_digest": digest,
        "approved_version": state["package_version"],
        "approved_scopes": scopes,
        "explicit_user_message": "forged",
        "revoked": False,
    }
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return ExecutionAuthorizationContext(
        package_dir=pkg_dir,
        state_file=state_file,
        project_id=state["project_id"],
        package_version=state["package_version"],
        expected_digest=digest,
    )


def test_critical_audit_regression_negative_conditional_quoted_and_ambiguous_approvals() -> None:
    sample_digest = "a" * 64

    # CRITICAL AUDIT REGRESSION: Must strictly return False!
    assert is_explicit_approval_message("Saya tidak setuju paket v1, jangan render", "v1") is False

    invalid_messages = [
        "",
        "lanjutkan",
        "ok",
        "setuju",
        "Saya setujui paket v1",
        "Saya tidak setuju paket v1, jangan render",
        "Jangan setujui paket v1",
        "Tolak paket v1",
        "Batal render paket v1",
        f"Tidak XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production",
        f"XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production jika musik diganti",
        f"Saya setujui paket v1 tapi ubah karakter dulu digest={sample_digest[:16]}",
        f'"XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production"',
        f"`XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production`",
        f"> XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production",
        f"Contoh: XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production",
        f"XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production?",
        f"XDX-APPROVE project=p1 version=v2 digest={sample_digest[:16]} scopes=all_production",
        f"XDX-APPROVE project=wrong_proj version=v1 digest={sample_digest[:16]} scopes=all_production",
        f"XDX-APPROVE project=p1 version=v1 digest={'b' * 16} scopes=all_production",
        f"XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=unknown_scope",
        f"XDX-APPROVE project=p1 version=v1 digest={sample_digest[:16]} scopes=all_production\nmalicious_second_line",
    ]

    for msg in invalid_messages:
        assert (
            is_explicit_approval_message(
                msg,
                "v1",
                project_id="p1",
                package_digest=sample_digest,
            )
            is False
        ), f"Should have rejected fail-closed: {msg!r}"

    # Valid canonical structured approval succeeds
    valid_cmd = format_structured_approval_command(
        project_id="p1",
        package_version="v1",
        package_digest=sample_digest,
        scopes=["all_production"],
    )
    assert is_explicit_approval_message(valid_cmd, "v1", project_id="p1", package_digest=sample_digest) is True


def test_invalid_state_transitions_ai_self_approval_expiry_and_revocation(tmp_path: Path, trusted_approver) -> None:
    from intelligence.authored_showcase_150s import build_authored_time_perception_payload

    pkg_dir = tmp_path / "pkg_sec"
    res = PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="sec_proj_01",
        target_duration_s=15,
        authored_payload=build_authored_time_perception_payload(project_id="sec_proj_01", target_duration_s=15),
    )
    state_mgr = ProjectStateManager(pkg_dir / "project_state.json")
    digest = res["package_digest"]
    valid_cmd = res["approval_command_example"]

    # 1. Direct transition() to APPROVED or skipping WAITING_APPROVAL -> SHOT_RENDER is forbidden
    with pytest.raises(InvalidStateTransitionError):
        state_mgr.transition("APPROVED", reason="Bypass approval", package_dir=pkg_dir)
    with pytest.raises(InvalidStateTransitionError):
        state_mgr.transition("SHOT_RENDER", reason="Jump straight to render", package_dir=pkg_dir)
    with pytest.raises(InvalidStateTransitionError):
        state_mgr.transition("DELIVERED", reason="Jump straight to delivered", package_dir=pkg_dir)

    # 2. AI self-approval MUST be rejected fail-closed
    with pytest.raises(ApprovalAuthorizationError):
        state_mgr.record_explicit_user_approval(
            package_dir=pkg_dir,
            user_message=valid_cmd,
            actor_role="ai_agent",
        )
    with pytest.raises(ApprovalAuthorizationError):
        state_mgr.record_explicit_user_approval(
            package_dir=pkg_dir,
            user_message=valid_cmd,
            actor_role="assistant",
        )

    # 3. Unsigned structured commands are not proof of a human (Phase 01.6D trusted channel).
    from governance.trusted_approval import (
        ApprovalExpiredError,
        ApprovalRevokedError,
        PhaseBoundaryBlockedError,
        ScopeMismatchError,
        UnsignedApprovalError,
    )

    with pytest.raises(UnsignedApprovalError):
        state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=valid_cmd)
    assert state_mgr.load()["current_state"] == "WAITING_APPROVAL"

    # 4. Signed approval limited to `mcp_preflight` allows MCP_PREFLIGHT only; STYLE_FRAME -> scope mismatch,
    #    approval invalidated and state reverted to WAITING_APPROVAL.
    narrow = trusted_approver.sign(package_dir=pkg_dir, project_id="sec_proj_01", scopes=["mcp_preflight"])
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=narrow)
    assert state_mgr.load()["current_state"] == "APPROVED"
    state_mgr.transition("MCP_PREFLIGHT", reason="Allowed by narrow scope", package_dir=pkg_dir)
    with pytest.raises(ScopeMismatchError):
        state_mgr.transition("STYLE_FRAME", reason="Disallowed by narrow scope", package_dir=pkg_dir)
    assert state_mgr.load()["current_state"] == "WAITING_APPROVAL"

    # 5. Full scope: approval works, but production execution stays behind the Phase 02 boundary.
    full = trusted_approver.sign(package_dir=pkg_dir, project_id="sec_proj_01", scopes=["all_production"])
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=full, ttl_hours=1.0)
    ctx = state_mgr.build_authorization_context(pkg_dir)
    gate = ApprovalGate()
    with pytest.raises(PhaseBoundaryBlockedError):
        gate.verify_live_execution_context(ctx, required_scope="render_production")
    assert state_mgr.load()["current_state"] == "APPROVED"  # boundary is not a tamper: approval kept

    # Expiry: past the signed 1-hour TTL is rejected before the boundary.
    with pytest.raises(ApprovalExpiredError):
        gate.verify_live_execution_context(
            ctx, required_scope="mcp_preflight", now=datetime.now(timezone.utc) + timedelta(hours=2)
        )

    # Revocation: state drops to WAITING_APPROVAL; even if an agent hand-restores APPROVED state and
    # un-revokes approval_record.json, the hash-chained ledger still says REVOKED.
    state_mgr.revoke_approval(package_dir=pkg_dir, reason="User cancelled run")
    with pytest.raises(ApprovalAuthorizationError):
        gate.verify_live_execution_context(ctx, required_scope="mcp_preflight")
    rec_p = pkg_dir / "approval_record.json"
    rec_doc = json.loads(rec_p.read_text(encoding="utf-8"))
    rec_doc["revoked"] = False
    rec_p.write_text(json.dumps(rec_doc), encoding="utf-8")
    st_doc = json.loads((pkg_dir / "project_state.json").read_text(encoding="utf-8"))
    st_doc["current_state"] = "APPROVED"
    st_doc["approval_status"].update({"approved": True, "revoked": False})
    (pkg_dir / "project_state.json").write_text(json.dumps(st_doc), encoding="utf-8")
    with pytest.raises(ApprovalRevokedError):
        gate.verify_live_execution_context(ctx, required_scope="mcp_preflight")
    st_doc["current_state"] = "WAITING_APPROVAL"
    (pkg_dir / "project_state.json").write_text(json.dumps(st_doc), encoding="utf-8")

    # Replay of an already consumed token is rejected.
    from governance.trusted_approval import ApprovalReplayError

    with pytest.raises(ApprovalReplayError):
        state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=full)

    # 6. Forged on-disk APPROVED state + record (no valid signature) cannot unlock execution.
    ctx_forged = _forge_approved_state_on_disk(pkg_dir, scopes=["all_production"], ttl_hours=1.0)
    with pytest.raises(UnsignedApprovalError):
        gate.verify_live_execution_context(ctx_forged, required_scope="mcp_preflight")


def test_mcp_tool_allowlist_unknown_tool_rejection_and_live_tamper_blocking(tmp_path: Path, trusted_approver) -> None:
    from intelligence.authored_showcase_150s import build_authored_time_perception_payload

    pkg_dir = tmp_path / "pkg_mcp_authz"
    res = PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="mcp_proj_01",
        target_duration_s=15,
        authored_payload=build_authored_time_perception_payload(project_id="mcp_proj_01", target_duration_s=15),
    )
    state_mgr = ProjectStateManager(pkg_dir / "project_state.json")

    adapter_ro = XDXBlenderMCPAdapter(read_only=True)
    # Read-only allowlist tools pass authorization without auth_context
    adapter_ro.authorize_tool_call("get_mobile_device_profile", {})
    adapter_ro.authorize_tool_call("get_scene_info", {})
    adapter_ro.authorize_tool_call("look", {"mode": "viewport", "shading": "material"})

    # Unknown/unclassified tool MUST be rejected fail-closed even in read-only mode
    with pytest.raises(UnclassifiedMCPToolError):
        adapter_ro.authorize_tool_call("delete_all_scenes_unclassified", {})

    # Active-mode adapter (`read_only=False`) STILL blocks mutating tools without a valid ExecutionAuthorizationContext
    adapter_rw = XDXBlenderMCPAdapter(read_only=False)
    for mut_tool in ("create_primitive", "modify_object", "set_material", "execute_blender_code", "configure_mobile_guard"):
        with pytest.raises(MCPSceneMutationBlockedError):
            adapter_rw.authorize_tool_call(mut_tool, {}, auth_context=None)

    # Unsigned approval is rejected; forged on-disk approval cannot authorize a scene mutation.
    from governance.trusted_approval import UnsignedApprovalError

    with pytest.raises(UnsignedApprovalError):
        state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=res["approval_command_example"])
    forged_ctx = _forge_approved_state_on_disk(pkg_dir, scopes=["all_production"])
    with pytest.raises(MCPSceneMutationBlockedError, match="UNSIGNED"):
        adapter_rw.authorize_tool_call("create_primitive", {"primitive": "cube"}, auth_context=forged_ctx)
    # restore genuine WAITING_APPROVAL state for the trusted path
    import json as _json

    st = _json.loads((pkg_dir / "project_state.json").read_text(encoding="utf-8"))
    st["current_state"] = "WAITING_APPROVAL"
    st["approval_status"]["approved"] = False
    (pkg_dir / "project_state.json").write_text(_json.dumps(st), encoding="utf-8")
    (pkg_dir / "approval_record.json").unlink()

    # Genuine signed human approval: read-only preflight OK, scene mutation blocked by the Phase 02 boundary.
    token = trusted_approver.sign(package_dir=pkg_dir, project_id="mcp_proj_01", scopes=["all_production"])
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=token)
    state_mgr.transition("MCP_PREFLIGHT", reason="Verified preflight", package_dir=pkg_dir)
    ctx = state_mgr.build_authorization_context(pkg_dir)
    with pytest.raises(MCPSceneMutationBlockedError, match="PHASE02_EXECUTION_NOT_STARTED"):
        adapter_rw.authorize_tool_call("create_primitive", {"primitive": "cube"}, auth_context=ctx)

    # Modify 1 byte in ANY production input (here narration) AFTER approval -> blocked as tampering.
    nd_path = pkg_dir / "narration_dialogue.json"
    nd_path.write_text(nd_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(MCPSceneMutationBlockedError, match="modified on disk"):
        adapter_rw.authorize_tool_call("create_primitive", {"primitive": "cube"}, auth_context=ctx)
