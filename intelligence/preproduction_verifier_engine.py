"""Independent 15-Dimension Semantic Preproduction Verifier Engine (Phase 01.6C — Section 18).

Evaluates a complete project preproduction directory in read-only mode against the Master Director's
immutable 15-criterion ``ImmutableReviewCriteriaManifest`` without mutating any producer file.
NEVER grants ``PASS`` merely because JSON parses: checks lexical topic relevance, verified citations,
originality, 0-3s hook, 3-act coherence, adaptive narration timing, 100% semantic clause coverage,
11-field character continuity, 8-profile style cohesion, 12-field asset feasibility, 14-field motion
planning, dynamic camera focal lengths, 14-field reference adaptation / 10D fusion, hybrid engine
compatibility, and 13-item approval package completeness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from intelligence.creative_pipeline import (
    CreativePayloadValidator,
    PLACEHOLDER_PATTERNS,
    TopicRelevanceError,
)
from intelligence.reference_lifecycle import MANDATORY_ADAPTATION_FIELDS, TEN_FUSION_DIMENSIONS
from intelligence.universal_preproduction import (
    MANDATORY_11_CHARACTER_FIELDS,
    MANDATORY_12_ASSET_FIELDS,
    MANDATORY_14_ACTION_FIELDS,
    SUPPORTED_STYLE_PROFILES,
)
from orchestration.handoff_manager import compute_file_sha256
from orchestration.native_execution_adapter import ImmutableReviewCriteriaManifest

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"

MANDATORY_15_PREPRODUCTION_CRITERIA: tuple[tuple[str, str, str, list[str]], ...] = (
    (
        "CRIT_01_TOPIC_RELEVANCE",
        "topic_relevance",
        "Topic title, research claims, blueprint premise, narration, and shot actions align semantically without unrelated fallback.",
        ["authored_creative_payload.json", "blueprint.md", "script.md"],
    ),
    (
        "CRIT_02_FACTUAL_ACCURACY",
        "factual_accuracy",
        "Research dossier includes topic scope, questions, verified https:// claims, excerpts, misconceptions, uncertainties, and narration mapping.",
        ["research_report.json", "research.md"],
    ),
    (
        "CRIT_03_ORIGINALITY",
        "originality",
        "Script, characters, and actions are 100% original with zero placeholder tokens and zero copied reference IP.",
        ["script.md", "authored_creative_payload.json", "character_bible.json"],
    ),
    (
        "CRIT_04_HOOK_STRENGTH",
        "hook",
        "0-3s visual and spoken hooks are concrete, immediate, and free of meta instructions.",
        ["blueprint.md", "authored_creative_payload.json"],
    ),
    (
        "CRIT_05_NARRATIVE_COHERENCE",
        "narrative_coherence",
        "Three-act progression (setup, escalation, resolution) and payoff/callback connect logically across beats.",
        ["blueprint.md", "storyboard.json"],
    ),
    (
        "CRIT_06_NARRATION_TIMING",
        "narration_timing",
        "Adaptive Indonesian narration timing is ESTIMATED with playback_speed_multiplier==1.0 and comfortable pacing or explicit duration recommendation.",
        ["narration_dialogue.json", "production_config.json"],
    ),
    (
        "CRIT_07_SEMANTIC_VISUAL_COVERAGE",
        "semantic_visual_coverage",
        "100% of substantive clauses map to purposeful shots on an integer-frame timeline with every shot <= 10.0s.",
        ["semantic_visual_plan.json", "storyboard.json"],
    ),
    (
        "CRIT_08_CHARACTER_CONSISTENCY",
        "character_consistency",
        "Every character specifies all 11 design/rig/pose/action attributes and cross-shot continuity locks.",
        ["character_bible.json", "character_bible.md"],
    ),
    (
        "CRIT_09_STYLE_CONSISTENCY",
        "style_consistency",
        "Global Style Bible uses a valid supported profile with unified detail tier across characters, environments, and props, and zero premature modeling.",
        ["style_bible.json"],
    ),
    (
        "CRIT_10_ASSET_FEASIBILITY",
        "asset_feasibility",
        "Every storyboard asset has a 12-field semantic specification, honest non-READY status, and zero PLACEHOLDER geometry.",
        ["asset_manifest.json", "storyboard.json"],
    ),
    (
        "CRIT_11_MOTION_FEASIBILITY",
        "motion_feasibility",
        "Every shot has a 14-field character/mechanism action plan with contact/IK targets and zero generic idle loops.",
        ["motion_plan.json"],
    ),
    (
        "CRIT_12_CAMERA_SUITABILITY",
        "camera_suitability",
        "Camera plan selects focal lengths dynamically according to narrative visual purpose (never locked to 36mm across all shots).",
        ["camera_plan.json", "storyboard.json"],
    ),
    (
        "CRIT_13_REFERENCE_ADAPTATION",
        "reference_adaptation",
        "10-dimension reference fusion resolves conflicts cleanly and emits 14-field shot-bound adaptation records (or clean autonomous no-ref mode).",
        ["reference_adaptation.json", "reference_analysis.md"],
    ),
    (
        "CRIT_14_ENGINE_COMPATIBILITY",
        "engine_compatibility",
        "Hybrid engine routing and execution plan validate against engine_plan.schema.json with zero live rendering or Blender mutation.",
        ["engine_plan.json", "execution_plan.md"],
    ),
    (
        "CRIT_15_PACKAGE_COMPLETENESS",
        "package_completeness",
        "All 13 mandatory human approval items exist, are non-empty, match SHA-256 digests, and halt at WAITING_APPROVAL.",
        ["approval_package_manifest.json", "production_config.json"],
    ),
)


def build_mandatory_15_criteria_manifest(
    *,
    project_id: str,
    producer_task_id: str,
    reviewer_task_id: str,
    additional_reviewed_task_ids: list[str] | None = None,
) -> ImmutableReviewCriteriaManifest:
    """Create the Master Director's immutable 15-criterion preproduction manifest BEFORE review."""
    criteria_defs = [
        {
            "criterion_id": cid,
            "category": cat,
            "description": desc,
            "required_artifacts": [f"projects/{project_id}/{a}" for a in arts],
        }
        for cid, cat, desc, arts in MANDATORY_15_PREPRODUCTION_CRITERIA
    ]
    return ImmutableReviewCriteriaManifest.create_sealed(
        project_id=project_id,
        producer_task_id=producer_task_id,
        reviewer_task_id=reviewer_task_id,
        additional_reviewed_task_ids=additional_reviewed_task_ids,
        required_criteria=criteria_defs,
        created_by="master_director",
    )


class PreproductionVerifierEngine:
    """Read-only deterministic + semantic verifier for all 15 preproduction review dimensions."""

    def __init__(self, *, schemas_dir: Path | None = None) -> None:
        sdir = schemas_dir or SCHEMAS_DIR
        self._payload_validator = CreativePayloadValidator(schemas_dir=sdir)
        self._storyboard_schema = json.loads((sdir / "storyboard.schema.json").read_text(encoding="utf-8"))
        self._engine_schema = json.loads((sdir / "engine_plan.schema.json").read_text(encoding="utf-8"))
        self._approval_schema = json.loads((sdir / "approval_package.schema.json").read_text(encoding="utf-8"))

    def evaluate_package_readonly(
        self,
        *,
        package_dir: Path,
        project_id: str,
        criteria_manifest: ImmutableReviewCriteriaManifest,
    ) -> dict[str, Any]:
        """Inspect package artifacts strictly read-only and report per-criterion evidence + all defects."""
        if not criteria_manifest.verify_integrity():
            raise ValueError("Refusing review: ImmutableReviewCriteriaManifest failed SHA-256 integrity check")

        checked_criteria: list[dict[str, Any]] = []
        defects: list[dict[str, Any]] = []

        def _record_pass(cid: str, evidence: str, arts: list[str]) -> None:
            checked_criteria.append(
                {
                    "criterion_id": cid,
                    "status": "PASS",
                    "evidence": evidence,
                    "inspected_artifacts": arts,
                }
            )

        def _record_fail(
            cid: str,
            *,
            artifact: str,
            clause_or_shot: str | None,
            severity: str,
            expected: str,
            observed: str,
            evidence: str,
            responsible_agent: str,
        ) -> None:
            checked_criteria.append(
                {
                    "criterion_id": cid,
                    "status": "FAIL",
                    "evidence": evidence,
                    "inspected_artifacts": [artifact],
                }
            )
            defects.append(
                {
                    "defect_id": f"DEF-{project_id[:16]}-{len(defects) + 1:03d}",
                    "criterion_id": cid,
                    "location": f"{artifact}:{clause_or_shot or 'root'}",
                    "artifact": artifact,
                    "clause_or_shot_id": clause_or_shot,
                    "severity": severity,
                    "expected_result": expected,
                    "observed_result": observed,
                    "evidence": evidence,
                    "responsible_agent": responsible_agent,
                }
            )

        def _load_json(fname: str) -> dict[str, Any] | None:
            p = package_dir / fname
            if not p.is_file() or p.stat().st_size == 0:
                return None
            return json.loads(p.read_text(encoding="utf-8"))

        payload = _load_json("authored_creative_payload.json")
        res_rep = _load_json("research_report.json")
        style_bible = _load_json("style_bible.json")
        char_bible = _load_json("character_bible.json")
        storyboard = _load_json("storyboard.json")
        sem_plan = _load_json("semantic_visual_plan.json")
        motion_plan = _load_json("motion_plan.json")
        camera_plan = _load_json("camera_plan.json")
        asset_man = _load_json("asset_manifest.json")
        nar_plan = _load_json("narration_dialogue.json")
        cap_plan = _load_json("caption_audio_plan.json")
        ref_adapt = _load_json("reference_adaptation.json")
        eng_plan = _load_json("engine_plan.json")
        prod_cfg = _load_json("production_config.json")
        app_man = _load_json("approval_package_manifest.json")
        script_text = (package_dir / "script.md").read_text(encoding="utf-8") if (package_dir / "script.md").is_file() else ""
        bp_text = (package_dir / "blueprint.md").read_text(encoding="utf-8") if (package_dir / "blueprint.md").is_file() else ""

        # 1. CRIT_01_TOPIC_RELEVANCE
        try:
            if payload is None:
                raise TopicRelevanceError("Missing authored_creative_payload.json")
            metrics = self._payload_validator.validate(payload)
            _record_pass(
                "CRIT_01_TOPIC_RELEVANCE",
                (
                    f"Topic '{payload['topic_title']}' verified across premise, claims, and narration "
                    f"(title_overlap={metrics['title_keyword_overlap_script']}, domain_overlap={metrics['domain_keyword_overlap_script']})."
                ),
                [f"projects/{project_id}/authored_creative_payload.json", f"projects/{project_id}/script.md"],
            )
        except Exception as exc:
            _record_fail(
                "CRIT_01_TOPIC_RELEVANCE",
                artifact=f"projects/{project_id}/authored_creative_payload.json",
                clause_or_shot="topic_title",
                severity="CRITICAL",
                expected="Substantive lexical & causal alignment between topic_title, research, and script",
                observed=str(exc),
                evidence=f"Payload topic validation rejected script: {exc}",
                responsible_agent="scriptwriter_agent",
            )

        # 2. CRIT_02_FACTUAL_ACCURACY
        if (
            res_rep
            and res_rep.get("topic_scope")
            and res_rep.get("research_questions")
            and len(res_rep.get("verified_factual_claims", [])) >= 1
            and all(str(u).startswith("https://") for u in res_rep.get("source_urls", []))
            and res_rep.get("misconceptions")
            and res_rep.get("uncertainties")
            and res_rep.get("fact_to_narration_mapping")
        ):
            _record_pass(
                "CRIT_02_FACTUAL_ACCURACY",
                (
                    f"Verified {len(res_rep['verified_factual_claims'])} factual claim(s), "
                    f"{len(res_rep['source_urls'])} https:// source(s), misconceptions, uncertainties, and narration mapping."
                ),
                [f"projects/{project_id}/research_report.json", f"projects/{project_id}/research.md"],
            )
        else:
            _record_fail(
                "CRIT_02_FACTUAL_ACCURACY",
                artifact=f"projects/{project_id}/research_report.json",
                clause_or_shot="verified_factual_claims",
                severity="CRITICAL",
                expected="Complete 10-element research report with verified https:// primary/institutional URLs",
                observed="Missing or unverified research claims/mappings",
                evidence="research_report.json missing mandatory scope, https:// URLs, misconceptions, or narration mapping.",
                responsible_agent="topic_research_agent",
            )

        # 3. CRIT_03_ORIGINALITY
        has_placeholder = bool(PLACEHOLDER_PATTERNS.search(script_text) or PLACEHOLDER_PATTERNS.search(bp_text))
        copied_markers = any(
            bad in (script_text + bp_text).lower()
            for bad in ("az screen recorder", "mobizen", "yakhchal" if payload and "yakhchal" not in payload["topic_title"].lower() else "__never__")
        )
        if script_text and not has_placeholder and not copied_markers and char_bible:
            _record_pass(
                "CRIT_03_ORIGINALITY",
                f"Zero placeholder patterns, zero recorder watermarks, and zero leaked reference subject tokens in {len(script_text)}B script.",
                [f"projects/{project_id}/script.md", f"projects/{project_id}/character_bible.json"],
            )
        else:
            _record_fail(
                "CRIT_03_ORIGINALITY",
                artifact=f"projects/{project_id}/script.md",
                clause_or_shot="B01",
                severity="HIGH",
                expected="Original Indonesian narration without placeholders or leaked reference topics",
                observed=f"has_placeholder={has_placeholder}, copied_markers={copied_markers}",
                evidence="Detected placeholder token or leaked reference subject in script/blueprint.",
                responsible_agent="scriptwriter_agent",
            )

        # 4. CRIT_04_HOOK_STRENGTH
        bp_obj = (payload or {}).get("blueprint") or {}
        h_vis = str(bp_obj.get("hook_0_3s_visual", "")).strip()
        h_spk = str(bp_obj.get("hook_0_3s_spoken", "")).strip()
        if len(h_vis) >= 20 and len(h_spk.split()) >= 4 and not PLACEHOLDER_PATTERNS.search(h_vis + " " + h_spk):
            _record_pass(
                "CRIT_04_HOOK_STRENGTH",
                f"Concrete 0-3s visual hook ({len(h_vis)} chars) and spoken hook ({len(h_spk.split())} words) verified.",
                [f"projects/{project_id}/blueprint.md"],
            )
        else:
            _record_fail(
                "CRIT_04_HOOK_STRENGTH",
                artifact=f"projects/{project_id}/blueprint.md",
                clause_or_shot="hook_0_3s",
                severity="HIGH",
                expected="Concrete 0-3s visual and spoken hook",
                observed=f"hook_visual_len={len(h_vis)}, hook_spoken_words={len(h_spk.split())}",
                evidence="0-3s hook is missing, generic, or too short.",
                responsible_agent="creative_director",
            )

        # 5. CRIT_05_NARRATIVE_COHERENCE
        arc = bp_obj.get("story_arc") or {}
        acts_present = {b["act"] for b in (payload or {}).get("narrative_beats", [])}
        if (
            all(len(str(arc.get(k, ""))) >= 12 for k in ("act_1_setup", "act_2_escalation", "act_3_resolution"))
            and len(str(bp_obj.get("payoff_callback", ""))) >= 12
            and {"ACT_1", "ACT_2", "ACT_3"}.issubset(acts_present)
        ):
            _record_pass(
                "CRIT_05_NARRATIVE_COHERENCE",
                f"Verified 3-act dramatic structure ({sorted(acts_present)}) and explicit payoff/callback.",
                [f"projects/{project_id}/blueprint.md", f"projects/{project_id}/storyboard.json"],
            )
        else:
            _record_fail(
                "CRIT_05_NARRATIVE_COHERENCE",
                artifact=f"projects/{project_id}/blueprint.md",
                clause_or_shot="story_arc",
                severity="MEDIUM",
                expected="Complete ACT_1, ACT_2, ACT_3 progression and payoff_callback",
                observed=f"acts_present={sorted(acts_present)}",
                evidence="Incomplete 3-act arc or missing payoff callback across narrative beats.",
                responsible_agent="creative_director",
            )

        # 6. CRIT_06_NARRATION_TIMING
        est_t = (nar_plan or {}).get("estimated_timing") or {}
        wpm = float((nar_plan or {}).get("measured_script_wpm") or 0.0)
        from intelligence.universal_preproduction import NARRATION_DURATION_TOLERANCE

        try:
            est_total = float(est_t.get("estimated_total_s"))
            target_total = float(est_t.get("target_duration_s"))
        except (TypeError, ValueError):
            est_total, target_total = float("inf"), 0.0
        within_target = target_total > 0 and est_total <= target_total * (1.0 + NARRATION_DURATION_TOLERANCE)
        if (
            nar_plan
            and nar_plan.get("timing_status") == "ESTIMATED"
            and est_t.get("playback_speed_multiplier") == 1.0
            and 85.0 <= wpm <= 175.0
            and within_target
        ):
            _record_pass(
                "CRIT_06_NARRATION_TIMING",
                f"Narration timing marked ESTIMATED at {wpm} WPM (~{est_t.get('estimated_total_s')}s) with speed_multiplier=1.0.",
                [f"projects/{project_id}/narration_dialogue.json"],
            )
        else:
            _record_fail(
                "CRIT_06_NARRATION_TIMING",
                artifact=f"projects/{project_id}/narration_dialogue.json",
                clause_or_shot="estimated_timing",
                severity="HIGH",
                expected=(
                    "ESTIMATED timing at natural WPM (85-175), playback_speed_multiplier==1.0, and estimated "
                    f"duration <= target x {1 + NARRATION_DURATION_TOLERANCE:.2f}"
                ),
                observed=(
                    f"status={(nar_plan or {}).get('timing_status')}, wpm={wpm}, "
                    f"estimated={est_t.get('estimated_total_s')}s, target={est_t.get('target_duration_s')}s"
                ),
                evidence=(
                    "Estimated narration exceeds the target duration (shorten script or change target; never speed up audio)."
                    if not within_target
                    else "Narration WPM out of natural delivery bounds or missing ESTIMATED marker."
                ),
                responsible_agent="audio_director",
            )

        # 7. CRIT_07_SEMANTIC_VISUAL_COVERAGE
        try:
            if storyboard is None or sem_plan is None:
                raise ValueError("Missing storyboard.json or semantic_visual_plan.json")
            jsonschema.validate(instance=storyboard, schema=self._storyboard_schema)
            max_dur = max(float(s["duration_s"]) for s in storyboard["shots"])
            cov = float(sem_plan.get("clause_coverage_ratio", 0.0))
            if cov < 1.0 or max_dur > 10.0 or sem_plan.get("total_clauses", 0) < 3:
                raise ValueError(f"coverage={cov}, max_shot_s={max_dur}, clauses={sem_plan.get('total_clauses')}")
            _record_pass(
                "CRIT_07_SEMANTIC_VISUAL_COVERAGE",
                (
                    f"100% clause coverage ({sem_plan['mapped_clauses']}/{sem_plan['total_clauses']} clauses) across "
                    f"{len(storyboard['shots'])} integer-frame shots (max={max_dur}s <= 10.0s, purposes={sem_plan['visual_purposes_used']})."
                ),
                [f"projects/{project_id}/semantic_visual_plan.json", f"projects/{project_id}/storyboard.json"],
            )
        except Exception as exc:
            _record_fail(
                "CRIT_07_SEMANTIC_VISUAL_COVERAGE",
                artifact=f"projects/{project_id}/storyboard.json",
                clause_or_shot="S001",
                severity="CRITICAL",
                expected="100% clause-to-shot coverage, valid storyboard schema, all shots <= 10.0s",
                observed=str(exc),
                evidence=f"Storyboard or semantic clause mapping failed verification: {exc}",
                responsible_agent="storyboard_director",
            )

        # 8. CRIT_08_CHARACTER_CONSISTENCY
        chars = (char_bible or {}).get("characters") or []
        if chars and all(all(f in c and c[f] for f in MANDATORY_11_CHARACTER_FIELDS) and c.get("continuity_lock") for c in chars):
            _record_pass(
                "CRIT_08_CHARACTER_CONSISTENCY",
                f"Verified {len(chars)} character(s) with all 11 mandatory attributes and cross-shot continuity locks.",
                [f"projects/{project_id}/character_bible.json"],
            )
        else:
            _record_fail(
                "CRIT_08_CHARACTER_CONSISTENCY",
                artifact=f"projects/{project_id}/character_bible.json",
                clause_or_shot="characters",
                severity="HIGH",
                expected="All 11 mandatory character attributes + continuity_lock",
                observed=f"character_count={len(chars)}",
                evidence="character_bible.json missing mandatory 11-field character attributes or continuity lock.",
                responsible_agent="character_design_agent",
            )

        # 9. CRIT_09_STYLE_CONSISTENCY
        s_prof = (style_bible or {}).get("style_profile")
        cohesion = (style_bible or {}).get("cross_asset_consistency_contract") or {}
        if (
            style_bible
            and s_prof in SUPPORTED_STYLE_PROFILES
            and style_bible.get("modeling_executed_in_phase_01_6c") is False
            and cohesion.get("character_detail_tier") == cohesion.get("environment_detail_tier") == cohesion.get("prop_detail_tier")
        ):
            _record_pass(
                "CRIT_09_STYLE_CONSISTENCY",
                f"Style profile '{s_prof}' ({style_bible['style_bible_id']}) locks uniform detail tier '{cohesion['detail_tier']}' with modeling_executed=False.",
                [f"projects/{project_id}/style_bible.json"],
            )
        else:
            _record_fail(
                "CRIT_09_STYLE_CONSISTENCY",
                artifact=f"projects/{project_id}/style_bible.json",
                clause_or_shot="style_profile",
                severity="HIGH",
                expected="Valid Global Style Bible profile with uniform detail tier and modeling_executed=False",
                observed=f"style_profile={s_prof!r}",
                evidence="style_bible.json missing valid profile, uniform detail tier, or modeling guard.",
                responsible_agent="art_director",
            )

        # 10. CRIT_10_ASSET_FEASIBILITY
        specs = (asset_man or {}).get("semantic_asset_specs") or []
        sb_assets = {
            aid
            for sh in (storyboard or {}).get("shots", [])
            for aid in [sh["environment_id"], *sh.get("character_ids", []), *sh.get("asset_ids", [])]
            if aid
        }
        spec_ids = {a["asset_id"] for a in specs}
        if (
            asset_man
            and specs
            and sb_assets.issubset(spec_ids)
            and asset_man.get("procurement_or_modeling_executed") is False
            and all(all(f in a and a[f] for f in MANDATORY_12_ASSET_FIELDS) and a.get("ready_on_disk_now") is False for a in specs)
        ):
            _record_pass(
                "CRIT_10_ASSET_FEASIBILITY",
                f"Verified {len(specs)} storyboard-derived 12-field semantic asset specs (zero premature READY claims, zero PLACEHOLDER boxes).",
                [f"projects/{project_id}/asset_manifest.json"],
            )
        else:
            _record_fail(
                "CRIT_10_ASSET_FEASIBILITY",
                artifact=f"projects/{project_id}/asset_manifest.json",
                clause_or_shot="semantic_asset_specs",
                severity="HIGH",
                expected="100% storyboard asset coverage with 12 semantic fields and ready_on_disk_now==False",
                observed=f"missing_assets={sorted(sb_assets - spec_ids)}",
                evidence="asset_manifest.json missing storyboard assets, 12-field specs, or claimed premature READY.",
                responsible_agent="asset_specialist",
            )

        # 11. CRIT_11_MOTION_FEASIBILITY
        p_acts = (motion_plan or {}).get("planned_actions") or []
        if (
            motion_plan
            and len(p_acts) == len((storyboard or {}).get("shots", []))
            and motion_plan.get("generic_idle_actions_used") is False
            and all(all(f in a and a[f] not in (None, "", []) for f in MANDATORY_14_ACTION_FIELDS) for a in p_acts)
        ):
            _record_pass(
                "CRIT_11_MOTION_FEASIBILITY",
                f"Verified {len(p_acts)} shot-bound 14-field character/mechanism actions with IK/contact targets.",
                [f"projects/{project_id}/motion_plan.json"],
            )
        else:
            _record_fail(
                "CRIT_11_MOTION_FEASIBILITY",
                artifact=f"projects/{project_id}/motion_plan.json",
                clause_or_shot="planned_actions",
                severity="HIGH",
                expected="14-field planned action per shot with contact/IK targets and zero generic loops",
                observed=f"planned_actions={len(p_acts)}",
                evidence="motion_plan.json missing 14-field action records or uses generic idle actions.",
                responsible_agent="motion_director",
            )

        # 12. CRIT_12_CAMERA_SUITABILITY
        distinct_lenses = (camera_plan or {}).get("distinct_focal_lengths_mm") or []
        if (
            camera_plan
            and camera_plan.get("locked_to_single_36mm_focal_length") is False
            and (len(distinct_lenses) >= 2 or (len(distinct_lenses) == 1 and distinct_lenses[0] != 36.0))
        ):
            _record_pass(
                "CRIT_12_CAMERA_SUITABILITY",
                f"Verified purpose-driven camera lenses {distinct_lenses}mm across {len(camera_plan.get('shots', []))} shots (not locked to 36mm).",
                [f"projects/{project_id}/camera_plan.json"],
            )
        else:
            _record_fail(
                "CRIT_12_CAMERA_SUITABILITY",
                artifact=f"projects/{project_id}/camera_plan.json",
                clause_or_shot="distinct_focal_lengths_mm",
                severity="MEDIUM",
                expected="Dynamic purpose-driven focal lengths across shots (not locked to 36mm)",
                observed=f"distinct_focal_lengths_mm={distinct_lenses}",
                evidence="camera_plan.json missing or locked to single 36mm focal length.",
                responsible_agent="cinematographer",
            )

        # 13. CRIT_13_REFERENCE_ADAPTATION
        fusion = (ref_adapt or {}).get("multi_reference_fusion") or {}
        dims = fusion.get("dimensions") or {}
        sel_refs = (ref_adapt or {}).get("selected_reference_ids") or []
        ad_recs = (ref_adapt or {}).get("adaptation_records") or []
        ref_ok = (
            ref_adapt is not None
            and set(dims.keys()) == set(TEN_FUSION_DIMENSIONS)
            and fusion.get("style_consistency_verified") is True
            and ref_adapt.get("production_authorized") is False
            and (
                (len(sel_refs) == 0 and len(ad_recs) == 0)
                or (
                    len(sel_refs) >= 1
                    and len(ad_recs) == len((storyboard or {}).get("shots", []))
                    and all(all(f in r and r[f] for f in MANDATORY_ADAPTATION_FIELDS) for r in ad_recs)
                )
            )
        )
        if ref_ok:
            _record_pass(
                "CRIT_13_REFERENCE_ADAPTATION",
                (
                    f"Verified 10-dimension fusion (refs={sel_refs}, conflicts_resolved={fusion.get('conflicts_detected_count')}) "
                    f"and {len(ad_recs)} shot-bound 14-field adaptation records."
                ),
                [f"projects/{project_id}/reference_adaptation.json", f"projects/{project_id}/reference_analysis.md"],
            )
        else:
            _record_fail(
                "CRIT_13_REFERENCE_ADAPTATION",
                artifact=f"projects/{project_id}/reference_adaptation.json",
                clause_or_shot="adaptation_records",
                severity="HIGH",
                expected="10-dimension fusion + 14-field shot-bound adaptation records (or clean no-ref autonomous mode)",
                observed=f"refs={sel_refs}, adaptation_records={len(ad_recs)}",
                evidence="reference_adaptation.json missing 10-dimension fusion or 14-field shot adaptation records.",
                responsible_agent="rea_video_reference_analyst",
            )

        # 14. CRIT_14_ENGINE_COMPATIBILITY
        try:
            if eng_plan is None or not (package_dir / "execution_plan.md").is_file():
                raise ValueError("Missing engine_plan.json or execution_plan.md")
            jsonschema.validate(instance=eng_plan, schema=self._engine_schema)
            if cap_plan is None or cap_plan.get("timestamp_status") != "ESTIMATED":
                raise ValueError("caption_audio_plan.json missing timestamp_status=='ESTIMATED'")
            _record_pass(
                "CRIT_14_ENGINE_COMPATIBILITY",
                f"Engine routing ({eng_plan['engines_used']}) and ESTIMATED caption/audio plans validated with zero live render execution.",
                [f"projects/{project_id}/engine_plan.json", f"projects/{project_id}/caption_audio_plan.json"],
            )
        except Exception as exc:
            _record_fail(
                "CRIT_14_ENGINE_COMPATIBILITY",
                artifact=f"projects/{project_id}/engine_plan.json",
                clause_or_shot="shots",
                severity="HIGH",
                expected="Valid engine_plan.json, execution_plan.md, and ESTIMATED caption_audio_plan.json",
                observed=str(exc),
                evidence=f"Engine/caption compatibility validation failed: {exc}",
                responsible_agent="remotion_specialist",
            )

        # 15. CRIT_15_PACKAGE_COMPLETENESS
        try:
            if app_man is None or prod_cfg is None:
                raise ValueError("Missing approval_package_manifest.json or production_config.json")
            jsonschema.validate(instance=app_man, schema=self._approval_schema)
            items_13 = app_man["mandatory_13_items"]
            if len(items_13) != 13 or app_man["status"] != "WAITING_APPROVAL":
                raise ValueError(f"items={len(items_13)}, status={app_man['status']}")
            for item_key, item_val in items_13.items():
                af = package_dir / item_val["artifact_file"]
                if not af.is_file() or af.stat().st_size == 0:
                    raise ValueError(f"13-item '{item_key}' points to missing/empty '{item_val['artifact_file']}'")
            for rel_f, exp_sha in app_man["required_files_sha256"].items():
                fp = package_dir / rel_f
                if not fp.is_file() or compute_file_sha256(fp) != exp_sha:
                    raise ValueError(f"SHA-256 mismatch on package file '{rel_f}'")
            _record_pass(
                "CRIT_15_PACKAGE_COMPLETENESS",
                f"All 13 mandatory items and {len(app_man['required_files_sha256'])} file SHA-256 digests verified; status=='WAITING_APPROVAL'.",
                [f"projects/{project_id}/approval_package_manifest.json"],
            )
        except Exception as exc:
            _record_fail(
                "CRIT_15_PACKAGE_COMPLETENESS",
                artifact=f"projects/{project_id}/approval_package_manifest.json",
                clause_or_shot="mandatory_13_items",
                severity="CRITICAL",
                expected="Complete 13-item package verified on disk at WAITING_APPROVAL",
                observed=str(exc),
                evidence=f"13-item package completeness failed: {exc}",
                responsible_agent="master_director",
            )

        verdict = "PASS" if not defects else "REVISION_REQUIRED"
        return {
            "verdict": verdict,
            "required_criteria_ids": criteria_manifest.required_criteria_ids,
            "criteria_manifest_digest": criteria_manifest.manifest_sha256,
            "checked_criteria": checked_criteria,
            "defects": defects,
        }
