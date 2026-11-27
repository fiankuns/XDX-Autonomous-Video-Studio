"""Phase 02A Security Preflight & 15s 4-Shot AC Benchmark Preparation Tests."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
from pathlib import Path
from typing import Any

import pytest

from engines.web_engines import assert_render_authorized
from governance.canonical_manifest import (
    CanonicalManifestError,
    build_canonical_manifest,
    build_production_dependencies_manifest,
    manifest_digest,
    verify_production_dependencies,
)
from governance.trusted_approval import (
    ApprovalReplayError,
    PhaseBoundaryBlockedError,
    TrustedApprovalGuard,
    generate_approver_keypair,
    sign_approval_token,
)
from scripts.execution_guard_hook import decide as guard_decide

ROOT_DIR = Path(__file__).resolve().parent.parent


def _concurrent_consume_worker(args: tuple[str, str, str, str, str, str]) -> str:
    pkg_dir_s, reg_path_s, token, pid, ver, digest = args
    guard = TrustedApprovalGuard(Path(reg_path_s))
    va = guard.verify_token(
        token,
        expected_project_id=pid,
        expected_package_version=ver,
        live_manifest_digest=digest,
        required_scope="mcp_preflight",
    )
    try:
        guard.consume(Path(pkg_dir_s), va)
        return "CONSUMED"
    except ApprovalReplayError:
        return "REPLAY"


@pytest.mark.integration
def test_p02a_01_concurrent_approval_consume_is_atomic_and_hash_chain_intact(tmp_path: Path) -> None:
    """DEF-P02A-033: 6 concurrent processes consuming the same single-use token -> exactly 1 succeeds, 5 REPLAY."""
    priv, pub = generate_approver_keypair()
    reg_path = tmp_path / "trusted_approvers.json"
    reg_path.write_text(
        json.dumps(
            {
                "schema_version": "4.0.0-phase01.6d",
                "approvers": [
                    {
                        "key_id": "owner-conc-1",
                        "algorithm": "ed25519",
                        "public_key_b64url": pub,
                        "owner": "owner",
                        "added_at": "2026-11-27T00:00:00+00:00",
                        "revoked": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    digest = "a" * 64
    tok = sign_approval_token(
        private_key_raw=priv,
        key_id="owner-conc-1",
        project_id="conc_proj",
        package_version="v1",
        manifest_digest=digest,
        scopes=["mcp_preflight"],
    )

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=6) as pool:
        results = pool.map(
            _concurrent_consume_worker,
            [(str(pkg), str(reg_path), tok, "conc_proj", "v1", digest)] * 6,
        )

    assert results.count("CONSUMED") == 1, f"Expected exactly 1 CONSUMED, got {results}"
    assert results.count("REPLAY") == 5, f"Expected 5 REPLAY, got {results}"
    entries = TrustedApprovalGuard(reg_path).read_ledger(pkg)
    assert len(entries) == 1
    assert entries[0]["seq"] == 1


@pytest.mark.unit
def test_p02a_02_trust_registry_out_of_band_sha256_pin_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DEF-P02A-032: mismatch against out-of-band XDX_TRUSTED_REGISTRY_SHA256 marks channel UNAVAILABLE."""
    _, pub = generate_approver_keypair()
    reg_path = tmp_path / "trusted_approvers.json"
    reg_path.write_text(
        json.dumps(
            {
                "schema_version": "4.0.0-phase01.6d",
                "approvers": [
                    {
                        "key_id": "owner-pin-1",
                        "algorithm": "ed25519",
                        "public_key_b64url": pub,
                        "owner": "owner",
                        "added_at": "2026-11-27T00:00:00+00:00",
                        "revoked": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    guard = TrustedApprovalGuard(reg_path)
    actual_sha = hashlib.sha256(reg_path.read_bytes()).hexdigest()

    monkeypatch.setenv("XDX_TRUSTED_REGISTRY_SHA256", actual_sha)
    assert guard.channel_status()["status"] == "AVAILABLE"

    monkeypatch.setenv("XDX_TRUSTED_REGISTRY_SHA256", "0" * 64)
    st = guard.channel_status()
    assert st["status"] == "UNAVAILABLE"
    assert st["production_status"] == "BLOCKED"


@pytest.mark.unit
def test_p02a_03_terminal_and_renderer_guard_blocks_all_bypass_patterns() -> None:
    """DEF-P02A-034: Execution guard blocks CommandLine, npx remotion, threejs node, ffmpeg outputs, indirection & trust tamper."""
    blocked_cmds = [
        {"tool_name": "run_command", "arguments": {"CommandLine": "npx remotion render src/index.ts out.mp4"}},
        {"tool_name": "run_command", "arguments": {"CommandLine": "node engines/web/three_deterministic_scene.mjs --render"}},
        {"tool_name": "bash", "arguments": {"command": "ffmpeg -i in.png -c:v libx264 /tmp/leak.mp4"}},
        {"tool_name": "run_command", "arguments": {"CommandLine": "python3 -c 'import subprocess; subprocess.run([\"remotion\", \"render\"])'"}},
        {"tool_name": "run_command", "arguments": {"CommandLine": "echo '{}' > registry/trusted_approvers.json"}},
        {"tool_name": "run_command", "arguments": {"CommandLine": "git add registry/trusted_approvers.json && git commit -m inject"}},
    ]
    for ev in blocked_cmds:
        ok, reason = guard_decide(ev)
        assert ok is False, f"Expected BLOCK for {ev}, got allow ({reason})"

    # Renderer-level Python guard must also fail-closed!
    with pytest.raises(PhaseBoundaryBlockedError):
        assert_render_authorized(ROOT_DIR / "projects" / "bench_p02a_ac_15s", required_scope="render_production")


@pytest.mark.unit
def test_p02a_04_production_dependencies_pinned_and_drift_detected(tmp_path: Path) -> None:
    """DEF-P02A-035: Modifying an external renderer dependency after pinning raises CanonicalManifestError."""
    fake_repo = tmp_path / "repo"
    (fake_repo / "engines").mkdir(parents=True)
    dep = fake_repo / "engines" / "renderer.mjs"
    dep.write_text("console.log('v1');\n", encoding="utf-8")

    pkg = fake_repo / "projects" / "p1"
    pkg.mkdir(parents=True)
    dep_man = build_production_dependencies_manifest(fake_repo, ["engines/renderer.mjs"])
    (pkg / "production_dependencies.json").write_text(json.dumps(dep_man), encoding="utf-8")

    assert verify_production_dependencies(pkg, fake_repo)["verified"] is True

    # Mutate external renderer script -> must fail closed!
    dep.write_text("console.log('tampered');\n", encoding="utf-8")
    with pytest.raises(CanonicalManifestError, match="drift"):
        verify_production_dependencies(pkg, fake_repo)


@pytest.mark.integration
def test_p02a_05_ac_15s_4shot_benchmark_package_waiting_approval_and_canonical_verified() -> None:
    """Verify projects/bench_p02a_ac_15s meets all Phase 02A Part B requirements and stops at WAITING_APPROVAL."""
    pkg = ROOT_DIR / "projects" / "bench_p02a_ac_15s"
    assert pkg.is_dir(), "projects/bench_p02a_ac_15s must be prepared"

    sb = json.loads((pkg / "storyboard.json").read_text(encoding="utf-8"))
    assert sb["duration_s"] == 15.0
    assert sb["total_frames"] == 450
    assert len(sb["shots"]) == 4

    nar = json.loads((pkg / "narration_dialogue.json").read_text(encoding="utf-8"))
    assert nar["estimated_timing"]["duration_fit_status"] == "WITHIN_TARGET"
    assert nar["estimated_timing"]["estimated_total_s"] <= 15.3

    canon = build_canonical_manifest(pkg)
    live_digest = manifest_digest(canon)
    assert "production_dependencies.json" in canon["files"]
    assert verify_production_dependencies(pkg, ROOT_DIR)["verified"] is True

    app_man = json.loads((pkg / "approval_package_manifest.json").read_text(encoding="utf-8"))
    assert app_man["status"] == "WAITING_APPROVAL"
    assert app_man["package_digest"] == live_digest

    v4_state = json.loads((pkg / "project_state_v4.json").read_text(encoding="utf-8"))
    assert v4_state["current_state"] == "WAITING_APPROVAL"
    assert v4_state["approval_status"]["approved"] is False

    # Zero MP4 renders before approval
    assert list(pkg.rglob("*.mp4")) == []
