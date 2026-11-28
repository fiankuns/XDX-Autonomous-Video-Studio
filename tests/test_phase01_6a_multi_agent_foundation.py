"""Comprehensive Phase 01.6A Multi-Agent Foundation, Handoff DAG, Ownership & Permission Tests.

Covers PART 27 & PART 28 Phase 01.6A acceptance criteria:
1. Additive v4.0 structure (`TEAM.md`, `.agents/agents/`, `.agents/skills/`, `.agents/rules/`, `orchestration/`, `governance/`, `memory/`).
2. `AgentRegistry` (`master_director` + 20 specialists, 3-6 active roster cap, frontmatter & tool-hang prevention).
3. 18-field `TaskHandoff` schema, DAG cycle/missing/unready dependency rejection, single-writer conflict detection, and input SHA-256 checks.
4. Independent Verification `SilentArtifactMutationError` enforcement (reviewers never silently edit producer artifacts).
5. `PermissionPolicyEngine` default-deny, unknown tool rejection, read-only verifier isolation, and Blender single-worker/approval gates.
6. `RuntimeCapabilityDiscovery`, 10 User Command Modes in `MasterDirectorTaskRouter`, and `xdx_studio.py` CLI subcommands.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from governance.permission_policy import PermissionDeniedError, PermissionPolicyEngine
from orchestration.agent_registry import AgentRegistry
from orchestration.capability_discovery import RuntimeCapabilityDiscovery
from orchestration.handoff_manager import (
    HandoffValidationError,
    InvalidTaskDependencyError,
    ParallelWriteConflictError,
    ReadOnlyAgentOwnershipError,
    SilentArtifactMutationError,
    TaskHandoffManager,
    UnverifiedInputArtifactError,
    compute_file_sha256,
)
from orchestration.task_router import MasterDirectorTaskRouter

ROOT_DIR = Path(__file__).resolve().parent.parent


def _sample_handoff(
    *,
    task_id: str = "TASK-UNIT-001",
    assigned_agent: str = "topic_research_agent",
    dependencies: list[str] | None = None,
    owned_artifacts: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    status: str = "PENDING",
    workspace_mode: str = "inherit",
) -> dict:
    eff_owned = owned_artifacts if owned_artifacts is not None else ["projects/proj_phase016a_unit/research.md"]
    return {
        "task_id": task_id,
        "project_id": "proj_phase016a_unit",
        "parent_task_id": None,
        "assigned_agent": assigned_agent,
        "goal": "Compile verified primary-source research claims for Indonesian science explainer.",
        "context": {
            "project_state": "RESEARCHING",
            "genre_ids": ["explainer"],
            "reference_ids": ["REF-002"],
            "workspace_mode": workspace_mode,
            "notes": "Unit test handoff contract.",
        },
        "input_artifacts": [],
        "input_artifact_hashes": {},
        "dependencies": dependencies if dependencies is not None else [],
        "owned_artifacts": eff_owned,
        "allowed_tools": allowed_tools if allowed_tools is not None else ["view_file", "google_search"],
        "forbidden_actions": ["Fabricate citations", "Mutate Blender scenes"],
        "expected_output": {
            "summary": "Verified Markdown research dossier.",
            "output_artifacts": list(eff_owned),
            "output_format": "markdown",
        },
        "return_schema": "xdx.research-dossier.v4.0",
        "done_when": [
            {
                "criterion_id": "DONE_01",
                "check_type": "file_exists_nonempty",
                "target": "projects/proj_phase016a_unit/research.md",
                "description": "Research dossier exists and contains verified https:// citations.",
            }
        ],
        "required_evidence": ["Citation URLs and epistemic status per claim"],
        "retry_budget": {"max_attempts": 3, "attempts_used": 0, "timeout_seconds": 120},
        "status": status,
    }


def test_team_charter_and_additive_v4_structure() -> None:
    expected = [
        "TEAM.md",
        "orchestration/agent_registry.py",
        "orchestration/handoff_manager.py",
        "orchestration/task_router.py",
        "orchestration/capability_discovery.py",
        "orchestration/master_director_config.json",
        "governance/permission_policy.py",
        "memory/README.md",
        "registry/agent_registry_v4.json",
        "schemas/agent_role_contract.schema.json",
        "schemas/task_handoff.schema.json",
        "docs/PHASE_01_6A_BASELINE_AUDIT.md",
        "docs/AGENT_CAPABILITY_AND_MODEL_ROUTING.md",
        "docs/PHASE_01_6B_IMPLEMENTATION_PLAN.md",
    ]
    for rel in expected:
        assert (ROOT_DIR / rel).is_file(), f"Missing Phase 01.6A artifact: {rel}"

    team_md = (ROOT_DIR / "TEAM.md").read_text(encoding="utf-8")
    assert "ORCHESTRATOR" in team_md
    assert "INDEPENDENT VERIFIER" in team_md
    assert "SUCCESS AUDITOR" in team_md


def test_agent_registry_20_specialists_and_frontmatter_validation(tmp_path: Path) -> None:
    reg = AgentRegistry()
    spec_ids = reg.list_specialist_ids()
    assert len(spec_ids) == 20
    assert [reg.get_role(sid)["agent_number"] for sid in spec_ids] == list(range(1, 21))

    # Verify department counts: 7 Creative + 9 Production + 4 Independent Verification = 20
    depts = [reg.get_role(sid)["department"] for sid in spec_ids]
    assert depts.count("creative_department") == 7
    assert depts.count("production_department") == 9
    assert depts.count("independent_verification_department") == 4

    # Separation of duties & Blender single-worker constraint
    assert reg.get_role("master_director")["can_self_approve"] is False
    assert reg.get_role("blender_specialist")["max_concurrent_instances"] == 1
    for vid in ("preproduction_verifier", "visual_critic", "technical_auditor", "success_auditor"):
        v_role = reg.get_role(vid)
        assert v_role["read_only"] is True
        assert v_role["requires_fresh_context"] is True
        assert v_role["owned_artifact_patterns"] == []

    # Active specialist cap (3-6 recommended; >6 rejected unless explicitly overridden)
    roster_ok = reg.validate_active_roster(spec_ids[:5])
    assert roster_ok["within_recommended_3_to_6"] is True
    with pytest.raises(ValueError, match="exceeds initial cap"):
        reg.validate_active_roster(spec_ids[:7])

    # Validate .agents/ customizations & test fail-closed detection of misspelled tools / bad rule triggers
    cust = reg.validate_workspace_customizations()
    assert cust["roles_validated"] == 21
    assert len(cust["custom_agent_files_validated"]) == 10
    assert len(cust["workspace_skills_validated"]) == 4
    assert len(cust["workspace_rules_validated"]) == 3

    fake_root = tmp_path / "workspace"
    shutil.copytree(ROOT_DIR / ".agents", fake_root / ".agents")
    shutil.copytree(ROOT_DIR / "schemas", fake_root / "schemas")
    for mod_rel in {m for r in [reg.data["master_director"], *reg.data["specialists"]] for m in r["linked_python_modules"]}:
        src = ROOT_DIR / mod_rel
        if src.is_file():
            dst = fake_root / mod_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    shutil.copy2(ROOT_DIR / "SKILL.md", fake_root / "SKILL.md")

    bad_agent = fake_root / ".agents" / "agents" / "xdx-topic-researcher.md"
    bad_agent.write_text(
        bad_agent.read_text(encoding="utf-8").replace("- view_file", "- hallucinated_nonexistent_tool"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unmapped tool"):
        AgentRegistry(root_dir=fake_root).validate_workspace_customizations()


def test_18_field_handoff_dag_dependencies_and_parallel_write_conflicts(tmp_path: Path) -> None:
    mgr = TaskHandoffManager()

    # 1. Valid 18-field handoff passes
    h1 = _sample_handoff(task_id="TASK-A01", status="COMPLETED")
    assert set(h1.keys()) == {
        "task_id", "project_id", "parent_task_id", "assigned_agent", "goal", "context",
        "input_artifacts", "input_artifact_hashes", "dependencies", "owned_artifacts",
        "allowed_tools", "forbidden_actions", "expected_output", "return_schema",
        "done_when", "required_evidence", "retry_budget", "status",
    }
    mgr.validate_handoff(h1)

    # 2. Missing required field rejected
    broken = copy.deepcopy(h1)
    del broken["done_when"]
    with pytest.raises(HandoffValidationError):
        mgr.validate_handoff(broken)

    # 3. Unsupported devbox workspace_mode='branch' rejected when enforced
    branch_h = _sample_handoff(task_id="TASK-BR01", workspace_mode="branch")
    with pytest.raises(HandoffValidationError, match="inherit"):
        mgr.validate_handoff(branch_h, enforce_devbox_workspace_mode=True)

    # 4. Read-only verifier claiming owned_artifacts rejected
    ro_bad = _sample_handoff(
        task_id="TASK-RO01",
        assigned_agent="preproduction_verifier",
        owned_artifacts=["projects/x/script.md"],
        allowed_tools=["view_file"],
    )
    with pytest.raises(ReadOnlyAgentOwnershipError):
        mgr.validate_handoff(ro_bad)

    # 5. Unknown dependency, cycle, and premature RUNNING status rejected
    h_missing_dep = _sample_handoff(task_id="TASK-B01", dependencies=["TASK-NONEXISTENT"])
    with pytest.raises(InvalidTaskDependencyError, match="unknown task"):
        mgr.validate_task_dag_and_ownership([h1, h_missing_dep])

    cyc_a = _sample_handoff(task_id="TASK-CYC1", dependencies=["TASK-CYC2"])
    cyc_b = _sample_handoff(
        task_id="TASK-CYC2",
        assigned_agent="creative_director",
        dependencies=["TASK-CYC1"],
        owned_artifacts=["projects/proj_phase016a_unit/blueprint.md"],
        allowed_tools=["view_file"],
    )
    with pytest.raises(InvalidTaskDependencyError, match="Cycle detected"):
        mgr.validate_task_dag_and_ownership([cyc_a, cyc_b])

    premature_up = _sample_handoff(task_id="TASK-UP01", status="RUNNING")
    premature_dn = _sample_handoff(
        task_id="TASK-DN01",
        assigned_agent="creative_director",
        dependencies=["TASK-UP01"],
        owned_artifacts=["projects/proj_phase016a_unit/blueprint.md"],
        allowed_tools=["view_file"],
        status="RUNNING",
    )
    with pytest.raises(InvalidTaskDependencyError, match="before upstream dependencies completed"):
        mgr.validate_task_dag_and_ownership([premature_up, premature_dn])

    # 6. Parallel write conflict on same owned_artifact & Blender single-worker mutex
    w1 = _sample_handoff(
        task_id="TASK-W01",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/proj_phase016a_unit/research.md"],
        status="RUNNING",
    )
    w2 = _sample_handoff(
        task_id="TASK-W02",
        assigned_agent="topic_research_agent",
        owned_artifacts=["projects/proj_phase016a_unit/research.md"],
        status="RUNNING",
    )
    with pytest.raises(ParallelWriteConflictError, match="(?i)parallel write conflict"):
        mgr.validate_task_dag_and_ownership([w1, w2])

    b1 = _sample_handoff(
        task_id="TASK-BL01",
        assigned_agent="blender_specialist",
        owned_artifacts=["projects/proj_phase016a_unit/scenes/s1.json"],
        allowed_tools=["view_file", "run_command"],
        status="RUNNING",
    )
    b2 = _sample_handoff(
        task_id="TASK-BL02",
        assigned_agent="blender_specialist",
        owned_artifacts=["projects/proj_phase016a_unit/scenes/s2.json"],
        allowed_tools=["view_file", "run_command"],
        status="RUNNING",
    )
    with pytest.raises(ParallelWriteConflictError, match="max_concurrent_instances=1"):
        mgr.validate_task_dag_and_ownership([b1, b2])

    # 7. Input SHA-256 verification on disk
    sample_in = tmp_path / "input_doc.json"
    sample_in.write_text('{"ok": true}\n', encoding="utf-8")
    good_sha = compute_file_sha256(sample_in)
    h_in = _sample_handoff(task_id="TASK-IN01")
    h_in["input_artifacts"] = ["input_doc.json"]
    h_in["input_artifact_hashes"] = {"input_doc.json": good_sha}
    assert mgr.verify_input_artifacts_on_disk(h_in, base_dir=tmp_path) == {"input_doc.json": good_sha}

    sample_in.write_text('{"ok": false}\n', encoding="utf-8")
    with pytest.raises(UnverifiedInputArtifactError, match="SHA-256 mismatch"):
        mgr.verify_input_artifacts_on_disk(h_in, base_dir=tmp_path)


def test_independent_verifier_blocks_silent_artifact_mutation(tmp_path: Path) -> None:
    mgr = TaskHandoffManager()
    rel_script = "projects/proj_phase016a_unit/script.md"
    prod_file = tmp_path / rel_script
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text("# Naskah Asli Producer\n", encoding="utf-8")
    pre_hashes = {rel_script: compute_file_sha256(prod_file)}

    p_handoff = _sample_handoff(
        task_id="TASK-PROD-01",
        assigned_agent="scriptwriter_agent",
        owned_artifacts=[rel_script],
        allowed_tools=["view_file", "write_to_file"],
        status="COMPLETED",
    )
    v_handoff = _sample_handoff(
        task_id="TASK-VER-01",
        assigned_agent="preproduction_verifier",
        dependencies=["TASK-PROD-01"],
        owned_artifacts=[],
        allowed_tools=["view_file"],
        status="RUNNING",
    )
    v_handoff["input_artifacts"] = [rel_script]
    v_handoff["input_artifact_hashes"] = dict(pre_hashes)

    report = {
        "schema_version": "4.0.0-phase01.6b",
        "review_id": "REV-UNIT-001",
        "project_id": "proj_phase016a_unit",
        "verifier_agent": "preproduction_verifier",
        "reviewed_task_id": "TASK-PROD-01",
        "producer_agent": "scriptwriter_agent",
        "verdict": "PASS",
        "invocation_receipt": {
            "invocation_id": "RCPT-VER-UNIT-01",
            "receipt_id": "RCPT-VER-UNIT-01",
            "agent_id": "preproduction_verifier",
            "runtime_name": "antigravity",
            "execution_mode": "native_subagent",
            "actually_invoked": True,
            "conversation_id": "conv_verifier_fresh_ctx_001",
            "started_at": "2026-11-27T14:00:00+00:00",
            "completed_at": "2026-11-27T14:00:05+00:00",
        },
        "reviewed_artifact_hashes": dict(pre_hashes),
        "required_criteria_ids": ["CRIT_ORIGINALITY"],
        "checked_criteria": [
            {
                "criterion_id": "CRIT_ORIGINALITY",
                "status": "PASS",
                "evidence": "Verified original Indonesian script without placeholder labels or silent edits.",
            }
        ],
        "defects": [],
    }
    res = mgr.verify_independent_review_pass(
        verifier_handoff=v_handoff,
        producer_handoff=p_handoff,
        pre_review_hashes=pre_hashes,
        review_report=report,
        base_dir=tmp_path,
    )
    assert res["verified"] is True

    # Simulate rogue silent edit during review -> must raise SilentArtifactMutationError!
    prod_file.write_text("# Naskah Diedit Diam-Diam oleh Reviewer\n", encoding="utf-8")
    with pytest.raises(SilentArtifactMutationError):
        mgr.verify_independent_review_pass(
            verifier_handoff=v_handoff,
            producer_handoff=p_handoff,
            pre_review_hashes=pre_hashes,
            review_report=report,
            base_dir=tmp_path,
        )


def test_permission_policy_default_deny_and_mcp_guards() -> None:
    policy = PermissionPolicyEngine()

    assert policy.check_antigravity_tool("preproduction_verifier", "view_file") is True
    with pytest.raises(PermissionDeniedError, match="Read-only agent"):
        policy.check_antigravity_tool("preproduction_verifier", "write_to_file")
    with pytest.raises(PermissionDeniedError, match="unknown Antigravity tool"):
        policy.check_antigravity_tool("master_director", "invented_shell_bypass")

    # Blender MCP mutation guard
    assert policy.check_blender_mcp_tool("rea_video_reference_analyst", "get_scene_info") is True
    with pytest.raises(PermissionDeniedError, match="Only 'blender_specialist'"):
        policy.check_blender_mcp_tool(
            "threejs_specialist", "execute_blender_code", has_live_approval_context=True
        )
    with pytest.raises(PermissionDeniedError, match="without verified human ExecutionAuthorizationContext"):
        policy.check_blender_mcp_tool(
            "blender_specialist", "execute_blender_code", has_live_approval_context=False
        )
    assert (
        policy.check_blender_mcp_tool(
            "blender_specialist", "execute_blender_code", has_live_approval_context=True
        )
        is True
    )
    with pytest.raises(PermissionDeniedError, match="unclassified Blender MCP tool"):
        policy.check_blender_mcp_tool("blender_specialist", "delete_entire_android_storage")


def test_capability_discovery_router_modes_and_cli() -> None:
    cap = RuntimeCapabilityDiscovery().discover()
    ag_detected = cap["adapters_probed"]["antigravity"]["detected"]
    expected_inherit_statuses = (
        {"DOCUMENTED_CAPABILITY", "SUPPORTED_AND_VERIFIED"} if ag_detected else {"UNKNOWN"}
    )
    assert cap["antigravity_native_multi_agent"]["workspace_modes"]["inherit"] in expected_inherit_statuses
    assert len(cap["reference_database"]["verified_references"]) == 3  # REF-001, REF-002, REF-003

    router = MasterDirectorTaskRouter()
    for mode in (
        "CARI_TOPIK", "BUAT_VIDEO", "BUAT_OTOMATIS", "ANALISIS_REFERENSI", "GUNAKAN_REF",
        "GABUNGKAN_REFERENSI", "REVISI", "SETUJUI_PAKET", "LANJUTKAN_PROJECT", "AUDIT_PROJECT",
    ):
        plan = router.build_dispatch_plan(mode)
        assert 1 <= plan["active_specialist_count"] <= 6
        assert plan["auto_authorizes_production"] is False
        assert plan["verifier_requires_fresh_context"] is True

    cli_cap = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "xdx_studio.py"), "capabilities"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(cli_cap.stdout)["schema_version"].startswith("4.0.0-phase01.6")


def test_recorded_live_subagent_producer_and_independent_verifier_evidence() -> None:
    ev = ROOT_DIR / "docs" / "evidence"
    mgr = TaskHandoffManager()

    prod_h = json.loads((ev / "task_handoff_producer_01.json").read_text(encoding="utf-8"))
    ver_h = json.loads((ev / "task_handoff_verifier_02.json").read_text(encoding="utf-8"))
    topo = mgr.validate_task_dag_and_ownership([prod_h, ver_h])
    assert topo == ["TASK-P016A-PRODUCER-01", "TASK-P016A-VERIFIER-02"]

    dna = json.loads((ev / "producer_reference_dna_v4.json").read_text(encoding="utf-8"))
    assert dna["schema"] == "xdx.reference-dna.v4.0"
    assert len(dna["dna_techniques"]) == 6

    ver_rep = json.loads((ev / "independent_verifier_report_v4.json").read_text(encoding="utf-8"))
    assert ver_rep["verdict"] == "PASS"
    assert ver_rep["fresh_context_confirmed"] is True
    assert ver_rep["defects"] == []
    assert ver_rep["cryptographic_review_verification"]["artifacts_unchanged"] == 7

    exp_rep = json.loads((ev / "builtin_research_explorer_evidence.json").read_text(encoding="utf-8"))
    assert exp_rep["isolated_context_confirmed"] is True
    assert exp_rep["xdx_blender_studio_unmodified"] is True
