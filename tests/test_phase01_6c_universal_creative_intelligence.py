"""Phase 01.6C Comprehensive Regression, Hardening, Universal Creative Intelligence & Benchmark Suite (24 Tests).

Covers all Section 3–Section 21 requirements of Phase 01.6C, categorized explicitly across all 5 test tiers:
- ``@pytest.mark.unit`` (15 tests)
- ``@pytest.mark.integration`` (4 tests)
- ``@pytest.mark.mock_test`` (3 tests)
- ``@pytest.mark.replay_test`` (1 test)
- ``@pytest.mark.live_evidence`` (1 test)
"""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from intelligence.authored_showcase_150s import (
    build_authored_social_satire_payload,
    build_authored_time_perception_payload,
)
from intelligence.creative_pipeline import (
    CreativePayloadRequiredError,
    CreativePayloadValidator,
    PreProductionPackageBuilder,
    TopicRelevanceError,
)
from intelligence.preproduction_verifier_engine import (
    MANDATORY_15_PREPRODUCTION_CRITERIA,
    PreproductionVerifierEngine,
    build_mandatory_15_criteria_manifest,
)
from intelligence.reference_lifecycle import (
    MANDATORY_ADAPTATION_FIELDS,
    TEN_FUSION_DIMENSIONS,
    MultiReferenceFusionEngine,
    REAReferenceLifecycleManager,
    ReferenceToProductionAdapter,
    compute_actual_analyzer_source_fingerprint,
    compute_analyzer_config_hash,
)
from intelligence.state_and_approval import ApprovalGate
from intelligence.universal_preproduction import (
    MANDATORY_11_CHARACTER_FIELDS,
    MANDATORY_12_ASSET_FIELDS,
    MANDATORY_14_ACTION_FIELDS,
    SEMANTIC_VISUAL_PURPOSES,
    SUPPORTED_STYLE_PROFILES,
    CharacterActionPlanner,
    CharacterAndStyleIntelligence,
    NarrationTimingIntelligence,
    PurposeDrivenCameraAudioCaptionPlanner,
    SemanticAssetPlanner,
    SemanticVisualDirector,
)
from memory.persistent_memory import SecretLeakBlockedError, SixPartitionMemoryStore
from orchestration.acceptance_criteria import (
    AcceptanceCriteriaEngine,
    MissingSchemaTargetError,
    ReceiptOutputHashMismatchError,
    UnrelatedEvidenceError,
    UnsupportedAcceptanceCheckError,
    WorkerIdentityMismatchError,
)
from orchestration.capability_discovery import RuntimeCapabilityDiscovery
from orchestration.checkpoint_manager import (
    CheckpointManager,
    CrossProjectCheckpointError,
    TaskGraphMismatchError,
    UnverifiedCheckpointError,
)
from orchestration.defect_registry import DefectRegistryValidationError, MasterAuditDefectRegistry
from orchestration.dependency_scheduler import (
    InitialCompletedStatusRejectedError,
    PhaseBoundaryExecutionBlockedError,
    TaskDependencyScheduler,
)
from orchestration.handoff_manager import (
    HandoffValidationError,
    ReviewerCriteriaManipulationError,
    TaskHandoffManager,
    compute_file_sha256,
)
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentInvocationReceipt,
    AgentReviewReport,
    ImmutableReviewCriteriaManifest,
    NativeAgentExecutionAdapter,
    utc_now_iso,
)
from orchestration.preproduction_workflow import PreproductionMultiAgentWorkflow
from orchestration.shared_state import ProductionApprovalFrozenError, SharedProjectStateMachine
from tests.fixtures.synthetic_fixture_generator import ensure_deterministic_synthetic_mp4

ROOT_DIR = Path(__file__).resolve().parent.parent


def _setup_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws_p016c"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "schemas").mkdir()
    for sf in (ROOT_DIR / "schemas").glob("*.schema.json"):
        (ws / "schemas" / sf.name).write_bytes(sf.read_bytes())
    return ws


def _mk_handoff(
    *,
    task_id: str,
    project_id: str = "proj_016c",
    assigned_agent: str = "topic_research_agent",
    dependencies: list[str] | None = None,
    input_artifacts: list[str] | None = None,
    input_artifact_hashes: dict[str, str] | None = None,
    owned_artifacts: list[str] | None = None,
    output_artifacts: list[str] | None = None,
    done_when: list[dict[str, Any]] | None = None,
    required_evidence: list[str] | None = None,
    status: str = "PENDING",
    max_attempts: int = 1,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owned = owned_artifacts if owned_artifacts is not None else [f"projects/{project_id}/research.md"]
    outs = output_artifacts if output_artifacts is not None else list(owned)
    target = outs[0] if outs else f"projects/{project_id}/research.md"
    ctx: dict[str, Any] = {
        "project_state": "RESEARCHING",
        "genre_ids": ["explainer"],
        "reference_ids": ["REF-002"],
        "workspace_mode": "inherit",
        "notes": "Phase 01.6C regression handoff",
    }
    if extra_context:
        ctx.update(extra_context)
    return {
        "task_id": task_id,
        "project_id": project_id,
        "parent_task_id": None,
        "assigned_agent": assigned_agent,
        "goal": f"Execute Phase 01.6C deterministic verification task {task_id}.",
        "context": ctx,
        "input_artifacts": input_artifacts or [],
        "input_artifact_hashes": input_artifact_hashes or {},
        "dependencies": dependencies or [],
        "owned_artifacts": owned,
        "allowed_tools": ["view_file", "write_to_file"] if outs else ["view_file"],
        "forbidden_actions": ["Mutate outside project boundary"],
        "expected_output": {
            "summary": f"Output summary for {task_id}.",
            "output_artifacts": outs,
            "output_format": "json" if target.endswith(".json") else "markdown",
        },
        "return_schema": "xdx.phase01_6c.test.v4.0",
        "done_when": done_when
        or [
            {
                "criterion_id": "DONE_01",
                "check_type": "file_exists_nonempty",
                "target": target,
                "description": "Target file exists and is non-empty.",
            }
        ],
        "required_evidence": required_evidence or [f"Verified output for {task_id} ({target})"],
        "retry_budget": {"max_attempts": max_attempts, "attempts_used": 0, "timeout_seconds": 30},
        "status": status,
    }


def _build_custom_ac_payload(project_id: str = "ac_unit_test", duration_s: int = 30) -> dict[str, Any]:
    return {
        "schema_version": "4.0.0-phase01.6c",
        "project_id": project_id,
        "topic_title": "Bagaimana AC Mendinginkan Ruangan?",
        "style_profile": "stylized_3d",
        "genres": ["explainer", "edukasi"],
        "reference_ids": ["REF-002"],
        "target_duration_s": duration_s,
        "topic_research": {
            "epistemic_mode": "factual_verified",
            "research_status": "VERIFIED_COMPLETE",
            "summary": "Siklus refrigerasi kompresi uap menyerap kalor laten udara ruangan melalui evaporator dan membuangnya ke luar melalui kondensor.",
            "topic_scope": "Termodinamika siklus kompresi uap pada pendingin ruangan rumah tangga.",
            "research_questions": [
                "Mengapa AC mendinginkan kamar tanpa memasukkan udara luar?",
                "Bagaimana evaporator, kompresor, kondensor, dan katup ekspansi memindahkan kalor?",
            ],
            "misconceptions": [
                {
                    "misconception": "AC menyemprotkan udara segar dingin dari luar rumah.",
                    "correction": "AC mensirkulasikan ulang udara dalam ruangan sambil memindahkan kalornya keluar lewat refrigeran.",
                    "claim_ref": "CLM_01",
                }
            ],
            "uncertainties": ["Efisiensi COP aktual bervariasi menurut kelembapan relatif dan suhu ambien luar."],
            "claims": [
                {
                    "claim_id": "CLM_01",
                    "statement": "Evaporator AC menyerap kalor udara dalam ruangan ketika refrigeran cair bertekanan rendah menguap menjadi gas.",
                    "epistemic_status": "verified_fact",
                    "source_title": "U.S. Department of Energy — Central Air Conditioning",
                    "source_url": "https://www.energy.gov/energysaver/central-air-conditioning",
                    "publication_year": 2024,
                    "evidence_excerpt": "Liquid refrigerant evaporates inside the indoor evaporator coil, pulling heat out of indoor air.",
                },
                {
                    "claim_id": "CLM_02",
                    "statement": "Kompresor menaikkan tekanan dan suhu uap refrigeran agar kondensor luar dapat melepas kalor ke udara luar yang panas.",
                    "epistemic_status": "verified_fact",
                    "source_title": "Encyclopaedia Britannica — Air-Conditioning Principles",
                    "source_url": "https://www.britannica.com/technology/air-conditioning",
                    "publication_year": 2024,
                    "evidence_excerpt": "The compressor pressurizes refrigerant vapor so heat rejects across outdoor condenser fins.",
                },
            ],
        },
        "blueprint": {
            "premise": "Membongkar cara kerja AC memindahkan panas ruangan keluar melalui pipa refrigeran tertutup.",
            "hook_0_3s_visual": "Kamera membelah unit AC dinding yang berembun saat suhu kamar turun dari 33 ke 24 derajat.",
            "hook_0_3s_spoken": "AC di kamarmu sebenarnya tidak menciptakan dingin, melainkan merampok panas ruanganmu!",
            "story_arc": {
                "act_1_setup": "Kamar pengap 33 derajat dan miskonsepsi udara luar pada unit AC.",
                "act_2_escalation": "Belahan penampang pipa evaporator, kompresor, kondensor luar, dan katup ekspansi.",
                "act_3_resolution": "Kamar sejuk 24 derajat sementara kipas kondensor luar menghembuskan panas yang dipindahkan.",
            },
            "explainer_mechanism": "Siklus kompresi uap empat komponen dengan perubahan wujud cair-gas refrigeran.",
            "humor_strategy": "Kontras ekspresi penghuni kamar memeluk kipas sebelum paham panasnya dibuang ke halaman luar.",
            "historical_biography_notes": "Prinsip kontrol kelembapan dan termodinamika pendinginan modern.",
            "payoff_callback": "Kembali ke termometer kamar 24 derajat sambil menyentuh angin hangat di unit outdoor.",
        },
        "characters": [
            {
                "character_id": "char_nadia_presenter",
                "name": "Nadia",
                "role": "hero",
                "silhouette_and_proportions": "Tinggi 165cm proporsi stylized 3D rapi dengan jaket teknik biru muda.",
                "facial_design": "Mata ekspresif hangat dengan kacamata bingkai tipis.",
                "wardrobe": "Kemeja kerja abu terang dengan gulungan lengan siku.",
                "materials": ["mat_cotton_stylized", "mat_skin_stylized_sss"],
                "palette": ["#2B6CB0", "#EDF2F7", "#F6AD55"],
                "expressions": ["curious_smile", "focused_explain", "aha_grin"],
                "rig_spec": "rig_humanoid_ik_fk_viseme_v4",
                "biography_disclaimer": "Karakter presenter fiksi orisinal XDX Studio.",
            }
        ],
        "narrative_beats": [
            {
                "beat_id": "B01",
                "act": "ACT_1",
                "sequence_id": "SEQ_01",
                "scene_id": "SCN_01",
                "environment_id": "env_kamar_tropis_ac_v1",
                "beat_role": "hook_anomaly",
                "target_duration_s": duration_s * 0.30,
                "narration_vo": "Saat tombol remote ditekan, AC sebenarnya tidak menyemprotkan udara luar yang dingin, melainkan menyerap kalor dari udara kamarmu sendiri.",
                "claim_refs": ["CLM_01"],
                "emotion": "curious",
                "dialogue_lines": [],
                "shot_blueprints": [
                    {
                        "visual_purpose": "establishing_shot",
                        "visual_subject": "Nadia berdiri di kamar panas menunjuk unit AC indoor",
                        "concrete_action": "Nadia menekan remote AC hingga kisi penutup unit dinding terbuka dan indikator suhu menyala.",
                        "props": ["prop_ac_indoor_unit", "prop_remote_ac", "prop_digital_thermometer"],
                        "preferred_engine": "blender",
                        "shot_size": "establishing",
                    },
                    {
                        "visual_purpose": "technical_cutaway",
                        "visual_subject": "Potongan melintang kumparan evaporator AC indoor",
                        "concrete_action": "Dinding casing AC terbelah memperlihatkan pipa evaporator dingin menyerap panah kalor merah dari udara ruangan.",
                        "props": ["prop_evaporator_coil_cutaway", "prop_heat_arrow_red"],
                        "preferred_engine": "threejs",
                        "shot_size": "cutaway",
                        "is_cutaway": True,
                        "scientific_labels": ["Evaporator", "Kalor Laten"],
                    },
                ],
            },
            {
                "beat_id": "B02",
                "act": "ACT_2",
                "sequence_id": "SEQ_01",
                "scene_id": "SCN_02",
                "environment_id": "env_dinding_belah_indoor_outdoor_v1",
                "beat_role": "mechanism_escalation",
                "target_duration_s": duration_s * 0.40,
                "narration_vo": "Cairan refrigeran mendidih di dalam pipa evaporator, lalu dipompa kompresor menuju kondensor luar agar panasnya terbuang ke udara halaman.",
                "claim_refs": ["CLM_01", "CLM_02"],
                "emotion": "curious",
                "dialogue_lines": [],
                "shot_blueprints": [
                    {
                        "visual_purpose": "scientific_mechanism",
                        "visual_subject": "Sirkuit pipa refrigeran dari kompresor ke kondensor luar",
                        "concrete_action": "Kompresor memampatkan uap refrigeran bertekanan tinggi sementara kipas kondensor melepas gelombang panas keluar.",
                        "props": ["prop_compressor_cutaway", "prop_condenser_fins_outdoor"],
                        "preferred_engine": "threejs",
                        "shot_size": "cutaway",
                        "is_cutaway": True,
                        "scientific_labels": ["Kompresor", "Kondensor"],
                    },
                    {
                        "visual_purpose": "exploded_view",
                        "visual_subject": "Katup ekspansi sempit di antara kondensor dan evaporator",
                        "concrete_action": "Katup ekspansi menyempitkan aliran cairan refrigeran sehingga tekanannya anjlok dan suhunya kembali dingin.",
                        "props": ["prop_expansion_valve_macro", "prop_refrigerant_droplets"],
                        "preferred_engine": "blender",
                        "shot_size": "insert",
                    },
                ],
            },
            {
                "beat_id": "B03",
                "act": "ACT_3",
                "sequence_id": "SEQ_01",
                "scene_id": "SCN_03",
                "environment_id": "env_kamar_tropis_ac_v1",
                "beat_role": "payoff_callback",
                "target_duration_s": duration_s * 0.30,
                "narration_vo": "Begitu siklus tertutup ini berulang, ruanganmu sejuk dua puluh empat derajat karena panasnya sudah pindah ke luar jendela.",
                "claim_refs": ["CLM_02"],
                "emotion": "warm",
                "dialogue_lines": [],
                "shot_blueprints": [
                    {
                        "visual_purpose": "reaction_shot",
                        "visual_subject": "Nadia tersenyum lega melihat termometer kamar 24 derajat",
                        "concrete_action": "Nadia meletakkan remote di meja saat angka termometer turun ke 24 derajat sementara unit luar membuang uap hangat.",
                        "props": ["prop_digital_thermometer", "prop_ac_outdoor_fan"],
                        "preferred_engine": "blender",
                        "shot_size": "reaction",
                    }
                ],
            },
        ],
    }


# ==============================================================================
# 1–13: PHASE 01.6B AUDIT CORRECTIONS (Section 4.A – 4.F)
# ==============================================================================


@pytest.mark.unit
def test_01_initial_completed_status_rejected_without_worker_execution(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr)

    forged_completed = _mk_handoff(task_id="TASK-INIT-COMP", status="COMPLETED")
    worker_called = False

    async def _worker(_h: dict[str, Any], _a: int) -> AgentExecutionResult:
        nonlocal worker_called
        worker_called = True
        raise AssertionError("Worker must not run on invalid initial status")

    with pytest.raises(InitialCompletedStatusRejectedError, match="forbidden initial status='COMPLETED'"):
        asyncio.run(sched.execute_dag([forged_completed], executor=_worker))
    assert worker_called is False


@pytest.mark.unit
def test_02_unverified_checkpoint_resume_state_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr)

    t1 = _mk_handoff(task_id="TASK-UNVER-01")
    fake_resume = {
        "project_id": "proj_016c",
        "completed_tasks": ["TASK-UNVER-01"],
        "pending_tasks": [],
        "failed_tasks": [],
        "blocked_tasks": [],
        "cancelled_tasks": [],
        "artifact_manifest": {},
        "artifact_sha256": {},
        "agent_invocation_receipts": {},
        "idempotency_ledger": {},
    }

    async def _noop(_h: dict[str, Any], _a: int) -> AgentExecutionResult:
        raise AssertionError("Unverified resume_state must be rejected before dispatch")

    with pytest.raises(UnverifiedCheckpointError):
        asyncio.run(sched.execute_dag([t1], executor=_noop, resume_state=fake_resume))


@pytest.mark.unit
def test_03_cross_project_checkpoint_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    ckpt_mgr = CheckpointManager(tmp_path / "ckpts_cross", root_dir=ws, handoff_manager=mgr)
    sched = TaskDependencyScheduler(
        root_dir=ws, handoff_manager=mgr, execution_adapter=adapter, checkpoint_manager=ckpt_mgr
    )

    t_proj_a = _mk_handoff(
        task_id="TASK-PROJ-A",
        project_id="project_alpha",
        owned_artifacts=["projects/project_alpha/research.md"],
    )

    async def _ok_worker(h: dict[str, Any], _a: int) -> AgentExecutionResult:
        p = ws / h["owned_artifacts"][0]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Alpha Research\n", encoding="utf-8")
        return adapter.execute_sequential_fallback(
            handoff=h,
            worker_fn=lambda _hd, _rt: {"evidence_items": [f"Completed {h['task_id']} research.md"]},
        )

    asyncio.run(sched.execute_dag([t_proj_a], executor=_ok_worker))
    resumed_alpha = ckpt_mgr.resume(expected_project_id="project_alpha")

    with pytest.raises(CrossProjectCheckpointError):
        ckpt_mgr.resume(expected_project_id="project_beta")

    t_proj_b = _mk_handoff(
        task_id="TASK-PROJ-A",
        project_id="project_beta",
        owned_artifacts=["projects/project_beta/research.md"],
    )
    with pytest.raises(CrossProjectCheckpointError):
        asyncio.run(sched.execute_dag([t_proj_b], executor=_ok_worker, resume_state=resumed_alpha))


@pytest.mark.unit
def test_04_task_graph_and_definition_mismatch_checkpoint_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    ckpt_mgr = CheckpointManager(tmp_path / "ckpts_graph", root_dir=ws, handoff_manager=mgr)
    sched = TaskDependencyScheduler(
        root_dir=ws, handoff_manager=mgr, execution_adapter=adapter, checkpoint_manager=ckpt_mgr
    )

    t1 = _mk_handoff(task_id="TASK-GR1")

    async def _ok_worker(h: dict[str, Any], _a: int) -> AgentExecutionResult:
        p = ws / h["owned_artifacts"][0]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# GR1\n", encoding="utf-8")
        return adapter.execute_sequential_fallback(
            handoff=h,
            worker_fn=lambda _hd, _rt: {"evidence_items": [f"Completed {h['task_id']} research.md"]},
        )

    asyncio.run(sched.execute_dag([t1], executor=_ok_worker))
    resumed = ckpt_mgr.resume()

    # Mutate task goal / add extra task -> task_graph_digest & task_definition_digest mismatch!
    t1_modified = copy.deepcopy(t1)
    t1_modified["goal"] = "Completely altered task goal that invalidates task_definition_digest."
    with pytest.raises(TaskGraphMismatchError):
        asyncio.run(sched.execute_dag([t1_modified], executor=_ok_worker, resume_state=resumed))

    t2_extra = _mk_handoff(
        task_id="TASK-GR2",
        assigned_agent="creative_director",
        dependencies=["TASK-GR1"],
        owned_artifacts=["projects/proj_016c/blueprint.md"],
    )
    with pytest.raises(TaskGraphMismatchError):
        ckpt_mgr.resume(expected_handoffs=[t1, t2_extra])


@pytest.mark.integration
def test_05_missing_json_schema_target_rejected_and_all_6_acceptance_handlers_verified(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    (ws / "tests").mkdir(parents=True, exist_ok=True)
    mini_test = ws / "tests" / "test_mini_check.py"
    mini_test.write_text("def test_mini_ok():\n    assert 2 + 2 == 4\n", encoding="utf-8")

    protected_dir = ws / "protected_zone"
    protected_dir.mkdir()
    prot_file = protected_dir / "immutable.txt"
    prot_file.write_text("do not touch\n", encoding="utf-8")

    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    engine = AcceptanceCriteriaEngine(root_dir=ws, handoff_manager=mgr)

    # 1. Missing JSON schema target must raise MissingSchemaTargetError!
    style_rel = "projects/proj_016c/style_bible.json"
    style_path = ws / style_rel
    style_path.parent.mkdir(parents=True, exist_ok=True)
    style_path.write_text('{"ok": true}\n', encoding="utf-8")
    h_missing_schema = _mk_handoff(
        task_id="TASK-NOSCHEMA",
        assigned_agent="art_director",
        owned_artifacts=[style_rel],
        done_when=[
            {
                "criterion_id": "DONE_01",
                "check_type": "json_schema_valid",
                "target": style_rel,  # return_schema is 'xdx.phase01_6c.test.v4.0' (no matching .schema.json!)
                "description": "Validate JSON without resolvable schema target.",
            }
        ],
    )
    res_ns = adapter.execute_sequential_fallback(
        handoff=h_missing_schema,
        worker_fn=lambda _hd, _rt: {"evidence_items": [f"Completed TASK-NOSCHEMA ({style_rel})"]},
    )
    with pytest.raises(MissingSchemaTargetError):
        engine.evaluate_all(handoff=h_missing_schema, result=res_ns, context_state={})

    # 2. Execute DAG exercising file_exists_nonempty, sha256_verified, json_schema_valid, pytest_pass, no_unapproved_mutation, and independent_review_verdict!
    eng_rel = "projects/proj_016c/engine_plan.json"
    exec_rel = "projects/proj_016c/execution_plan.md"
    valid_eng_doc = {
        "schema_version": "3.4.0",
        "project_id": "proj_016c",
        "master_compositor": "remotion",
        "encoding_validator": "ffmpeg",
        "reference_qc_engine": "rea_video",
        "fps": 30,
        "resolution": {"width": 1080, "height": 1920, "pixel_format": "yuv420p"},
        "color_management": {
            "working_space": "ACEScg",
            "view_transform": "sRGB",
            "delivery_space": "bt709",
            "alpha_interchange": "straight_rgba16",
        },
        "engines_used": ["blender", "remotion", "rea_video", "ffmpeg"],
        "omitted_engines_rationale": {"threejs": "Single hero 3D shot test"},
        "shot_routing": [
            {
                "shot_id": "S001",
                "start_frame": 0,
                "end_frame": 90,
                "primary_engine": "blender",
                "overlay_engine": "remotion",
                "rationale": "3D stage with caption overlay",
                "deterministic_seed": 42,
                "inputs": ["storyboard.json"],
                "output_contract": {"format": "png_sequence", "has_alpha": True, "frame_count": 90},
                "style_consistency_notes": "Stylized 3D ACEScg",
                "proposed_fallback": "threejs_3d_stage",
            }
        ],
    }
    expected_eng_bytes = (json.dumps(valid_eng_doc, indent=2) + "\n").encode("utf-8")
    expected_exec_bytes = b"# Execution Plan\n"
    import hashlib

    expected_eng_sha = hashlib.sha256(expected_eng_bytes).hexdigest()
    expected_exec_sha = hashlib.sha256(expected_exec_bytes).hexdigest()

    t_prod = _mk_handoff(
        task_id="TASK-ALL-CHECKS",
        assigned_agent="remotion_specialist",
        owned_artifacts=[eng_rel, exec_rel],
        done_when=[
            {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": exec_rel, "description": "Execution markdown non-empty."},
            {"criterion_id": "DONE_02", "check_type": "sha256_verified", "target": f"{eng_rel}::{expected_eng_sha}", "description": "Exact SHA-256 verified."},
            {"criterion_id": "DONE_03", "check_type": "json_schema_valid", "target": f"{eng_rel}::schemas/engine_plan.schema.json", "description": "Valid engine_plan schema."},
            {"criterion_id": "DONE_04", "check_type": "pytest_pass", "target": "tests/test_mini_check.py", "description": "Pytest mini check passes."},
            {"criterion_id": "DONE_05", "check_type": "no_unapproved_mutation", "target": "protected_zone", "description": "Protected zone untouched."},
        ],
    )
    crit_man = ImmutableReviewCriteriaManifest.create_sealed(
        project_id="proj_016c",
        producer_task_id="TASK-ALL-CHECKS",
        reviewer_task_id="TASK-VER-CHECKS",
        required_criteria=[{"criterion_id": "CRIT_ENGINE_OK", "description": "Engine plan verified"}],
    )
    t_ver = _mk_handoff(
        task_id="TASK-VER-CHECKS",
        assigned_agent="preproduction_verifier",
        dependencies=["TASK-ALL-CHECKS"],
        input_artifacts=[eng_rel, exec_rel],
        input_artifact_hashes={eng_rel: expected_eng_sha, exec_rel: expected_exec_sha},
        owned_artifacts=[],
        output_artifacts=[],
        done_when=[
            {
                "criterion_id": "DONE_01",
                "check_type": "independent_review_verdict",
                "target": "TASK-ALL-CHECKS",
                "description": "Independent verifier verdict PASS.",
            }
        ],
        required_evidence=["Completed TASK-VER-CHECKS review on engine_plan.json"],
        extra_context={"criteria_manifest": crit_man.to_dict()},
    )

    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr, execution_adapter=adapter)

    async def _worker(h: dict[str, Any], _a: int) -> AgentExecutionResult:
        if h["task_id"] == "TASK-ALL-CHECKS":
            (ws / eng_rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / eng_rel).write_bytes(expected_eng_bytes)
            (ws / exec_rel).write_text("# Execution Plan\n", encoding="utf-8")
            return adapter.execute_sequential_fallback(
                handoff=h,
                worker_fn=lambda _hd, _rt: {"evidence_items": [f"Completed TASK-ALL-CHECKS ({eng_rel})"]},
            )
        base = adapter.execute_sequential_fallback(
            handoff=h,
            worker_fn=lambda _hd, _rt: {"evidence_items": ["Completed TASK-VER-CHECKS review on engine_plan.json"]},
        )
        hashes = {
            eng_rel: compute_file_sha256(ws / eng_rel),
            exec_rel: compute_file_sha256(ws / exec_rel),
        }
        rep = AgentReviewReport(
            schema_version="4.0.0-phase01.6c",
            review_id="REV-ALL-001",
            project_id="proj_016c",
            verifier_agent="preproduction_verifier",
            reviewer_task_id="TASK-VER-CHECKS",
            reviewed_task_id="TASK-ALL-CHECKS",
            producer_agent="remotion_specialist",
            producer_conversation_id=None,
            reviewer_conversation_id=None,
            criteria_manifest_digest=crit_man.manifest_sha256,
            verdict="PASS",
            invocation_receipt=base.receipt.to_review_receipt_dict(),
            reviewed_artifact_hashes=hashes,
            pre_review_hashes=hashes,
            post_review_hashes=hashes,
            reviewed_artifact_manifest={k: {"sha256": v, "owner_task_id": "TASK-ALL-CHECKS"} for k, v in hashes.items()},
            required_criteria_ids=["CRIT_ENGINE_OK"],
            checked_criteria=[{"criterion_id": "CRIT_ENGINE_OK", "status": "PASS", "evidence": "Verified engine_plan.json and execution_plan.md hashes."}],
            defects=[],
        )
        return AgentExecutionResult(
            task_id=base.task_id,
            project_id=base.project_id,
            status=base.status,
            receipt=base.receipt,
            evidence_items=base.evidence_items,
            criterion_evidence=base.criterion_evidence,
            review_report=rep,
        )

    out = asyncio.run(sched.execute_dag([t_prod, t_ver], executor=_worker))
    assert out["overall_status"] == "SUCCEEDED", out["failures"]
    assert out["completed_tasks"] == ["TASK-ALL-CHECKS", "TASK-VER-CHECKS"]


@pytest.mark.unit
def test_06_unsupported_acceptance_check_transitions_task_to_blocked(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr)

    t_unsup = _mk_handoff(
        task_id="TASK-UNSUP-01",
        done_when=[
            {
                "criterion_id": "DONE_01",
                "check_type": "unsupported_ai_vibe_check",
                "target": "projects/proj_016c/research.md",
                "description": "Unsupported check type must block task.",
            }
        ],
    )
    t_down = _mk_handoff(
        task_id="TASK-UNSUP-DOWN",
        assigned_agent="creative_director",
        dependencies=["TASK-UNSUP-01"],
        owned_artifacts=["projects/proj_016c/blueprint.md"],
    )

    async def _never(_h: dict[str, Any], _a: int) -> AgentExecutionResult:
        raise AssertionError("Unsupported check task should be BLOCKED, not executed")

    res = asyncio.run(sched.execute_dag([t_unsup, t_down], executor=_never))
    assert res["overall_status"] == "PARTIAL_OR_FAILED"
    assert res["completed_tasks"] == []
    assert res["blocked_tasks"] == ["TASK-UNSUP-01", "TASK-UNSUP-DOWN"]
    assert res["failures"][0]["error_category"] == "UNSUPPORTED_ACCEPTANCE_CHECK"

    with pytest.raises(UnsupportedAcceptanceCheckError):
        sched.acceptance_engine.evaluate_all(
            handoff=t_unsup,
            result=sched.execution_adapter.emit_host_dispatch_plan_only(
                _mk_handoff(task_id="TASK-UNSUP-01")
            ),
            context_state={},
        )


@pytest.mark.unit
def test_07_unrelated_evidence_and_foreign_task_evidence_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    sched = TaskDependencyScheduler(root_dir=ws, handoff_manager=mgr, execution_adapter=adapter)

    t1 = _mk_handoff(
        task_id="TASK-EVID-01",
        required_evidence=["Verified thermodynamic evaporator citations in research.md"],
    )
    f_out = ws / "projects" / "proj_016c" / "research.md"
    f_out.parent.mkdir(parents=True, exist_ok=True)
    f_out.write_text("# Real file on disk\n", encoding="utf-8")

    # 1. Generic filler / unrelated text of length >= 5 must be rejected!
    res_unrelated = adapter.execute_sequential_fallback(
        handoff=t1,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Completed task successfully without errors"]},
    )
    with pytest.raises(UnrelatedEvidenceError):
        sched.acceptance_engine.evaluate_all(handoff=t1, result=res_unrelated, context_state={})

    # 2. Evidence referencing a foreign task ID must be rejected!
    res_foreign = adapter.execute_sequential_fallback(
        handoff=t1,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Verified research.md for TASK-OTHER-999"]},
    )
    with pytest.raises(UnrelatedEvidenceError):
        sched.acceptance_engine.evaluate_all(handoff=t1, result=res_foreign, context_state={})


@pytest.mark.unit
def test_08_receipt_task_identity_mismatch_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    engine = AcceptanceCriteriaEngine(root_dir=ws, handoff_manager=mgr)

    t1 = _mk_handoff(task_id="TASK-ID-A", owned_artifacts=["projects/proj_016c/research.md"])
    t2 = _mk_handoff(
        task_id="TASK-ID-B",
        assigned_agent="creative_director",
        owned_artifacts=["projects/proj_016c/blueprint.md"],
    )
    for rel in ("projects/proj_016c/research.md", "projects/proj_016c/blueprint.md"):
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Content\n", encoding="utf-8")

    wrong_worker_res = adapter.execute_sequential_fallback(
        handoff=t2,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Completed TASK-ID-B blueprint.md"]},
    )
    with pytest.raises(WorkerIdentityMismatchError):
        engine.evaluate_all(handoff=t1, result=wrong_worker_res, context_state={})


@pytest.mark.unit
def test_09_receipt_output_hash_mismatch_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    engine = AcceptanceCriteriaEngine(root_dir=ws, handoff_manager=mgr)

    rel = "projects/proj_016c/research.md"
    f_out = ws / rel
    f_out.parent.mkdir(parents=True, exist_ok=True)
    f_out.write_text("# Initial version hashed into receipt\n", encoding="utf-8")

    t1 = _mk_handoff(task_id="TASK-HASH-01", owned_artifacts=[rel])
    res = adapter.execute_sequential_fallback(
        handoff=t1,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Completed TASK-HASH-01 research.md"]},
    )
    # Modify file on disk AFTER receipt was sealed -> receipt output hash != live disk SHA-256!
    f_out.write_text("# Tampered after receipt creation!\n", encoding="utf-8")
    with pytest.raises(ReceiptOutputHashMismatchError):
        engine.evaluate_all(handoff=t1, result=res, context_state={})


@pytest.mark.unit
def test_10_reviewer_criteria_manipulation_and_missing_defect_rejected(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    rel = "projects/proj_016c/script.md"
    f_script = ws / rel
    f_script.parent.mkdir(parents=True, exist_ok=True)
    f_script.write_text("# Naskah Asli\n", encoding="utf-8")
    sha = compute_file_sha256(f_script)

    prod_h = _mk_handoff(task_id="TASK-P10", assigned_agent="scriptwriter_agent", owned_artifacts=[rel])
    manifest = ImmutableReviewCriteriaManifest.create_sealed(
        project_id="proj_016c",
        producer_task_id="TASK-P10",
        reviewer_task_id="TASK-V10",
        required_criteria=[
            {"criterion_id": "CRIT_A", "description": "Topic accuracy check"},
            {"criterion_id": "CRIT_B", "description": "Originality check"},
        ],
    )
    ver_h = _mk_handoff(
        task_id="TASK-V10",
        assigned_agent="preproduction_verifier",
        dependencies=["TASK-P10"],
        input_artifacts=[rel],
        input_artifact_hashes={rel: sha},
        owned_artifacts=[],
        output_artifacts=[],
        extra_context={"criteria_manifest": manifest.to_dict()},
    )

    base_report = {
        "schema_version": "4.0.0-phase01.6c",
        "review_id": "REV-MANIP-01",
        "project_id": "proj_016c",
        "verifier_agent": "preproduction_verifier",
        "reviewer_task_id": "TASK-V10",
        "reviewed_task_id": "TASK-P10",
        "producer_agent": "scriptwriter_agent",
        "producer_conversation_id": "conv_prod_11111111",
        "reviewer_conversation_id": "conv_rev_22222222",
        "criteria_manifest_digest": manifest.manifest_sha256,
        "verdict": "PASS",
        "invocation_receipt": {
            "invocation_id": "RCPT-V10",
            "agent_id": "preproduction_verifier",
            "runtime_name": "antigravity",
            "execution_mode": "native_subagent",
            "actually_invoked": True,
            "conversation_id": "conv_rev_22222222",
            "started_at": "2026-11-27T14:00:00+00:00",
            "completed_at": "2026-11-27T14:00:05+00:00",
        },
        "reviewed_artifact_hashes": {rel: sha},
        "pre_review_hashes": {rel: sha},
        "post_review_hashes": {rel: sha},
        "reviewed_artifact_manifest": {rel: {"sha256": sha, "owner_task_id": "TASK-P10", "size_bytes": f_script.stat().st_size}},
        "required_criteria_ids": ["CRIT_A", "CRIT_B"],
        "checked_criteria": [
            {"criterion_id": "CRIT_A", "status": "PASS", "evidence": "Verified topic accuracy against claims."},
            {"criterion_id": "CRIT_B", "status": "PASS", "evidence": "Verified script originality on disk."},
        ],
        "defects": [],
    }
    assert (
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes={rel: sha},
            review_report=base_report,
            producer_conversation_id="conv_prod_11111111",
            base_dir=ws,
        )["verified"]
        is True
    )

    # 1. Reviewer drops CRIT_B from required_criteria_ids -> ReviewerCriteriaManipulationError!
    dropped = copy.deepcopy(base_report)
    dropped["required_criteria_ids"] = ["CRIT_A"]
    dropped["checked_criteria"] = [dropped["checked_criteria"][0]]
    with pytest.raises(ReviewerCriteriaManipulationError):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes={rel: sha},
            review_report=dropped,
            producer_conversation_id="conv_prod_11111111",
            base_dir=ws,
        )

    # 2. Reviewer fails CRIT_B with REVISION_REQUIRED but omits defect entry -> HandoffValidationError!
    missing_defect = copy.deepcopy(base_report)
    missing_defect["verdict"] = "REVISION_REQUIRED"
    missing_defect["checked_criteria"][1]["status"] = "FAIL"
    missing_defect["defects"] = []
    with pytest.raises(HandoffValidationError, match="Incomplete defect reporting"):
        mgr.verify_independent_review_pass(
            verifier_handoff=ver_h,
            producer_handoff=prod_h,
            pre_review_hashes={rel: sha},
            review_report=missing_defect,
            producer_conversation_id="conv_prod_11111111",
            base_dir=ws,
        )


@pytest.mark.mock_test
def test_11_corrupted_latest_checkpoint_automatic_fallback_and_portable_bundle(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mem = SixPartitionMemoryStore(tmp_path / "ckpt_mem.sqlite3")
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)
    ckpt_mgr = CheckpointManager(tmp_path / "ckpts_fb", root_dir=ws, handoff_manager=mgr, memory_store=mem)
    sched = TaskDependencyScheduler(
        root_dir=ws, handoff_manager=mgr, execution_adapter=adapter, checkpoint_manager=ckpt_mgr, memory_store=mem
    )

    t1 = _mk_handoff(task_id="TASK-FB-01", owned_artifacts=["projects/proj_016c/research.md"])
    t2 = _mk_handoff(
        task_id="TASK-FB-02",
        assigned_agent="creative_director",
        dependencies=["TASK-FB-01"],
        owned_artifacts=["projects/proj_016c/blueprint.md"],
    )

    async def _worker(h: dict[str, Any], _a: int) -> AgentExecutionResult:
        p = ws / h["owned_artifacts"][0]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {h['task_id']}\n", encoding="utf-8")
        return adapter.execute_sequential_fallback(
            handoff=h,
            worker_fn=lambda _hd, _rt: {"evidence_items": [f"Completed {h['task_id']} ({h['owned_artifacts'][0]})"]},
        )

    asyncio.run(sched.execute_dag([t1, t2], executor=_worker))

    # Corrupt latest_checkpoint.json AND the newest numbered checkpoint -> must fall back automatically!
    (ckpt_mgr.latest_file).write_text("{truncated_corrupt_json", encoding="utf-8")
    seq_files = sorted(ckpt_mgr.checkpoint_dir.glob("checkpoint_*.json"))
    assert len(seq_files) >= 2
    seq_files[-1].write_text('{"corrupt": true}', encoding="utf-8")

    rec = ckpt_mgr.resume(expected_project_id="proj_016c", expected_handoffs=[t1, t2])
    assert rec["fallback_recovery"]["recovered_via_fallback"] is True
    assert "latest_checkpoint.json" in rec["fallback_recovery"]["corrupted_checkpoints_skipped"]
    assert rec["cross_vm_verified"] is False
    assert rec["checkpoint_lineage"]["sequence_number"] >= 1

    # Portable bundle export/import + secret leak rejection
    bundle_file = tmp_path / "portable_bundle.json"
    exported = ckpt_mgr.export_portable_bundle(bundle_file)
    assert exported["cross_vm_automatic_storage_available"] is False

    ckpt_mgr_imported = CheckpointManager(tmp_path / "ckpts_imported", root_dir=ws, handoff_manager=mgr)
    imported_resume = ckpt_mgr_imported.import_portable_bundle(bundle_file, expected_project_id="proj_016c")
    assert imported_resume["project_id"] == "proj_016c"

    leaked_bundle = tmp_path / "leaked_bundle.json"
    leaked_bundle.write_text('{"token": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"}', encoding="utf-8")
    with pytest.raises(SecretLeakBlockedError):
        ckpt_mgr_imported.import_portable_bundle(leaked_bundle)


@pytest.mark.mock_test
def test_12_runtime_capability_portability_unknown_outside_antigravity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disc = RuntimeCapabilityDiscovery(evidence_path=tmp_path / "none.json")
    monkeypatch.setattr(
        disc.antigravity_adapter,
        "detect_host_markers",
        lambda: {
            "detected": False,
            "is_remote_devbox": False,
            "jetski_appdata_present": False,
            "agy_cli_binary": None,
            "python_can_introspect_host_llm_tools_directly": False,
        },
    )
    rep = disc.discover()
    assert rep["runtime_identity"]["adapter_type"] in {"codex", "python_standalone"}
    for tool_cap in (
        "host_tool:invoke_subagent",
        "host_tool:define_subagent",
        "host_tool:send_message",
        "host_tool:manage_subagents",
        "workspace_mode:inherit",
    ):
        entry = rep["capabilities"][tool_cap]
        assert entry["status"] == "UNKNOWN"
        assert entry["runtime_capability_status"] == "UNKNOWN"
        assert entry["documentation_status"] == "NOT_APPLICABLE_ON_CURRENT_HOST"
        assert entry["live_invocation_evidence"]["verified"] is False


@pytest.mark.unit
def test_13_untrusted_approval_and_boolean_production_bypass_rejected(tmp_path: Path) -> None:
    with pytest.raises(ProductionApprovalFrozenError):
        SharedProjectStateMachine(tmp_path / "sm_bool.json", allow_production_approval=True)

    with pytest.raises(PhaseBoundaryExecutionBlockedError):
        TaskDependencyScheduler(root_dir=ROOT_DIR, allow_phase02_roles=True)

    sm = SharedProjectStateMachine(tmp_path / "sm_freeze.json")
    sm.initialize(project_id="proj_frz", project_title="Freeze Test", genres=["explainer"])
    sm.transition("REQUEST_RECEIVED", expected_version=1, trigger="1", actor="master_director", evidence="ok")
    sm.transition("RESEARCHING", expected_version=2, trigger="2", actor="master_director", evidence="ok")
    sm.transition("CREATIVE_DEVELOPMENT", expected_version=3, trigger="3", actor="master_director", evidence="ok")
    sm.transition("STORYBOARDING", expected_version=4, trigger="4", actor="master_director", evidence="ok")
    sm.transition("PREPRODUCTION_QC", expected_version=5, trigger="5", actor="preproduction_verifier", evidence="ok")
    sm.transition("WAITING_APPROVAL", expected_version=6, trigger="6", actor="master_director", evidence="ok")

    # Invalid digest + trusted_channel_verified=False + actor label MUST all fail closed!
    for bad_approval in (
        {"approved_digest": "not-a-sha256", "trusted_channel_verified": False},
        {"approved_digest": "b" * 64, "trusted_channel_verified": False},
        {"approved_digest": "b" * 64, "trusted_channel_verified": True},
    ):
        with pytest.raises(ProductionApprovalFrozenError):
            sm.transition(
                "APPROVED",
                expected_version=7,
                trigger="forged_gate",
                actor="trusted_human_approval_gate",
                evidence="Agent-crafted dictionary",
                verified_human_approval=bad_approval,
            )
    assert sm.load()["current_state"] == "WAITING_APPROVAL"
    assert sm.load()["approval_status"]["approved"] is False


# ==============================================================================
# 14–21: UNIVERSAL CREATIVE, REFERENCE LIFECYCLE, SEMANTIC & DEFECT REGISTRY
# ==============================================================================


@pytest.mark.unit
def test_14_universal_topic_relevance_and_unrelated_authored_fallback_rejected(tmp_path: Path) -> None:
    builder = PreProductionPackageBuilder()

    # 1. Requesting a new topic without authored_payload MUST halt at CREATIVE_PAYLOAD_REQUIRED!
    pkg_missing = tmp_path / "pkg_missing_payload"
    with pytest.raises(CreativePayloadRequiredError) as exc_info:
        builder.build_waiting_approval_package(
            package_dir=pkg_missing,
            project_id="ac_no_payload",
            topic="Bagaimana AC mendinginkan ruangan?",
            genres=["explainer"],
            target_duration_s=60,
        )
    assert exc_info.value.status == "CREATIVE_PAYLOAD_REQUIRED"
    v4_st = json.loads((pkg_missing / "project_state_v4.json").read_text(encoding="utf-8"))
    assert v4_st["current_state"] == "CREATIVE_PAYLOAD_REQUIRED"

    # 2. Renaming the Time Perception or Social Satire showcase payload to an unrelated topic MUST fail!
    swapped = build_authored_time_perception_payload(project_id="title_swap_attack", target_duration_s=60)
    swapped["topic_title"] = "Bagaimana AC Mendinginkan Ruangan?"
    with pytest.raises(TopicRelevanceError):
        CreativePayloadValidator().validate(swapped)

    swapped_satire = build_authored_social_satire_payload(project_id="title_swap_ocean", target_duration_s=60)
    swapped_satire["topic_title"] = "Apa yang Terjadi Jika Seluruh Laut Bumi Menghilang?"
    with pytest.raises(TopicRelevanceError):
        CreativePayloadValidator().validate(swapped_satire)

    # 3. Genuine AC payload passes validation cleanly
    valid_ac = _build_custom_ac_payload()
    metrics = CreativePayloadValidator().validate(valid_ac)
    assert metrics["title_keyword_overlap_script"] >= 1


@pytest.mark.integration
def test_15_reference_analyzer_fingerprint_change_and_8part_cache_invalidation(tmp_path: Path) -> None:
    mem = SixPartitionMemoryStore(tmp_path / "ref_cache.sqlite3")
    mgr = REAReferenceLifecycleManager(memory_store=mem, cache_dir=tmp_path / "rea_cache")

    real_fp = compute_actual_analyzer_source_fingerprint(ROOT_DIR)
    cfg_h1 = compute_analyzer_config_hash({"scene_threshold": 0.30})
    cfg_h2 = compute_analyzer_config_hash({"scene_threshold": 0.18})
    reg_sha = compute_file_sha256(ROOT_DIR / "reference_database" / "reference_registry.json")
    assert len(real_fp) == 64
    assert cfg_h1 != cfg_h2
    assert cfg_h1 != reg_sha  # Never uses reference_registry.json as config hash!

    # Run 1: initial population (without slow full-video decode on 38MB LFS MP4 in unit cache check)
    r1 = mgr.inspect_or_refresh_reference("REF-002", run_live_reanalysis_on_miss=False)
    assert r1["cache_status"] == "CACHE_POPULATED_INITIAL"
    assert set(r1["epistemic_analysis"].keys()) == {"measurements", "visual_observations", "inferences", "limitations"}

    # Run 2: identical 8-part cache key -> CACHE_HIT_VALID
    r2 = mgr.inspect_or_refresh_reference("REF-002", run_live_reanalysis_on_miss=False)
    assert r2["cache_status"] == "CACHE_HIT_VALID"

    # Run 3: simulate analyzer source fingerprint change -> CACHE_MISS_INVALIDATED + prior versions preserved!
    r3 = mgr.inspect_or_refresh_reference(
        "REF-002",
        analyzer_source_fingerprint_override="f" * 64,
        run_live_reanalysis_on_miss=False,
    )
    assert r3["cache_status"] == "CACHE_MISS_INVALIDATED"
    assert "changed:analyzer_source_fingerprint" in r3["invalidation_reasons"]
    assert r3["preserved_versions_count"] >= 4

    # Run 4: register a new custom reference using synthetic MP4 and run LIVE REA re-analysis on config change!
    synth_mp4 = ensure_deterministic_synthetic_mp4(tmp_path / "custom_ref.mp4")
    new_rec = mgr.register_new_reference(
        reference_id="REF-901",
        genre="explainer",
        video_path=synth_mp4,
        title="Synthetic Custom Reference",
        staging_dir=tmp_path / "ref901_stage",
    )
    assert new_rec.reference_id == "REF-901"
    c_init = mgr.inspect_or_refresh_reference("REF-901", analyzer_config={"scene_threshold": 0.30}, run_live_reanalysis_on_miss=True)
    assert c_init["reanalyzed"] is True
    c_inv = mgr.inspect_or_refresh_reference("REF-901", analyzer_config={"scene_threshold": 0.20}, run_live_reanalysis_on_miss=True)
    assert c_inv["cache_status"] == "CACHE_MISS_INVALIDATED"
    assert "changed:analyzer_config_hash" in c_inv["invalidation_reasons"]
    assert c_inv["reanalyzed"] is True


@pytest.mark.unit
def test_16_semantic_clause_coverage_and_12_visual_purposes(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "pkg_ac_sem"
    ac_payload = _build_custom_ac_payload(project_id="ac_sem_01", duration_s=30)
    PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="ac_sem_01",
        target_duration_s=30,
        authored_payload=ac_payload,
    )
    sem = json.loads((pkg_dir / "semantic_visual_plan.json").read_text(encoding="utf-8"))
    sb = json.loads((pkg_dir / "storyboard.json").read_text(encoding="utf-8"))

    assert len(SEMANTIC_VISUAL_PURPOSES) == 12
    assert sem["clause_coverage_ratio"] == 1.0
    assert sem["mapped_clauses"] == sem["total_clauses"] >= 3
    assert set(sem["visual_purposes_used"]).issubset(set(SEMANTIC_VISUAL_PURPOSES))
    assert len(sem["visual_purposes_used"]) >= 3
    assert sb["total_frames"] == 900
    assert all(isinstance(s["start_frame"], int) and isinstance(s["end_frame"], int) for s in sb["shots"])
    assert all(s["duration_s"] <= 10.0 for s in sb["shots"])


@pytest.mark.unit
def test_17_narration_duration_estimation_and_non_destructive_tightening() -> None:
    timing = NarrationTimingIntelligence()
    overlong_payload = _build_custom_ac_payload(project_id="ac_overlong", duration_s=18)
    overlong_payload["narrative_beats"][0]["narration_vo"] = (
        "Perlu kita ketahui bersama bahwa sebenarnya pada dasarnya AC sangat amat bekerja keras "
        "menyerap kalor laten udara ruangan melalui pipa evaporator bertekanan rendah. "
        "Perlu kita ketahui bersama bahwa sebenarnya pada dasarnya AC sangat amat bekerja keras "
        "menyerap kalor laten udara ruangan melalui pipa evaporator bertekanan rendah."
    )
    rep = timing.evaluate_and_adapt_payload_timing(overlong_payload, base_wpm=145)
    assert rep["timing_status"] == "ESTIMATED"
    assert rep["playback_speed_multiplier"] == 1.0
    assert rep["audio_speedup_forbidden"] is True
    assert len(rep["non_destructive_tightening_revisions"]) >= 1
    assert rep["final_estimated_duration_s"] < rep["initial_estimated_duration_s"]
    assert rep["duration_recommendation"]["recommended_target_duration_s"] >= 18


@pytest.mark.unit
def test_18_multi_reference_10d_conflict_handling_and_14_field_adaptation(tmp_path: Path) -> None:
    mgr = REAReferenceLifecycleManager()
    ctx = mgr.resolve_lifecycle_context(
        genres=["explainer", "satir_sosial"],
        explicit_reference_ids=["REF-001", "REF-002"],
    )
    fusion = MultiReferenceFusionEngine().fuse(
        ctx["records"],
        genres=["explainer", "satir_sosial"],
        chosen_style_profile="stylized_3d",
    )
    assert fusion["fusion_mode"] == "multi_reference_10d_conflict_resolved"
    assert set(fusion["dimensions"].keys()) == set(TEN_FUSION_DIMENSIONS)
    assert fusion["conflicts_detected_count"] == 10
    assert fusion["style_consistency_verified"] is True
    for dim, dinfo in fusion["dimensions"].items():
        assert dinfo["primary_reference_id"] in {"REF-001", "REF-002"}
        assert len(dinfo["adaptation_rationale"]) > 20

    pkg_dir = tmp_path / "pkg_multiref"
    ac_payload = _build_custom_ac_payload(project_id="ac_multiref", duration_s=30)
    PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="ac_multiref",
        genres=["explainer", "satir_sosial"],
        reference_ids=["REF-001", "REF-002"],
        target_duration_s=30,
        authored_payload=ac_payload,
    )
    adapt_doc = json.loads((pkg_dir / "reference_adaptation.json").read_text(encoding="utf-8"))
    sb = json.loads((pkg_dir / "storyboard.json").read_text(encoding="utf-8"))
    assert len(adapt_doc["adaptation_records"]) == len(sb["shots"])
    for rec in adapt_doc["adaptation_records"]:
        for req_f in MANDATORY_ADAPTATION_FIELDS:
            assert req_f in rec and rec[req_f]


@pytest.mark.unit
def test_19_character_11_field_continuity_and_8_style_profiles_consistency() -> None:
    cs = CharacterAndStyleIntelligence()
    assert set(SUPPORTED_STYLE_PROFILES.keys()) == {
        "flat_cartoon",
        "stylized_3d",
        "diorama",
        "anime_inspired",
        "2d_animation",
        "realistic",
        "infographic",
        "mixed_media",
    }
    for prof_name in SUPPORTED_STYLE_PROFILES:
        p = _build_custom_ac_payload(project_id=f"style_{prof_name}", duration_s=24)
        p["style_profile"] = prof_name
        sb_style = cs.compile_style_bible(p, reference_ids=[])
        assert sb_style["style_profile"] == prof_name
        assert sb_style["forced_from_ref001_or_ref002"] is False
        assert sb_style["modeling_executed_in_phase_01_6c"] is False

    # Verify 11 character fields, 14 action fields, 12 asset fields, and non-36mm camera focal lengths
    sample = _build_custom_ac_payload(project_id="char_act_asset", duration_s=30)
    style = cs.compile_style_bible(sample, reference_ids=["REF-002"])
    from intelligence.creative_pipeline import StoryboardDirector, UniversalMasterPromptEngine

    blend = UniversalMasterPromptEngine().blend_genres(sample["genres"])
    sb = StoryboardDirector().compile_hierarchical_storyboard(sample, genre_blend=blend)
    timing = NarrationTimingIntelligence().evaluate_and_adapt_payload_timing(sample)
    SemanticVisualDirector().build_clause_to_shot_plan(payload=sample, storyboard=sb, timing_report=timing)
    cam_plan = PurposeDrivenCameraAudioCaptionPlanner().build_camera_plan(sb, style)
    assert cam_plan["locked_to_single_36mm_focal_length"] is False
    assert len(cam_plan["distinct_focal_lengths_mm"]) >= 3

    cb_json, chars_v4, _ = cs.compile_character_bible_v4(sample, style_bible=style, storyboard=sb)
    assert all(all(f in c for f in MANDATORY_11_CHARACTER_FIELDS) for c in cb_json["characters"])

    m_plan = CharacterActionPlanner().build_action_plan(storyboard=sb, characters=chars_v4)
    assert all(all(f in a for f in MANDATORY_14_ACTION_FIELDS) for a in m_plan["planned_actions"])

    a_man = SemanticAssetPlanner().build_semantic_asset_manifest(
        project_id="char_act_asset", storyboard=sb, style_bible=style, characters=chars_v4
    )
    assert all(
        all(f in spec for f in MANDATORY_12_ASSET_FIELDS) and spec["ready_on_disk_now"] is False
        for spec in a_man["semantic_asset_specs"]
    )


@pytest.mark.unit
def test_20_master_audit_defect_registry_completeness_and_verified_guard(tmp_path: Path) -> None:
    reg = MasterAuditDefectRegistry()
    doc = reg.load_and_validate()
    summary = reg.summary()
    assert summary["total_defects"] >= 18
    assert summary["counts_by_status"]["SCHEDULED"] >= 1  # Phase 01.6D Trusted Human Approval & Execution Guard

    # Append-only guard rejects deletion of historical defects
    existing_ids = {d["defect_id"] for d in doc["defects"]}
    truncated_doc = copy.deepcopy(doc)
    truncated_doc["defects"] = truncated_doc["defects"][1:]
    bad_file = tmp_path / "truncated_defects.json"
    bad_file.write_text(json.dumps(truncated_doc), encoding="utf-8")
    with pytest.raises(DefectRegistryValidationError, match="Append-only violation"):
        MasterAuditDefectRegistry(registry_path=bad_file).load_and_validate(previous_defect_ids=existing_ids)

    # Marking VERIFIED without an existing regression test MUST fail!
    untested_verified = copy.deepcopy(doc)
    untested_verified["defects"][-1]["current_status"] = "VERIFIED"
    untested_verified["defects"][-1]["regression_test"] = "tests/nonexistent_file.py::test_missing"
    bad_ver_file = tmp_path / "bad_verified.json"
    bad_ver_file.write_text(json.dumps(untested_verified), encoding="utf-8")
    with pytest.raises(DefectRegistryValidationError, match="does not exist"):
        MasterAuditDefectRegistry(registry_path=bad_ver_file).load_and_validate()


@pytest.mark.mock_test
def test_21_native_execution_5_modes_and_static_conversation_id_rejection(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    mgr = TaskHandoffManager(root_dir=ws, registry=TaskHandoffManager().registry)
    adapter = NativeAgentExecutionAdapter(root_dir=ws, handoff_manager=mgr, registry=mgr.registry)

    rel = "projects/proj_016c/research.md"
    f_out = ws / rel
    f_out.parent.mkdir(parents=True, exist_ok=True)
    f_out.write_text("# Mode Verification\n", encoding="utf-8")
    h = _mk_handoff(task_id="TASK-MODES-01", owned_artifacts=[rel])
    req = adapter.build_invocation_request(h)

    # 1. Static conversation_id WITHOUT host transcript or dispatcher proof rejected when require_live_host_proof=True!
    with pytest.raises(ValueError, match="static conversation_id"):
        adapter.record_host_subagent_completion(
            handoff=h,
            request=req,
            conversation_id="static_hardcoded_conv_id_12345",
            known_model_routing="inherit",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            payload={},
            evidence_items=["Completed TASK-MODES-01 research.md"],
            require_live_host_proof=True,
        )

    # 2. Genuine transcript file containing invoke_subagent + conversation_id passes!
    fake_transcript = tmp_path / "transcript.jsonl"
    fake_transcript.write_text(
        '{"tool":"invoke_subagent","type":"xdx-topic-researcher","conversationId":"live_conv_9988776655"}\n',
        encoding="utf-8",
    )
    live_res = adapter.record_host_subagent_completion(
        handoff=h,
        request=req,
        conversation_id="live_conv_9988776655",
        known_model_routing="inherit",
        started_at=utc_now_iso(),
        completed_at=utc_now_iso(),
        payload={},
        evidence_items=["Completed TASK-MODES-01 research.md"],
        transcript_path=fake_transcript,
        require_live_host_proof=True,
    )
    assert live_res.receipt.execution_mode == "native_subagent"

    # 3. Recorded workflow replay, sequential fallback, mock execution, and dispatch plan are all distinct
    replay_res = adapter.record_workflow_replay_completion(
        handoff=h,
        recorded_receipt=live_res.receipt.to_dict(),
        payload={},
        evidence_items=["Replayed TASK-MODES-01 research.md"],
    )
    seq_res = adapter.execute_sequential_fallback(
        handoff=h,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Sequential TASK-MODES-01 research.md"]},
    )
    mock_res = adapter.execute_mock_worker(
        handoff=h,
        worker_fn=lambda _hd, _rt: {"evidence_items": ["Mock TASK-MODES-01 research.md"]},
    )
    plan_res = adapter.emit_host_dispatch_plan_only(h)

    modes = {
        live_res.receipt.execution_mode,
        replay_res.receipt.execution_mode,
        seq_res.receipt.execution_mode,
        mock_res.receipt.execution_mode,
        plan_res.receipt.execution_mode,
    }
    assert modes == {
        "native_subagent",
        "recorded_workflow_replay",
        "sequential_fallback_honest",
        "mock_execution",
        "dispatch_plan_only_not_invoked",
    }


@pytest.mark.integration
def test_22_preproduction_workflow_revision_cycle_and_6_partition_memory_invalidation(tmp_path: Path) -> None:
    ws = _setup_ws(tmp_path)
    # Copy required read-only registries, libraries, and reference metadata symlinks into isolated ws
    for dirname in ("registry", "libraries", ".agents", "docs", "scripts", "intelligence", "orchestration", "governance", "adapters", "engines", "memory", "reference_database"):
        src = ROOT_DIR / dirname
        dst = ws / dirname
        if src.exists() and not dst.exists():
            dst.symlink_to(src, target_is_directory=src.is_dir())

    mem = SixPartitionMemoryStore(tmp_path / "wf_rev_mem.sqlite3")
    wf = PreproductionMultiAgentWorkflow(root_dir=ws, memory_store=mem, max_parallel_specialists=4)
    ac_payload = _build_custom_ac_payload(project_id="wf_rev_test", duration_s=30)

    def _tamper_caption_once(pdir: Path) -> None:
        # Simulate missing ESTIMATED status on first run so PreproductionVerifierEngine returns REVISION_REQUIRED!
        cap_file = pdir / "caption_audio_plan.json"
        doc = json.loads(cap_file.read_text(encoding="utf-8"))
        doc["timestamp_status"] = "UNVERIFIED_BAD_STATUS"
        cap_file.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    out = wf.run_workflow(
        project_id="wf_rev_test",
        topic="Bagaimana AC Mendinginkan Ruangan?",
        genres=["explainer", "edukasi"],
        target_duration_s=30,
        authored_payload=ac_payload,
        explicit_reference_ids=["REF-002"],
        execution_mode="sequential_fallback_honest",
        inject_revision_defect_once=_tamper_caption_once,
    )
    assert out["status"] == "WAITING_APPROVAL"
    assert len(out["revisions_applied"]) == 1
    assert out["independent_review_report"]["verdict"] == "PASS"
    assert len(out["approval_manifest"]["mandatory_13_items"]) == 13
    assert out["project_state_v4"]["current_state"] == "WAITING_APPROVAL"
    assert out["project_state_v4"]["approval_status"]["approved"] is False

    # Verify all 6 SQLite memory partitions received structured records!
    assert len(mem.knowledge.list_versions("research_evidence:wf_rev_test")) == 1
    assert mem.production.get_technique("style:xdx_stylized_3d_v4_0", "v4.0") is not None
    assert mem.project.get_latest_slot("wf_rev_test", "creative_decisions") is not None
    assert mem.project.get_latest_slot("wf_rev_test", "revision_history") is not None
    assert len(mem.execution.list_records("wf_rev_test", "task_completed")) >= 15
    assert len(mem.error.list_errors("wf_rev_test")) >= 1
    assert len(mem.quality.list_evaluations("wf_rev_test")) >= 1
    assert mem.verify_database_integrity()["all_rows_sha256_verified"] is True


# ==============================================================================
# 23–24: RECORDED WORKFLOW REPLAY & LIVE NATIVE BENCHMARK EVIDENCE
# ==============================================================================


@pytest.mark.replay_test
def test_23_recorded_workflow_replay_verifies_benchmark_receipts_honestly(tmp_path: Path) -> None:
    bench_summary_path = ROOT_DIR / "docs" / "evidence" / "phase01_6c_benchmarks" / "benchmark_suite_summary_v4.json"
    assert bench_summary_path.is_file(), "Benchmark suite summary must be generated before replay test"
    bench_summary = json.loads(bench_summary_path.read_text(encoding="utf-8"))

    bench_a_ReceiptMap = bench_summary["benchmarks"]["bench_a_ac_explainer_60s"]["agent_invocation_receipts"]
    bench_a_payload = json.loads(
        (ROOT_DIR / "projects" / "bench_a_ac_explainer_60s" / "authored_creative_payload.json").read_text(encoding="utf-8")
    )

    ws = _setup_ws(tmp_path)
    for dirname in ("registry", "libraries", ".agents", "docs", "scripts", "intelligence", "orchestration", "governance", "adapters", "engines", "memory", "reference_database"):
        src = ROOT_DIR / dirname
        dst = ws / dirname
        if src.exists() and not dst.exists():
            dst.symlink_to(src, target_is_directory=src.is_dir())

    wf = PreproductionMultiAgentWorkflow(root_dir=ws, max_parallel_specialists=4)
    # Phase 01.6D (DEF-P016D-026): benchmark A's narration is estimated at ~64.4s for a 60s target. The
    # recorded 01.6C review passed CRIT_06 anyway; the fixed verifier must now reject the 60s replay.
    with pytest.raises(RuntimeError, match="TASK-15-VERIFY"):
        wf.run_workflow(
            project_id="replay_bench_a_60s",
            topic=bench_a_payload["topic_title"],
            genres=bench_a_payload["genres"],
            target_duration_s=60,
            authored_payload=bench_a_payload,
            explicit_reference_ids=["REF-002"],
            execution_mode="recorded_workflow_replay",
            host_subagent_receipts=bench_a_ReceiptMap,
        )
    # Replay with the estimator's own recommended duration passes and receipts still verify honestly.
    replay_out = wf.run_workflow(
        project_id="replay_bench_a_70s",
        topic=bench_a_payload["topic_title"],
        genres=bench_a_payload["genres"],
        target_duration_s=70,
        authored_payload=bench_a_payload,
        explicit_reference_ids=["REF-002"],
        execution_mode="recorded_workflow_replay",
        host_subagent_receipts=bench_a_ReceiptMap,
    )
    assert replay_out["status"] == "WAITING_APPROVAL"
    assert replay_out["execution_mode"] == "recorded_workflow_replay"
    for rcpt in replay_out["dag_execution"]["agent_invocation_receipts"].values():
        assert rcpt["execution_mode"] == "recorded_workflow_replay"
        assert rcpt["actually_invoked"] is True


@pytest.mark.live_evidence
def test_24_live_native_creative_workflow_four_benchmarks_independent_review_and_13_item_packages() -> None:
    ev_dir = ROOT_DIR / "docs" / "evidence" / "phase01_6c_benchmarks"
    summary_path = ev_dir / "benchmark_suite_summary_v4.json"
    assert summary_path.is_file(), "Phase 01.6C live benchmark summary missing"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    expected_benchmarks = {
        "bench_a_ac_explainer_60s": (60, ["REF-002"], "stylized_3d"),
        "bench_b_birokrasi_satir_60s": (60, ["REF-001"], "diorama"),
        "bench_c_laut_hilang_hybrid_180s": (180, ["REF-001", "REF-002"], "stylized_3d"),
        "bench_d_kaus_kaki_flat_cartoon_45s": (45, [], "flat_cartoon"),
    }
    gate = ApprovalGate()
    assert len(MANDATORY_15_PREPRODUCTION_CRITERIA) == 15

    for bid, (exp_dur, exp_refs, exp_style) in expected_benchmarks.items():
        b_dir = ROOT_DIR / "projects" / bid
        assert b_dir.is_dir(), f"Missing benchmark directory {b_dir}"
        b_info = summary["benchmarks"][bid]

        assert b_info["status"] == "WAITING_APPROVAL"
        assert b_info["selected_reference_ids"] == exp_refs
        assert b_info["style_profile"] == exp_style
        assert b_info["rendering_or_blender_executed"] is False

        # Verify 13-item package via ApprovalGate + WAITING_APPROVAL state freeze
        gate_check = gate.inspect_package(b_dir)
        assert gate_check["status"] == "WAITING_APPROVAL"
        app_man = json.loads((b_dir / "approval_package_manifest.json").read_text(encoding="utf-8"))
        assert len(app_man["mandatory_13_items"]) == 13

        sb = json.loads((b_dir / "storyboard.json").read_text(encoding="utf-8"))
        assert sb["duration_s"] == float(exp_dur)
        assert sb["total_frames"] == exp_dur * 30
        assert all(s["duration_s"] <= 10.0 for s in sb["shots"])

        v4_state = json.loads((b_dir / "project_state_v4.json").read_text(encoding="utf-8"))
        assert v4_state["current_state"] == "WAITING_APPROVAL"
        assert v4_state["approval_status"]["approved"] is False

        # Verify 15-criterion independent review report PASS with distinct native reviewer conversation_id
        rev_rep = json.loads(
            (b_dir / ".reviews" / "independent_preproduction_review_v4.json").read_text(encoding="utf-8")
        )
        assert rev_rep["verdict"] == "PASS"
        assert len(rev_rep["checked_criteria"]) == 15
        assert rev_rep["defects"] == []
        assert rev_rep["invocation_receipt"]["execution_mode"] == "native_subagent"
        assert rev_rep["reviewer_conversation_id"] != rev_rep["producer_conversation_id"]

    # Confirm zero Blender Studio modifications and zero generated video renders in projects/
    blender_repo = ROOT_DIR.parent / "xdx-blender-studio"
    if blender_repo.is_dir():
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(blender_repo), capture_output=True, text=True, check=True)
        assert st.stdout.strip() == ""
    rendered_mp4s = list((ROOT_DIR / "projects").rglob("*.mp4"))
    assert rendered_mp4s == []
