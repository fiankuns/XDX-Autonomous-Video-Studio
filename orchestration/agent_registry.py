"""XDX Studio v4.0 Agent Registry & 20 Specialist Role Contracts (Phase 01.6A).

Defines and schema-validates:
- `master_director` (00 — Orchestration)
- Creative Department (`01`..`07`)
- Production Department (`08`..`16`)
- Independent Verification Department (`17`..`20`)

Also validates every workspace `.agents/agents/*.md`, `.agents/skills/*/SKILL.md`,
and `.agents/rules/*.md` file against official Google Antigravity specifications.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"

OFFICIAL_ANTIGRAVITY_TOOLS: frozenset[str] = frozenset(
    {
        "view_file",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "list_dir",
        "find_by_name",
        "grep_search",
        "search_web",
        "read_url_content",
        "google_search",
        "run_command",
        "manage_task",
        "schedule",
        "list_permissions",
        "ask_permission",
        "invoke_subagent",
        "define_subagent",
        "send_message",
        "manage_subagents",
        "list_skills",
        "lookup_skill",
        "lookup_skills",
        "get_skill_resources",
        "ask_question",
        "generate_image",
    }
)

VALID_RULE_TRIGGERS: frozenset[str] = frozenset({"always_on", "model_decision", "glob", "manual"})
MAX_RULE_FILE_BYTES: int = 24_000


def _role(
    *,
    agent_id: str,
    agent_number: int,
    department: str,
    display_name: str,
    mission: str,
    read_only: bool,
    requires_fresh_context: bool,
    max_concurrent_instances: int,
    session_pref: str,
    subagent_arg: str,
    routing_rationale: str,
    allowed_tools: list[str],
    forbidden_actions: list[str],
    owned_artifact_patterns: list[str],
    linked_skills: list[str],
    linked_python_modules: list[str],
    custom_subagent_file: str,
    implementation_status: str,
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "agent_number": agent_number,
        "department": department,
        "display_name": display_name,
        "mission": mission,
        "read_only": read_only,
        "requires_fresh_context": requires_fresh_context,
        "can_self_approve": False,
        "max_concurrent_instances": max_concurrent_instances,
        "preferred_model_routing": {
            "session_orchestrator_preference": session_pref,
            "subagent_tool_model_arg": subagent_arg,
            "rationale": routing_rationale,
        },
        "allowed_tools": allowed_tools,
        "forbidden_actions": forbidden_actions,
        "owned_artifact_patterns": owned_artifact_patterns,
        "linked_skills": linked_skills,
        "linked_python_modules": linked_python_modules,
        "custom_subagent_file": custom_subagent_file,
        "implementation_status": implementation_status,
    }


def build_default_agent_registry_dict() -> dict[str, Any]:
    """Construct the canonical Master Director + 20 Specialist Role Contracts."""
    master = _role(
        agent_id="master_director",
        agent_number=0,
        department="orchestration",
        display_name="XDX Master Director",
        mission="Understand user intent, select mode/genre/references, schedule 3-6 active specialists via 18-field DAG handoffs, enforce human approval gate, and synthesize final reports.",
        read_only=False,
        requires_fresh_context=False,
        max_concurrent_instances=1,
        session_pref="Gemini 4 Neon (Orchestrator Planner)",
        subagent_arg="inherit",
        routing_rationale="Strong frontier reasoning required for multi-department decomposition, conflict resolution, and state governance.",
        allowed_tools=[
            "view_file",
            "write_to_file",
            "replace_file_content",
            "run_command",
            "manage_task",
            "invoke_subagent",
            "define_subagent",
            "send_message",
            "manage_subagents",
            "list_skills",
            "lookup_skill",
            "ask_question",
        ],
        forbidden_actions=[
            "Act as sole verifier of its own creative or production artifacts",
            "Transition project state directly to APPROVED or COMPLETED without verified gates",
            "Execute Blender scene mutations or rendering prior to verified human approval",
        ],
        owned_artifact_patterns=[
            "projects/*/project_state.json",
            "projects/*/production_config.json",
            "projects/*/approval_package_manifest.json",
        ],
        linked_skills=[".agents/skills/xdx-master-orchestration", "SKILL.md"],
        linked_python_modules=[
            "orchestration/agent_registry.py",
            "orchestration/handoff_manager.py",
            "orchestration/task_router.py",
            "intelligence/state_and_approval.py",
        ],
        custom_subagent_file=".agents/agents/xdx-master-director.md",
        implementation_status="RUNTIME_TESTED",
    )

    specialists: list[dict[str, Any]] = [
        # ---------------- CREATIVE DEPARTMENT (01-07) ----------------
        _role(
            agent_id="topic_research_agent",
            agent_number=1,
            department="creative_department",
            display_name="01. Topic Research Agent",
            mission="Discover compelling topics, formulate core questions, verify primary/institutional https:// sources, separate facts from misconceptions, and build an evidence ledger.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Neon / Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Requires careful epistemic discrimination and primary source verification.",
            allowed_tools=["view_file", "write_to_file", "google_search", "lookup_skill"],
            forbidden_actions=[
                "Fabricate URLs, publication years, statistics, or historical quotes",
                "Mark pending_external_verification as completed factual research",
            ],
            owned_artifact_patterns=["projects/*/research.md"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-topic-researcher.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="rea_video_reference_analyst",
            agent_number=2,
            department="creative_department",
            display_name="02. REA-Video Reference Analyst",
            mission="Verify Git LFS reference MP4 SHA-256 hashes, run REA-Video multimodal inspection, distinguish measured signals from visual observations/inferences, and emit Reference DNA manifests.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Hydrogen / Gemini 4 Neon",
            subagent_arg="inherit",
            routing_rationale="Combines deterministic ffprobe/OpenCV execution with multimodal frame review.",
            allowed_tools=["view_file", "write_to_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Ask user to re-upload verified reference_database/ MP4s",
                "Overwrite or delete prior_analysis.* files",
                "Claim FFmpeg/OpenCV heuristics alone constitute complete multimodal analysis",
            ],
            owned_artifact_patterns=["projects/*/reference_analysis.md"],
            linked_skills=["rea-video", ".agents/skills/xdx-reference-intelligence"],
            linked_python_modules=[
                "intelligence/rea_reference_intelligence.py",
                "intelligence/reference_database_bridge.py",
                "reference_database/scripts/reference_db.py",
            ],
            custom_subagent_file=".agents/agents/xdx-rea-reference-analyst.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="creative_director",
            agent_number=3,
            department="creative_department",
            display_name="03. Creative Director",
            mission="Define story concept, genre/subgenre blend, narrative arc, 0-3s hook, experiment/demonstration, escalation, reveal, payoff, callback, humor, and visual delivery strategy.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Neon",
            subagent_arg="inherit",
            routing_rationale="High-level dramatic structure and genre adaptation require deep creative reasoning.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Force a single rigid story formula onto unrelated genres",
                "Copy copyrighted plots, political names, or character identities from references",
            ],
            owned_artifact_patterns=["projects/*/blueprint.md"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-creative-scriptwriter.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="scriptwriter_agent",
            agent_number=4,
            department="creative_department",
            display_name="04. Scriptwriter Agent",
            mission="Author original, natural, broadcast-ready Indonesian narration and character dialogue across all supported genres without template placeholders or unrelated showcase fallbacks.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Neon",
            subagent_arg="inherit",
            routing_rationale="Natural spoken Indonesian cadence, situational humor, and lexical fidelity require strong authoring quality.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Emit bracketed beat placeholders ([HOOK_ANOMALY], TODO, TBD)",
                "Substitute time-perception or social-satire showcase scripts onto unrelated user topics",
            ],
            owned_artifact_patterns=["projects/*/script.md", "projects/*/authored_creative_payload.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-creative-scriptwriter.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="storyboard_director",
            agent_number=5,
            department="creative_department",
            display_name="05. Storyboard Director",
            mission="Compile script into integer-frame Story Arc -> Sequence -> Scene -> Narrative Beat -> Shot (2-6s typical, <=10s max) -> Action/Camera/Audio/Caption/VFX Events with concrete clause-aligned visuals.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen / Gemini 4 Neon",
            subagent_arg="inherit",
            routing_rationale="Structured hierarchical compilation paired with semantic clause-to-visual alignment.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Emit shots longer than 10.0s without explicit user-approved exception",
                "Leave unrecorded timeline gaps or unplanned frame overlaps",
            ],
            owned_artifact_patterns=["projects/*/storyboard.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-storyboard-cinematographer.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="character_design_agent",
            agent_number=6,
            department="creative_department",
            display_name="06. Character Design Agent",
            mission="Author Character Bibles for hero and supporting characters defining silhouette, proportions, face, hair, wardrobe, materials, palette, expressions, rig spec, and pose/motion traits.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Focused structured design specification with strict cross-shot continuity rules.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Alter character face, proportions, or wardrobe across shots without approved narrative reason",
                "Clone copyrighted character designs from REF-001 or REF-002",
            ],
            owned_artifact_patterns=["projects/*/character_bible.md"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-character-art-director.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="art_director",
            agent_number=7,
            department="creative_department",
            display_name="07. Art Director",
            mission="Govern Global Style Bible across 2D, flat cartoon, stylized 3D, diorama, anime-inspired, realistic, infographic, and mixed-media profiles ensuring uniform asset/character/environment quality.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Neon / Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Maintains holistic visual, material, color-space, and typographic cohesion.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Mix polished environments with crude prototype box props or mismatched shader styles",
                "Lock unrelated genres into desert palettes or rigid 3D cartoon defaults",
            ],
            owned_artifact_patterns=["projects/*/style_bible.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/asset_management.py", "intelligence/asset_style_converter.py"],
            custom_subagent_file=".agents/agents/xdx-character-art-director.md",
            implementation_status="UNIT_TESTED",
        ),
        # ---------------- PRODUCTION DEPARTMENT (08-16) ----------------
        _role(
            agent_id="asset_specialist",
            agent_number=8,
            department="production_department",
            display_name="08. Asset Specialist",
            mission="Execute the 9-stage asset pipeline (Registry -> Cache -> Audited Providers -> License/SSRF Check -> Download/Procedural glTF Generation -> Style Harmonization -> Asset QC -> Persistent Cache).",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Deterministic procurement, glTF/GLB buffer inspection, and license ledger enforcement.",
            allowed_tools=["view_file", "write_to_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Pass primitive 12-triangle PLACEHOLDER boxes as final production assets",
                "Bulk-download entire external asset repositories or accept UNLICENSED/copyleft-tainted assets",
            ],
            owned_artifact_patterns=["projects/*/asset_manifest.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=[
                "intelligence/asset_management.py",
                "intelligence/procedural_geometry.py",
                "intelligence/asset_style_converter.py",
            ],
            custom_subagent_file=".agents/agents/xdx-hybrid-production-engineer.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="blender_specialist",
            agent_number=9,
            department="production_department",
            display_name="09. Blender Specialist",
            mission="Compile and execute authorized Blender XDX scenes, armatures, IK, facial states, lighting, cameras, and renders while preserving mobile_guard and honest 6-tier MCP reporting.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Single-worker exclusive scene mutation discipline and AST-verified bpy compilation.",
            allowed_tools=["view_file", "write_to_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Mutate any Blender scene without verified APPROVED ExecutionAuthorizationContext",
                "Run more than 1 concurrent worker mutating the same Blender scene",
                "Modify fiankuns/xdx-blender-studio or write to /tmp instead of bpy.app.tempdir",
            ],
            owned_artifact_patterns=["projects/*/scenes/*.json"],
            linked_skills=["xdx-blender-vivo", ".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["adapters/xdx_mcp_adapter.py", "engines/blender_xdx_engine.py"],
            custom_subagent_file=".agents/agents/xdx-hybrid-production-engineer.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="threejs_specialist",
            agent_number=10,
            department="production_department",
            display_name="10. Three.js Specialist",
            mission="Build deterministic frame/fps Three.js v0.187 procedural 3D scenes, technical cutaways, scientific simulations, mechanism animations, particles, and WebGL frame renderers.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Fast deterministic WebGL/Three.js scene implementation with seeded PRNG and load barriers.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Use wall-clock requestAnimationFrame delta or unseeded Math.random() for production renders",
                "Start production frame rendering before human approval",
            ],
            owned_artifact_patterns=["projects/*/threejs/*.json"],
            linked_skills=["threejs", ".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["engines/web_engines.py", "engines/web/three_deterministic_scene.mjs"],
            custom_subagent_file=".agents/agents/xdx-hybrid-production-engineer.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="remotion_specialist",
            agent_number=11,
            department="production_department",
            display_name="11. Remotion Specialist",
            mission="Assemble the master deterministic Remotion v4.0.547 timeline, multi-layer compositing, motion graphics, transitions, safe-area captions, audio mixing, and FFmpeg handoff.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Master timeline assembly across Blender/Three.js sequences, captions, and audio tracks.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Replace Remotion master compositor without explicit user approval",
                "Import UNLICENSED caption packages or non-deterministic CSS animations",
            ],
            owned_artifact_patterns=["projects/*/engine_plan.json", "projects/*/execution_plan.md"],
            linked_skills=["web-app-development", ".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=[
                "engines/web_engines.py",
                "engines/web/remotion_timeline_spec.mjs",
                "engines/ffmpeg_engine.py",
            ],
            custom_subagent_file=".agents/agents/xdx-hybrid-production-engineer.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="motion_director",
            agent_number=12,
            department="production_department",
            display_name="12. Motion Director",
            mission="Translate storyboard actions into concrete body mechanics (anticipation, easing, follow-through, weight transfer, start/end/key poses, contact points, IK targets, facial & lip-sync cues).",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Detailed per-shot pose, contact, and IK planning backed by preset executors.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Reduce distinct physical actions to generic torso/hand rotation loops",
                "Claim live IK/curve retargeting is RENDER_TESTED when still SPECIFICATION_ONLY",
            ],
            owned_artifact_patterns=["projects/*/motion_plan.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py", "engines/preset_executors.py"],
            custom_subagent_file=".agents/agents/xdx-storyboard-cinematographer.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="cinematographer",
            agent_number=13,
            department="production_department",
            display_name="13. Cinematographer",
            mission="Design narrative-driven 36mm-sensor shot sizes, camera angles, lenses, DoF, dolly/pan/tilt/orbit/push-in trajectories, spatial continuity, and lighting direction.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Deterministic camera math and 180-degree spatial orientation continuity across cuts.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Add unmotivated camera motion that obscures technical cutaways or captions",
                "Break sensor/focal-length consistency between Blender and Three.js shots",
            ],
            owned_artifact_patterns=["projects/*/camera_plan.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py", "engines/preset_executors.py"],
            custom_subagent_file=".agents/agents/xdx-storyboard-cinematographer.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="vfx_specialist",
            agent_number=14,
            department="production_department",
            display_name="14. VFX Specialist",
            mission="Configure particles, dust, smoke, fog, rain, sparks, glow, atmosphere, and color-coded 3D airflow/thermal vectors without obstructing scene or caption readability.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Applies audited particle and ACESFilmic grading presets within mobile/cloud budgets.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Occlude lower-third safe-area captions or primary mechanism cutaways with dense particles",
                "Use non-seeded particle emitters that vary across re-renders",
            ],
            owned_artifact_patterns=["projects/*/vfx_plan.json"],
            linked_skills=["threejs", ".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["engines/preset_executors.py", "libraries/loader.py"],
            custom_subagent_file=".agents/agents/xdx-hybrid-production-engineer.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="audio_director",
            agent_number=15,
            department="production_department",
            display_name="15. Audio Director",
            mission="Plan narration voice settings, character dialogue delivery, ~130-160 WPM Indonesian pacing estimates pre-approval, BGM/ambience/foley/SFX cues, -15 LUFS mastering, and post-approval WAV alignment.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Deterministic speech duration estimation before approval and exact WAV sync post-approval.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Clone voices from reference videos without explicit authorization",
                "Trigger paid TTS synthesis before human approval (or separate preview approval)",
                "Time-compress speech unnaturally instead of revising overly long narration",
            ],
            owned_artifact_patterns=["projects/*/narration_dialogue.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["intelligence/creative_pipeline.py", "adapters/caption_lipsync_adapter.py"],
            custom_subagent_file=".agents/agents/xdx-audio-caption-specialist.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="caption_specialist",
            agent_number=16,
            department="production_department",
            display_name="16. Caption Specialist",
            mission="Generate classic bold, word-highlight, karaoke, phrase, kinetic, scientific-label, numeric-callout, and speaker-ID captions inside safe areas synced to verified audio/ASR timestamps.",
            read_only=False,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Hydrogen",
            subagent_arg="inherit",
            routing_rationale="Safe-area geometry enforcement and honest separation of pre-approval estimates vs ASR alignment.",
            allowed_tools=["view_file", "write_to_file", "replace_file_content", "lookup_skill"],
            forbidden_actions=[
                "Claim uniform word-duration estimates are verified forced-aligned ASR",
                "Place captions outside vertical 9:16 safe zones or over critical visual labels",
            ],
            owned_artifact_patterns=["projects/*/caption_audio_plan.json"],
            linked_skills=[".agents/skills/xdx-preproduction-planning"],
            linked_python_modules=["adapters/caption_lipsync_adapter.py", "engines/preset_executors.py"],
            custom_subagent_file=".agents/agents/xdx-audio-caption-specialist.md",
            implementation_status="RUNTIME_TESTED",
        ),
        # ---------------- INDEPENDENT VERIFICATION DEPARTMENT (17-20) ----------------
        _role(
            agent_id="preproduction_verifier",
            agent_number=17,
            department="independent_verification_department",
            display_name="17. Preproduction Verifier",
            mission="Audit pre-production packages in a separate fresh context across topic fit, fact citations, script originality, hook strength, clause-to-shot alignment, character/asset completeness, and engine compatibility.",
            read_only=True,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Neon / Cross-Family Verifier",
            subagent_arg="inherit",
            routing_rationale="Independent fresh-context critique prevents producer confirmation bias.",
            allowed_tools=["view_file", "lookup_skill"],
            forbidden_actions=[
                "Silently edit, patch, or overwrite any producer artifact",
                "Approve packages containing placeholder scripts, unverified factual claims, or >10s unapproved shots",
            ],
            owned_artifact_patterns=[],
            linked_skills=[".agents/skills/xdx-independent-audit"],
            linked_python_modules=["orchestration/handoff_manager.py", "intelligence/creative_pipeline.py"],
            custom_subagent_file=".agents/agents/xdx-preproduction-verifier.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="visual_critic",
            agent_number=18,
            department="independent_verification_department",
            display_name="18. Visual Critic",
            mission="Inspect actual rendered frames, contact sheets, and temporal motion via REA-Video for character continuity, foot sliding, mesh penetration, hand-prop contact, lighting, readability, and narrative relevance.",
            read_only=True,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Neon (Multimodal Vision)",
            subagent_arg="inherit",
            routing_rationale="Requires genuine multimodal visual inspection citing exact shot_id, timestamp, or frame.",
            allowed_tools=["view_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Judge visual quality from JSON manifests alone without inspecting actual rendered frames",
                "Mutate scene or render files directly instead of emitting shot-referenced defects",
            ],
            owned_artifact_patterns=[],
            linked_skills=["rea-video", ".agents/skills/xdx-independent-audit"],
            linked_python_modules=["intelligence/visual_qc_engine.py", "intelligence/rea_reference_intelligence.py"],
            custom_subagent_file=".agents/agents/xdx-visual-technical-success-auditor.md",
            implementation_status="UNIT_TESTED",
        ),
        _role(
            agent_id="technical_auditor",
            agent_number=19,
            department="independent_verification_department",
            display_name="19. Technical Auditor",
            mission="Deterministically verify file integrity, full FFmpeg video decode, resolution, FPS, frame count, duration, audio sync, zero timeline gaps/overlaps, asset provenance, and SHA-256 approval digests.",
            read_only=True,
            requires_fresh_context=True,
            max_concurrent_instances=2,
            session_pref="Gemini 4 Hydrogen / Gemini 4 Neon",
            subagent_arg="inherit",
            routing_rationale="Executes deterministic CLI/Python checks (ffprobe, ffmpeg -f null, approval_gate, pytest).",
            allowed_tools=["view_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Modify source code, tests, or approval records to mask technical failures",
                "Skip full stream decode verification on rendered media",
            ],
            owned_artifact_patterns=[],
            linked_skills=[".agents/skills/xdx-independent-audit"],
            linked_python_modules=["engines/ffmpeg_engine.py", "intelligence/state_and_approval.py"],
            custom_subagent_file=".agents/agents/xdx-visual-technical-success-auditor.md",
            implementation_status="RUNTIME_TESTED",
        ),
        _role(
            agent_id="success_auditor",
            agent_number=20,
            department="independent_verification_department",
            display_name="20. Success Auditor",
            mission="Render the final evidence-based PASS/REVISION_REQUIRED verdict across Preproduction Verifier, Technical Auditor, and Visual Critic reports against explicit milestone acceptance criteria.",
            read_only=True,
            requires_fresh_context=True,
            max_concurrent_instances=1,
            session_pref="Gemini 4 Neon / Cross-Family Verifier",
            subagent_arg="inherit",
            routing_rationale="Final adversarial gatekeeper preventing premature victory claims.",
            allowed_tools=["view_file", "run_command", "lookup_skill"],
            forbidden_actions=[
                "Grant final production PASS based solely on unit tests, schema validation, or self-tests",
                "Lower acceptance criteria or silently waive unresolved defects",
            ],
            owned_artifact_patterns=[],
            linked_skills=[".agents/skills/xdx-independent-audit"],
            linked_python_modules=["orchestration/handoff_manager.py", "intelligence/visual_qc_engine.py"],
            custom_subagent_file=".agents/agents/xdx-visual-technical-success-auditor.md",
            implementation_status="RUNTIME_TESTED",
        ),
    ]

    return {
        "schema_version": "4.0.0-phase01.6a",
        "studio_version": "4.0.0-alpha.1",
        "max_initial_active_specialists": {
            "min_recommended": 3,
            "max_recommended": 6,
            "hard_cap_without_override": 6,
        },
        "master_director": master,
        "specialists": specialists,
    }


def parse_markdown_frontmatter(md_path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and Markdown body from an Antigravity customization file."""
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing opening YAML frontmatter delimiter in {md_path}")
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        raise ValueError(f"Missing closing YAML frontmatter delimiter in {md_path}")
    fm_raw = text[4:end_idx]
    body = text[end_idx + 5 :]
    meta = yaml.safe_load(fm_raw)
    if not isinstance(meta, dict):
        raise ValueError(f"Frontmatter in {md_path} must deserialize to a YAML mapping")
    return meta, body


class AgentRegistry:
    """Loads and validates Master Director + 20 Specialist contracts and `.agents/` workspace files."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self._schema = json.loads(
            (self.root_dir / "schemas" / "agent_role_contract.schema.json").read_text(encoding="utf-8")
        )
        self._data = build_default_agent_registry_dict()
        jsonschema.validate(instance=self._data, schema=self._schema)

        all_roles = [self._data["master_director"], *self._data["specialists"]]
        self._by_id: dict[str, dict[str, Any]] = {r["agent_id"]: r for r in all_roles}
        if len(self._by_id) != 21:
            raise ValueError(f"Expected 21 unique roles (Master Director + 20 specialists), got {len(self._by_id)}")

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def list_specialist_ids(self) -> list[str]:
        return [s["agent_id"] for s in self._data["specialists"]]

    def get_role(self, agent_id: str) -> dict[str, Any]:
        if agent_id not in self._by_id:
            raise KeyError(f"Unknown agent_id '{agent_id}'. Registered: {sorted(self._by_id)}")
        return self._by_id[agent_id]

    def validate_active_roster(self, specialist_ids: list[str], *, allow_override: bool = False) -> dict[str, Any]:
        """Enforce PART 04 active specialist cap (3-6 specialists recommended, never all 20 at once)."""
        deduped = list(dict.fromkeys(specialist_ids))
        for sid in deduped:
            if sid == "master_director":
                continue
            self.get_role(sid)

        hard_cap = int(self._data["max_initial_active_specialists"]["hard_cap_without_override"])
        if not allow_override and len(deduped) > hard_cap:
            raise ValueError(
                f"Active specialist roster ({len(deduped)}) exceeds initial cap of {hard_cap}: {deduped}"
            )
        return {
            "active_count": len(deduped),
            "active_specialists": deduped,
            "within_recommended_3_to_6": 3 <= len(deduped) <= 6,
        }

    def validate_workspace_customizations(self) -> dict[str, Any]:
        """Validate `.agents/agents/*.md`, `.agents/skills/*/SKILL.md`, and `.agents/rules/*.md`."""
        agents_dir = self.root_dir / ".agents" / "agents"
        skills_dir = self.root_dir / ".agents" / "skills"
        rules_dir = self.root_dir / ".agents" / "rules"

        agent_files = sorted(agents_dir.glob("*.md"))
        if not agent_files:
            raise FileNotFoundError(f"No custom agent files found in {agents_dir}")

        validated_agents: list[str] = []
        for af in agent_files:
            meta, body = parse_markdown_frontmatter(af)
            for req_key in ("name", "description", "tools", "subagent", "mainAgent"):
                if req_key not in meta:
                    raise ValueError(f"Custom agent {af.name} missing frontmatter key '{req_key}'")
            if not body.strip():
                raise ValueError(f"Custom agent {af.name} has empty system prompt body")
            tools = meta["tools"]
            if not isinstance(tools, list) or not tools:
                raise ValueError(f"Custom agent {af.name} must declare a non-empty tools list")
            unknown_tools = [t for t in tools if t not in OFFICIAL_ANTIGRAVITY_TOOLS]
            if unknown_tools:
                raise ValueError(
                    f"Custom agent {af.name} declares unmapped tool(s) {unknown_tools} (risk of subagent hang!)"
                )
            if meta.get("model", "inherit") not in {"inherit", "flash", "pro"}:
                raise ValueError(f"Invalid frontmatter model in {af.name}: {meta.get('model')}")
            if meta.get("commandExecutionPolicy", "sandbox") not in {"off", "auto", "eager", "sandbox"}:
                raise ValueError(f"Invalid commandExecutionPolicy in {af.name}")
            for sk in meta.get("skills", []):
                sk_path = self.root_dir / sk / "SKILL.md"
                if not sk_path.is_file():
                    raise FileNotFoundError(f"Agent {af.name} references missing workspace skill {sk_path}")
            validated_agents.append(meta["name"])

        # Verify every role contract points to a real custom subagent file and real Python modules
        for role in self._by_id.values():
            sub_file = self.root_dir / role["custom_subagent_file"]
            if not sub_file.is_file():
                raise FileNotFoundError(f"Role {role['agent_id']} missing {sub_file}")
            for mod_rel in role["linked_python_modules"]:
                if mod_rel in {"orchestration/handoff_manager.py", "orchestration/task_router.py"}:
                    # Checked once orchestration package is loaded
                    continue
                if not (self.root_dir / mod_rel).is_file():
                    raise FileNotFoundError(f"Role {role['agent_id']} links missing module {mod_rel}")

        skill_manifests = sorted(skills_dir.glob("*/SKILL.md"))
        if not skill_manifests:
            raise FileNotFoundError(f"No workspace skills found in {skills_dir}")
        validated_skills: list[str] = []
        for sm in skill_manifests:
            meta, body = parse_markdown_frontmatter(sm)
            if not meta.get("description") or not body.strip():
                raise ValueError(f"Invalid SKILL.md in {sm}")
            validated_skills.append(meta.get("name", sm.parent.name))

        rule_files = sorted(rules_dir.glob("*.md"))
        if not rule_files:
            raise FileNotFoundError(f"No workspace rules found in {rules_dir}")
        validated_rules: list[str] = []
        for rf in rule_files:
            if rf.stat().st_size > MAX_RULE_FILE_BYTES:
                raise ValueError(f"Rule {rf.name} exceeds Antigravity 24,000-byte limit")
            meta, body = parse_markdown_frontmatter(rf)
            trig = meta.get("trigger")
            if trig not in VALID_RULE_TRIGGERS:
                raise ValueError(f"Rule {rf.name} has invalid trigger {trig!r} (silently discarded by Antigravity!)")
            if trig == "model_decision" and not meta.get("description"):
                raise ValueError(f"Rule {rf.name} with trigger=model_decision requires description")
            if not body.strip():
                raise ValueError(f"Rule {rf.name} has empty body")
            validated_rules.append(rf.name)

        return {
            "roles_validated": len(self._by_id),
            "custom_agent_files_validated": validated_agents,
            "workspace_skills_validated": validated_skills,
            "workspace_rules_validated": validated_rules,
        }
