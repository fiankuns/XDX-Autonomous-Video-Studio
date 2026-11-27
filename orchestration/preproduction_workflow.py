"""End-to-End 15-Task Multi-Agent Preproduction Workflow & 6-Partition Memory Integrator (Phase 01.6C).

Implements Sections 16, 17, 18 & 21:
- Orchestrates the full Creative + Preproduction Planning Department DAG through ``TaskDependencyScheduler``:
  Master Director
  -> Research Agent (01) & REA Reference Agent (02) [Parallel]
  -> Creative Director (03)
  -> Scriptwriter (04)
  -> Character Agent (06) & Art Director (07) [Parallel]
  -> Storyboard Director (05)
  -> Reference-to-Production Adaptation (02), Motion Planning (12), Cinematographer (13),
     Asset Planning (08), Audio Planning (15), Caption Planning (16), Engine Routing (11)
  -> Master Director Package Assembly + Sealed 15-Criterion ``ImmutableReviewCriteriaManifest``
  -> Independent Preproduction Verifier (17) [Fresh-Context Read-Only]
  -> Non-Destructive Revision Loop via ``RevisionManager`` if ``verdict == 'REVISION_REQUIRED'``
  -> Halts fail-closed at ``WAITING_APPROVAL`` (NEVER ``APPROVED`` or production!).
- Explicitly distinguishes all 5 execution modes:
  ``native_subagent``, ``recorded_workflow_replay``, ``sequential_fallback_honest``,
  ``mock_execution``, and ``dispatch_plan_only_not_invoked``.
- Persists all 11 required items into ``SixPartitionMemoryStore`` and supports safe secret-scanned
  portable checkpoint export/import.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

from intelligence.asset_management import atomic_write_bytes
from intelligence.creative_pipeline import (
    CreativePayloadRequiredError,
    CreativePayloadValidator,
    HybridEngineOrchestrator,
    StoryboardDirector,
    StoryScriptIntelligence,
    TopicResearchEngine,
    UniversalMasterPromptEngine,
)
from intelligence.preproduction_verifier_engine import (
    PreproductionVerifierEngine,
    build_mandatory_15_criteria_manifest,
)
from intelligence.reference_database_bridge import ReferenceDatabaseBridge, normalize_genre_list
from intelligence.reference_lifecycle import (
    MultiReferenceFusionEngine,
    REAReferenceLifecycleManager,
    ReferenceToProductionAdapter,
)
from intelligence.state_and_approval import (
    ProjectStateManager,
    compute_package_digest,
    format_structured_approval_command,
)
from intelligence.universal_preproduction import (
    CharacterActionPlanner,
    CharacterAndStyleIntelligence,
    NarrationTimingIntelligence,
    PurposeDrivenCameraAudioCaptionPlanner,
    SemanticAssetPlanner,
    SemanticVisualDirector,
    UniversalTopicResearchCompiler,
)
from libraries.loader import PresetLibraryRegistry
from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.agent_registry import AgentRegistry
from orchestration.checkpoint_manager import CheckpointManager
from orchestration.dependency_scheduler import TaskDependencyScheduler
from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentReviewReport,
    ImmutableReviewCriteriaManifest,
    NativeAgentExecutionAdapter,
    utc_now_iso,
)
from orchestration.revision_manager import RevisionManager
from orchestration.shared_state import SharedProjectStateMachine

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"


def _mk_task(
    *,
    task_id: str,
    project_id: str,
    assigned_agent: str,
    project_state: str,
    genres: list[str],
    ref_ids: list[str],
    goal: str,
    dependencies: list[str],
    input_artifacts: list[str],
    owned_artifacts: list[str],
    allowed_tools: list[str],
    done_when: list[dict[str, Any]],
    required_evidence: list[str],
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "project_state": project_state,
        "genre_ids": list(genres),
        "reference_ids": list(ref_ids),
        "workspace_mode": "inherit",
        "notes": f"Phase 01.6C native preproduction workflow task {task_id}",
    }
    if extra_context:
        ctx.update(extra_context)

    has_json = any(p.endswith(".json") for p in owned_artifacts)
    has_md = any(p.endswith(".md") for p in owned_artifacts)
    out_fmt = (
        "json_and_markdown"
        if (has_json and has_md)
        else ("json" if has_json else "markdown")
    )

    return {
        "task_id": task_id,
        "project_id": project_id,
        "parent_task_id": None,
        "assigned_agent": assigned_agent,
        "goal": goal,
        "context": ctx,
        "input_artifacts": list(input_artifacts),
        "input_artifact_hashes": {p: "0" * 64 for p in input_artifacts},
        "dependencies": list(dependencies),
        "owned_artifacts": list(owned_artifacts),
        "allowed_tools": list(allowed_tools),
        "forbidden_actions": [
            "Mutate files outside owned_artifacts",
            "Execute Blender modeling, animation, or rendering prior to Phase 02 approval",
            "Use unrelated time-perception or social-satire fallback payloads",
        ],
        "expected_output": {
            "summary": f"Verified preproduction artifact(s) for {task_id}.",
            "output_artifacts": list(owned_artifacts),
            "output_format": out_fmt,
        },
        "return_schema": "xdx.phase01_6c.preproduction.v4.0",
        "done_when": done_when,
        "required_evidence": required_evidence,
        "retry_budget": {"max_attempts": 2, "attempts_used": 0, "timeout_seconds": 120},
        "status": "PENDING",
    }


class PreproductionMultiAgentWorkflow:
    """Executes the complete 15-task Creative + Preproduction DAG and halts at WAITING_APPROVAL."""

    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
        max_parallel_specialists: int = 4,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.registry = AgentRegistry(root_dir=self.root_dir)
        self.handoff_manager = TaskHandoffManager(root_dir=self.root_dir, registry=self.registry)
        self.adapter = NativeAgentExecutionAdapter(
            root_dir=self.root_dir,
            handoff_manager=self.handoff_manager,
            registry=self.registry,
        )
        self.memory_store = memory_store
        self.max_parallel_specialists = max_parallel_specialists

        self.master_prompt = UniversalMasterPromptEngine()
        self.payload_validator = CreativePayloadValidator(schemas_dir=self.root_dir / "schemas")
        self.research_v34 = TopicResearchEngine()
        self.research_v4 = UniversalTopicResearchCompiler()
        self.story_engine = StoryScriptIntelligence()
        self.timing_engine = NarrationTimingIntelligence()
        self.storyboard_dir = StoryboardDirector()
        self.semantic_visual = SemanticVisualDirector()
        self.char_style = CharacterAndStyleIntelligence()
        self.action_planner = CharacterActionPlanner()
        self.asset_planner = SemanticAssetPlanner()
        self.cam_aud_cap = PurposeDrivenCameraAudioCaptionPlanner()
        self.hybrid_orch = HybridEngineOrchestrator()
        self.ref_bridge = ReferenceDatabaseBridge(studio_root=self.root_dir)
        self.ref_lifecycle = REAReferenceLifecycleManager(
            studio_root=self.root_dir, memory_store=self.memory_store
        )
        self.fusion_engine = MultiReferenceFusionEngine()
        self.ref_adapter = ReferenceToProductionAdapter()
        self.verifier_engine = PreproductionVerifierEngine(schemas_dir=self.root_dir / "schemas")
        self.presets = PresetLibraryRegistry()
        self._approval_schema = json.loads(
            (self.root_dir / "schemas" / "approval_package.schema.json").read_text(encoding="utf-8")
        )

    def build_15_task_dag(
        self,
        *,
        project_id: str,
        genres: list[str],
        reference_ids: list[str],
        criteria_manifest: ImmutableReviewCriteriaManifest,
    ) -> list[dict[str, Any]]:
        """Construct the validated 15-task preproduction DAG with canonical single-writer ownership."""
        p = f"projects/{project_id}"
        producer_ids = [
            "TASK-01-RESEARCH",
            "TASK-02-REFERENCE",
            "TASK-03-CREATIVE",
            "TASK-04-SCRIPT",
            "TASK-05-CHARACTER",
            "TASK-06-STYLE",
            "TASK-07-STORYBOARD",
            "TASK-08-REF-ADAPT",
            "TASK-09-MOTION",
            "TASK-10-CAMERA",
            "TASK-11-ASSET",
            "TASK-12-AUDIO",
            "TASK-13-CAPTION",
            "TASK-14-ENGINE",
        ]

        t01 = _mk_task(
            task_id="TASK-01-RESEARCH",
            project_id=project_id,
            assigned_agent="topic_research_agent",
            project_state="RESEARCHING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile verified research claims, primary https:// sources, misconceptions, and narration mapping for {project_id}.",
            dependencies=[],
            input_artifacts=[],
            owned_artifacts=[f"{p}/research.md", f"{p}/research_report.json"],
            allowed_tools=["view_file", "write_to_file", "google_search"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/research.md", "description": "Research markdown exists and is non-empty."},
                {"criterion_id": "DONE_02", "check_type": "file_exists_nonempty", "target": f"{p}/research_report.json", "description": "Structured research report JSON exists."},
            ],
            required_evidence=[f"Verified https:// research report for TASK-01-RESEARCH ({p}/research_report.json)"],
        )
        t02 = _mk_task(
            task_id="TASK-02-REFERENCE",
            project_id=project_id,
            assigned_agent="rea_video_reference_analyst",
            project_state="REFERENCE_ANALYSIS",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Verify reference MP4 SHA-256s, validate 8-part REA cache, and emit reference_analysis.md for {project_id}.",
            dependencies=[],
            input_artifacts=[],
            owned_artifacts=[f"{p}/reference_analysis.md"],
            allowed_tools=["view_file", "write_to_file", "run_command"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/reference_analysis.md", "description": "Reference analysis markdown exists."},
            ],
            required_evidence=[f"Verified reference analysis for TASK-02-REFERENCE ({p}/reference_analysis.md)"],
        )
        t03 = _mk_task(
            task_id="TASK-03-CREATIVE",
            project_id=project_id,
            assigned_agent="creative_director",
            project_state="CREATIVE_DEVELOPMENT",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Author original 3-act concept, 0-3s hook, humor strategy, and payoff blueprint for {project_id}.",
            dependencies=["TASK-01-RESEARCH", "TASK-02-REFERENCE"],
            input_artifacts=[f"{p}/research_report.json", f"{p}/reference_analysis.md"],
            owned_artifacts=[f"{p}/blueprint.md", f"{p}/creative_concept.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/blueprint.md", "description": "Blueprint markdown exists."},
                {"criterion_id": "DONE_02", "check_type": "file_exists_nonempty", "target": f"{p}/creative_concept.json", "description": "Creative concept JSON exists."},
            ],
            required_evidence=[f"Original 3-act blueprint for TASK-03-CREATIVE ({p}/blueprint.md)"],
        )
        t04 = _mk_task(
            task_id="TASK-04-SCRIPT",
            project_id=project_id,
            assigned_agent="scriptwriter_agent",
            project_state="CREATIVE_DEVELOPMENT",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Author natural Indonesian VO script, character dialogue, and schema-validated payload for {project_id}.",
            dependencies=["TASK-01-RESEARCH", "TASK-02-REFERENCE", "TASK-03-CREATIVE"],
            input_artifacts=[f"{p}/research_report.json", f"{p}/blueprint.md"],
            owned_artifacts=[f"{p}/script.md", f"{p}/authored_creative_payload.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/script.md", "description": "Broadcast-ready Indonesian script exists."},
                {
                    "criterion_id": "DONE_02",
                    "check_type": "json_schema_valid",
                    "target": f"{p}/authored_creative_payload.json::schemas/creative_intelligence.schema.json",
                    "description": "Creative payload validates against creative_intelligence.schema.json.",
                },
            ],
            required_evidence=[f"Validated Indonesian script & payload for TASK-04-SCRIPT ({p}/authored_creative_payload.json)"],
        )
        t05 = _mk_task(
            task_id="TASK-05-CHARACTER",
            project_id=project_id,
            assigned_agent="character_design_agent",
            project_state="CREATIVE_DEVELOPMENT",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile 11-attribute Character Bible and cross-shot continuity locks for {project_id}.",
            dependencies=["TASK-04-SCRIPT"],
            input_artifacts=[f"{p}/authored_creative_payload.json"],
            owned_artifacts=[f"{p}/character_bible.md", f"{p}/character_bible.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/character_bible.json", "description": "Character bible JSON exists."},
                {"criterion_id": "DONE_02", "check_type": "file_exists_nonempty", "target": f"{p}/character_bible.md", "description": "Character bible markdown exists."},
            ],
            required_evidence=[f"11-attribute Character Bible for TASK-05-CHARACTER ({p}/character_bible.json)"],
        )
        t06 = _mk_task(
            task_id="TASK-06-STYLE",
            project_id=project_id,
            assigned_agent="art_director",
            project_state="CREATIVE_DEVELOPMENT",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile Global Style Bible with unified detail tier across cast, environment, and props for {project_id}.",
            dependencies=["TASK-02-REFERENCE", "TASK-04-SCRIPT"],
            input_artifacts=[f"{p}/reference_analysis.md", f"{p}/authored_creative_payload.json"],
            owned_artifacts=[f"{p}/style_bible.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/style_bible.json", "description": "Global Style Bible JSON exists."},
            ],
            required_evidence=[f"Unified Global Style Bible for TASK-06-STYLE ({p}/style_bible.json)"],
        )
        t07 = _mk_task(
            task_id="TASK-07-STORYBOARD",
            project_id=project_id,
            assigned_agent="storyboard_director",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile integer-frame hierarchical storyboard (<=10s shots) and 100% clause-to-shot semantic plan for {project_id}.",
            dependencies=["TASK-04-SCRIPT", "TASK-05-CHARACTER", "TASK-06-STYLE"],
            input_artifacts=[f"{p}/authored_creative_payload.json", f"{p}/character_bible.json", f"{p}/style_bible.json"],
            owned_artifacts=[f"{p}/storyboard.json", f"{p}/semantic_visual_plan.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {
                    "criterion_id": "DONE_01",
                    "check_type": "json_schema_valid",
                    "target": f"{p}/storyboard.json::schemas/storyboard.schema.json",
                    "description": "Storyboard validates against storyboard.schema.json.",
                },
                {"criterion_id": "DONE_02", "check_type": "file_exists_nonempty", "target": f"{p}/semantic_visual_plan.json", "description": "Semantic visual plan JSON exists."},
            ],
            required_evidence=[f"Integer-frame storyboard & clause plan for TASK-07-STORYBOARD ({p}/storyboard.json)"],
        )
        t08 = _mk_task(
            task_id="TASK-08-REF-ADAPT",
            project_id=project_id,
            assigned_agent="rea_video_reference_analyst",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile 10-dimension reference fusion and 14-field shot-bound reference adaptation plan for {project_id}.",
            dependencies=["TASK-02-REFERENCE", "TASK-06-STYLE", "TASK-07-STORYBOARD"],
            input_artifacts=[f"{p}/reference_analysis.md", f"{p}/style_bible.json", f"{p}/storyboard.json"],
            owned_artifacts=[f"{p}/reference_adaptation.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/reference_adaptation.json", "description": "Shot-bound reference adaptation JSON exists."},
            ],
            required_evidence=[f"10D fusion & 14-field adaptations for TASK-08-REF-ADAPT ({p}/reference_adaptation.json)"],
        )
        t09 = _mk_task(
            task_id="TASK-09-MOTION",
            project_id=project_id,
            assigned_agent="motion_director",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile 14-field character and mechanism action plan with IK/contact targets for {project_id}.",
            dependencies=["TASK-05-CHARACTER", "TASK-07-STORYBOARD"],
            input_artifacts=[f"{p}/character_bible.json", f"{p}/storyboard.json"],
            owned_artifacts=[f"{p}/motion_plan.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/motion_plan.json", "description": "Motion plan JSON exists."},
            ],
            required_evidence=[f"14-field IK motion plan for TASK-09-MOTION ({p}/motion_plan.json)"],
        )
        t10 = _mk_task(
            task_id="TASK-10-CAMERA",
            project_id=project_id,
            assigned_agent="cinematographer",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile purpose-driven dynamic focal-length camera plan across shots for {project_id}.",
            dependencies=["TASK-06-STYLE", "TASK-07-STORYBOARD"],
            input_artifacts=[f"{p}/style_bible.json", f"{p}/storyboard.json"],
            owned_artifacts=[f"{p}/camera_plan.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/camera_plan.json", "description": "Camera plan JSON exists."},
            ],
            required_evidence=[f"Dynamic lens camera plan for TASK-10-CAMERA ({p}/camera_plan.json)"],
        )
        t11 = _mk_task(
            task_id="TASK-11-ASSET",
            project_id=project_id,
            assigned_agent="asset_specialist",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile 12-field semantic asset specifications derived from storyboard shots for {project_id}.",
            dependencies=["TASK-05-CHARACTER", "TASK-06-STYLE", "TASK-07-STORYBOARD"],
            input_artifacts=[f"{p}/character_bible.json", f"{p}/style_bible.json", f"{p}/storyboard.json"],
            owned_artifacts=[f"{p}/asset_manifest.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/asset_manifest.json", "description": "Semantic asset manifest JSON exists."},
            ],
            required_evidence=[f"12-field semantic asset manifest for TASK-11-ASSET ({p}/asset_manifest.json)"],
        )
        t12 = _mk_task(
            task_id="TASK-12-AUDIO",
            project_id=project_id,
            assigned_agent="audio_director",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile ESTIMATED narration timing, dialogue direction, music, ambience, foley, and SFX events for {project_id}.",
            dependencies=["TASK-04-SCRIPT", "TASK-07-STORYBOARD"],
            input_artifacts=[f"{p}/authored_creative_payload.json", f"{p}/storyboard.json"],
            owned_artifacts=[f"{p}/narration_dialogue.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/narration_dialogue.json", "description": "Audio narration & dialogue plan JSON exists."},
            ],
            required_evidence=[f"ESTIMATED audio & narration plan for TASK-12-AUDIO ({p}/narration_dialogue.json)"],
        )
        t13 = _mk_task(
            task_id="TASK-13-CAPTION",
            project_id=project_id,
            assigned_agent="caption_specialist",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile ESTIMATED phrase-grouped captions, safe-area specs, keyword highlights, and scientific labels for {project_id}.",
            dependencies=["TASK-06-STYLE", "TASK-07-STORYBOARD", "TASK-12-AUDIO"],
            input_artifacts=[f"{p}/style_bible.json", f"{p}/storyboard.json", f"{p}/narration_dialogue.json"],
            owned_artifacts=[f"{p}/caption_audio_plan.json"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {"criterion_id": "DONE_01", "check_type": "file_exists_nonempty", "target": f"{p}/caption_audio_plan.json", "description": "Caption & audio mastering plan JSON exists."},
            ],
            required_evidence=[f"ESTIMATED caption & scientific label plan for TASK-13-CAPTION ({p}/caption_audio_plan.json)"],
        )
        t14 = _mk_task(
            task_id="TASK-14-ENGINE",
            project_id=project_id,
            assigned_agent="remotion_specialist",
            project_state="STORYBOARDING",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Compile hybrid engine routing and post-approval execution plan for {project_id}.",
            dependencies=["TASK-06-STYLE", "TASK-07-STORYBOARD", "TASK-10-CAMERA", "TASK-11-ASSET"],
            input_artifacts=[f"{p}/style_bible.json", f"{p}/storyboard.json", f"{p}/camera_plan.json", f"{p}/asset_manifest.json"],
            owned_artifacts=[f"{p}/engine_plan.json", f"{p}/execution_plan.md"],
            allowed_tools=["view_file", "write_to_file"],
            done_when=[
                {
                    "criterion_id": "DONE_01",
                    "check_type": "json_schema_valid",
                    "target": f"{p}/engine_plan.json::schemas/engine_plan.schema.json",
                    "description": "Engine routing plan validates against engine_plan.schema.json.",
                },
                {"criterion_id": "DONE_02", "check_type": "file_exists_nonempty", "target": f"{p}/execution_plan.md", "description": "Execution plan markdown exists."},
            ],
            required_evidence=[f"Validated hybrid engine routing for TASK-14-ENGINE ({p}/engine_plan.json)"],
        )
        t15 = _mk_task(
            task_id="TASK-15-VERIFY",
            project_id=project_id,
            assigned_agent="preproduction_verifier",
            project_state="PREPRODUCTION_QC",
            genres=genres,
            ref_ids=reference_ids,
            goal=f"Audit all 15 mandatory preproduction criteria in fresh read-only context for {project_id}.",
            dependencies=producer_ids,
            input_artifacts=[
                f"{p}/research_report.json",
                f"{p}/reference_analysis.md",
                f"{p}/blueprint.md",
                f"{p}/script.md",
                f"{p}/authored_creative_payload.json",
                f"{p}/character_bible.json",
                f"{p}/style_bible.json",
                f"{p}/storyboard.json",
                f"{p}/semantic_visual_plan.json",
                f"{p}/reference_adaptation.json",
                f"{p}/motion_plan.json",
                f"{p}/camera_plan.json",
                f"{p}/asset_manifest.json",
                f"{p}/narration_dialogue.json",
                f"{p}/caption_audio_plan.json",
                f"{p}/engine_plan.json",
                f"{p}/execution_plan.md",
            ],
            owned_artifacts=[],
            allowed_tools=["view_file", "lookup_skill"],
            done_when=[
                {
                    "criterion_id": "DONE_01",
                    "check_type": "independent_review_verdict",
                    "target": "TASK-07-STORYBOARD",
                    "description": "Independent 15-criterion preproduction verification returns PASS.",
                }
            ],
            required_evidence=[f"15-criterion read-only review verdict for TASK-15-VERIFY ({p}/storyboard.json)"],
            extra_context={
                "criteria_manifest": criteria_manifest.to_dict(),
                "required_criteria_ids": criteria_manifest.required_criteria_ids,
                "additional_reviewed_task_ids": [tid for tid in producer_ids if tid != "TASK-07-STORYBOARD"],
            },
        )
        t15["expected_output"] = {
            "summary": f"15-criterion independent preproduction review report for {project_id}.",
            "output_artifacts": [],
            "output_format": "json",
        }
        return [t01, t02, t03, t04, t05, t06, t07, t08, t09, t10, t11, t12, t13, t14, t15]

    def run_workflow(
        self,
        *,
        project_id: str,
        topic: str,
        genres: list[str],
        target_duration_s: int,
        authored_payload: dict[str, Any] | None,
        explicit_reference_ids: list[str] | None = None,
        disable_reference: bool = False,
        package_version: str = "v1",
        execution_mode: str = "sequential_fallback_honest",
        host_subagent_receipts: dict[str, dict[str, Any]] | None = None,
        transcript_path: Path | None = None,
        external_verifier_report: dict[str, Any] | None = None,
        inject_revision_defect_once: Callable[[Path], None] | None = None,
    ) -> dict[str, Any]:
        """Run the full 15-task multi-agent preproduction DAG, shared memory sync, and 13-item sealing."""
        if execution_mode not in {
            "native_subagent",
            "recorded_workflow_replay",
            "sequential_fallback_honest",
            "mock_execution",
            "dispatch_plan_only_not_invoked",
        }:
            raise ValueError(f"Unsupported workflow execution_mode: {execution_mode}")

        self.presets.load_all(validate=True)
        proj_dir = self.root_dir / "projects" / project_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        v4_state_path = proj_dir / "project_state_v4.json"
        sm = SharedProjectStateMachine(v4_state_path)
        norm_genres = normalize_genre_list(genres) or ["explainer"]
        sm.initialize(project_id=project_id, project_title=topic, genres=norm_genres)

        sm.transition(
            "REQUEST_RECEIVED",
            expected_version=sm.load()["state_version"],
            trigger="BUAT_VIDEO",
            actor="master_director",
            evidence=f"Accepted preproduction request topic={topic!r} ({target_duration_s}s, {norm_genres})",
        )

        if authored_payload is None:
            sm.transition(
                "CREATIVE_PAYLOAD_REQUIRED",
                expected_version=sm.load()["state_version"],
                trigger="missing_creative_payload",
                actor="master_director",
                evidence="No authored creative payload available; refusing unrelated showcase fallback.",
            )
            raise CreativePayloadRequiredError(project_id, topic, state_file=v4_state_path)

        # Resolve reference lifecycle & 8-part cache
        lifecycle_ctx = self.ref_lifecycle.resolve_lifecycle_context(
            genres=genres,
            explicit_reference_ids=explicit_reference_ids,
            disable_reference=disable_reference,
            run_live_reanalysis_on_miss=False,
        )
        selected_refs = list(lifecycle_ctx["selected_reference_ids"])
        resolved_records = list(lifecycle_ctx["records"])

        if disable_reference or (explicit_reference_ids is not None and len(explicit_reference_ids) == 0):
            ref_context = {
                "schema_version": "4.0.0-phase01.6c",
                "database_integrated": True,
                "selection_mode": "genre_without_specific_reference",
                "normalized_genres": norm_genres,
                "selected_reference_ids": [],
                "related_candidate_ids": [],
                "upload_prompt_suppressed": False,
                "production_authorized": False,
                "analyzer_fingerprint": self.ref_lifecycle.bridge._db_mod.analyzer_fingerprint(
                    self.ref_lifecycle.bridge.db_root.parent
                ),
                "references": [],
                "fused_production_profile": None,
                "reference_analysis_markdown": (
                    f"# Analisis Referensi Pra-Produksi — {topic}\n\n"
                    "- **Mode Pemilihan**: `genre_without_specific_reference`\n"
                    "- **Keputusan Artistik**: Genre dijalankan dengan Global Style Bible otonom tanpa memaksakan `REF-001` / `REF-002`.\n"
                    "- **Status Otorisasi Produksi**: `False`\n"
                ),
            }
        else:
            ref_context = self.ref_bridge.resolve_context(
                genres=genres,
                explicit_reference_ids=selected_refs or None,
            )

        # Seal Master Director's immutable 15-criterion manifest BEFORE building/running the verifier!
        reviews_dir = proj_dir / ".reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        producer_ids = [
            "TASK-01-RESEARCH",
            "TASK-02-REFERENCE",
            "TASK-03-CREATIVE",
            "TASK-04-SCRIPT",
            "TASK-05-CHARACTER",
            "TASK-06-STYLE",
            "TASK-07-STORYBOARD",
            "TASK-08-REF-ADAPT",
            "TASK-09-MOTION",
            "TASK-10-CAMERA",
            "TASK-11-ASSET",
            "TASK-12-AUDIO",
            "TASK-13-CAPTION",
            "TASK-14-ENGINE",
        ]
        criteria_manifest = build_mandatory_15_criteria_manifest(
            project_id=project_id,
            producer_task_id="TASK-07-STORYBOARD",
            reviewer_task_id="TASK-15-VERIFY",
            additional_reviewed_task_ids=[tid for tid in producer_ids if tid != "TASK-07-STORYBOARD"],
        )
        manifest_path = reviews_dir / "criteria_manifest_TASK-15-VERIFY.json"
        atomic_write_bytes(
            manifest_path,
            (json.dumps(criteria_manifest.to_dict(), indent=2) + "\n").encode("utf-8"),
        )

        handoffs = self.build_15_task_dag(
            project_id=project_id,
            genres=norm_genres,
            reference_ids=selected_refs,
            criteria_manifest=criteria_manifest,
        )

        if execution_mode == "dispatch_plan_only_not_invoked":
            plans = [self.adapter.emit_host_dispatch_plan_only(h).to_dict() for h in handoffs]
            return {
                "status": "DISPATCH_PLAN_ONLY",
                "project_id": project_id,
                "execution_mode": execution_mode,
                "criteria_manifest": criteria_manifest.to_dict(),
                "dispatch_plans": plans,
            }

        # Prepare working payload copy with exact project_id, topic, genres, duration, and references
        work_payload = copy.deepcopy(authored_payload)
        work_payload["project_id"] = project_id
        work_payload["topic_title"] = topic.strip()
        work_payload["genres"] = norm_genres
        work_payload["target_duration_s"] = int(target_duration_s)
        if selected_refs:
            work_payload["reference_ids"] = list(selected_refs)
        else:
            work_payload.pop("reference_ids", None)

        blend = self.master_prompt.blend_genres(norm_genres, reference_context=ref_context)
        timing_report = self.timing_engine.evaluate_and_adapt_payload_timing(
            work_payload, base_wpm=blend["target_wpm"]
        )

        # Shared intermediate state across specialist tasks
        compiled_cache: dict[str, Any] = {}
        defect_injected = False

        sm.transition(
            "RESEARCHING",
            expected_version=sm.load()["state_version"],
            trigger="dispatch_wave_1",
            actor="master_director",
            task_id="TASK-01-RESEARCH",
            evidence="Dispatched Topic Research & REA Reference specialists",
        )

        def _assemble_master_director_package_manifests() -> tuple[str, dict[str, str], dict[str, Any]]:
            """Master Director assembles production_config.json + approval_package_manifest.json before verify."""
            topic_obj = compiled_cache["topic_obj"]
            creative_metrics = compiled_cache["creative_metrics"]
            style_bible = compiled_cache["style_bible"]
            fusion_plan = compiled_cache["fusion_plan"]
            adaptation_records = compiled_cache["adaptation_records"]
            storyboard = compiled_cache["storyboard"]
            research_report_v4 = compiled_cache["research_report_v4"]
            narration_plan = compiled_cache["narration_plan"]
            camera_plan = compiled_cache["camera_plan"]
            asset_manifest = compiled_cache["asset_manifest"]
            chars_v4 = compiled_cache["chars_v4"]
            motion_plan = compiled_cache["motion_plan"]
            caption_audio_plan = compiled_cache["caption_audio_plan"]
            engine_plan = compiled_cache["engine_plan"]

            prod_config = {
                "schema_version": "4.0.0-phase01.6c",
                "project_id": project_id,
                "package_version": package_version,
                "topic": topic_obj,
                "style_profile": style_bible["style_profile"],
                "style_bible_id": style_bible["style_bible_id"],
                "creative_validation_metrics": creative_metrics,
                "narration_timing_summary": {
                    "timing_status": timing_report["timing_status"],
                    "estimated_duration_s": timing_report["final_estimated_duration_s"],
                    "implied_wpm": timing_report["implied_script_wpm"],
                    "duration_recommendation": timing_report["duration_recommendation"],
                },
                "reference_intelligence": {
                    "selection_mode": ref_context["selection_mode"],
                    "selected_reference_ids": selected_refs,
                    "related_candidate_ids": ref_context["related_candidate_ids"],
                    "upload_prompt_suppressed": ref_context["upload_prompt_suppressed"],
                    "production_authorized": False,
                    "analyzer_fingerprint": ref_context["analyzer_fingerprint"],
                    "cache_reports": lifecycle_ctx["cache_reports"],
                    "references": ref_context["references"],
                    "fused_production_profile": ref_context["fused_production_profile"],
                    "ten_dimension_fusion": fusion_plan,
                    "adaptation_record_count": len(adaptation_records),
                },
                "fps": storyboard["fps"],
                "width": storyboard["width"],
                "height": storyboard["height"],
                "aspect_ratio": storyboard["aspect_ratio"],
                "total_frames": storyboard["total_frames"],
            }
            atomic_write_bytes(
                proj_dir / "production_config.json",
                (json.dumps(prod_config, indent=2) + "\n").encode("utf-8"),
            )
            digest, file_hashes = compute_package_digest(proj_dir)
            approval_manifest = {
                "schema_version": "4.0.0-phase01.6c",
                "project_id": project_id,
                "package_version": package_version,
                "status": "WAITING_APPROVAL",
                "package_digest": digest,
                "mandatory_13_items": {
                    "01_topic_and_concept": {"present": True, "artifact_file": "blueprint.md", "summary": f"{work_payload['topic_title']} ({', '.join(norm_genres)})"},
                    "02_research_results": {"present": True, "artifact_file": "research.md", "summary": f"{len(research_report_v4['verified_factual_claims'])} klaim terverifikasi + pemetaan narasi"},
                    "03_full_script": {"present": True, "artifact_file": "script.md", "summary": f"{len(work_payload['narrative_beats'])} beat naskah Bahasa Indonesia siap baca"},
                    "04_narration_and_dialogue": {"present": True, "artifact_file": "narration_dialogue.json", "summary": f"{len(narration_plan['vo_segments'])} VO & {len(narration_plan['dialogue_lines'])} dialog ({narration_plan['measured_script_wpm']} WPM, ESTIMATED)"},
                    "05_clip_by_clip_storyboard": {"present": True, "artifact_file": "storyboard.json", "summary": f"{len(storyboard['sequences'])} seq / {len(storyboard['scenes'])} scene / {len(storyboard['narrative_beats'])} beat / {len(storyboard['shots'])} shot"},
                    "06_shot_timestamps_and_durations": {"present": True, "artifact_file": "storyboard.json", "summary": f"{storyboard['total_frames']} frame ({storyboard['duration_s']}s @ {storyboard['fps']}fps, semua shot <= 10s)"},
                    "07_camera_framing_cutaway_transitions": {"present": True, "artifact_file": "camera_plan.json", "summary": f"Lensa dinamis {camera_plan['distinct_focal_lengths_mm']}mm sesuai tujuan naratif"},
                    "08_complete_asset_list": {"present": True, "artifact_file": "asset_manifest.json", "summary": f"{len(asset_manifest['semantic_asset_specs'])} spesifikasi aset semantik 12-atribut"},
                    "09_character_designs": {"present": True, "artifact_file": "character_bible.json", "summary": f"{len(chars_v4)} karakter orisinal 11-atribut ({style_bible['style_profile']})"},
                    "10_motion_plan": {"present": True, "artifact_file": "motion_plan.json", "summary": f"{len(motion_plan['planned_actions'])} rencana aksi 14-atribut dengan kontak IK"},
                    "11_caption_and_audio_plan": {"present": True, "artifact_file": "caption_audio_plan.json", "summary": f"{len(caption_audio_plan['cues'])} cue takarir ESTIMATED & label ilmiah"},
                    "12_engine_selection_per_shot": {"present": True, "artifact_file": "engine_plan.json", "summary": f"Routing hybrid ({', '.join(engine_plan['engines_used'])})"},
                    "13_hybrid_execution_plan": {"present": True, "artifact_file": "execution_plan.md", "summary": "Rencana eksekusi pasca-persetujuan Blender MCP, Three.js, Remotion & FFmpeg"},
                },
                "required_files_sha256": file_hashes,
            }
            atomic_write_bytes(
                proj_dir / "approval_package_manifest.json",
                (json.dumps(approval_manifest, indent=2) + "\n").encode("utf-8"),
            )
            return digest, file_hashes, approval_manifest

        def _execute_specialist_body(h: dict[str, Any], _root: Path) -> dict[str, Any]:
            nonlocal defect_injected
            tid = h["task_id"]

            if tid == "TASK-01-RESEARCH":
                topic_obj, _ = self.research_v34.validate_and_compile_research(work_payload)
                rep_v4, res_md = self.research_v4.compile_research_dossier(work_payload)
                compiled_cache["topic_obj"] = topic_obj
                compiled_cache["research_report_v4"] = rep_v4
                atomic_write_bytes(proj_dir / "research.md", (res_md + "\n").encode("utf-8"))
                atomic_write_bytes(proj_dir / "research_report.json", (json.dumps(rep_v4, indent=2) + "\n").encode("utf-8"))
                if self.memory_store is not None:
                    self.memory_store.knowledge.put_versioned(
                        entry_id=f"research_evidence:{project_id}",
                        version_tag=package_version,
                        category="topic_research_evidence",
                        payload=rep_v4,
                    )
                return {"evidence_items": [f"Completed {tid} -> research_report.json ({len(rep_v4['verified_factual_claims'])} claims)"]}

            if tid == "TASK-02-REFERENCE":
                atomic_write_bytes(
                    proj_dir / "reference_analysis.md",
                    ref_context["reference_analysis_markdown"].encode("utf-8"),
                )
                return {"evidence_items": [f"Completed {tid} -> reference_analysis.md (refs={selected_refs})"]}

            if tid == "TASK-03-CREATIVE":
                bp_md, _ = self.story_engine.compile_blueprint_and_script_markdown(work_payload, genre_blend=blend)
                concept_doc = {
                    "schema_version": "4.0.0-phase01.6c",
                    "project_id": project_id,
                    "topic_title": work_payload["topic_title"],
                    "genres": norm_genres,
                    "blueprint": work_payload["blueprint"],
                }
                compiled_cache["blueprint_md"] = bp_md
                atomic_write_bytes(proj_dir / "blueprint.md", (bp_md + "\n").encode("utf-8"))
                atomic_write_bytes(proj_dir / "creative_concept.json", (json.dumps(concept_doc, indent=2) + "\n").encode("utf-8"))
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(project_id, "creative_decisions", concept_doc)
                return {"evidence_items": [f"Completed {tid} -> blueprint.md & creative_concept.json"]}

            if tid == "TASK-04-SCRIPT":
                c_metrics = self.payload_validator.validate(work_payload)
                _, script_md = self.story_engine.compile_blueprint_and_script_markdown(work_payload, genre_blend=blend)
                compiled_cache["creative_metrics"] = c_metrics
                atomic_write_bytes(proj_dir / "script.md", (script_md + "\n").encode("utf-8"))
                atomic_write_bytes(
                    proj_dir / "authored_creative_payload.json",
                    (json.dumps(work_payload, indent=2) + "\n").encode("utf-8"),
                )
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(
                        project_id,
                        "script_version",
                        {"version": package_version, "metrics": c_metrics, "beat_count": len(work_payload["narrative_beats"])},
                    )
                return {"evidence_items": [f"Completed {tid} -> authored_creative_payload.json ({c_metrics['spoken_word_count']} words)"]}

            if tid == "TASK-05-CHARACTER":
                tmp_style = self.char_style.compile_style_bible(work_payload, reference_ids=selected_refs)
                tmp_sb = self.storyboard_dir.compile_hierarchical_storyboard(work_payload, genre_blend=blend)
                cb_json, chars_v4, cb_md = self.char_style.compile_character_bible_v4(
                    work_payload, style_bible=tmp_style, storyboard=tmp_sb
                )
                compiled_cache["char_bible_json"] = cb_json
                compiled_cache["chars_v4"] = chars_v4
                atomic_write_bytes(proj_dir / "character_bible.md", (cb_md + "\n").encode("utf-8"))
                atomic_write_bytes(proj_dir / "character_bible.json", (json.dumps(cb_json, indent=2) + "\n").encode("utf-8"))
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(project_id, "character_bible", cb_json)
                return {"evidence_items": [f"Completed {tid} -> character_bible.json ({len(chars_v4)} characters)"]}

            if tid == "TASK-06-STYLE":
                style_bible = self.char_style.compile_style_bible(work_payload, reference_ids=selected_refs)
                compiled_cache["style_bible"] = style_bible
                atomic_write_bytes(proj_dir / "style_bible.json", (json.dumps(style_bible, indent=2) + "\n").encode("utf-8"))
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(project_id, "style_bible", style_bible)
                    self.memory_store.production.record_tested_technique(
                        technique_id=f"style:{style_bible['style_bible_id']}",
                        version_tag="v4.0",
                        domain="style_profile",
                        test_status="INTEGRATION_TESTED",
                        payload=style_bible,
                    )
                return {"evidence_items": [f"Completed {tid} -> style_bible.json ({style_bible['style_profile']})"]}

            if tid == "TASK-07-STORYBOARD":
                style_bible = compiled_cache["style_bible"]
                sb = self.storyboard_dir.compile_hierarchical_storyboard(work_payload, genre_blend=blend)
                sb["style_bible_id"] = style_bible["style_bible_id"]
                sem_plan = self.semantic_visual.build_clause_to_shot_plan(
                    payload=work_payload, storyboard=sb, timing_report=timing_report
                )
                # Pre-apply purpose-driven camera lenses onto storyboard shots so storyboard.json & camera_plan.json match identically withoutTASK-10 mutating storyboard.json!
                cam_plan_preview = self.cam_aud_cap.build_camera_plan(sb, style_bible)
                compiled_cache["storyboard"] = sb
                compiled_cache["semantic_visual_plan"] = sem_plan
                compiled_cache["camera_plan_preview"] = cam_plan_preview
                atomic_write_bytes(proj_dir / "storyboard.json", (json.dumps(sb, indent=2) + "\n").encode("utf-8"))
                atomic_write_bytes(
                    proj_dir / "semantic_visual_plan.json",
                    (json.dumps(sem_plan, indent=2) + "\n").encode("utf-8"),
                )
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(
                        project_id,
                        "shot_plan",
                        {
                            "shot_count": len(sb["shots"]),
                            "total_frames": sb["total_frames"],
                            "clause_coverage_ratio": sem_plan["clause_coverage_ratio"],
                            "visual_purposes_used": sem_plan["visual_purposes_used"],
                        },
                    )
                return {"evidence_items": [f"Completed {tid} -> storyboard.json ({len(sb['shots'])} shots, {sem_plan['total_clauses']} clauses)"]}

            if tid == "TASK-08-REF-ADAPT":
                style_bible = compiled_cache["style_bible"]
                sb = compiled_cache["storyboard"]
                fusion_plan = self.fusion_engine.fuse(
                    resolved_records,
                    genres=norm_genres,
                    chosen_style_profile=style_bible["style_profile"],
                )
                ad_recs = self.ref_adapter.build_adaptation_records(
                    storyboard=sb,
                    records=resolved_records,
                    fusion_plan=fusion_plan,
                    genres=norm_genres,
                )
                ref_adapt_doc = {
                    "schema_version": "4.0.0-phase01.6c",
                    "project_id": project_id,
                    "selection_mode": ref_context["selection_mode"],
                    "selected_reference_ids": selected_refs,
                    "multi_reference_fusion": fusion_plan,
                    "adaptation_records": ad_recs,
                    "production_authorized": False,
                }
                compiled_cache["fusion_plan"] = fusion_plan
                compiled_cache["adaptation_records"] = ad_recs
                atomic_write_bytes(
                    proj_dir / "reference_adaptation.json",
                    (json.dumps(ref_adapt_doc, indent=2) + "\n").encode("utf-8"),
                )
                if self.memory_store is not None:
                    self.memory_store.project.put_slot(project_id, "reference_adaptation", ref_adapt_doc)
                return {"evidence_items": [f"Completed {tid} -> reference_adaptation.json ({len(ad_recs)} shot adaptations)"]}

            if tid == "TASK-09-MOTION":
                m_plan = self.action_planner.build_action_plan(
                    storyboard=compiled_cache["storyboard"],
                    characters=compiled_cache["chars_v4"],
                )
                compiled_cache["motion_plan"] = m_plan
                atomic_write_bytes(proj_dir / "motion_plan.json", (json.dumps(m_plan, indent=2) + "\n").encode("utf-8"))
                return {"evidence_items": [f"Completed {tid} -> motion_plan.json ({len(m_plan['planned_actions'])} actions)"]}

            if tid == "TASK-10-CAMERA":
                cam_plan = compiled_cache["camera_plan_preview"]
                compiled_cache["camera_plan"] = cam_plan
                atomic_write_bytes(proj_dir / "camera_plan.json", (json.dumps(cam_plan, indent=2) + "\n").encode("utf-8"))
                return {"evidence_items": [f"Completed {tid} -> camera_plan.json (lenses={cam_plan['distinct_focal_lengths_mm']}mm)"]}

            if tid == "TASK-11-ASSET":
                a_man = self.asset_planner.build_semantic_asset_manifest(
                    project_id=project_id,
                    storyboard=compiled_cache["storyboard"],
                    style_bible=compiled_cache["style_bible"],
                    characters=compiled_cache["chars_v4"],
                )
                compiled_cache["asset_manifest"] = a_man
                atomic_write_bytes(proj_dir / "asset_manifest.json", (json.dumps(a_man, indent=2) + "\n").encode("utf-8"))
                return {"evidence_items": [f"Completed {tid} -> asset_manifest.json ({len(a_man['semantic_asset_specs'])} specs)"]}

            if tid == "TASK-12-AUDIO":
                nar_plan, cap_plan = self.cam_aud_cap.build_audio_and_caption_plans(
                    payload=work_payload,
                    storyboard=compiled_cache["storyboard"],
                    style_bible=compiled_cache["style_bible"],
                    timing_report=timing_report,
                    caption_preset_id=blend["default_caption_preset"],
                    typography_preset_id=blend["default_typography_preset"],
                )
                compiled_cache["narration_plan"] = nar_plan
                compiled_cache["caption_audio_plan_preview"] = cap_plan
                atomic_write_bytes(
                    proj_dir / "narration_dialogue.json",
                    (json.dumps(nar_plan, indent=2) + "\n").encode("utf-8"),
                )
                return {"evidence_items": [f"Completed {tid} -> narration_dialogue.json ({nar_plan['measured_script_wpm']} WPM ESTIMATED)"]}

            if tid == "TASK-13-CAPTION":
                cap_plan = compiled_cache["caption_audio_plan_preview"]
                compiled_cache["caption_audio_plan"] = cap_plan
                atomic_write_bytes(
                    proj_dir / "caption_audio_plan.json",
                    (json.dumps(cap_plan, indent=2) + "\n").encode("utf-8"),
                )
                if inject_revision_defect_once is not None and not defect_injected:
                    defect_injected = True
                    inject_revision_defect_once(proj_dir)
                return {"evidence_items": [f"Completed {tid} -> caption_audio_plan.json ({len(cap_plan['cues'])} ESTIMATED cues)"]}

            if tid == "TASK-14-ENGINE":
                eng_plan, exec_md = self.hybrid_orch.build_engine_plan(compiled_cache["storyboard"])
                compiled_cache["engine_plan"] = eng_plan
                atomic_write_bytes(proj_dir / "engine_plan.json", (json.dumps(eng_plan, indent=2) + "\n").encode("utf-8"))
                atomic_write_bytes(proj_dir / "execution_plan.md", (exec_md + "\n").encode("utf-8"))
                return {"evidence_items": [f"Completed {tid} -> engine_plan.json ({eng_plan['engines_used']})"]}

            raise ValueError(f"Unexpected producer task '{tid}'")

        ckpt_dir = proj_dir / ".checkpoints"
        ckpt_mgr = CheckpointManager(
            ckpt_dir,
            root_dir=self.root_dir,
            handoff_manager=self.handoff_manager,
            memory_store=self.memory_store,
        )
        sched = TaskDependencyScheduler(
            root_dir=self.root_dir,
            max_parallel_specialists=self.max_parallel_specialists,
            handoff_manager=self.handoff_manager,
            execution_adapter=self.adapter,
            memory_store=self.memory_store,
            checkpoint_manager=ckpt_mgr,
            disallow_mock_execution=(execution_mode != "mock_execution"),
        )

        # Advance state transitions cleanly alongside waves
        sm.transition(
            "REFERENCE_ANALYSIS",
            expected_version=sm.load()["state_version"],
            trigger="wave_1_reference",
            actor="master_director",
            task_id="TASK-02-REFERENCE",
            evidence="Reference selection and cache validation active",
        )
        sm.transition(
            "CREATIVE_DEVELOPMENT",
            expected_version=sm.load()["state_version"],
            trigger="wave_2_creative",
            actor="master_director",
            task_id="TASK-03-CREATIVE",
            evidence="Blueprint, Indonesian script, Character Bible, and Global Style Bible development",
        )
        sm.transition(
            "STORYBOARDING",
            expected_version=sm.load()["state_version"],
            trigger="wave_5_storyboard",
            actor="master_director",
            task_id="TASK-07-STORYBOARD",
            evidence="Integer-frame storyboard, motion, camera, asset, audio, caption, and engine compilation",
        )

        receipts_cfg = host_subagent_receipts or {}

        async def _task_executor(h: dict[str, Any], _attempt: int) -> AgentExecutionResult:
            tid = h["task_id"]

            if tid == "TASK-15-VERIFY":
                # Master Director seals production_config.json & approval_package_manifest.json right before review
                _assemble_master_director_package_manifests()
                cur_st = sm.load()
                if cur_st["current_state"] != "PREPRODUCTION_QC":
                    sm.transition(
                        "PREPRODUCTION_QC",
                        expected_version=cur_st["state_version"],
                        trigger="enter_independent_preproduction_qc",
                        actor="master_director",
                        task_id=tid,
                        evidence=f"Invoking read-only preproduction_verifier against manifest {criteria_manifest.manifest_sha256[:12]}",
                    )

                # Snapshot all 14 producer tasks' owned artifacts before verifier runs
                by_tid_local = {x["task_id"]: x for x in handoffs}
                pre_hashes: dict[str, str] = {}
                art_man_for_review: dict[str, dict[str, Any]] = {}
                for ptid in producer_ids:
                    ph = by_tid_local[ptid]
                    for cp in self.handoff_manager.canonical_owned_paths(ph, base_dir=self.root_dir):
                        rel_p = cp.relative_to(self.root_dir).as_posix()
                        sha = compute_file_sha256(cp)
                        pre_hashes[rel_p] = sha
                        art_man_for_review[rel_p] = {
                            "owner_task_id": ptid,
                            "owner_agent": ph["assigned_agent"],
                            "sha256": sha,
                            "size_bytes": cp.stat().st_size,
                        }

                eval_res = external_verifier_report or self.verifier_engine.evaluate_package_readonly(
                    package_dir=proj_dir,
                    project_id=project_id,
                    criteria_manifest=criteria_manifest,
                )

                # Build verifier invocation receipt according to honest execution_mode
                req = self.adapter.build_invocation_request(h)
                started = utc_now_iso()
                completed = utc_now_iso()
                host_meta = receipts_cfg.get(tid) or {}

                if execution_mode == "native_subagent" and host_meta.get("conversation_id"):
                    base_res = self.adapter.record_host_subagent_completion(
                        handoff=h,
                        request=req,
                        conversation_id=host_meta["conversation_id"],
                        known_model_routing=host_meta.get("known_model_routing", "inherit"),
                        started_at=host_meta.get("started_at", started),
                        completed_at=host_meta.get("completed_at", completed),
                        payload={"verdict": eval_res["verdict"]},
                        evidence_items=[f"Completed {tid} read-only 15-criterion audit on storyboard.json"],
                        transcript_path=transcript_path,
                        host_invocation_evidence=host_meta.get("host_invocation_evidence"),
                        require_live_host_proof=True,
                    )
                elif execution_mode == "recorded_workflow_replay" and host_meta:
                    base_res = self.adapter.record_workflow_replay_completion(
                        handoff=h,
                        recorded_receipt=host_meta,
                        payload={"verdict": eval_res["verdict"]},
                        evidence_items=[f"Replayed {tid} read-only 15-criterion audit on storyboard.json"],
                    )
                elif execution_mode == "mock_execution":
                    base_res = self.adapter.execute_mock_worker(
                        handoff=h,
                        worker_fn=lambda _hd, _rt: {
                            "payload": {"verdict": eval_res["verdict"]},
                            "evidence_items": [f"Mock {tid} 15-criterion audit on storyboard.json"],
                        },
                    )
                else:
                    base_res = self.adapter.execute_sequential_fallback(
                        handoff=h,
                        worker_fn=lambda _hd, _rt: {
                            "payload": {"verdict": eval_res["verdict"]},
                            "evidence_items": [f"Completed {tid} 15-criterion audit on storyboard.json"],
                        },
                    )

                post_hashes = {
                    rel_p: compute_file_sha256(self.root_dir / rel_p) for rel_p in pre_hashes
                }
                prod_conv = (receipts_cfg.get("TASK-07-STORYBOARD") or {}).get("conversation_id")
                rev_report = AgentReviewReport(
                    schema_version="4.0.0-phase01.6c",
                    review_id=f"REV-{project_id[:24]}-001",
                    project_id=project_id,
                    verifier_agent="preproduction_verifier",
                    reviewer_task_id=tid,
                    reviewed_task_id="TASK-07-STORYBOARD",
                    additional_reviewed_task_ids=[pt for pt in producer_ids if pt != "TASK-07-STORYBOARD"],
                    producer_agent="storyboard_director",
                    producer_conversation_id=prod_conv,
                    reviewer_conversation_id=base_res.receipt.conversation_id,
                    criteria_manifest_digest=criteria_manifest.manifest_sha256,
                    verdict=eval_res["verdict"],
                    invocation_receipt=base_res.receipt.to_review_receipt_dict(),
                    reviewed_artifact_hashes=pre_hashes,
                    pre_review_hashes=pre_hashes,
                    post_review_hashes=post_hashes,
                    reviewed_artifact_manifest=art_man_for_review,
                    required_criteria_ids=eval_res["required_criteria_ids"],
                    checked_criteria=eval_res["checked_criteria"],
                    defects=eval_res["defects"],
                )
                atomic_write_bytes(
                    reviews_dir / "independent_preproduction_review_v4.json",
                    (json.dumps(rev_report.to_dict(), indent=2) + "\n").encode("utf-8"),
                )
                if self.memory_store is not None:
                    self.memory_store.quality.record_evaluation(
                        project_id=project_id,
                        evaluation_id=f"{rev_report.review_id}:{_attempt}:{len(revisions_applied)}",
                        target_ref="approval_package_manifest.json",
                        review_status=eval_res["verdict"],
                        payload={
                            "verdict": eval_res["verdict"],
                            "checked_count": len(eval_res["checked_criteria"]),
                            "defect_count": len(eval_res["defects"]),
                            "criteria_manifest_digest": criteria_manifest.manifest_sha256,
                        },
                    )
                    if eval_res["defects"]:
                        for d_item in eval_res["defects"]:
                            self.memory_store.error.record_error(
                                project_id=project_id,
                                error_id=d_item["defect_id"],
                                task_id=tid,
                                error_category="PREPRODUCTION_REVIEW_DEFECT",
                                payload=d_item,
                            )

                return AgentExecutionResult(
                    task_id=base_res.task_id,
                    project_id=base_res.project_id,
                    status=base_res.status,
                    receipt=base_res.receipt,
                    payload=base_res.payload,
                    evidence_items=base_res.evidence_items,
                    criterion_evidence=base_res.criterion_evidence,
                    review_report=rev_report,
                )

            # Producer task execution across the 4 executable modes
            host_meta = receipts_cfg.get(tid) or {}
            if execution_mode == "native_subagent" and host_meta.get("conversation_id"):
                out = await asyncio.to_thread(_execute_specialist_body, h, self.root_dir)
                req = self.adapter.build_invocation_request(h)
                return self.adapter.record_host_subagent_completion(
                    handoff=h,
                    request=req,
                    conversation_id=host_meta["conversation_id"],
                    known_model_routing=host_meta.get("known_model_routing", "inherit"),
                    started_at=host_meta.get("started_at", utc_now_iso()),
                    completed_at=host_meta.get("completed_at", utc_now_iso()),
                    payload=out.get("payload", {}),
                    evidence_items=out["evidence_items"],
                    transcript_path=transcript_path,
                    host_invocation_evidence=host_meta.get("host_invocation_evidence"),
                    require_live_host_proof=True,
                )
            if execution_mode == "recorded_workflow_replay" and host_meta:
                out = await asyncio.to_thread(_execute_specialist_body, h, self.root_dir)
                # Bind output hashes if recording didn't pre-populate dynamic hashes
                rec_copy = dict(host_meta)
                rec_copy.pop("output_artifact_hashes", None)
                return self.adapter.record_workflow_replay_completion(
                    handoff=h,
                    recorded_receipt=rec_copy,
                    payload=out.get("payload", {}),
                    evidence_items=out["evidence_items"],
                )
            if execution_mode == "mock_execution":
                return await asyncio.to_thread(
                    lambda: self.adapter.execute_mock_worker(handoff=h, worker_fn=_execute_specialist_body)
                )
            return await asyncio.to_thread(
                lambda: self.adapter.execute_sequential_fallback(handoff=h, worker_fn=_execute_specialist_body)
            )

        dag_result = asyncio.run(
            sched.execute_dag(
                handoffs,
                executor=_task_executor,
                state_version=sm.load()["state_version"],
            )
        )

        revisions_applied: list[dict[str, Any]] = []
        # Handle revision cycle if verifier detected a defect on Run 1
        if dag_result["overall_status"] != "SUCCEEDED" and "TASK-15-VERIFY" in dag_result["failed_tasks"]:
            sm.transition(
                "REVISION_REQUIRED",
                expected_version=sm.load()["state_version"],
                trigger="verifier_revision_required",
                actor="preproduction_verifier",
                task_id="TASK-15-VERIFY",
                evidence="Independent verifier reported preproduction defect(s); triggering RevisionManager",
            )
            rev_mgr = RevisionManager(
                root_dir=self.root_dir,
                handoff_manager=self.handoff_manager,
                memory_store=self.memory_store,
            )
            # Re-author clean caption_audio_plan.json via RevisionManager (non-destructive archive to .revisions/)
            clean_cap_bytes = (json.dumps(compiled_cache["caption_audio_plan"], indent=2) + "\n").encode("utf-8")
            rev_entry = rev_mgr.apply_revision(
                project_id=project_id,
                artifact_relpath=f"projects/{project_id}/caption_audio_plan.json",
                new_content_bytes=clean_cap_bytes,
                task_owner="TASK-13-CAPTION",
                owner_agent="caption_specialist",
                reason="Restore ESTIMATED timestamp_status after verifier defect detection",
                task_definitions={h["task_id"]: h for h in handoffs},
            )
            revisions_applied.append(rev_entry)
            sm.transition(
                "STORYBOARDING",
                expected_version=sm.load()["state_version"],
                trigger=f"revision_reexecution:{rev_entry['revision_id']}",
                actor="master_director",
                task_id="TASK-13-CAPTION",
                evidence="Re-validating revised artifact and re-running independent verifier",
            )
            external_verifier_report = None
            resumed_state = ckpt_mgr.resume(expected_project_id=project_id, expected_handoffs=handoffs)
            resumed_state["failed_tasks"] = []
            resumed_state["pending_tasks"] = sorted(
                set(resumed_state["pending_tasks"]) | {"TASK-15-VERIFY"}
            )
            resumed_state["retry_budget"]["TASK-15-VERIFY"]["attempts_used"] = 0
            dag_result = asyncio.run(
                sched.execute_dag(
                    handoffs,
                    executor=_task_executor,
                    state_version=sm.load()["state_version"],
                    resume_state=resumed_state,
                )
            )

        if dag_result["overall_status"] != "SUCCEEDED":
            raise RuntimeError(
                f"Preproduction DAG failed for '{project_id}': failed={dag_result['failed_tasks']}, "
                f"blocked={dag_result['blocked_tasks']}, failures={dag_result['failures']}"
            )

        digest, file_hashes, approval_manifest = _assemble_master_director_package_manifests()

        # Sync legacy v3.4 project_state.json AND transition v4 SharedProjectStateMachine -> WAITING_APPROVAL
        v34_mgr = ProjectStateManager(proj_dir / "project_state.json")
        v34_mgr.initialize(
            project_id=project_id,
            project_title=work_payload["topic_title"],
            genres=norm_genres,
            total_frames=compiled_cache["storyboard"]["total_frames"],
        )
        v34_state = v34_mgr.mark_waiting_approval(digest, package_version=package_version)

        v4_final = sm.transition(
            "WAITING_APPROVAL",
            expected_version=sm.load()["state_version"],
            trigger="preproduction_verifier_pass",
            actor="master_director",
            task_id="TASK-15-VERIFY",
            evidence=f"All 15 independent review criteria PASSED; sealed 13-item package digest={digest[:16]}",
            artifact_manifest=file_hashes,
        )
        assert v4_final["current_state"] == "WAITING_APPROVAL"
        assert v4_final["approval_status"]["approved"] is False

        if self.memory_store is not None:
            self.memory_store.project.put_slot(project_id, "approval_package_manifest", approval_manifest)
            if revisions_applied:
                self.memory_store.project.put_slot(project_id, "revision_history", {"revisions": revisions_applied})

        portable_bundle_path = proj_dir / ".checkpoints" / "portable_checkpoint_bundle_v4.json"
        ckpt_mgr.export_portable_bundle(portable_bundle_path)

        review_doc = json.loads(
            (reviews_dir / "independent_preproduction_review_v4.json").read_text(encoding="utf-8")
        )
        return {
            "status": "WAITING_APPROVAL",
            "project_id": project_id,
            "project_dir": proj_dir.as_posix(),
            "execution_mode": execution_mode,
            "package_version": package_version,
            "package_digest": digest,
            "approval_command_example": format_structured_approval_command(
                project_id=project_id,
                package_version=package_version,
                package_digest=digest,
            ),
            "selected_reference_ids": selected_refs,
            "style_profile": compiled_cache["style_bible"]["style_profile"],
            "criteria_manifest": criteria_manifest.to_dict(),
            "independent_review_report": review_doc,
            "dag_execution": dag_result,
            "revisions_applied": revisions_applied,
            "project_state_v4": v4_final,
            "project_state_v3_4": v34_state,
            "approval_manifest": approval_manifest,
            "portable_checkpoint_bundle": portable_bundle_path.relative_to(self.root_dir).as_posix(),
            "rendering_or_blender_executed": False,
        }
