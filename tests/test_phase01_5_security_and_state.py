"""Phase 01.5 Regression Tests — Fail-Closed Approval Gate, State Machine & MCP Authorization (Categories 1–4)."""

from __future__ import annotations

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
    InvalidStateTransitionError,
    ProjectStateManager,
    format_structured_approval_command,
    is_explicit_approval_message,
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


def test_invalid_state_transitions_ai_self_approval_expiry_and_revocation(tmp_path: Path) -> None:
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

    # 3. Scoped approval limited only to `mcp_preflight` MUST block `SHOT_RENDER`
    narrow_cmd = format_structured_approval_command(
        project_id="sec_proj_01",
        package_version="v1",
        package_digest=digest,
        scopes=["mcp_preflight"],
    )
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=narrow_cmd)
    state_mgr.transition("MCP_PREFLIGHT", reason="Allowed by narrow scope", package_dir=pkg_dir)
    with pytest.raises(ApprovalAuthorizationError):
        state_mgr.transition("STYLE_FRAME", reason="Disallowed by narrow scope", package_dir=pkg_dir)
    # Reverted automatically to WAITING_APPROVAL after scope violation
    assert state_mgr.load()["current_state"] == "WAITING_APPROVAL"

    # 4. Grant full scope, test expiry check and revocation
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=valid_cmd, ttl_hours=1.0)
    ctx = state_mgr.build_authorization_context(pkg_dir)
    gate = ApprovalGate()

    # Future timestamp past 1-hour TTL is rejected
    future_after_ttl = datetime.now(timezone.utc) + timedelta(hours=2)
    with pytest.raises(ApprovalAuthorizationError):
        gate.verify_live_execution_context(ctx, required_scope="render_production", now=future_after_ttl)

    # Revoking approval immediately invalidates live context
    state_mgr.revoke_approval(package_dir=pkg_dir, reason="User cancelled run")
    with pytest.raises(ApprovalAuthorizationError):
        gate.verify_live_execution_context(ctx, required_scope="render_production")


def test_mcp_tool_allowlist_unknown_tool_rejection_and_live_tamper_blocking(tmp_path: Path) -> None:
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

    # Approve properly and verify authorization passes while package is intact
    state_mgr.record_explicit_user_approval(package_dir=pkg_dir, user_message=res["approval_command_example"])
    state_mgr.transition("MCP_PREFLIGHT", reason="Verified preflight", package_dir=pkg_dir)
    ctx = state_mgr.build_authorization_context(pkg_dir)
    adapter_rw.authorize_tool_call("create_primitive", {"primitive": "cube"}, auth_context=ctx)

    # Modify 1 byte in engine_plan.json AFTER approval -> live MCP authorization MUST immediately block!
    ep_path = pkg_dir / "engine_plan.json"
    ep_path.write_text(ep_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(MCPSceneMutationBlockedError):
        adapter_rw.authorize_tool_call("create_primitive", {"primitive": "cube"}, auth_context=ctx)
