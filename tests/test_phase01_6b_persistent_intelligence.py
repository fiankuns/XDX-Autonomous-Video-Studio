"""Phase 01.6B Comprehensive Audit Hardening, DAG Scheduler, 6-Partition Memory & Checkpoint Suite (28 Tests).

Covers all Section 2–Section 13 requirements of Phase 01.6B, categorized explicitly with pytest markers:
- `@pytest.mark.unit` (12 tests): Deterministic schema, boundary, verifier, capability, adapter, and state tests.
- `@pytest.mark.integration` (9 tests): Real symlink, cross-process `fcntl.flock`, multi-process SQLite WAL, DAG async execution, checkpoint resume, and revision archiving tests.
- `@pytest.mark.mock_test` (6 tests): Controlled simulated timeouts, cancellations, stale capability TTLs, corrupted SQLite/checkpoint payloads, and interrupted external tasks.
- `@pytest.mark.live_evidence` (1 test): Verification of the live Phase 01.6B native multi-agent workflow (`xdx-rea-reference-analyst` + `research` + `xdx-preproduction-verifier`), Reference DB preservation, and subprocess checkpoint resume proof.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from memory.persistence_probe import (
    STORAGE_TIERS,
    StoragePersistenceProbe,
    sync_reference_database_into_knowledge_memory,
)
from memory.persistent_memory import (
    CorruptedMemoryRecordError,
    MemoryIntegrityError,
    SecretLeakBlockedError,
    SixPartitionMemoryStore,
)
from orchestration.capability_discovery import CAPABILITY_STATUSES, RuntimeCapabilityDiscovery
from orchestration.checkpoint_manager import (
    MANDATORY_CHECKPOINT_FIELDS,
    CheckpointManager,
    CorruptedCheckpointError,
)
from orchestration.dependency_scheduler import (
    PhaseBoundaryExecutionBlockedError,
    TaskDependencyScheduler,
)
from orchestration.handoff_manager import (
    ArtifactBoundaryError,
    ArtifactOwnershipLockManager,
    DuplicateArtifactPathError,
    HandoffValidationError,
    InvalidArtifactOwnershipError,
    ParallelWriteConflictError,
    TaskHandoffManager,
    compute_file_sha256,
)
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentInvocationReceipt,
    AgentReviewReport,
    NativeAgentExecutionAdapter,
    utc_now_iso,
)
from orchestration.revision_manager import RevisionManager
from orchestration.shared_state import (
    ALL_26_PROJECT_STATES_V4,
    SharedProjectStateMachine,
    StateVersionConflictError,
)
from intelligence.state_and_approval import InvalidStateTransitionError

ROOT_DIR = Path(__file__).resolve().parent.parent


def _make_handoff(
    *,
    task_id: str,
    project_id: str = "proj_p016b",
    assigned_agent: str = "topic_research_agent",
    dependencies: list[str] | None = None,
    input_artifacts: list[str] | None = None,
    input_artifact_hashes: dict[str, str] | None = None,
    owned_artifacts: list[str] | None = None,
    output_artifacts: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    status: str = "PENDING",
    max_attempts: int = 2,
    timeout_seconds: int = 30,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owned = owned_artifacts if owned_artifacts is not None else [f"projects/{project_id}/research.md"]
    outs = output_artifacts if output_artifacts is not None else list(owned)
    ctx: dict[str, Any] = {
        "project_state": "RESEARCHING",
        "genre_ids": ["explainer"],
        "reference_ids": ["REF-002"],
        "workspace_mode": "inherit",
        "notes": "Phase 01.6B test handoff",
    }
    if extra_context:
        ctx.update(extra_context)

    done_target = outs[0] if outs else f"projects/{project_id}/research.md"
    done_type = "file_exists_nonempty" if outs else "independent_review_verdict"
    return {
        "task_id": task_id,
        "project_id": project_id,
        "parent_task_id": None,
        "assigned_agent": assigned_agent,
        "goal": f"Execute deterministic Phase 01.6B test task {task_id} safely.",
        "context": ctx,
        "input_artifacts": input_artifacts if input_artifacts is not None else [],
        "input_artifact_hashes": input_artifact_hashes if input_artifact_hashes is not None else {},
        "dependencies": dependencies if dependencies is not None else [],
        "owned_artifacts": owned,
        "allowed_tools": allowed_tools if allowed_tools is not None else ["view_file", "write_to_file"],
        "forbidden_actions": ["Mutate outside project boundary", "Bypass independent verification"],
        "expected_output": {
            "summary": f"Output summary for {task_id}.",
            "output_artifacts": outs,
            "output_format": "json" if done_target.endswith(".json") else "markdown",
        },
        "return_schema": "xdx.phase01_6b.test.v4.0",
        "done_when": [
            {
                "criterion_id": "DONE_01",
                "check_type": done_type,
                "target": done_target,
                "description": "Deterministic output check.",
            }
        ],
        "required_evidence": [f"Verified output evidence for {task_id}"],
        "retry_budget": {"max_attempts": max_attempts, "attempts_used": 0, "timeout_seconds": timeout_seconds},
        "status": status,
    }


def _copy_minimal_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "schemas").mkdir()
    for sf in (ROOT_DIR / "schemas").glob("*.schema.json"):
        (ws / "schemas" / sf.name).write_bytes(sf.read_bytes())
    return ws


# ==============================================================================
# 1–9: INDEPENDENT AUDIT FIXES (Canonical Ownership, Boundaries, Verifier)
# ==============================================================================


@pytest.mark.unit
def test_01_canonical_path_collision_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)

    # Duplicate alias inside a single handoff
    dup_single = _make_handoff(
        task_id="TASK-DUP-01",
        owned_artifacts=[
            "projects/proj_p016b/research.md",
            "./projects/proj_p016b/../proj_p016b/research.md",
        ],
    )
    with pytest.raises(DuplicateArtifactPathError):
        mgr.validate_handoff(dup_single, base_dir=ws)

    # Two distinct path strings pointing to the exact same physical file across two concurrent tasks
    t1 = _make_handoff(
        task_id="TASK-CAN-01",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/proj_p016b/research.md"],
        status="RUNNING",
    )
    t2 = _make_handoff(
        task_id="TASK-CAN-02",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/./proj_p016b/sub/../research.md"],
        status="RUNNING",
    )
    with pytest.raises(ParallelWriteConflictError, match="Canonical parallel write conflict"):
        mgr.validate_task_dag_and_ownership([t1, t2], base_dir=ws)


@pytest.mark.integration
def test_02_symlink_escape_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    outside_secret = tmp_path / "outside_host_file.md"
    outside_secret.write_text("host secret\n", encoding="utf-8")

    proj_dir = ws / "projects" / "proj_p016b"
    proj_dir.mkdir(parents=True)
    escape_link = proj_dir / "research.md"
    escape_link.symlink_to(outside_secret)

    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    h = _make_handoff(task_id="TASK-SYM-01", owned_artifacts=["projects/proj_p016b/research.md"])
    with pytest.raises(ArtifactBoundaryError, match="Symlink escape rejected"):
        mgr.validate_handoff(h, base_dir=ws)

    # Symlink inside project pointing to a sibling project must also be rejected for writable outputs
    other_proj = ws / "projects" / "other_proj"
    other_proj.mkdir(parents=True)
    other_file = other_proj / "research.md"
    other_file.write_text("other project\n", encoding="utf-8")
    escape_link.unlink()
    escape_link.symlink_to(other_file)
    with pytest.raises(ArtifactBoundaryError, match="outside project boundary"):
        mgr.validate_handoff(h, base_dir=ws)


@pytest.mark.unit
def test_03_outside_workspace_and_outside_project_output_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)

    h_outside_ws = _make_handoff(task_id="TASK-BDR-01", owned_artifacts=["../../etc/passwd"])
    with pytest.raises(ArtifactBoundaryError, match="escapes workspace"):
        mgr.validate_handoff(h_outside_ws, base_dir=ws)

    h_wrong_proj = _make_handoff(
        task_id="TASK-BDR-02",
        project_id="proj_alpha",
        owned_artifacts=["projects/proj_beta/research.md"],
    )
    with pytest.raises(ArtifactBoundaryError, match="Output boundary violation"):
        mgr.validate_handoff(h_wrong_proj, base_dir=ws)

    h_protected = _make_handoff(
        task_id="TASK-BDR-03",
        owned_artifacts=["orchestration/handoff_manager.py"],
    )
    with pytest.raises(ArtifactBoundaryError):
        mgr.validate_handoff(h_protected, base_dir=ws)


@pytest.mark.unit
def test_04_output_artifacts_not_in_owned_artifacts_and_role_pattern_mismatch_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)

    h_unowned_out = _make_handoff(
        task_id="TASK-OWN-01",
        owned_artifacts=["projects/proj_p016b/research.md"],
        output_artifacts=["projects/proj_p016b/research.md", "projects/proj_p016b/extra.md"],
    )
    with pytest.raises(InvalidArtifactOwnershipError, match="not declared in owned_artifacts"):
        mgr.validate_handoff(h_unowned_out, base_dir=ws)

    # topic_research_agent cannot claim ownership of storyboard.json
    h_wrong_role_pat = _make_handoff(
        task_id="TASK-OWN-02",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/proj_p016b/storyboard.json"],
    )
    with pytest.raises(InvalidArtifactOwnershipError, match="does not match role"):
        mgr.validate_handoff(h_wrong_role_pat, base_dir=ws)


@pytest.mark.integration
def test_05_cross_process_fcntl_ownership_lock_and_stale_lock_recovery(tmp_path: Path) -> None:
    lock_dir = tmp_path / "locks"
    target_file = (tmp_path / "projects" / "proj_p016b" / "research.md").resolve()
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("# Locked\n", encoding="utf-8")

    # 1. Spawn a real child OS process holding the fcntl lock and verify parent gets ParallelWriteConflictError
    ready_flag = tmp_path / "child_locked.flag"
    release_flag = tmp_path / "release_child.flag"
    child_code = "\n".join(
        [
            "import sys, time",
            "from pathlib import Path",
            f"sys.path.insert(0, {str(ROOT_DIR)!r})",
            "from orchestration.handoff_manager import ArtifactOwnershipLockManager",
            f"lm = ArtifactOwnershipLockManager(Path({str(lock_dir)!r}))",
            f"lm.acquire_for_task(task_id='TASK-CHILD', agent_id='topic_research_agent', canonical_paths=[Path({str(target_file)!r})])",
            f"Path({str(ready_flag)!r}).write_text('ready')",
            f"while not Path({str(release_flag)!r}).exists():",
            "    time.sleep(0.05)",
            "lm.release_for_task('TASK-CHILD')",
        ]
    )
    proc = subprocess.Popen([sys.executable, "-c", child_code], cwd=str(ROOT_DIR))
    try:
        deadline = time.time() + 10.0
        while not ready_flag.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert ready_flag.exists(), "Child process failed to acquire lock in time"

        parent_lm = ArtifactOwnershipLockManager(lock_dir)
        with pytest.raises(ParallelWriteConflictError, match="Cross-process write lock conflict"):
            parent_lm.acquire_for_task(
                task_id="TASK-PARENT",
                agent_id="topic_research_agent",
                canonical_paths=[target_file],
            )
    finally:
        release_flag.write_text("release")
        proc.wait(timeout=10)

    # 2. Simulate crashed dead PID stale metadata sidecar (flock is free because OS closed dead fd)
    key = ArtifactOwnershipLockManager._key_for_canonical(target_file)
    meta_file = lock_dir / f"{key}.meta.json"
    meta_file.write_text(
        json.dumps(
            {
                "canonical_path": target_file.as_posix(),
                "lock_key": key,
                "task_id": "TASK-CRASHED",
                "agent_id": "topic_research_agent",
                "pid": 99999999,
                "acquired_at_epoch": time.time() - 9999,
                "ttl_seconds": 10,
                "released": False,
            }
        ),
        encoding="utf-8",
    )
    recovered_handles = parent_lm.acquire_for_task(
        task_id="TASK-RECOVERY",
        agent_id="topic_research_agent",
        canonical_paths=[target_file],
    )
    assert len(recovered_handles) == 1
    assert recovered_handles[0].stale_recovered is True
    assert parent_lm.release_for_task("TASK-RECOVERY") == 1


def _build_valid_producer_and_verifier_fixture(ws: Path) -> tuple[TaskHandoffManager, dict, dict, dict[str, str], dict]:
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    rel_script = "projects/proj_p016b/script.md"
    f_script = ws / rel_script
    f_script.parent.mkdir(parents=True, exist_ok=True)
    f_script.write_text("# Naskah Bahasa Indonesia Asli\n", encoding="utf-8")
    sha = compute_file_sha256(f_script)
    pre_hashes = {rel_script: sha}

    prod_h = _make_handoff(
        task_id="TASK-PROD-10",
        assigned_agent="scriptwriter_agent",
        owned_artifacts=[rel_script],
        status="COMPLETED",
    )
    ver_h = _make_handoff(
        task_id="TASK-VER-10",
        assigned_agent="preproduction_verifier",
        dependencies=["TASK-PROD-10"],
        input_artifacts=[rel_script],
        input_artifact_hashes=dict(pre_hashes),
        owned_artifacts=[],
        output_artifacts=[],
        allowed_tools=["view_file"],
        status="RUNNING",
    )
    report = {
        "schema_version": "4.0.0-phase01.6b",
        "review_id": "REV-P016B-010",
        "project_id": "proj_p016b",
        "verifier_agent": "preproduction_verifier",
        "reviewed_task_id": "TASK-PROD-10",
        "producer_agent": "scriptwriter_agent",
        "verdict": "PASS",
        "invocation_receipt": {
            "invocation_id": "RCPT-VER-010",
            "agent_id": "preproduction_verifier",
            "runtime_name": "antigravity",
            "execution_mode": "native_subagent",
            "actually_invoked": True,
            "conversation_id": "conv_verifier_isolated_999",
            "started_at": "2026-11-27T14:00:00+00:00",
            "completed_at": "2026-11-27T14:00:05+00:00",
        },
        "reviewed_artifact_hashes": dict(pre_hashes),
        "required_criteria_ids": ["CRIT_01", "CRIT_02"],
        "checked_criteria": [
            {"criterion_id": "CRIT_01", "status": "PASS", "evidence": "Original Indonesian narration verified on disk."},
            {"criterion_id": "CRIT_02", "status": "PASS", "evidence": "Zero silent mutations or placeholder tokens."},
        ],
        "defects": [],
    }
    return mgr, prod_h, ver_h, pre_hashes, report


@pytest.mark.unit
def test_06_verifier_empty_hashes_or_empty_criteria_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr, prod_h, ver_h, pre_hashes, report = _build_valid_producer_and_verifier_fixture(ws)

    with pytest.raises(HandoffValidationError, match="Empty pre_review_hashes"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes={},
            review_report=report,
            base_dir=ws,
        )

    bad_empty_rep_hashes = copy.deepcopy(report)
    bad_empty_rep_hashes["reviewed_artifact_hashes"] = {}
    with pytest.raises(HandoffValidationError):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=bad_empty_rep_hashes,
            base_dir=ws,
        )

    bad_empty_crit = copy.deepcopy(report)
    bad_empty_crit["required_criteria_ids"] = []
    bad_empty_crit["checked_criteria"] = []
    with pytest.raises(HandoffValidationError):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=bad_empty_crit,
            base_dir=ws,
        )


@pytest.mark.unit
def test_07_verifier_incomplete_artifact_manifest_and_mismatched_producer_task_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr, prod_h, ver_h, pre_hashes, report = _build_valid_producer_and_verifier_fixture(ws)

    # Mismatched producer task ID
    wrong_task_rep = copy.deepcopy(report)
    wrong_task_rep["reviewed_task_id"] = "TASK-OTHER-999"
    with pytest.raises(HandoffValidationError, match="Mismatched reviewed_task_id"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=wrong_task_rep,
            base_dir=ws,
        )

    # Producer owns 2 artifacts, but verifier only hashed 1 -> incomplete manifest rejected!
    second_rel = "projects/proj_p016b/authored_creative_payload.json"
    f2 = ws / second_rel
    f2.write_text('{"ok": true}\n', encoding="utf-8")
    prod_h2 = copy.deepcopy(prod_h)
    prod_h2["owned_artifacts"].append(second_rel)
    prod_h2["expected_output"]["output_artifacts"].append(second_rel)
    with pytest.raises(HandoffValidationError, match="Incomplete artifact hash manifest"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h2,
            pre_review_hashes=pre_hashes,
            review_report=report,
            base_dir=ws,
        )


@pytest.mark.unit
def test_08_verifier_false_pass_with_failed_criterion_or_defects_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr, prod_h, ver_h, pre_hashes, report = _build_valid_producer_and_verifier_fixture(ws)

    false_pass_crit = copy.deepcopy(report)
    false_pass_crit["checked_criteria"][1]["status"] = "FAIL"
    with pytest.raises(HandoffValidationError, match="False PASS rejected"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=false_pass_crit,
            base_dir=ws,
        )

    false_pass_defect = copy.deepcopy(report)
    false_pass_defect["defects"] = [
        {
            "defect_id": "DEF-001",
            "location": "projects/proj_p016b/script.md:1",
            "severity": "HIGH",
            "expected_result": "Verified citation",
            "observed_result": "Missing citation",
            "evidence": "Line 1 lacks verified URL",
            "responsible_agent": "scriptwriter_agent",
        }
    ]
    with pytest.raises(HandoffValidationError, match="False PASS rejected"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=false_pass_defect,
            base_dir=ws,
        )


@pytest.mark.unit
def test_09_verifier_invocation_receipt_and_same_conversation_context_rejection(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr, prod_h, ver_h, pre_hashes, report = _build_valid_producer_and_verifier_fixture(ws)

    # Boolean fresh_context_confirmed=True without invocation_receipt rejected
    legacy_boolean_only = copy.deepcopy(report)
    del legacy_boolean_only["invocation_receipt"]
    legacy_boolean_only["fresh_context_confirmed"] = True
    with pytest.raises(HandoffValidationError):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=legacy_boolean_only,
            base_dir=ws,
        )

    # Same conversation_id as producer -> context isolation violation!
    with pytest.raises(HandoffValidationError, match="equals producer conversation_id"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes=pre_hashes,
            review_report=report,
            producer_conversation_id="conv_verifier_isolated_999",
            base_dir=ws,
        )


# ==============================================================================
# 10–12: RUNTIME CAPABILITY DISCOVERY (7 Tiers, Evidence TTL, Adapters)
# ==============================================================================


@pytest.mark.unit
def test_10_capability_discovery_7_statuses_no_hardcoded_detected_host_tools(tmp_path: Path) -> None:
    missing_ev = tmp_path / "no_evidence.json"
    disc = RuntimeCapabilityDiscovery(evidence_path=missing_ev)
    rep = disc.discover()

    assert set(rep["capabilities_by_status"].keys()) == set(CAPABILITY_STATUSES)
    for host_tool in (
        "host_tool:invoke_subagent",
        "host_tool:define_subagent",
        "host_tool:send_message",
        "host_tool:manage_subagents",
    ):
        assert rep["capabilities"][host_tool]["status"] != "DETECTED_CAPABILITY"
        assert rep["capabilities"][host_tool]["status"] in {"DOCUMENTED_CAPABILITY", "UNKNOWN"}


@pytest.mark.mock_test
def test_11_capability_evidence_live_verified_and_stale_report_detection(tmp_path: Path) -> None:
    ev_file = tmp_path / "cap_ev.json"
    disc = RuntimeCapabilityDiscovery(evidence_path=ev_file)
    t0 = datetime(2026, 11, 27, 14, 0, 0, tzinfo=timezone.utc)

    disc.record_host_capability_evidence(
        [
            {
                "capability_id": "host_tool:invoke_subagent",
                "status": "LIVE_INVOCATION_VERIFIED",
                "verification_method": "host_subagent_invocation_receipt",
                "invocation_id": "INV-TEST-001",
                "conversation_id": "da609aaf922107b8f659c4ec5d199b1f",
                "workspace_mode": "inherit",
                "timestamp_utc": t0.isoformat(),
                "evidence_summary": "Simulated live subagent invocation receipt for TTL verification.",
            }
        ],
        ttl_seconds=300,
        now=t0,
    )

    fresh = disc.discover(now=t0 + timedelta(seconds=60))
    assert fresh["capability_evidence_status"]["is_stale"] is False
    assert fresh["capabilities"]["host_tool:invoke_subagent"]["status"] == "LIVE_INVOCATION_VERIFIED"

    stale = disc.discover(now=t0 + timedelta(seconds=601))
    assert stale["capability_evidence_status"]["is_stale"] is True
    assert stale["capabilities"]["host_tool:invoke_subagent"]["status"] == "DOCUMENTED_CAPABILITY"


@pytest.mark.mock_test
def test_12_codex_and_antigravity_runtime_adapters_honest_probing(monkeypatch: pytest.MonkeyPatch) -> None:
    disc = RuntimeCapabilityDiscovery()
    ag = disc.antigravity_adapter.detect_host_markers()
    assert ag["python_can_introspect_host_llm_tools_directly"] is False

    monkeypatch.setenv("CODEX_SANDBOX_ENV", "1")
    cx = disc.codex_adapter.detect_host_markers()
    assert cx["detected"] is True
    assert "CODEX_SANDBOX_ENV" in cx["env_markers_present"]
    assert cx["python_can_introspect_host_llm_tools_directly"] is False


# ==============================================================================
# 13–18: DEPENDENCY SCHEDULER & NATIVE EXECUTION ADAPTER
# ==============================================================================


@pytest.mark.integration
def test_13_dag_topological_parallel_execution_and_concurrency_cap(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    sched = TaskDependencyScheduler(
        root_dir=ws, max_parallel_specialists=2, handoff_manager=mgr, execution_adapter=adapter
    )

    # 3 independent root tasks + 1 join task; concurrency cap=2 ensures peak active <= 2
    t1 = _make_handoff(
        task_id="TASK-DAG-01",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/proj_p016b/research.md"],
    )
    t2 = _make_handoff(
        task_id="TASK-DAG-02",
        assigned_agent="rea_video_reference_analyst",
        owned_artifacts=["projects/proj_p016b/reference_analysis.md"],
    )
    t3 = _make_handoff(
        task_id="TASK-DAG-03",
        assigned_agent="creative_director",
        owned_artifacts=["projects/proj_p016b/blueprint.md"],
    )
    t4 = _make_handoff(
        task_id="TASK-DAG-04",
        assigned_agent="scriptwriter_agent",
        dependencies=["TASK-DAG-01", "TASK-DAG-02", "TASK-DAG-03"],
        input_artifacts=[
            "projects/proj_p016b/research.md",
            "projects/proj_p016b/reference_analysis.md",
            "projects/proj_p016b/blueprint.md",
        ],
        input_artifact_hashes={
            "projects/proj_p016b/research.md": "0" * 64,
            "projects/proj_p016b/reference_analysis.md": "0" * 64,
            "projects/proj_p016b/blueprint.md": "0" * 64,
        },
        owned_artifacts=["projects/proj_p016b/script.md"],
    )

    in_flight = 0
    peak_in_flight = 0

    async def _worker(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        nonlocal in_flight, peak_in_flight
        in_flight += 1
        peak_in_flight = max(peak_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

        def _sync_write(hd: dict[str, Any], root: Path) -> dict[str, Any]:
            for rel in hd["owned_artifacts"]:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f"# Generated by {hd['task_id']} attempt {attempt}\n", encoding="utf-8")
            return {"evidence_items": [f"Completed {hd['task_id']} deterministically"]}

        return adapter.execute_sequential_fallback(handoff=h, worker_fn=_sync_write)

    res = asyncio.run(sched.execute_dag([t1, t2, t3, t4], executor=_worker))
    assert res["overall_status"] == "SUCCEEDED"
    assert res["completed_tasks"] == ["TASK-DAG-01", "TASK-DAG-02", "TASK-DAG-03", "TASK-DAG-04"]
    assert peak_in_flight == 2  # Proves concurrent execution AND strict cap=2 enforcement!


@pytest.mark.unit
def test_14_blender_worker_phase01_6b_execution_blocked(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr)

    tb = _make_handoff(
        task_id="TASK-BLENDER-BLOCKED",
        assigned_agent="blender_specialist",
        owned_artifacts=["projects/proj_p016b/scenes/shot_01.json"],
        allowed_tools=["view_file", "run_command"],
    )

    async def _never_called(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        raise AssertionError("Blender worker must never be invoked in Phase 01.6B")

    with pytest.raises(PhaseBoundaryExecutionBlockedError, match="blocked in Phase 01.6B"):
        asyncio.run(sched.execute_dag([tb], executor=_never_called))


@pytest.mark.mock_test
def test_15_scheduler_task_timeout_retry_and_retry_exhaustion_downstream_blocked(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mem = SixPartitionMemoryStore(tmp_path / "sched_err.sqlite3")
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(
        root_dir=ws, handoff_manager=mgr, memory_store=mem, timeout_override_seconds=0.1
    )

    t_slow = _make_handoff(
        task_id="TASK-SLOW-01",
        max_attempts=2,
        timeout_seconds=5,
        owned_artifacts=["projects/proj_p016b/research.md"],
    )
    t_down = _make_handoff(
        task_id="TASK-DOWN-02",
        assigned_agent="creative_director",
        dependencies=["TASK-SLOW-01"],
        owned_artifacts=["projects/proj_p016b/blueprint.md"],
    )

    attempts_seen = 0

    async def _slow_worker(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        nonlocal attempts_seen
        attempts_seen += 1
        await asyncio.sleep(0.5)
        raise AssertionError("Should have timed out")

    res = asyncio.run(sched.execute_dag([t_slow, t_down], executor=_slow_worker))
    assert attempts_seen == 2
    assert res["failed_tasks"] == ["TASK-SLOW-01"]
    assert res["blocked_tasks"] == ["TASK-DOWN-02"]
    errs = mem.error.list_errors("proj_p016b")
    assert len(errs) == 2
    assert all(e["error_category"] == "TIMEOUT" for e in errs)


@pytest.mark.mock_test
def test_16_scheduler_cancellation_propagates_cancelled_and_blocked(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr)

    t1 = _make_handoff(task_id="TASK-CANC-01", owned_artifacts=["projects/proj_p016b/research.md"])
    t2 = _make_handoff(
        task_id="TASK-CANC-02",
        assigned_agent="creative_director",
        dependencies=["TASK-CANC-01"],
        owned_artifacts=["projects/proj_p016b/blueprint.md"],
    )

    async def _noop(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        raise AssertionError("Cancelled task should not run")

    res = asyncio.run(
        sched.execute_dag([t1, t2], executor=_noop, cancelled_task_ids={"TASK-CANC-01"})
    )
    assert res["overall_status"] == "CANCELLED"
    assert res["cancelled_tasks"] == ["TASK-CANC-01"]
    assert res["blocked_tasks"] == ["TASK-CANC-02"]


@pytest.mark.unit
def test_17_scheduler_rejects_false_worker_completion_missing_output_or_dispatch_plan(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr, execution_adapter=adapter)

    t_fake = _make_handoff(
        task_id="TASK-FAKE-DONE",
        max_attempts=1,
        owned_artifacts=["projects/proj_p016b/research.md"],
    )

    async def _liar_worker(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        # Claims SUCCEEDED without writing projects/proj_p016b/research.md to disk!
        return adapter.execute_sequential_fallback(
            handoff=h,
            worker_fn=lambda _hd, _rt: {"evidence_items": ["Claimed done without writing file"]},
        )

    res = asyncio.run(sched.execute_dag([t_fake], executor=_liar_worker))
    assert res["failed_tasks"] == ["TASK-FAKE-DONE"]
    assert res["completed_tasks"] == []
    assert res["failures"][0]["error_category"] == "VALIDATION_FAILED"


@pytest.mark.unit
def test_18_native_execution_adapter_separates_dispatch_plan_native_receipt_and_honest_fallback(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)

    h = _make_handoff(task_id="TASK-ADP-01", owned_artifacts=["projects/proj_p016b/research.md"])

    # 1. Dispatch plan NEVER claims actually_invoked=True
    plan_res = adapter.emit_host_dispatch_plan_only(h)
    assert plan_res.status == "DISPATCH_PENDING_HOST"
    assert plan_res.receipt.execution_mode == "dispatch_plan_only_not_invoked"
    assert plan_res.receipt.actually_invoked is False
    assert plan_res.receipt.verify_integrity() is True

    # 2. Cannot forge native_subagent receipt without valid conversation_id
    req = adapter.build_invocation_request(h)
    with pytest.raises(ValueError, match="valid conversation_id"):
        AgentInvocationReceipt.create_verified(
            request=req,
            runtime_name="antigravity",
            execution_mode="native_subagent",
            actually_invoked=True,
            conversation_id="",
            known_model_routing="inherit",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_artifact_hashes={},
        )

    # 3. Honest sequential fallback must have conversation_id=None
    out_p = ws / "projects" / "proj_p016b" / "research.md"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    seq_res = adapter.execute_sequential_fallback(
        handoff=h,
        worker_fn=lambda _hd, _rt: (out_p.write_text("# Honest\n", encoding="utf-8"), {"evidence_items": ["Written honestly"]})[1],
    )
    assert seq_res.receipt.execution_mode == "sequential_fallback_honest"
    assert seq_res.receipt.conversation_id is None
    assert "projects/proj_p016b/research.md" in seq_res.receipt.output_artifact_hashes


# ==============================================================================
# 19–20: 26-STATE SHARED PROJECT STATE MACHINE
# ==============================================================================


@pytest.mark.unit
def test_19_shared_state_26_states_optimistic_version_conflict_and_task_state_separation(tmp_path: Path) -> None:
    assert len(ALL_26_PROJECT_STATES_V4) == 26
    sm = SharedProjectStateMachine(tmp_path / "project_state_v4.json")
    doc = sm.initialize(project_id="proj_st", project_title="Uji 26 State", genres=["explainer"])
    assert doc["current_state"] == "IDLE"
    assert doc["state_version"] == 1

    doc = sm.transition(
        "REQUEST_RECEIVED",
        expected_version=1,
        trigger="BUAT_VIDEO",
        actor="master_director",
        evidence="User request accepted",
    )
    assert doc["state_version"] == 2

    # Stale expected_version=1 must fail with StateVersionConflictError!
    with pytest.raises(StateVersionConflictError):
        sm.transition(
            "RESEARCHING",
            expected_version=1,
            trigger="stale_writer",
            actor="master_director",
            evidence="Stale optimistic lock test",
        )

    # TaskState ('RUNNING' / 'READY') rejected from ProjectState transitions!
    with pytest.raises(InvalidStateTransitionError, match="TaskState"):
        sm.transition(
            "RUNNING",
            expected_version=2,
            trigger="bad_mix",
            actor="master_director",
            evidence="Task state mixed into project state",
        )

    v34 = sm.export_v3_4_compatible_view()
    assert v34["v3_4_compatible_state"] == "INIT"


@pytest.mark.unit
def test_20_shared_state_blocks_agent_self_approval_and_unverified_completed(tmp_path: Path) -> None:
    sm = SharedProjectStateMachine(tmp_path / "project_state_gates.json")
    sm.initialize(project_id="proj_gates", project_title="Gate Safety", genres=["explainer"])
    sm.transition("REQUEST_RECEIVED", expected_version=1, trigger="init", actor="master_director", evidence="ok")
    sm.transition("RESEARCHING", expected_version=2, trigger="r", actor="master_director", evidence="ok")
    sm.transition("CREATIVE_DEVELOPMENT", expected_version=3, trigger="c", actor="master_director", evidence="ok")
    sm.transition("STORYBOARDING", expected_version=4, trigger="s", actor="master_director", evidence="ok")
    sm.transition("PREPRODUCTION_QC", expected_version=5, trigger="q", actor="preproduction_verifier", evidence="ok")
    sm.transition("WAITING_APPROVAL", expected_version=6, trigger="w", actor="master_director", evidence="ok")

    # Master director cannot self-approve!
    with pytest.raises(InvalidStateTransitionError, match="trusted_human_approval_gate"):
        sm.transition("APPROVED", expected_version=7, trigger="self_approve", actor="master_director", evidence="fake")

    # Pause & LANJUTKAN_PROJECT cannot auto-approve!
    sm.transition("PAUSED", expected_version=7, trigger="pause", actor="master_director", evidence="paused")
    with pytest.raises(InvalidStateTransitionError, match="LANJUTKAN_PROJECT cannot auto-approve"):
        sm.restore_after_interruption(expected_version=8, resume_target_state="APPROVED")

    sm.restore_after_interruption(expected_version=8, resume_target_state="WAITING_APPROVAL")
    assert sm.load()["approval_status"]["approved"] is False


# ==============================================================================
# 21–24: SIX-PARTITION SQLITE MEMORY & 5-TIER PERSISTENCE PROOF
# ==============================================================================


@pytest.mark.integration
def test_21_six_partition_sqlite_wal_crud_project_isolation_and_secret_leak_blocker(tmp_path: Path) -> None:
    store = SixPartitionMemoryStore(tmp_path / "six_part.sqlite3")

    # 1. KnowledgeMemory append-only protection
    store.knowledge.put_versioned(entry_id="topic:yakhchal", version_tag="v1", category="research", payload={"temp_c": 0})
    with pytest.raises(MemoryIntegrityError, match="Append-only violation"):
        store.knowledge.put_versioned(entry_id="topic:yakhchal", version_tag="v1", category="research", payload={"temp_c": 5})

    # 2. ProductionMemory blocks unverified techniques
    with pytest.raises(MemoryIntegrityError, match="Cannot promote unverified technique"):
        store.production.record_tested_technique(
            technique_id="cam_untested", version_tag="v1", domain="camera", test_status="SPECIFICATION_ONLY", payload={}
        )
    store.production.record_tested_technique(
        technique_id="cam_ortho", version_tag="v1", domain="camera", test_status="RUNTIME_TESTED", payload={"focal_mm": 36}
    )

    # 3. ProjectMemory strict project_id isolation
    store.project.put_slot("proj_A", "script", {"title": "Video Proyek A"})
    store.project.put_slot("proj_B", "script", {"title": "Video Proyek B"})
    assert store.project.get_latest_slot("proj_A", "script")["payload"]["title"] == "Video Proyek A"
    assert store.project.get_latest_slot("proj_B", "script")["payload"]["title"] == "Video Proyek B"
    assert store.project.get_latest_slot("proj_C", "script") is None

    # 4. ExecutionMemory, ErrorMemory, QualityMemory
    store.execution.append_record(project_id="proj_A", record_kind="step", record_id="s1", payload={"ok": True})
    store.error.record_error(project_id="proj_A", error_id="e1", task_id="TASK-1", error_category="TIMEOUT", payload={"ms": 1000})
    store.quality.record_evaluation(project_id="proj_A", evaluation_id="q1", target_ref="TASK-1", review_status="PASS", payload={"lufs": -14.8})
    assert store.execution.list_records("proj_B") == []
    assert store.error.list_errors("proj_B") == []
    assert store.quality.list_evaluations("proj_B") == []

    # 5. Secret/token leak blocker
    with pytest.raises(SecretLeakBlockedError):
        store.project.put_slot("proj_A", "leak1", {"token": "gh" + "p_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"})
    with pytest.raises(SecretLeakBlockedError):
        store.project.put_slot("proj_A", "leak2", {"path": "/opt/antigravity/tokens/github.json"})

    integ = store.verify_database_integrity()
    assert integ["all_rows_sha256_verified"] is True


@pytest.mark.mock_test
def test_22_corrupted_sqlite_memory_row_sha256_detection(tmp_path: Path) -> None:
    db_file = tmp_path / "tamper.sqlite3"
    store = SixPartitionMemoryStore(db_file)
    store.project.put_slot("proj_tamper", "storyboard", {"shots": 12})

    # Corrupt payload_json directly via raw sqlite3 without updating record_sha256
    conn = sqlite3.connect(str(db_file))
    conn.execute("UPDATE project_memory SET payload_json='{\"shots\": 999}' WHERE project_id='proj_tamper';")
    conn.commit()
    conn.close()

    with pytest.raises(CorruptedMemoryRecordError, match="Corrupted record detected"):
        store.project.get_latest_slot("proj_tamper", "storyboard")
    with pytest.raises(CorruptedMemoryRecordError):
        store.verify_database_integrity()


@pytest.mark.integration
def test_23_concurrent_multiprocess_sqlite_wal_writes_zero_corruption(tmp_path: Path) -> None:
    db_file = tmp_path / "concurrent_wal.sqlite3"
    SixPartitionMemoryStore(db_file)

    worker_script = "\n".join(
        [
            "import sys",
            "from pathlib import Path",
            f"sys.path.insert(0, {str(ROOT_DIR)!r})",
            "from memory.persistent_memory import SixPartitionMemoryStore",
            "wid = int(sys.argv[1])",
            f"s = SixPartitionMemoryStore(Path({str(db_file)!r}))",
            "for i in range(15):",
            "    s.execution.append_record(project_id='proj_conc', record_kind='worker_log', record_id=f'w{wid}', payload={'w': wid, 'i': i})",
        ]
    )
    procs = [subprocess.Popen([sys.executable, "-c", worker_script, str(w)], cwd=str(ROOT_DIR)) for w in range(4)]
    for p in procs:
        assert p.wait(timeout=20) == 0

    store = SixPartitionMemoryStore(db_file)
    integ = store.verify_database_integrity()
    assert integ["all_rows_sha256_verified"] is True
    assert integ["partition_row_counts"]["execution_memory"] == 60


@pytest.mark.integration
def test_24_five_tier_persistence_probe_cross_process_durability_and_honest_vm_limit() -> None:
    rep = StoragePersistenceProbe().generate_tier_report()
    assert set(rep["tiers"].keys()) == set(STORAGE_TIERS)
    assert rep["tiers"]["CURRENT_PROCESS_MEMORY"]["survives_process_exit"] is False
    assert rep["tiers"]["WORKSPACE_PERSISTENT_STORAGE"]["survives_process_exit"] is True
    assert rep["tiers"]["WORKSPACE_PERSISTENT_STORAGE"]["survives_vm_deletion"] is False
    assert rep["tiers"]["WORKSPACE_PERSISTENT_STORAGE"]["cross_process_proof"]["verified"] is True
    assert rep["tiers"]["GITHUB_PERSISTENT_KNOWLEDGE"]["survives_vm_deletion"] is True
    assert rep["tiers"]["EXTERNAL_ARTIFACT_STORAGE"]["git_lfs_media_hydrated"] is True


# ==============================================================================
# 25–27: CHECKPOINT RECOVERY & REVISION INVALIDATION
# ==============================================================================


@pytest.mark.integration
def test_25_checkpoint_12_fields_seal_corruption_rejection_and_zero_duplicate_resume(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    ckpt_mgr = CheckpointManager(tmp_path / "ckpts", root_dir=ws, handoff_manager=mgr)
    sched = TaskDependencyScheduler(
        root_dir=ws, handoff_manager=mgr, execution_adapter=adapter, checkpoint_manager=ckpt_mgr
    )

    t1 = _make_handoff(task_id="TASK-CK-01", owned_artifacts=["projects/proj_p016b/research.md"])
    t2 = _make_handoff(
        task_id="TASK-CK-02",
        assigned_agent="creative_director",
        dependencies=["TASK-CK-01"],
        input_artifacts=["projects/proj_p016b/research.md"],
        input_artifact_hashes={"projects/proj_p016b/research.md": "0" * 64},
        owned_artifacts=["projects/proj_p016b/blueprint.md"],
        max_attempts=1,
    )

    calls: dict[str, int] = {"TASK-CK-01": 0, "TASK-CK-02": 0}
    fail_t2_first_run = True

    async def _worker(h: dict[str, Any], attempt: int) -> AgentExecutionResult:
        tid = h["task_id"]
        calls[tid] += 1
        if tid == "TASK-CK-02" and fail_t2_first_run:
            raise RuntimeError("Simulated mid-DAG interruption on TASK-CK-02")

        def _write(hd: dict[str, Any], root: Path) -> dict[str, Any]:
            p = root / hd["owned_artifacts"][0]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# Output of {hd['task_id']}\n", encoding="utf-8")
            return {"evidence_items": [f"Persisted {hd['task_id']}"]}

        return adapter.execute_sequential_fallback(handoff=h, worker_fn=_write)

    run1 = asyncio.run(sched.execute_dag([t1, t2], executor=_worker))
    assert run1["completed_tasks"] == ["TASK-CK-01"]
    assert run1["failed_tasks"] == ["TASK-CK-02"]

    saved_ckpt = ckpt_mgr.load_verified_checkpoint()
    for field_name in MANDATORY_CHECKPOINT_FIELDS:
        assert field_name in saved_ckpt

    # Tampered checkpoint copy must raise CorruptedCheckpointError
    bad_ckpt = tmp_path / "tampered_ckpt.json"
    tampered_doc = copy.deepcopy(saved_ckpt)
    tampered_doc["approval_status"]["approved"] = True
    bad_ckpt.write_text(json.dumps(tampered_doc), encoding="utf-8")
    with pytest.raises(CorruptedCheckpointError, match="seal mismatch"):
        ckpt_mgr.load_verified_checkpoint(bad_ckpt)

    # Resume after clearing failure on TASK-CK-02: TASK-CK-01 MUST NOT re-run (calls['TASK-CK-01'] stays 1!)
    fail_t2_first_run = False
    resumed = ckpt_mgr.resume()
    resumed["failed_tasks"] = []
    resumed["pending_tasks"] = ["TASK-CK-02"]
    resumed["retry_budget"]["TASK-CK-02"]["attempts_used"] = 0

    run2 = asyncio.run(sched.execute_dag([t1, t2], executor=_worker, resume_state=resumed))
    assert run2["overall_status"] == "SUCCEEDED"
    assert calls["TASK-CK-01"] == 1  # Zero duplicate execution!
    assert calls["TASK-CK-02"] == 2


@pytest.mark.mock_test
def test_26_checkpoint_resume_demotes_missing_output_invalidates_downstream_and_blocks_unknown_external(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    ckpt_mgr = CheckpointManager(tmp_path / "ckpts_rec", root_dir=ws, handoff_manager=mgr)

    f1 = ws / "projects" / "proj_p016b" / "research.md"
    f2 = ws / "projects" / "proj_p016b" / "blueprint.md"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("# R1\n", encoding="utf-8")
    f2.write_text("# B1\n", encoding="utf-8")
    s1, s2 = compute_file_sha256(f1), compute_file_sha256(f2)

    t1 = _make_handoff(task_id="TASK-R1", owned_artifacts=["projects/proj_p016b/research.md"], status="COMPLETED")
    t2 = _make_handoff(
        task_id="TASK-R2",
        assigned_agent="creative_director",
        dependencies=["TASK-R1"],
        owned_artifacts=["projects/proj_p016b/blueprint.md"],
        status="COMPLETED",
    )
    t3_ext = _make_handoff(
        task_id="TASK-EXT-RUNNING",
        assigned_agent="asset_specialist",
        owned_artifacts=["projects/proj_p016b/asset_manifest.json"],
        status="RUNNING",
        extra_context={"external_side_effect_status": "unknown", "idempotent_retry_safe": False},
    )

    ckpt_mgr.save_checkpoint(
        project_id="proj_p016b",
        task_graph_version=1,
        completed_tasks=["TASK-R1", "TASK-R2"],
        pending_tasks=[],
        running_tasks=["TASK-EXT-RUNNING"],
        failed_tasks=[],
        artifact_manifest={
            "projects/proj_p016b/research.md": {"owner_task_id": "TASK-R1", "sha256": s1},
            "projects/proj_p016b/blueprint.md": {"owner_task_id": "TASK-R2", "sha256": s2},
        },
        artifact_sha256={
            "projects/proj_p016b/research.md": s1,
            "projects/proj_p016b/blueprint.md": s2,
        },
        agent_invocation_receipts={},
        retry_budget={
            "TASK-R1": {"max_attempts": 2, "attempts_used": 1, "timeout_seconds": 30},
            "TASK-R2": {"max_attempts": 2, "attempts_used": 1, "timeout_seconds": 30},
            "TASK-EXT-RUNNING": {"max_attempts": 2, "attempts_used": 0, "timeout_seconds": 30},
        },
        approval_status={"approved": False, "approved_digest": None},
        state_version=3,
        task_definitions={"TASK-R1": t1, "TASK-R2": t2, "TASK-EXT-RUNNING": t3_ext},
        idempotency_ledger={"idem1": "TASK-R1", "idem2": "TASK-R2"},
    )

    # Delete f1 on disk -> resume() must demote TASK-R1 AND invalidate downstream TASK-R2, AND block TASK-EXT-RUNNING!
    f1.unlink()
    rec = ckpt_mgr.resume(trigger="LANJUTKAN_PROJECT")
    assert rec["demoted_due_to_missing_or_corrupt_artifacts"] == ["TASK-R1"]
    assert rec["downstream_invalidated_tasks"] == ["TASK-R2"]
    assert rec["pending_tasks"] == ["TASK-R1", "TASK-R2"]
    assert rec["reconciled_unknown_external_tasks"] == ["TASK-EXT-RUNNING"]
    assert rec["blocked_tasks"] == ["TASK-EXT-RUNNING"]
    assert rec["approval_status"]["approved"] is False


@pytest.mark.integration
def test_27_revision_manager_archives_prior_versions_invalidates_downstream_and_revokes_approval(tmp_path: Path) -> None:
    ws = _copy_minimal_workspace(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    mem = SixPartitionMemoryStore(tmp_path / "rev_mem.sqlite3")
    rev_mgr = RevisionManager(root_dir=ws, handoff_manager=mgr, memory_store=mem)

    sm = SharedProjectStateMachine(tmp_path / "proj_state.json")
    sm.initialize(project_id="proj_p016b", project_title="Rev Test", genres=["explainer"])
    sm.transition("REQUEST_RECEIVED", expected_version=1, trigger="1", actor="master_director", evidence="ok")
    sm.transition("RESEARCHING", expected_version=2, trigger="2", actor="master_director", evidence="ok")
    sm.transition("CREATIVE_DEVELOPMENT", expected_version=3, trigger="3", actor="master_director", evidence="ok")
    sm.transition("STORYBOARDING", expected_version=4, trigger="4", actor="master_director", evidence="ok")
    sm.transition("PREPRODUCTION_QC", expected_version=5, trigger="5", actor="preproduction_verifier", evidence="ok")
    sm.transition("WAITING_APPROVAL", expected_version=6, trigger="6", actor="master_director", evidence="ok")
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(
            "APPROVED",
            expected_version=7,
            trigger="human_approve",
            actor="trusted_human_approval_gate",
            evidence="Human signed package",
            verified_human_approval={"approved_digest": "a" * 64, "approved_version": "v1", "trusted_channel_verified": True},
        )
    assert sm.load()["approval_status"]["approved"] is False

    nar_rel = "projects/proj_p016b/narration_dialogue.json"
    nar_file = ws / nar_rel
    nar_file.parent.mkdir(parents=True, exist_ok=True)
    nar_file.write_bytes(b'{"version": 1, "lines": ["Kalimat awal."]}\n')
    old_sha = compute_file_sha256(nar_file)

    task_defs = {
        "TASK-NAR": _make_handoff(task_id="TASK-NAR", assigned_agent="audio_director", owned_artifacts=[nar_rel]),
        "TASK-CAP": _make_handoff(
            task_id="TASK-CAP",
            assigned_agent="caption_specialist",
            dependencies=["TASK-NAR"],
            owned_artifacts=["projects/proj_p016b/caption_audio_plan.json"],
        ),
        "TASK-QC": _make_handoff(
            task_id="TASK-QC",
            assigned_agent="preproduction_verifier",
            dependencies=["TASK-CAP"],
            owned_artifacts=[],
            output_artifacts=[],
            allowed_tools=["view_file"],
        ),
    }

    rev_entry = rev_mgr.apply_revision(
        project_id="proj_p016b",
        artifact_relpath=nar_rel,
        new_content_bytes=b'{"version": 2, "lines": ["Kalimat hasil revisi baru."]}\n',
        task_owner="TASK-NAR",
        owner_agent="audio_director",
        reason="Perbaikan tempo kalimat pembuka",
        task_definitions=task_defs,
        state_machine=sm,
    )

    assert rev_entry["previous_digest"] == old_sha
    assert rev_entry["new_digest"] != old_sha
    assert (ws / rev_entry["archived_previous_path"]).is_file()
    assert compute_file_sha256(ws / rev_entry["archived_previous_path"]) == old_sha
    assert rev_entry["affected_downstream_tasks"] == ["TASK-CAP", "TASK-QC"]
    assert "human_approval_gate" in rev_entry["required_revalidation"]
    assert rev_entry["approval_invalidated"] is True

    st_after = sm.load()
    assert st_after["current_state"] == "REVISION_REQUIRED"
    assert st_after["approval_status"]["approved"] is False
    assert st_after["approval_status"]["revoked"] is True


# ==============================================================================
# 28: REFERENCE KNOWLEDGE INDEX & LIVE MULTI-AGENT WORKFLOW EVIDENCE
# ==============================================================================


@pytest.mark.live_evidence
def test_28_reference_knowledge_index_preserves_ref001_ref002_prior_and_v34_and_live_workflow_evidence(tmp_path: Path) -> None:
    # 1. Verify KnowledgeMemory Reference DB index contract & untouched prior_analysis.*
    mem = SixPartitionMemoryStore(tmp_path / "ref_idx_check.sqlite3")
    sync_res = sync_reference_database_into_knowledge_memory(
        mem, export_seed_path=tmp_path / "seed_idx.json"
    )
    assert sync_res["references_indexed"] == ["REF-001", "REF-002"]
    assert sync_res["versions_registered"] == 4
    for rid in ("REF-001", "REF-002"):
        vers = [v["version_tag"] for v in mem.knowledge.list_versions(f"ref_index:{rid}")]
        assert vers == ["prior_v1", "rea_v3.4"]

    # 2. Verify sibling xdx-blender-studio remains 100% unmodified
    blender_repo = ROOT_DIR.parent / "xdx-blender-studio"
    if blender_repo.is_dir():
        git_st = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(blender_repo),
            capture_output=True,
            text=True,
            check=True,
        )
        assert git_st.stdout.strip() == ""

    # 3. Verify recorded live Phase 01.6B multi-agent workflow & subprocess checkpoint resume proof
    wf_dir = ROOT_DIR / "docs" / "evidence" / "phase01_6b_workflow"
    summary_file = wf_dir / "workflow_execution_summary_v4.json"
    assert summary_file.is_file(), "Live Phase 01.6B workflow summary missing"
    summary = json.loads(summary_file.read_text(encoding="utf-8"))

    assert summary["overall_status"] == "SUCCEEDED"
    assert summary["completed_tasks"] == ["TASK-P016B-EXP-02", "TASK-P016B-REF-01", "TASK-P016B-VER-03"]
    assert summary["verifier_review_verification"]["verified"] is True
    assert summary["verifier_review_verification"]["verdict"] == "PASS"
    assert summary["verifier_review_verification"]["artifacts_unchanged"] >= 2
    assert summary["subprocess_resume_verification"]["zero_duplicate_execution_confirmed"] is True
    assert summary["blender_or_renderer_executed"] is False
