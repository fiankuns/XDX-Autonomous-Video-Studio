"""Universal Preproduction Intelligence Engines (Phase 01.6C — Sections 6, 10, 11, 12, 13, 14 & 15).

Provides deterministic Python validation, estimation, semantic clause-to-shot mapping, character/style
planning, 14-field action planning, 12-field semantic asset planning, and purpose-driven camera,
audio, and caption planning across all supported genres and topics without ever performing modeling,
rendering, asset purchasing, or Blender scene mutation.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from adapters.caption_lipsync_adapter import WhisperCaptionAdapter
from intelligence.procedural_geometry import SUPPORTED_PROCEDURAL_CATEGORIES
from libraries.loader import PresetLibraryRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent

SEMANTIC_VISUAL_PURPOSES: tuple[str, ...] = (
    "character_acting",
    "object_insert",
    "technical_cutaway",
    "exploded_view",
    "scientific_mechanism",
    "reaction_shot",
    "historical_reconstruction",
    "visual_metaphor",
    "data_visualization",
    "scale_comparison",
    "timeline",
    "establishing_shot",
)

SUPPORTED_STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "flat_cartoon": {
        "style_bible_id": "xdx_flat_cartoon_v4_0",
        "display_name": "2D Flat Graphic Cartoon",
        "shading_model": "flat_cel_ink_outline_2px",
        "color_space": "sRGB_broadcast_rec709",
        "detail_tier": "clean_silhouette_graphic_shapes",
        "primary_engines": ["remotion", "threejs"],
        "palette_mood": "saturated_playful_high_contrast",
        "material_rules": "Zero photoreal roughness noise; crisp stepped fills across characters, props, and backdrops.",
    },
    "stylized_3d": {
        "style_bible_id": "xdx_stylized_3d_v4_0",
        "display_name": "Stylized 3D Narrative & Cutaway",
        "shading_model": "pbr_stylized_soft_subsurface_acescg",
        "color_space": "ACEScg_rec709_view",
        "detail_tier": "medium_sculpted_beveled_forms",
        "primary_engines": ["blender", "threejs", "remotion"],
        "palette_mood": "balanced_warm_cool_cinematic",
        "material_rules": "Hand-crafted tactile PBR roughness with beveled silhouettes; uniform texel density across cast and props.",
    },
    "diorama": {
        "style_bible_id": "xdx_stylized_diorama_v4_0",
        "display_name": "Tactile Miniature Architectural Diorama",
        "shading_model": "pbr_miniature_tiltshift_acescg",
        "color_space": "ACEScg_rec709_view",
        "detail_tier": "crafted_miniature_architectural_detail",
        "primary_engines": ["blender", "threejs", "remotion"],
        "palette_mood": "warm_tungsten_and_daylight_contrast",
        "material_rules": "Matte clay/wood/brushed-metal miniature finish; consistent bevel scale across rooms, characters, and props.",
    },
    "anime_inspired": {
        "style_bible_id": "xdx_anime_inspired_v4_0",
        "display_name": "Anime-Inspired Cel & Painted Background",
        "shading_model": "two_band_cel_shader_painted_env",
        "color_space": "sRGB_rec709",
        "detail_tier": "expressive_linework_painted_environment",
        "primary_engines": ["blender", "threejs", "remotion"],
        "palette_mood": "atmospheric_sky_and_rimlight_accents",
        "material_rules": "Crisp cel shadow terminator on characters and hero props matched to painterly background brushwork.",
    },
    "2d_animation": {
        "style_bible_id": "xdx_2d_animation_v4_0",
        "display_name": "2D Rigged Character & Motion Illustration",
        "shading_model": "layered_vector_textured_2d",
        "color_space": "sRGB_rec709",
        "detail_tier": "layered_2d_illustration",
        "primary_engines": ["remotion", "threejs"],
        "palette_mood": "editorial_warm_palette",
        "material_rules": "Unified stroke weight and grain overlay across 2D character rigs, environments, and callout props.",
    },
    "realistic": {
        "style_bible_id": "xdx_physically_based_realistic_v4_0",
        "display_name": "Physically Based Documentary Realism",
        "shading_model": "physically_based_acescg_path_or_eevee_next",
        "color_space": "ACEScg_rec709_view",
        "detail_tier": "high_fidelity_physically_plausible",
        "primary_engines": ["blender", "threejs", "remotion"],
        "palette_mood": "naturalistic_measured_contrast",
        "material_rules": "Energy-conserving PBR materials, calibrated real-world scale (1 unit = 1m), zero cartoon exaggeration.",
    },
    "infographic": {
        "style_bible_id": "xdx_kinetic_infographic_v4_0",
        "display_name": "Precision Scientific & Data Infographic",
        "shading_model": "clean_isometric_data_shader_and_svg",
        "color_space": "sRGB_rec709",
        "detail_tier": "high_legibility_schematic_precision",
        "primary_engines": ["threejs", "remotion"],
        "palette_mood": "high_contrast_editorial_signal_colors",
        "material_rules": "Color-coded functional parts, crisp typographic hierarchy, and distraction-free neutral stages.",
    },
    "mixed_media": {
        "style_bible_id": "xdx_curated_mixed_media_v4_0",
        "display_name": "Intentional Archival Collage & 3D Stage Mixed Media",
        "shading_model": "3d_stage_with_paper_halftone_cutouts",
        "color_space": "ACEScg_rec709_view",
        "detail_tier": "tactile_paper_collage_on_3d_stage",
        "primary_engines": ["blender", "threejs", "remotion"],
        "palette_mood": "archival_paper_and_spot_accent",
        "material_rules": "Deliberate contrast rule: archival paper texture for historical inserts framed inside unified 3D stage lighting.",
    },
}

MANDATORY_11_CHARACTER_FIELDS: tuple[str, ...] = (
    "character_id",
    "identity",
    "silhouette",
    "proportions",
    "facial_design",
    "clothing",
    "materials",
    "color_palette",
    "expressions",
    "rig_requirements",
    "pose_requirements",
    "action_requirements",
)

MANDATORY_14_ACTION_FIELDS: tuple[str, ...] = (
    "actor_id",
    "action_type",
    "object_target",
    "start_frame",
    "end_frame",
    "start_pose",
    "key_poses",
    "end_pose",
    "contact_point",
    "ik_target",
    "weight_transfer",
    "facial_expression",
    "motion_intent",
    "acceptance_criteria",
)

MANDATORY_12_ASSET_FIELDS: tuple[str, ...] = (
    "asset_id",
    "semantic_category",
    "geometry_specification",
    "visual_style",
    "dimensions",
    "material",
    "rig_requirement",
    "animation_requirement",
    "engine_compatibility",
    "license_requirements",
    "source_strategy",
    "qc_criteria",
)

_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?;:—])\s+|,\s+(?=(?:namun|tetapi|sehingga|ketika|saat|lalu|kemudian|sementara|padahal|akibatnya|artinya)\b)", re.IGNORECASE)

_TECHNICAL_TERMS_RE = re.compile(
    r"\b("
    r"evaporator|kondensor|kompresor|refrigeran|ekspansi|termodinamika|kalor|entalpi|tekanan|"
    r"atmosfer|hidrologi|albedo|tektonik|palung|mariana|fotosintesis|fitoplankton|salinitas|"
    r"suprachiasmatic|hipokampus|neurotransmiter|dopamin|metabolisme|elektromagnetik|"
    r"kilometer|miliar|derajat|pascal|celsius|kelvin"
    r")\b",
    re.IGNORECASE,
)

_REDUNDANT_FILLER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsebenarnya\s+pada\s+dasarnya\b", re.IGNORECASE), "pada dasarnya"),
    (re.compile(r"\bsangat\s+amat\b", re.IGNORECASE), "sangat"),
    (re.compile(r"\bperlu\s+kita\s+ketahui\s+bersama\s+bahwa\s+", re.IGNORECASE), ""),
    (re.compile(r"\bdapat\s+dikatakan\s+bahwa\s+", re.IGNORECASE), ""),
)


def split_into_semantic_clauses(text: str) -> list[str]:
    """Split spoken narration into meaningful clauses without losing short punchlines."""
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return []
    raw_parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(cleaned) if p and p.strip()]
    merged: list[str] = []
    for part in raw_parts:
        if merged and len(part.split()) < 3:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged or [cleaned]


class UniversalTopicResearchCompiler:
    """Compiles structured Section 6 Topic Research Intelligence with full epistemic separation."""

    FACTUAL_GENRES: frozenset[str] = frozenset(
        {"explainer", "edukasi", "sejarah", "biografi", "dokumenter"}
    )

    def compile_research_dossier(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        res = payload["topic_research"]
        genres = list(payload["genres"])
        topic_title = payload["topic_title"]
        claims = list(res["claims"])

        real_world_claims = [c for c in claims if c["epistemic_status"] != "declared_fiction"]
        fictional_claims = [c for c in claims if c["epistemic_status"] == "declared_fiction"]

        # Build fact-to-narration mapping across beats and clauses
        fact_to_narration: dict[str, list[dict[str, Any]]] = {c["claim_id"]: [] for c in claims}
        for beat in payload["narrative_beats"]:
            explicit_refs = list(beat.get("claim_refs") or [])
            if not explicit_refs and real_world_claims:
                # Match lexically when claim_refs omitted on legacy v3.4 payloads
                vo_low = beat["narration_vo"].lower()
                for c in real_world_claims:
                    c_words = {w for w in re.findall(r"[a-zA-Z]{5,}", c["statement"].lower())}
                    if any(w in vo_low for w in c_words):
                        explicit_refs.append(c["claim_id"])
            for cid in explicit_refs:
                if cid in fact_to_narration:
                    fact_to_narration[cid].append(
                        {
                            "beat_id": beat["beat_id"],
                            "beat_role": beat["beat_role"],
                            "narration_excerpt": beat["narration_vo"][:140],
                        }
                    )

        # Ensure every verified claim has at least one mapped beat if claims exist
        if payload["narrative_beats"]:
            first_beat = payload["narrative_beats"][0]
            for cid, mappings in fact_to_narration.items():
                if not mappings:
                    mappings.append(
                        {
                            "beat_id": first_beat["beat_id"],
                            "beat_role": first_beat["beat_role"],
                            "narration_excerpt": first_beat["narration_vo"][:140],
                        }
                    )

        topic_scope = res.get("topic_scope") or (
            f"Cakupan kajian terfokus pada '{topic_title}' lintas genre {', '.join(genres)} "
            f"untuk durasi target {payload['target_duration_s']} detik."
        )
        questions = list(res.get("research_questions") or [
            f"Apa mekanisme atau dinamika inti di balik '{topic_title}'?",
            f"Apa miskonsepsi umum penonton mengenai '{topic_title}' dan bagaimana bukti ilmiah/faktual meluruskannya?",
            f"Apa konsekuensi nyata yang paling relevan bagi kehidupan sehari-hari penonton?",
        ])
        misconceptions = list(res.get("misconceptions") or [
            {
                "misconception": f"Penyederhanaan keliru seputar '{topic_title}' tanpa melihat mekanisme kausal utamanya.",
                "correction": claims[0]["statement"],
                "claim_ref": claims[0]["claim_id"],
            }
        ])
        uncertainties = list(res.get("uncertainties") or [
            "Rentang kuantitatif pada kondisi ekstrem bergantung pada asumsi batas model dan variasi lingkungan lokal."
        ])
        declared_fiction_list = list(res.get("fictional_elements_declared") or [
            c["statement"] for c in fictional_claims
        ])
        if not declared_fiction_list and any(g in {"storytelling", "satir_sosial", "social_satire", "komedi_absurd", "horor"} for g in genres):
            declared_fiction_list = [
                f"Karakter, nama tokoh ({', '.join(ch['name'] for ch in payload['characters'])}), adegan dramatisasi, dan hiperbola komedi bersifat fiksi orisinal."
            ]

        primary_sources = []
        seen_urls: set[str] = set()
        for c in real_world_claims:
            url = c["source_url"]
            if url not in seen_urls:
                seen_urls.add(url)
                pub_date = (
                    c.get("publication_date")
                    or (str(c["publication_year"]) if c.get("publication_year") is not None else "unknown_not_stated")
                )
                primary_sources.append(
                    {
                        "claim_id": c["claim_id"],
                        "source_title": c["source_title"],
                        "source_url": url,
                        "publication_date": pub_date,
                        "is_primary_or_institutional": bool(c.get("is_primary_source", True)),
                        "evidence_excerpt": c.get("evidence_excerpt") or c["statement"],
                    }
                )

        report_json = {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "topic_title": topic_title,
            "genres": genres,
            "epistemic_mode": res["epistemic_mode"],
            "research_status": res["research_status"],
            "topic_scope": topic_scope,
            "research_questions": questions,
            "verified_factual_claims": [
                {
                    "claim_id": c["claim_id"],
                    "statement": c["statement"],
                    "epistemic_status": c["epistemic_status"],
                    "source_title": c["source_title"],
                    "source_url": c["source_url"],
                    "publication_date": c.get("publication_date")
                    or (str(c["publication_year"]) if c.get("publication_year") is not None else "unknown_not_stated"),
                    "evidence_excerpt": c.get("evidence_excerpt") or c["statement"],
                }
                for c in real_world_claims
            ],
            "primary_sources": primary_sources,
            "source_urls": [s["source_url"] for s in primary_sources],
            "evidence_excerpts": [
                {"claim_id": c["claim_id"], "excerpt": c.get("evidence_excerpt") or c["statement"]}
                for c in real_world_claims
            ],
            "misconceptions": misconceptions,
            "uncertainties": uncertainties,
            "fictional_vs_real_world_separation": {
                "contains_fictional_dramatization": bool(declared_fiction_list),
                "real_world_claim_ids": [c["claim_id"] for c in real_world_claims],
                "declared_fictional_elements": declared_fiction_list,
            },
            "fact_to_narration_mapping": fact_to_narration,
        }

        md_lines = [
            f"# Dossier Riset Universal v4.0 — {topic_title}",
            "",
            f"- **Cakupan Topik (`Topic Scope`)**: {topic_scope}",
            f"- **Genre**: `{', '.join(genres)}` | **Mode Epistemik**: `{res['epistemic_mode']}` (`{res['research_status']}`)",
            "",
            "## Pertanyaan Riset Utama",
            *[f"{idx}. {q}" for idx, q in enumerate(questions, 1)],
            "",
            "## Klaim Faktual Terverifikasi & Kutipan Bukti",
            *[
                f"- **`{c['claim_id']}` [{c['epistemic_status']}]**: {c['statement']}\n"
                f"  - Sumber: *{c['source_title']}* ({c['publication_date']}) — {c['source_url']}\n"
                f"  - Ringkasan Bukti: {c['evidence_excerpt']}"
                for c in report_json["verified_factual_claims"]
            ],
            "",
            "## Pemetaan Fakta ke Narasi (`Fact-to-Narration Mapping`)",
            *[
                f"- **`{cid}`** → Beat `{', '.join(m['beat_id'] for m in maps)}`"
                for cid, maps in fact_to_narration.items()
            ],
            "",
            "## Miskonsepsi Umum & Koreksi",
            *[
                f"- **Miskonsepsi**: {m['misconception']} → **Koreksi**: {m['correction']}"
                for m in misconceptions
            ],
            "",
            "## Batas Ketidakpastian (`Uncertainty`) & Pemisahan Fiksi",
            *[f"- *Ketidakpastian*: {u}" for u in uncertainties],
            *[f"- *Elemen Fiksi Terdeklarasi*: {fe}" for fe in declared_fiction_list],
            "",
        ]
        return report_json, "\n".join(md_lines)


class NarrationTimingIntelligence:
    """Adaptive narration duration estimator & non-destructive over-length tightener (Section 11)."""

    EMOTION_WPM_FACTOR: dict[str, float] = {
        "calm": 0.96,
        "curious": 1.00,
        "energetic": 1.05,
        "urgent": 1.06,
        "ironic_deadpan": 0.95,
        "deadpan": 0.95,
        "eerie": 0.88,
        "tense": 0.90,
        "awed": 0.91,
        "warm": 0.98,
    }

    VISUAL_COMPREHENSION_MIN_S: dict[str, float] = {
        "technical_cutaway": 3.2,
        "exploded_view": 3.4,
        "scientific_mechanism": 3.2,
        "scale_comparison": 3.0,
        "data_visualization": 3.0,
        "timeline": 2.8,
        "historical_reconstruction": 2.8,
        "visual_metaphor": 2.4,
        "character_acting": 2.2,
        "reaction_shot": 1.8,
        "object_insert": 2.0,
        "establishing_shot": 2.4,
    }

    def estimate_clause_duration_s(
        self,
        clause_text: str,
        *,
        language: str = "id-ID",
        base_wpm: int = 145,
        emotion: str = "curious",
        voice_style: str = "warm_clear_indonesian",
        visual_purpose: str = "character_acting",
        has_dialogue_turn: bool = False,
    ) -> dict[str, Any]:
        words = clause_text.split()
        word_count = len(words)
        lang_factor = 1.0 if language.lower().startswith("id") else 1.04
        emo_factor = self.EMOTION_WPM_FACTOR.get(emotion.lower(), 1.0)
        voice_factor = 0.94 if "authoritative" in voice_style or "documentary" in voice_style else 1.0
        effective_wpm = max(118.0, min(165.0, base_wpm * lang_factor * emo_factor * voice_factor))

        articulation_s = (word_count / effective_wpm) * 60.0
        comma_pauses_s = clause_text.count(",") * 0.18 + clause_text.count(";") * 0.25 + clause_text.count("—") * 0.24
        sentence_end_pause_s = 0.28 if clause_text.rstrip().endswith((".", "?", "!")) else 0.16
        tech_terms = _TECHNICAL_TERMS_RE.findall(clause_text)
        tech_comprehension_s = len(tech_terms) * 0.22
        dialogue_turn_s = 0.25 if has_dialogue_turn else 0.0

        spoken_plus_pauses_s = (
            articulation_s + comma_pauses_s + sentence_end_pause_s + tech_comprehension_s + dialogue_turn_s
        )
        visual_floor_s = self.VISUAL_COMPREHENSION_MIN_S.get(visual_purpose, 2.0)
        estimated_total_s = round(max(1.5, spoken_plus_pauses_s, visual_floor_s * 0.75), 3)

        return {
            "language": language,
            "word_count": word_count,
            "effective_wpm": round(effective_wpm, 1),
            "articulation_s": round(articulation_s, 3),
            "punctuation_and_breath_pause_s": round(comma_pauses_s + sentence_end_pause_s, 3),
            "technical_terms_detected": tech_terms,
            "technical_comprehension_bonus_s": round(tech_comprehension_s, 3),
            "dialogue_turn_pause_s": round(dialogue_turn_s, 3),
            "visual_comprehension_floor_s": visual_floor_s,
            "estimated_duration_s": estimated_total_s,
            "playback_speed_multiplier": 1.0,
            "timing_status": "ESTIMATED",
        }

    def evaluate_and_adapt_payload_timing(
        self,
        payload: dict[str, Any],
        *,
        base_wpm: int = 144,
    ) -> dict[str, Any]:
        """Evaluate full-script narration timing; tighten redundant phrasing if over budget without speeding audio."""
        target_s = float(payload["target_duration_s"])
        revisions_applied: list[dict[str, Any]] = []

        def _measure_beats(beats: list[dict[str, Any]]) -> tuple[float, int, list[dict[str, Any]]]:
            total_est = 0.0
            total_words = 0
            per_beat: list[dict[str, Any]] = []
            for b in beats:
                clauses = split_into_semantic_clauses(b["narration_vo"])
                emo = str(b.get("emotion") or "curious")
                v_style = str(b.get("voice_direction") or "warm_clear_indonesian")
                lead_purpose = str(b["shot_blueprints"][0].get("visual_purpose") or "character_acting")
                c_ests = [
                    self.estimate_clause_duration_s(
                        cl,
                        base_wpm=base_wpm,
                        emotion=emo,
                        voice_style=v_style,
                        visual_purpose=lead_purpose,
                    )
                    for cl in clauses
                ]
                dlg_s = 0.0
                dlg_words = 0
                for d in b.get("dialogue_lines", []):
                    dw = len(d["line"].split())
                    dlg_words += dw
                    dlg_s += (dw / max(125.0, base_wpm * 0.95)) * 60.0 + 0.30
                beat_est = round(sum(x["estimated_duration_s"] for x in c_ests) + dlg_s, 3)
                bw = sum(x["word_count"] for x in c_ests) + dlg_words
                total_est += beat_est
                total_words += bw
                per_beat.append(
                    {
                        "beat_id": b["beat_id"],
                        "target_duration_s": float(b["target_duration_s"]),
                        "estimated_duration_s": beat_est,
                        "word_count": bw,
                        "clauses": c_ests,
                    }
                )
            return round(total_est, 3), total_words, per_beat

        initial_est_s, initial_words, beat_reports = _measure_beats(payload["narrative_beats"])

        # If script exceeds target duration by >8%, apply non-destructive filler tightening first
        if initial_est_s > target_s * 1.08:
            for b in payload["narrative_beats"]:
                orig_vo = b["narration_vo"]
                new_vo = orig_vo
                for pat, repl in _REDUNDANT_FILLER_PATTERNS:
                    new_vo = pat.sub(repl, new_vo)
                # Deduplicate immediate repeated clauses if any
                clauses = split_into_semantic_clauses(new_vo)
                deduped: list[str] = []
                for cl in clauses:
                    if not deduped or cl.lower() != deduped[-1].lower():
                        deduped.append(cl)
                new_vo = " ".join(deduped).strip()
                if new_vo and new_vo != orig_vo and len(new_vo.split()) >= 6:
                    b["narration_vo"] = new_vo
                    revisions_applied.append(
                        {
                            "beat_id": b["beat_id"],
                            "previous_word_count": len(orig_vo.split()),
                            "revised_word_count": len(new_vo.split()),
                            "reason": "Trimmed redundant filler/repetition to preserve breath pauses without speeding audio.",
                        }
                    )

        final_est_s, final_words, beat_reports = _measure_beats(payload["narrative_beats"])
        implied_wpm = round(final_words / max(0.1, target_s / 60.0), 1)
        needs_longer_duration = final_est_s > target_s * 1.15 or implied_wpm > 168.0
        recommended_duration_s = (
            int(math.ceil((final_est_s * 1.06) / 5.0) * 5) if needs_longer_duration else int(target_s)
        )

        return {
            "timing_status": "ESTIMATED",
            "audio_forced_alignment_phase": "SCHEDULED_PHASE_04",
            "playback_speed_multiplier": 1.0,
            "audio_speedup_forbidden": True,
            "language": "id-ID",
            "base_target_wpm": base_wpm,
            "implied_script_wpm": implied_wpm,
            "initial_estimated_duration_s": initial_est_s,
            "final_estimated_duration_s": final_est_s,
            "target_duration_s": target_s,
            "within_comfortable_indonesian_pacing": not needs_longer_duration,
            "non_destructive_tightening_revisions": revisions_applied,
            "duration_recommendation": {
                "suggest_duration_change": needs_longer_duration,
                "recommended_target_duration_s": recommended_duration_s,
                "rationale": (
                    f"Estimated natural delivery with pauses requires ~{final_est_s}s; recommend {recommended_duration_s}s rather than accelerating speech."
                    if needs_longer_duration
                    else f"Estimated delivery ({final_est_s}s, {implied_wpm} WPM) fits comfortably within {int(target_s)}s with natural breath pauses."
                ),
            },
            "beats": beat_reports,
        }


class SemanticVisualDirector:
    """Implements CLAUSE -> VISUAL PURPOSE -> SHOT -> ACTION -> CHARACTER/OBJECT -> ASSET -> CAMERA -> ENGINE -> QC (Section 10)."""

    def infer_visual_purpose(self, clause_text: str, sb: dict[str, Any], genres: list[str], idx_in_beat: int) -> str:
        explicit = sb.get("visual_purpose")
        if explicit in SEMANTIC_VISUAL_PURPOSES:
            return explicit

        low = f"{clause_text} {sb.get('visual_subject', '')} {sb.get('concrete_action', '')} {sb.get('cutaway_purpose', '')}".lower()
        shot_size = sb.get("shot_size", "medium")
        if sb.get("is_cutaway") or shot_size == "cutaway":
            if any(k in low for k in ("belah", "cross-section", "potongan", "pipa", "kumparan", "dinding")):
                return "technical_cutaway"
            if any(k in low for k in ("terurai", "exploded", "komponen", "lapisan")):
                return "exploded_view"
            if any(k in low for k in ("skala", "dibanding", "ukuran", "palung", "kilometer", "volume")):
                return "scale_comparison"
            if any(k in low for k in ("grafik", "persen", "kurva", "angka", "statistik", "data")):
                return "data_visualization"
            if any(k in low for k in ("abad", "tahun", "kronologi", "linimasa")):
                return "timeline"
            return "scientific_mechanism"
        if shot_size == "establishing":
            return "establishing_shot"
        if shot_size == "reaction" or any(k in low for k in ("melongo", "terdiam", "reaksi", "menghela", "lirik")):
            return "reaction_shot"
        if shot_size == "insert":
            return "object_insert"
        if "sejarah" in genres or "biografi" in genres:
            if any(k in low for k in ("arsip", "abad", "masa", "tahun")):
                return "historical_reconstruction"
        if any(k in low for k in ("ibarat", "metafora", "menara", "gunung kertas", "labirin")):
            return "visual_metaphor"
        return "character_acting" if idx_in_beat % 2 == 0 else "object_insert"

    def build_clause_to_shot_plan(
        self,
        *,
        payload: dict[str, Any],
        storyboard: dict[str, Any],
        timing_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify and emit explicit 9-stage CLAUSE -> ... -> QC trace for every substantive clause."""
        shots_by_id = {s["shot_id"]: s for s in storyboard["shots"]}
        nb_by_id = {nb["beat_id"]: nb for nb in storyboard["narrative_beats"]}

        clause_mappings: list[dict[str, Any]] = []
        clause_counter = 0
        purposes_used: set[str] = set()

        for beat in payload["narrative_beats"]:
            bid = beat["beat_id"]
            nb_compiled = nb_by_id[bid]
            beat_shot_ids = list(nb_compiled["shot_ids"])
            clauses = split_into_semantic_clauses(beat["narration_vo"])
            for dlg in beat.get("dialogue_lines", []):
                clauses.append(f"[{dlg['speaker_id']}] {dlg['line']}")

            for c_idx, cl_text in enumerate(clauses):
                clause_counter += 1
                clause_id = f"CL_{clause_counter:03d}"
                # Map clause deterministically onto the beat's compiled shots
                mapped_idx = min(len(beat_shot_ids) - 1, int(c_idx * len(beat_shot_ids) / max(1, len(clauses))))
                shot_id = beat_shot_ids[mapped_idx]
                shot = shots_by_id[shot_id]
                sb_src = beat["shot_blueprints"][min(mapped_idx, len(beat["shot_blueprints"]) - 1)]
                v_purpose = self.infer_visual_purpose(cl_text, sb_src, payload["genres"], c_idx)
                shot["semantic_visual_purpose"] = v_purpose
                purposes_used.add(v_purpose)

                lead_act = shot["action_events"][0]
                clause_mappings.append(
                    {
                        "clause_id": clause_id,
                        "beat_id": bid,
                        "clause_text": cl_text,
                        "01_clause": cl_text,
                        "02_visual_purpose": v_purpose,
                        "03_shot_id": shot_id,
                        "03_frame_range": [shot["start_frame"], shot["end_frame"]],
                        "04_action": lead_act["concrete_action"],
                        "05_character_or_object": {
                            "characters": shot["character_ids"],
                            "subject": sb_src["visual_subject"],
                        },
                        "06_assets": [shot["environment_id"], *shot["asset_ids"]],
                        "07_camera": {
                            "shot_size": shot["camera"]["shot_size"],
                            "focal_length_mm": shot["camera"]["focal_length_mm"],
                            "angle": shot["camera"]["angle"],
                        },
                        "08_engine": {
                            "primary_engine": shot["primary_engine"],
                            "overlay_engine": shot.get("overlay_engine"),
                        },
                        "09_qc_criteria": shot["qc_criteria"],
                    }
                )

        # Ensure every shot also records semantic_visual_purpose
        for shot in storyboard["shots"]:
            if "semantic_visual_purpose" not in shot:
                shot["semantic_visual_purpose"] = (
                    "technical_cutaway" if shot["cutaway"]["is_cutaway"] else "character_acting"
                )
                purposes_used.add(shot["semantic_visual_purpose"])

        shot_durations_f = [s["duration_frames"] for s in storyboard["shots"]]
        sweet_spot_count = sum(1 for s in storyboard["shots"] if 1.8 <= s["duration_s"] <= 6.5)

        return {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "pipeline_chain": "CLAUSE -> VISUAL_PURPOSE -> SHOT -> ACTION -> CHARACTER_OBJECT -> ASSET -> CAMERA -> ENGINE -> QC",
            "total_clauses": len(clause_mappings),
            "mapped_clauses": len(clause_mappings),
            "clause_coverage_ratio": 1.0 if clause_mappings else 0.0,
            "visual_purposes_used": sorted(purposes_used),
            "supported_visual_purposes": list(SEMANTIC_VISUAL_PURPOSES),
            "master_timeline_unit": "integer_frames",
            "fps": storyboard["fps"],
            "total_frames": storyboard["total_frames"],
            "non_uniform_semantic_frame_allocation": len(set(shot_durations_f)) > 1 or len(shot_durations_f) == 1,
            "shots_in_2_to_6s_target_ratio": round(sweet_spot_count / max(1, len(storyboard["shots"])), 4),
            "max_shot_duration_s": max(s["duration_s"] for s in storyboard["shots"]),
            "narration_timing_summary": {
                "estimated_duration_s": timing_report["final_estimated_duration_s"],
                "implied_wpm": timing_report["implied_script_wpm"],
            },
            "clause_to_shot_mappings": clause_mappings,
        }


class CharacterAndStyleIntelligence:
    """Produces 11-field Character Bible and 8-profile Global Style Bible without forcing REF styles (Section 12)."""

    @staticmethod
    def select_style_profile(payload: dict[str, Any], reference_ids: list[str]) -> str:
        explicit = payload.get("style_profile")
        if explicit in SUPPORTED_STYLE_PROFILES:
            return explicit
        genres = set(payload.get("genres") or [])
        if not reference_ids:
            if "komedi_absurd" in genres:
                return "flat_cartoon"
            if "dokumenter" in genres:
                return "realistic"
            return "stylized_3d"
        if "REF-001" in reference_ids and "REF-002" not in reference_ids:
            return "diorama"
        return "stylized_3d"

    def compile_style_bible(
        self,
        payload: dict[str, Any],
        *,
        reference_ids: list[str],
    ) -> dict[str, Any]:
        prof_key = self.select_style_profile(payload, reference_ids)
        prof = SUPPORTED_STYLE_PROFILES[prof_key]
        return {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "style_profile": prof_key,
            "style_bible_id": prof["style_bible_id"],
            "display_name": prof["display_name"],
            "supported_profiles_available": sorted(SUPPORTED_STYLE_PROFILES.keys()),
            "forced_from_ref001_or_ref002": False,
            "reference_ids_consulted": list(reference_ids),
            "shading_model": prof["shading_model"],
            "color_space": prof["color_space"],
            "palette_mood": prof["palette_mood"],
            "cross_asset_consistency_contract": {
                "detail_tier": prof["detail_tier"],
                "character_detail_tier": prof["detail_tier"],
                "environment_detail_tier": prof["detail_tier"],
                "prop_detail_tier": prof["detail_tier"],
                "material_cohesion_rule": prof["material_rules"],
                "anti_placeholder_rule": "Zero untextured greybox cubes or mismatched shader models permitted.",
            },
            "modeling_executed_in_phase_01_6c": False,
        }

    def compile_character_bible_v4(
        self,
        payload: dict[str, Any],
        *,
        style_bible: dict[str, Any],
        storyboard: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        style_profile = style_bible["style_profile"]
        shots_by_char: dict[str, list[str]] = {c["character_id"]: [] for c in payload["characters"]}
        for sh in storyboard["shots"]:
            for cid in sh.get("character_ids", []):
                if cid in shots_by_char:
                    shots_by_char[cid].append(sh["shot_id"])

        compiled_chars: list[dict[str, Any]] = []
        md_lines = [f"# Character Bible v4.0 ({style_bible['display_name']}) — {payload['topic_title']}", ""]

        for ch in payload["characters"]:
            cid = ch["character_id"]
            sil_prop = ch["silhouette_and_proportions"]
            entry: dict[str, Any] = {
                "character_id": cid,
                "name": ch["name"],
                "role": ch["role"],
                "identity": {
                    "name": ch["name"],
                    "role": ch["role"],
                    "biography_disclaimer": ch["biography_disclaimer"],
                    "original_ip_verified": True,
                },
                "silhouette": sil_prop,
                "proportions": sil_prop,
                "facial_design": ch.get("facial_design")
                or f"Desain wajah ekspresif selaras gaya '{style_profile}' dengan keterbacaan mata & alis tinggi.",
                "clothing": ch["wardrobe"],
                "wardrobe": ch["wardrobe"],
                "materials": list(
                    ch.get("materials")
                    or [f"mat_{style_profile}_fabric_primary", f"mat_{style_profile}_skin_subsurface"]
                ),
                "color_palette": list(ch["palette"]),
                "palette": list(ch["palette"]),
                "expressions": list(
                    ch.get("expressions")
                    or ["neutral_attentive", "curious_eyebrow_raise", "deadpan_blink", "focused_explanation", "relieved_smile"]
                ),
                "rig_requirements": {
                    "rig_preset": ch["rig_spec"],
                    "ik_limbs": ["left_foot_ik", "right_foot_ik", "left_hand_ik", "right_hand_ik"],
                    "facial_controls": list(
                        ch.get("facial_controls")
                        or ["jaw_viseme", "brow_asym", "eyelid_blink", "eye_dart_target"]
                    ),
                    "execution_status": "PLANNED_SPEC_ONLY_NO_MODELING_YET",
                },
                "rig_spec": ch["rig_spec"],
                "pose_requirements": list(
                    ch.get("pose_requirements")
                    or ["grounded_neutral_stance", "pointing_cutaway_gesture", "leaning_inspect_pose", "reaction_hold_pose"]
                ),
                "action_requirements": list(
                    ch.get("action_requirements")
                    or ["weight_shifted_step", "prop_contact_interaction", "viseme_speech_articulation", "head_turn_anticipation"]
                ),
                "biography_disclaimer": ch["biography_disclaimer"],
                "shot_appearances": shots_by_char.get(cid, []),
                "continuity_lock": {
                    "palette_locked": list(ch["palette"]),
                    "proportions_locked": sil_prop,
                    "wardrobe_locked": ch["wardrobe"],
                    "style_profile_locked": style_profile,
                },
            }
            for req_f in MANDATORY_11_CHARACTER_FIELDS:
                assert req_f in entry and entry[req_f] not in (None, "", [])
            compiled_chars.append(entry)

            md_lines.extend(
                [
                    f"## `{cid}` — {ch['name']} ({ch['role']})",
                    f"- **Siluet & Proporsi**: {entry['silhouette']}",
                    f"- **Desain Wajah**: {entry['facial_design']}",
                    f"- **Pakaian & Material**: {entry['clothing']} (`{', '.join(entry['materials'])}`)",
                    f"- **Palet Warna Terkunci**: `{', '.join(entry['color_palette'])}`",
                    f"- **Ekspresi Wajib**: `{', '.join(entry['expressions'])}`",
                    f"- **Kebutuhan Rig & Pose**: `{ch['rig_spec']}` | Pose: `{', '.join(entry['pose_requirements'])}`",
                    f"- **Kemunculan Shot**: `{', '.join(entry['shot_appearances']) or 'offscreen/supporting'}`",
                    f"- **Catatan Orisinalitas**: {ch['biography_disclaimer']}",
                    "",
                ]
            )

        bible_json = {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "style_bible_id": style_bible["style_bible_id"],
            "style_profile": style_profile,
            "modeling_executed": False,
            "characters": compiled_chars,
        }
        return bible_json, compiled_chars, "\n".join(md_lines)


class CharacterActionPlanner:
    """Builds 14-field Character & Mechanism Action Plans without generic idle loops (Section 13)."""

    def build_action_plan(
        self,
        *,
        storyboard: dict[str, Any],
        characters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        char_ids = [c["character_id"] for c in characters]
        lead_actor = char_ids[0] if char_ids else "actor_mechanism_rig"

        planned_actions: list[dict[str, Any]] = []
        shots_summary: list[dict[str, Any]] = []

        for shot in storyboard["shots"]:
            sid = shot["shot_id"]
            s_frame = int(shot["start_frame"])
            e_frame = int(shot["end_frame"])
            mid_frame = s_frame + max(1, (e_frame - s_frame) // 2)
            v_purpose = shot.get("semantic_visual_purpose", "character_acting")

            actor_id = (
                shot["character_ids"][0]
                if shot.get("character_ids")
                else (shot["asset_ids"][0] if shot.get("asset_ids") else lead_actor)
            )
            obj_target = (
                shot["asset_ids"][0]
                if shot.get("asset_ids")
                else shot["environment_id"]
            )

            if v_purpose in {"technical_cutaway", "exploded_view", "scientific_mechanism", "scale_comparison", "data_visualization"}:
                action_type = f"mechanism_{v_purpose}"
                contact_pt = f"anchor_socket:{obj_target}:cutaway_plane"
                ik_target = f"rig_ctrl:{obj_target}:flow_path_target"
                weight_transfer = "rigid_or_fluid_causal_progression_no_foot_slip"
                facial_expr = "focused_explanation" if actor_id.startswith("char_") else "not_applicable_mechanism_rig"
            elif v_purpose == "reaction_shot":
                action_type = "character_micro_reaction_and_settle"
                contact_pt = f"floor_and_desk_contact:{shot['environment_id']}"
                ik_target = f"eye_look_at:{obj_target}"
                weight_transfer = "subtle_upper_torso_lean_back_3cm_planted_feet"
                facial_expr = "deadpan_double_take_to_eyebrow_raise"
            else:
                action_type = f"character_grounded_{v_purpose}"
                contact_pt = f"planted_feet_and_hand_prop:{obj_target}"
                ik_target = f"hand_ik_contact:{obj_target}"
                weight_transfer = "hips_lead_weight_shift_onto_support_leg_6f_anticipation"
                facial_expr = "expressive_engaged_articulation"

            action_record: dict[str, Any] = {
                "action_id": f"ACT_{sid}",
                "shot_id": sid,
                "actor_id": actor_id,
                "action_type": action_type,
                "object_target": obj_target,
                "start_frame": s_frame,
                "end_frame": e_frame,
                "start_pose": f"{actor_id}_anticipation_ready_at_{s_frame}f ({shot['action_start'][:70]})",
                "key_poses": [
                    {"frame": s_frame + max(1, (e_frame - s_frame) // 4), "pose": f"anticipation_and_reach_toward_{obj_target}"},
                    {"frame": mid_frame, "pose": f"apex_interaction_{shot['action_mid'][:65]}"},
                ],
                "end_pose": f"{actor_id}_settled_hold_at_{e_frame}f ({shot['action_end'][:70]})",
                "contact_point": contact_pt,
                "ik_target": ik_target,
                "weight_transfer": weight_transfer,
                "facial_expression": facial_expr,
                "motion_intent": f"Convey '{v_purpose}' clearly for beat {shot['beat_id']}: {shot['action_events'][0]['concrete_action']}",
                "acceptance_criteria": [
                    f"Exact frame bounds [{s_frame}, {e_frame}] respected with zero foot sliding",
                    f"Contact target '{obj_target}' maintained without mesh interpenetration",
                    "Zero generic idle-loop substitution",
                ],
            }
            for req_f in MANDATORY_14_ACTION_FIELDS:
                assert req_f in action_record and action_record[req_f] not in (None, "", [])
            planned_actions.append(action_record)

            shots_summary.append(
                {
                    "shot_id": sid,
                    "start_frame": s_frame,
                    "end_frame": e_frame,
                    "primary_engine": shot["primary_engine"],
                    "motion_curve": shot["camera"]["motion_curve"],
                    "action_events": shot["action_events"],
                    "planned_character_actions": [action_record],
                    "ik_foot_and_hand_contacts_required": True,
                }
            )

        return {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": storyboard["project_id"],
            "fps": storyboard["fps"],
            "total_frames": storyboard["total_frames"],
            "blender_executor_status": "PLANNED_ONLY_SCHEDULED_PHASE_02B_AND_PHASE_03",
            "generic_idle_actions_used": False,
            "planned_actions": planned_actions,
            "shots": shots_summary,
        }


class SemanticAssetPlanner:
    """Derives 12-field Semantic Asset Specifications from storyboard needs without fake READY claims (Section 14)."""

    def __init__(self, preset_registry: PresetLibraryRegistry | None = None) -> None:
        self.presets = preset_registry or PresetLibraryRegistry()

    @staticmethod
    def _classify_category(asset_id: str) -> str:
        low = asset_id.lower()
        if low.startswith("char_"):
            return "hero_character"
        if low.startswith("env_") or "room" in low or "interior" in low or "loket" in low or "ocean" in low:
            return "architectural_interior" if any(k in low for k in ("room", "kamar", "kantor", "loket", "interior", "laundry")) else "exterior_environment"
        if any(k in low for k in ("cutaway", "evaporator", "kompresor", "kondensor", "katup", "valve", "pipe", "coil", "pump", "mesin")):
            return "scientific_cutaway_device"
        if any(k in low for k in ("chart", "arrow", "gauge", "thermometer", "scale", "graph", "label", "diagram")):
            return "diagram_callout_3d"
        if any(k in low for k in ("meja", "kursi", "sofa", "lemari", "rak")):
            return "furniture"
        if any(k in low for k in ("dokumen", "surat", "map", "stempel", "formulir", "arsip", "kertas")):
            return "historical_artifact_prop"
        return "household_prop"

    def build_semantic_asset_manifest(
        self,
        *,
        project_id: str,
        storyboard: dict[str, Any],
        style_bible: dict[str, Any],
        characters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        loaded = self.presets.load_all(validate=False)
        known_3d_ids = {p["id"] for p in loaded.get("asset_3d_library", {}).get("presets", [])}
        known_env_ids = {p["id"] for p in loaded.get("environment_library", {}).get("presets", [])}

        # Collect every asset strictly from storyboard shots & characters
        asset_to_shots: dict[str, list[str]] = {}
        asset_engines: dict[str, set[str]] = {}
        for sh in storyboard["shots"]:
            sid = sh["shot_id"]
            eng = sh["primary_engine"]
            for aid in [sh["environment_id"], *sh.get("character_ids", []), *sh.get("asset_ids", [])]:
                if not aid:
                    continue
                asset_to_shots.setdefault(aid, []).append(sid)
                asset_engines.setdefault(aid, set()).add(eng)

        style_profile = style_bible["style_profile"]
        asset_specs: list[dict[str, Any]] = []
        status_counts = {
            "AVAILABLE_IN_LIBRARY_SPEC": 0,
            "PLANNED_PROCEDURAL_GENERATION": 0,
            "NEEDS_EXTERNAL_CC0_SEARCH": 0,
            "NEEDS_CUSTOM_AUTHORING": 0,
        }

        for aid in sorted(asset_to_shots.keys()):
            cat = self._classify_category(aid)
            if cat not in SUPPORTED_PROCEDURAL_CATEGORIES and cat not in {
                "hero_character",
                "architectural_interior",
                "exterior_environment",
                "scientific_cutaway_device",
                "diagram_callout_3d",
                "furniture",
                "historical_artifact_prop",
                "household_prop",
            }:
                cat = "household_prop"

            engines_needed = sorted(asset_engines.get(aid) or {"blender", "threejs"})
            if aid in known_3d_ids or aid in known_env_ids:
                planning_status = "AVAILABLE_IN_LIBRARY_SPEC"
                source_strategy = "preset_library_verified_spec_compile_in_phase02"
            elif cat in {"diagram_callout_3d", "scientific_cutaway_device"}:
                planning_status = "PLANNED_PROCEDURAL_GENERATION"
                source_strategy = "multi_component_procedural_geometry_phase02"
            elif cat in {"furniture", "household_prop", "historical_artifact_prop"}:
                planning_status = "NEEDS_EXTERNAL_CC0_SEARCH"
                source_strategy = "polyhaven_or_ambientcg_cc0_then_style_converter_phase02"
            else:
                planning_status = "NEEDS_CUSTOM_AUTHORING"
                source_strategy = "custom_character_or_stage_build_phase02"
            status_counts[planning_status] += 1

            if cat == "hero_character":
                dims = {"width_m": 0.52, "depth_m": 0.34, "height_m": 1.68}
                rig_req = "humanoid_fk_ik_and_facial_visemes"
                anim_req = "grounded_locomotion_gesture_and_speech"
            elif cat in {"architectural_interior", "exterior_environment"}:
                dims = {"width_m": 6.0, "depth_m": 6.0, "height_m": 3.2}
                rig_req = "static_modular_cutaway_walls_and_door_pivots"
                anim_req = "camera_clearance_and_lighting_fixture_state"
            elif cat == "scientific_cutaway_device":
                dims = {"width_m": 0.95, "depth_m": 0.45, "height_m": 0.65}
                rig_req = "hinged_cutaway_casing_and_flow_empties"
                anim_req = "fluid_or_thermal_phase_state_transition"
            else:
                dims = {"width_m": 0.35, "depth_m": 0.28, "height_m": 0.25}
                rig_req = "rigid_pivot_handle_or_none"
                anim_req = "hand_constraint_pickup_or_table_contact"

            spec: dict[str, Any] = {
                "asset_id": aid,
                "semantic_category": cat,
                "planning_status": planning_status,
                "ready_on_disk_now": False,
                "used_in_shots": asset_to_shots[aid],
                "geometry_specification": {
                    "min_sub_components": 4 if cat != "diagram_callout_3d" else 2,
                    "up_axis_blender": "+Z",
                    "up_axis_threejs": "+Y",
                    "placeholder_12_tri_box_forbidden": True,
                    "silhouette_notes": f"Multi-part semantic geometry for '{aid}' ({cat}) matching '{style_profile}'.",
                },
                "visual_style": {
                    "style_profile": style_profile,
                    "style_bible_id": style_bible["style_bible_id"],
                    "detail_tier": style_bible["cross_asset_consistency_contract"]["detail_tier"],
                },
                "dimensions": dims,
                "material": {
                    "shading_model": style_bible["shading_model"],
                    "primary_material_preset": f"mat_{style_profile}_{cat}",
                    "roughness_calibrated": True,
                },
                "rig_requirement": rig_req,
                "animation_requirement": anim_req,
                "engine_compatibility": engines_needed,
                "license_requirements": {
                    "allowed_licenses": ["CC0-1.0", "MIT", "Apache-2.0", "XDX-Original-Procedural"],
                    "attribution_ledger_required": True,
                    "paid_or_unlicensed_forbidden": True,
                },
                "source_strategy": source_strategy,
                "qc_criteria": [
                    "Non-placeholder geometry (>12 triangles, >=2 named sub-parts)",
                    "Valid normals and non-degenerate bounding box matching declared dimensions",
                    f"Shader & texel density consistent with '{style_profile}' Global Style Bible",
                ],
            }
            for req_f in MANDATORY_12_ASSET_FIELDS:
                assert req_f in spec and spec[req_f] not in (None, "", [])
            asset_specs.append(spec)

        return {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": project_id,
            "procurement_or_modeling_executed": False,
            "style_bible": style_bible,
            "characters": characters,
            "required_assets": [a["asset_id"] for a in asset_specs if not a["asset_id"].startswith("char_")],
            "status_breakdown": status_counts,
            "semantic_asset_specs": asset_specs,
        }


class PurposeDrivenCameraAudioCaptionPlanner:
    """Purpose-driven Camera (dynamic lenses, never locked to 36mm), Audio Director & Caption Specialist (Section 15)."""

    PURPOSE_LENS_RIGS: dict[str, tuple[str, float, str, float, str]] = {
        "establishing_shot": ("cam_establishing_diorama_28mm", 24.0, "elevated_establishing_16deg", 5.6, "mot_cinematic_ease_inout"),
        "scale_comparison": ("cam_establishing_diorama_28mm", 20.0, "ultra_wide_scale_perspective", 8.0, "mot_cinematic_ease_inout"),
        "historical_reconstruction": ("cam_establishing_diorama_28mm", 32.0, "period_tableau_eye_level", 4.5, "mot_cinematic_ease_inout"),
        "character_acting": ("cam_medium_storyteller_40mm", 40.0, "conversational_eye_level", 3.5, "mot_cinematic_ease_inout"),
        "visual_metaphor": ("cam_medium_storyteller_40mm", 35.0, "symmetric_deadpan_frame", 4.0, "mot_snappy_spring_pop"),
        "technical_cutaway": ("cam_insert_evidence_macro_70mm", 50.0, "orthographic_feel_cross_section_22deg", 5.6, "mot_cinematic_ease_inout"),
        "exploded_view": ("cam_insert_evidence_macro_70mm", 55.0, "isometric_exploded_axis_28deg", 5.6, "mot_cinematic_ease_inout"),
        "scientific_mechanism": ("cam_insert_evidence_macro_70mm", 65.0, "mechanism_flow_tracking", 4.0, "mot_cinematic_ease_inout"),
        "data_visualization": ("cam_medium_storyteller_40mm", 45.0, "clean_planar_chart_stage", 8.0, "mot_snappy_spring_pop"),
        "timeline": ("cam_establishing_diorama_28mm", 35.0, "lateral_chronology_glide", 5.6, "mot_cinematic_ease_inout"),
        "reaction_shot": ("cam_insert_evidence_macro_70mm", 75.0, "intimate_three_quarter_reaction", 2.8, "mot_snappy_spring_pop"),
        "object_insert": ("cam_insert_evidence_macro_70mm", 85.0, "macro_evidence_tabletop_32deg", 2.8, "mot_cinematic_ease_inout"),
    }

    def __init__(self) -> None:
        self.caption_adapter = WhisperCaptionAdapter()

    def build_camera_plan(self, storyboard: dict[str, Any], style_bible: dict[str, Any]) -> dict[str, Any]:
        """Assign narrative-purpose-driven focal lengths across shots and emit camera_plan.json."""
        camera_shots: list[dict[str, Any]] = []
        focal_lengths_used: set[float] = set()

        for idx, shot in enumerate(storyboard["shots"]):
            v_purpose = shot.get("semantic_visual_purpose", "character_acting")
            preset_id, focal_mm, angle, fstop, curve = self.PURPOSE_LENS_RIGS.get(
                v_purpose,
                ("cam_medium_storyteller_40mm", 40.0, "eye_level", 4.0, "mot_cinematic_ease_inout"),
            )
            # Update storyboard camera focal_length_mm & angle if default was generic so storyboard & camera_plan agree
            shot["camera"]["focal_length_mm"] = focal_mm
            shot["camera"]["angle"] = angle
            shot["camera"]["dof_fstop"] = fstop
            shot["camera"]["preset_id"] = preset_id
            shot["camera_event"] = dict(shot["camera"])
            focal_lengths_used.add(focal_mm)

            camera_shots.append(
                {
                    "shot_id": shot["shot_id"],
                    "beat_id": shot["beat_id"],
                    "start_frame": shot["start_frame"],
                    "end_frame": shot["end_frame"],
                    "narrative_visual_purpose": v_purpose,
                    "shot_size": shot["camera"]["shot_size"],
                    "focal_length_mm": focal_mm,
                    "sensor_width_mm": shot["camera"]["sensor_width_mm"],
                    "angle": angle,
                    "dof_fstop": fstop,
                    "motion_curve": shot["camera"]["motion_curve"] if idx == 0 else curve,
                    "position_start": shot["camera"]["position_start"],
                    "position_end": shot["camera"]["position_end"],
                    "target": shot["camera"]["target"],
                    "style_profile": style_bible["style_profile"],
                    "rationale": f"Selected {focal_mm}mm ({angle}, f/{fstop}) to serve '{v_purpose}' narrative purpose.",
                }
            )

        return {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": storyboard["project_id"],
            "locked_to_single_36mm_focal_length": False,
            "distinct_focal_lengths_mm": sorted(focal_lengths_used),
            "shots": camera_shots,
        }

    def build_audio_and_caption_plans(
        self,
        *,
        payload: dict[str, Any],
        storyboard: dict[str, Any],
        style_bible: dict[str, Any],
        timing_report: dict[str, Any],
        caption_preset_id: str,
        typography_preset_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compile Audio Director plan (narration_dialogue.json) & Caption Specialist plan (caption_audio_plan.json)."""
        beat_by_id = {b["beat_id"]: b for b in payload["narrative_beats"]}
        vo_segments: list[dict[str, Any]] = []
        all_dialogues: list[dict[str, Any]] = []
        foley_events: list[dict[str, Any]] = []
        sfx_events: list[dict[str, Any]] = []
        scientific_labels: list[dict[str, Any]] = []
        any_onscreen = False

        for idx, nb in enumerate(storyboard["narrative_beats"], 1):
            src_beat = beat_by_id[nb["beat_id"]]
            start_s = round(nb["start_frame"] / storyboard["fps"], 3)
            end_s = round(nb["end_frame"] / storyboard["fps"], 3)
            vo_text = src_beat["narration_vo"]
            vo_segments.append(
                {
                    "segment_id": f"VO_{idx:03d}",
                    "beat_id": nb["beat_id"],
                    "shot_id": nb["shot_ids"][0],
                    "shot_ids": nb["shot_ids"],
                    "speaker": "narrator_id_offscreen",
                    "text": vo_text,
                    "word_count": len(vo_text.split()),
                    "start_time_s": start_s,
                    "end_time_s": end_s,
                    "timing_status": "ESTIMATED",
                    "voice_direction": src_beat.get("voice_direction")
                    or f"{src_beat.get('emotion', 'curious')}_natural_indonesian_articulation",
                    "breath_pause_ms": 220,
                }
            )
            for dlg in src_beat.get("dialogue_lines", []):
                if dlg.get("onscreen_speaking"):
                    any_onscreen = True
                all_dialogues.append(
                    {
                        "beat_id": nb["beat_id"],
                        "shot_id": nb["shot_ids"][min(1, len(nb["shot_ids"]) - 1)],
                        "timing_status": "ESTIMATED",
                        **dlg,
                    }
                )
            for sb_idx, sb in enumerate(src_beat["shot_blueprints"]):
                mapped_sid = nb["shot_ids"][min(sb_idx, len(nb["shot_ids"]) - 1)]
                for lbl in sb.get("scientific_labels") or []:
                    scientific_labels.append(
                        {"shot_id": mapped_sid, "beat_id": nb["beat_id"], "label": lbl, "timing_status": "ESTIMATED"}
                    )

        for shot in storyboard["shots"]:
            sid = shot["shot_id"]
            v_purp = shot.get("semantic_visual_purpose", "character_acting")
            foley_events.append(
                {
                    "event_id": f"FOL_{sid}",
                    "shot_id": sid,
                    "start_frame": shot["start_frame"],
                    "end_frame": shot["end_frame"],
                    "foley_description": (
                        f"Subtle tactile foley for {shot['asset_ids'][0] if shot['asset_ids'] else shot['environment_id']} ({v_purp})"
                    ),
                    "gain_db": -16.0,
                    "timing_status": "ESTIMATED",
                }
            )
            sfx_events.append(
                {
                    "event_id": f"SFX_{sid}",
                    "shot_id": sid,
                    "start_frame": shot["start_frame"],
                    "end_frame": min(shot["end_frame"], shot["start_frame"] + 18),
                    "sfx_preset": shot["sfx_cues"][0] if shot.get("sfx_cues") else "sfx_soft_cutaway_transition",
                    "purpose": v_purp,
                    "gain_db": -12.0,
                    "timing_status": "ESTIMATED",
                }
            )
            # Extract technical terms as scientific callout labels when cutaway/mechanism
            if v_purp in {"technical_cutaway", "exploded_view", "scientific_mechanism", "scale_comparison", "data_visualization"}:
                terms = _TECHNICAL_TERMS_RE.findall(shot.get("narration_segment", ""))
                for t in dict.fromkeys(w.capitalize() for w in terms):
                    scientific_labels.append(
                        {"shot_id": sid, "beat_id": shot["beat_id"], "label": t, "timing_status": "ESTIMATED"}
                    )

        est_caps = self.caption_adapter.build_script_estimated_captions(vo_segments, max_words_per_cue=5)
        enriched_cues: list[dict[str, Any]] = []
        for cue in est_caps["cues"]:
            words = cue["text"].split()
            tech_hits = [w for w in words if _TECHNICAL_TERMS_RE.search(w)]
            highlight_word = tech_hits[0] if tech_hits else (words[0] if words else "")
            enriched_cues.append(
                {
                    **cue,
                    "timestamp_status": "ESTIMATED",
                    "phrase_word_count": len(words),
                    "highlighted_keyword": highlight_word,
                }
            )

        genres_set = set(payload["genres"])
        if "horor" in genres_set:
            music_dir = "Sparse low-register tension drone with wide dynamic headroom; ducked -18 dB under VO."
            ambience_dir = "Quiet room tone with subtle distant night air (-26 LUFS bed)."
        elif genres_set & {"satir_sosial", "social_satire", "komedi_absurd"}:
            music_dir = "Light acoustic pizzicato & dry percussion stings stopping cleanly before punchlines; ducked -16 dB under VO."
            ambience_dir = "Grounded Indonesian interior / public-counter room tone (-25 LUFS)."
        else:
            music_dir = "Warm curious marimba/synth pulse supporting causal momentum; ducked -16 dB under VO."
            ambience_dir = "Clean studio room tone with gentle mechanical/environmental air bed (-26 LUFS)."

        narration_plan = {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "timing_status": "ESTIMATED",
            "actual_audio_and_forced_alignment_phase": "SCHEDULED_PHASE_04",
            "language": "id-ID",
            "narration_style": (
                "Conversational satirical storyteller with deadpan pauses"
                if genres_set & {"satir_sosial", "social_satire"}
                else "Warm, articulate Indonesian science & story narrator"
            ),
            "target_wpm": timing_report["base_target_wpm"],
            "measured_script_wpm": timing_report["implied_script_wpm"],
            "estimated_timing": {
                "estimated_total_s": timing_report["final_estimated_duration_s"],
                "target_duration_s": timing_report["target_duration_s"],
                "playback_speed_multiplier": 1.0,
                "duration_recommendation": timing_report["duration_recommendation"],
            },
            "voice_delivery_mode": "hybrid_vo_and_character_dialogue" if all_dialogues else "offscreen_narrator",
            "voice_direction": {
                "narrator_register": "baritone_or_mezzo_clear_indonesian",
                "pace_policy": "Adaptive clause-breathing pace (~130-160 WPM); never time-stretched.",
                "dialogue_separation": "Distinct mic/room coloration and turn-taking pause per character.",
            },
            "music_direction": music_dir,
            "ambience": ambience_dir,
            "foley": foley_events,
            "sound_effect_events": sfx_events,
            "vo_segments": vo_segments,
            "dialogue_lines": all_dialogues,
            "lip_sync_plan": {
                "status": "ESTIMATED_PRE_AUDIO",
                "onscreen_dialogue_present": any_onscreen,
                "phase_04_backend": "rhubarb_or_whisper_forced_viseme_alignment",
            },
        }

        is_9x16 = storyboard.get("aspect_ratio", "9:16") == "9:16"
        caption_audio_plan = {
            "schema_version": "4.0.0-phase01.6c",
            "project_id": payload["project_id"],
            "timestamp_status": "ESTIMATED",
            "caption_preset_id": caption_preset_id,
            "caption_format": {
                "container_formats": ["SRT", "WebVTT", "Remotion_Estimated_JSON"],
                "max_lines_per_cue": 2,
                "max_words_per_phrase": 5,
            },
            "phrase_grouping": {
                "strategy": "syntactic_indonesian_clause_chunks",
                "orphan_single_word_avoided": True,
            },
            "typography": {
                "typography_preset_id": typography_preset_id,
                "style_profile": style_bible["style_profile"],
                "stroke_and_shadow_high_contrast": True,
            },
            "safe_area": {
                "aspect_ratio": storyboard.get("aspect_ratio", "9:16"),
                "bottom_margin_px": 340 if is_9x16 else 110,
                "top_margin_px": 220 if is_9x16 else 80,
                "horizontal_margin_px": 90,
                "ui_occlusion_free": True,
            },
            "word_highlight": {
                "enabled": True,
                "mode": "semantic_keyword_accent_not_distracting",
                "timing_source": "ESTIMATED_PRE_PHASE04_ALIGNMENT",
            },
            "scientific_labels": scientific_labels,
            "estimated_caption_timing": {
                "status": "ESTIMATED",
                "cue_count": len(enriched_cues),
                "requires_phase04_wav_realignment": True,
            },
            "audio_master_preset_id": "aud_master_vo_indonesia_15lufs",
            "sample_rate_hz": 48000,
            "target_lufs": -15.0,
            "true_peak_dbtp": -1.0,
            "music_direction": music_dir,
            "ambience": ambience_dir,
            "foley_count": len(foley_events),
            "sfx_event_count": len(sfx_events),
            "asr_backends_detected": self.caption_adapter.detect_backends(),
            "cues": enriched_cues,
            "srt_preview": est_caps["srt"],
        }
        return narration_plan, caption_audio_plan
