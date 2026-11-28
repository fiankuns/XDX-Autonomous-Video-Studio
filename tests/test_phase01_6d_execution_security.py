"""Phase 01.6D — Trusted Human Approval & Execution Guard regression tests (core profile, no LFS needed)."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from adapters.xdx_mcp_adapter import MCPSceneMutationBlockedError, XDXBlenderMCPAdapter
from governance import trusted_approval as ta
from governance.canonical_manifest import (
    REQUIRED_PRODUCTION_INPUTS,
    CanonicalManifestError,
    build_canonical_manifest,
)
from intelligence.authored_showcase_150s import build_authored_time_perception_payload
from intelligence.creative_pipeline import PreProductionPackageBuilder
from intelligence.state_and_approval import (
    ApprovalGate,
    InvalidStateTransitionError,
    ProjectStateManager,
    compute_package_digest,
)
from orchestration.shared_state import ProductionApprovalFrozenError, SharedProjectStateMachine

ROOT_DIR = Path(__file__).resolve().parent.parent


def _build_pkg(tmp_path: Path, project_id: str = "sec16d_proj") -> tuple[Path, dict]:
    pkg = tmp_path / project_id
    res = PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg,
        project_id=project_id,
        target_duration_s=15,
        authored_payload=build_authored_time_perception_payload(project_id=project_id, target_duration_s=15),
    )
    return pkg, res


# ----------------------------------------------------------------------------- trusted channel
def test_repo_trust_registry_is_fail_closed() -> None:
    """Empty/dirty registry -> BLOCKED. Owner-committed key (fian-termux-1, 9f87677) -> approval possible,
    but production execution stays behind the Phase 02 boundary."""
    st = ta.default_guard().channel_status()
    cli = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "trusted_approval.py"), "status"],
        cwd=ROOT_DIR, capture_output=True, text=True,
    )
    if st["status"] == "UNAVAILABLE":
        assert st["production_status"] == "BLOCKED"
        assert cli.returncode == 3 and json.loads(cli.stdout)["production_status"] == "BLOCKED"
    else:
        assert st["registry_git_state"] == "CLEAN" and st["approver_key_ids"] and not st["reasons"]
        assert cli.returncode == 0 and json.loads(cli.stdout)["status"] == "AVAILABLE"
        with pytest.raises(ta.PhaseBoundaryBlockedError):
            ta.assert_phase_boundary("render_production", action="render")


def test_uncommitted_trust_registry_change_makes_channel_unavailable(tmp_path: Path, monkeypatch) -> None:
    """A key added to the in-repo registry without a reviewed commit must not open the channel."""
    if not (ROOT_DIR / ".git").exists():
        pytest.skip("not a git checkout")
    reg = ROOT_DIR / "registry" / "trusted_approvers.json"
    original = reg.read_bytes()
    _, pub = ta.generate_approver_keypair()
    doc = json.loads(original)
    doc["approvers"].append(
        {"key_id": "agent-injected", "algorithm": "ed25519", "public_key_b64url": pub,
         "owner": "agent", "added_at": "2026-11-28T00:00:00+00:00", "revoked": False}
    )
    try:
        reg.write_text(json.dumps(doc), encoding="utf-8")
        st = ta.TrustedApprovalGuard(reg).channel_status()
        assert st["registry_git_state"] in {"MODIFIED", "UNTRACKED"}
        assert st["status"] == "UNAVAILABLE" and st["production_status"] == "BLOCKED"
    finally:
        reg.write_bytes(original)


# ----------------------------------------------------------------------------- token forgery
def test_forged_wrong_key_tampered_payload_and_malformed_tokens_rejected(tmp_path: Path, trusted_approver) -> None:
    pkg, res = _build_pkg(tmp_path)
    digest, _ = compute_package_digest(pkg)
    guard = ta.default_guard()
    kw = dict(expected_project_id="sec16d_proj", expected_package_version="v1", live_manifest_digest=digest)

    good = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj")
    assert guard.verify_token(good, **kw).covers("render_production")

    # Signed by an attacker key that claims the registered key_id.
    attacker_priv, _ = ta.generate_approver_keypair()
    forged = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", key=attacker_priv)
    with pytest.raises(ta.SignatureInvalidError):
        guard.verify_token(forged, **kw)

    # Payload edited after signing (scope escalation).
    env = json.loads(base64.urlsafe_b64decode(good[len(ta.TOKEN_PREFIX):] + "=="))
    env["payload"]["scopes"] = ["all_production", "render_production"]
    tampered = ta.TOKEN_PREFIX + base64.urlsafe_b64encode(ta.canonical_json(env)).decode().rstrip("=")
    with pytest.raises(ta.SignatureInvalidError):
        guard.verify_token(tampered, **kw)

    # Unknown key id, unsigned legacy command, chat phrase, extra field.
    env2 = dict(env, key_id="someone-else")
    with pytest.raises(ta.UnknownApproverError):
        guard.verify_token(ta.TOKEN_PREFIX + base64.urlsafe_b64encode(ta.canonical_json(env2)).decode().rstrip("="), **kw)
    for bad in (res["approval_command_example"], "lanjutkan", "setuju", ta.TOKEN_PREFIX + "!!!", good + "\nsecond line"):
        with pytest.raises(ta.UnsignedApprovalError):
            guard.verify_token(bad, **kw)


def test_binding_expiry_and_scope_rules(tmp_path: Path, trusted_approver) -> None:
    pkg, _ = _build_pkg(tmp_path)
    digest, _ = compute_package_digest(pkg)
    guard = ta.default_guard()
    kw = dict(expected_project_id="sec16d_proj", expected_package_version="v1", live_manifest_digest=digest)
    now = datetime.now(timezone.utc)

    other = trusted_approver.sign(package_dir=pkg, project_id="another_proj")
    with pytest.raises(ta.ApprovalBindingMismatchError):
        guard.verify_token(other, **kw)  # cross-project replay
    v2 = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", package_version="v2")
    with pytest.raises(ta.ApprovalBindingMismatchError):
        guard.verify_token(v2, **kw)
    stale = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", manifest_digest="0" * 64)
    with pytest.raises(ta.ApprovalBindingMismatchError):
        guard.verify_token(stale, **kw)

    expired = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", now=now - timedelta(hours=3))
    with pytest.raises(ta.ApprovalExpiredError):
        guard.verify_token(expired, **kw)
    future = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", now=now + timedelta(hours=1))
    with pytest.raises(ta.ApprovalExpiredError):
        guard.verify_token(future, **kw)
    too_long = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", ttl=timedelta(days=30))
    with pytest.raises(ta.ApprovalExpiredError):
        guard.verify_token(too_long, **kw)

    narrow = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", scopes=["mcp_preflight"])
    assert guard.verify_token(narrow, required_scope="mcp_preflight", **kw)
    with pytest.raises(ta.ScopeMismatchError):
        guard.verify_token(narrow, required_scope="blender_scene_mutation", **kw)
    bad_scope = trusted_approver.sign(package_dir=pkg, project_id="sec16d_proj", scopes=["root_shell"])
    with pytest.raises(ta.ScopeMismatchError):
        guard.verify_token(bad_scope, **kw)


# ----------------------------------------------------------------------------- canonical manifest
def test_canonical_manifest_covers_every_production_input_without_exception(tmp_path: Path) -> None:
    pkg, _ = _build_pkg(tmp_path)
    base, hashes = compute_package_digest(pkg)
    for name in (
        "narration_dialogue.json", "caption_audio_plan.json", "character_bible.json", "style_bible.json",
        "camera_plan.json", "semantic_visual_plan.json", "research_report.json", "reference_adaptation.json",
    ):
        assert name in REQUIRED_PRODUCTION_INPUTS and name in hashes
        f = pkg / name
        orig = f.read_bytes()
        f.write_bytes(orig + b" ")
        assert compute_package_digest(pkg)[0] != base, f"{name} change not detected"
        f.write_bytes(orig)
    assert compute_package_digest(pkg)[0] == base

    # Any NEW non-runtime file (e.g. a sneaked-in asset) also changes the digest.
    (pkg / "extra_asset_notes.md").write_text("x", encoding="utf-8")
    assert compute_package_digest(pkg)[0] != base
    (pkg / "extra_asset_notes.md").unlink()

    # Runtime files do not affect it.
    (pkg / ".approvals").mkdir(exist_ok=True)
    (pkg / ".approvals" / "approval_ledger.jsonl").write_text("{}\n", encoding="utf-8")
    (pkg / "project_state.json").write_text((pkg / "project_state.json").read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert compute_package_digest(pkg)[0] == base

    # Symlink and missing required input are rejected.
    os.symlink(pkg / "script.md", pkg / "link.md")
    with pytest.raises(CanonicalManifestError, match="Symlink"):
        build_canonical_manifest(pkg)
    (pkg / "link.md").unlink()
    (pkg / "camera_plan.json").unlink()
    with pytest.raises(CanonicalManifestError, match="camera_plan.json"):
        build_canonical_manifest(pkg)


# ----------------------------------------------------------------------------- v4 path, ledger, CLI
def test_v4_state_machine_only_accepts_trusted_gate(tmp_path: Path, trusted_approver) -> None:
    pkg, _ = _build_pkg(tmp_path, "sec16d_v4")
    sm = SharedProjectStateMachine(tmp_path / "state_v4.json")
    sm.initialize(project_id="sec16d_v4", project_title="v4 gate", genres=["explainer"])
    for i, st in enumerate(
        ["REQUEST_RECEIVED", "RESEARCHING", "CREATIVE_DEVELOPMENT", "STORYBOARDING", "PREPRODUCTION_QC", "WAITING_APPROVAL"],
        start=1,
    ):
        sm.transition(st, expected_version=i, trigger="t", actor="master_director", evidence="ok")

    # Actor label + agent-made dict (the 01.6B hole) is rejected.
    with pytest.raises(ProductionApprovalFrozenError):
        sm.transition(
            "APPROVED", expected_version=7, trigger="x", actor="trusted_human_approval_gate", evidence="fake",
            verified_human_approval={"approved_digest": "a" * 64, "trusted_channel_verified": True},
        )
    # A fabricated VerifiedApproval object with a bogus token is rejected by signature re-verification.
    fake = ta.VerifiedApproval("tap-x", "test-human-1", "sec16d_v4", "v1", "a" * 64, ("all_production",),
                               "ab" * 16, "2026-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00", "XDX-SIGNED-APPROVAL e30")
    with pytest.raises(ta.TrustedApprovalError):
        sm._transition("APPROVED", expected_version=7, trigger="x", actor="trusted_human_approval_gate", task_id=None,
                       evidence="x", artifact_manifest=None, verified_human_approval=None,
                       verified_success_auditor_pass=False, trusted_approval=fake)

    token = trusted_approver.sign(package_dir=pkg, project_id="sec16d_v4", scopes=["mcp_preflight"])
    doc = sm.approve_via_trusted_gate(signed_token=token, package_dir=pkg, package_version="v1", expected_version=7)
    assert doc["current_state"] == "APPROVED" and doc["approval_status"]["trusted_channel_verified"] is True
    # Replay into the same project after reset is rejected.
    sm.transition("WAITING_REAPPROVAL", expected_version=8, trigger="rev", actor="master_director", evidence="rev")
    with pytest.raises(ta.ApprovalReplayError):
        sm.approve_via_trusted_gate(signed_token=token, package_dir=pkg, package_version="v1", expected_version=9)
    # Production states stay behind the Phase 02 boundary.
    with pytest.raises((ProductionApprovalFrozenError, InvalidStateTransitionError)):
        sm.transition("ASSET_PRODUCTION", expected_version=9, trigger="go", actor="master_director", evidence="x")


def test_ledger_tamper_and_cli_cannot_bypass(tmp_path: Path, trusted_approver) -> None:
    pkg, _ = _build_pkg(tmp_path, "sec16d_cli")
    sm = ProjectStateManager(pkg / "project_state.json")
    token = trusted_approver.sign(package_dir=pkg, project_id="sec16d_cli")
    sm.record_explicit_user_approval(package_dir=pkg, user_message=token)
    gate = ApprovalGate()
    assert gate.inspect_package(pkg, check_record=True)["status"] == "RECORD_MATCH_ONLY"

    # CLI runs in a fresh process with the REPO trust registry, which does not trust the test key -> fail closed.
    cli = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "approval_gate.py"), str(pkg), "--check"],
        cwd=ROOT_DIR, capture_output=True, text=True,
    )
    assert cli.returncode == 2 and ("TRUSTED_CHANNEL_UNAVAILABLE" in cli.stdout or "not a registered, unrevoked trusted key" in cli.stdout)

    # Editing the hash-chained ledger is detected.
    led = ta.TrustedApprovalGuard.ledger_path(pkg)
    lines = led.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["scopes"] = ["mcp_preflight"]
    led.write_text(json.dumps(first) + "\n", encoding="utf-8")
    assert gate.inspect_package(pkg, check_record=True)["status"] == "BLOCKED"

    # Deleting the ledger does not let the same token be consumed twice (state history keeps the nonce).
    led.unlink()
    sm.revoke_approval(package_dir=pkg, reason="reset")
    with pytest.raises(ta.ApprovalReplayError):
        sm.record_explicit_user_approval(package_dir=pkg, user_message=token)


def test_mcp_mutation_never_executes_in_phase_01_6d(tmp_path: Path, trusted_approver) -> None:
    pkg, _ = _build_pkg(tmp_path, "sec16d_mcp")
    sm = ProjectStateManager(pkg / "project_state.json")
    sm.record_explicit_user_approval(
        package_dir=pkg, user_message=trusted_approver.sign(package_dir=pkg, project_id="sec16d_mcp")
    )
    ctx = sm.build_authorization_context(pkg)
    adapter = XDXBlenderMCPAdapter(read_only=False)
    adapter.authorize_tool_call("get_scene_info", {})
    for tool in ("create_primitive", "modify_object", "set_material", "execute_blender_code"):
        with pytest.raises(MCPSceneMutationBlockedError, match="PHASE02_EXECUTION_NOT_STARTED"):
            adapter.authorize_tool_call(tool, {}, auth_context=ctx)


# ----------------------------------------------------------------------------- narration estimator
def test_narration_estimate_over_target_is_not_pass() -> None:
    from intelligence.universal_preproduction import NARRATION_DURATION_TOLERANCE

    over, ok = [], []
    for proj in sorted((ROOT_DIR / "projects").glob("bench_[a-d]_*")):
        est = json.loads((proj / "narration_dialogue.json").read_text(encoding="utf-8"))["estimated_timing"]
        target = float(est["target_duration_s"])
        (over if float(est["estimated_total_s"]) > target * (1 + NARRATION_DURATION_TOLERANCE) else ok).append(proj.name)
    # All four 01.6C benchmarks overrun their target (5-13%); they must not be considered within target.
    assert len(over) == 4 and not ok


def test_pre_tool_execution_guard_hook_fails_closed() -> None:
    hook = ROOT_DIR / "scripts" / "execution_guard_hook.py"

    def run(ev: dict) -> int:
        return subprocess.run([sys.executable, str(hook)], input=json.dumps(ev), capture_output=True, text=True).returncode

    assert run({"tool_name": "get_scene_info"}) == 0
    assert run({"tool_name": "bash", "arguments": {"command": "pytest -q"}}) == 0
    assert run({"tool_name": "create_primitive"}) == 2
    assert run({"tool_name": "unclassified_tool"}) == 2
    assert run({"tool_name": "bash", "arguments": {"command": "blender -b x.blend -a"}}) == 2
    assert run({"tool_name": "bash", "arguments": {"command": "npx remotion render Comp out.mp4"}}) == 2
    assert run({"tool_name": "create_primitive", "package_dir": "projects/bench_a_ac_explainer_60s"}) == 2
    assert subprocess.run([sys.executable, str(hook)], input="not json", capture_output=True, text=True).returncode == 2
