"""Validator, Hierarchical Storyboard Compiler & Hybrid Production Orchestrator (v3.4).

Architectural Separation (Phase 01.5 Upgrade):
- The AI Agent acts as Researcher, Writer, Dramatist, Historian, and Director producing a
  structured `CreativeProductionPayload` (`schemas/creative_intelligence.schema.json`).
- Python acts strictly as Validator, Deterministic Frame Compiler, State Manager, and
  Hybrid Engine Orchestrator — rejecting template placeholders, unverified factual claims,
  and >10s shots fail-closed.
"""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

import jsonschema

from adapters.caption_lipsync_adapter import RhubarbLipSyncAdapter, WhisperCaptionAdapter
from intelligence.asset_management import GLOBAL_STYLE_BIBLE_V3_4, atomic_write_bytes
from intelligence.authored_showcase_150s import build_authored_time_perception_payload
from intelligence.state_and_approval import (
    ProjectStateManager,
    compute_package_digest,
    format_structured_approval_command,
)
from libraries.loader import PresetLibraryRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"

SUPPORTED_GENRES: tuple[str, ...] = (
    "explainer",
    "edukasi",
    "sejarah",
    "biografi",
    "dokumenter",
    "storytelling",
    "horor",
    "komedi_absurd",
)

FACTUAL_GENRES: frozenset[str] = frozenset(
    {"explainer", "edukasi", "sejarah", "biografi", "dokumenter"}
)

TRANSITION_OVERLAP_FRAMES: dict[str, int] = {
    "trans_hard_cut_zero": 0,
    "trans_whip_pan_cutaway_6f": 6,
    "trans_cross_dissolve_12f": 12,
}

PLACEHOLDER_PATTERNS = re.compile(
    r"("
    r"\[(?:HOOK_ANOMALY|CORE_QUESTION|MECHANISM_CUTAWAY|EVERYDAY_CONSEQUENCE|ESCALATION_OR_TWIST|"
    r"PAYOFF_CALLBACK|PLACEHOLDER|TODO|TBD|ISI_NASKAH|B[0-9]{2})\]|"
    r"staging\s+awal|"
    r"settle\s+pose\s*&\s*transisi\s+bersih|"
    r"hook\s+visual\s+langsung\s+0-3\s+detik\s+di\s+ruang\s+miniatur\s+tanpa\s+basa-basi|"
    r"pertanyaan\s+inti\s+yang\s+memicu\s+rasa\s+penasaran|"
    r"pending_external_verification|"
    r"lorem\s+ipsum|"
    r"<placeholder>|"
    r"\bTODO\b|\bTBD\b"
    r")",
    re.IGNORECASE,
)

INDONESIAN_STOPWORDS: frozenset[str] = frozenset(
    {
        "yang", "dan", "dari", "pada", "untuk", "dengan", "dalam", "saat", "ketika",
        "mengapa", "kenapa", "bagaimana", "apakah", "kita", "kamu", "mereka", "akan",
        "bisa", "lebih", "atau", "juga", "tidak", "bukan", "hingga", "sampai", "oleh",
        "sebagai", "adalah", "itu", "ini", "para", "satu", "dua", "tiga",
    }
)

GENRE_PROFILES: dict[str, dict[str, Any]] = {
    "explainer": {
        "hook_formula": "visual_anomaly_or_counterintuitive_object_0_3s",
        "lighting": "light_cozy_warm_interior",
        "vfx": "vfx_aces_diorama_clean",
        "caption": "cap_xdx_bold_stroke_9x16",
        "typography": "typo_jakarta_modern_explainer",
        "requires_hero_character": False,
        "pacing_wpm": 145,
    },
    "edukasi": {
        "hook_formula": "concrete_everyday_problem_0_3s",
        "lighting": "light_crisp_tropical_daylight",
        "vfx": "vfx_aces_diorama_clean",
        "caption": "cap_xdx_bold_stroke_9x16",
        "typography": "typo_jakarta_modern_explainer",
        "requires_hero_character": True,
        "pacing_wpm": 142,
    },
    "sejarah": {
        "hook_formula": "archival_artifact_or_pivotal_year_cutaway_0_3s",
        "lighting": "light_cozy_warm_interior",
        "vfx": "vfx_historical_warm_sepia_grain",
        "caption": "cap_documentary_clean_box",
        "typography": "typo_historical_archival_serif",
        "requires_hero_character": True,
        "pacing_wpm": 135,
    },
    "biografi": {
        "hook_formula": "defining_turning_point_moment_0_3s",
        "lighting": "light_cozy_warm_interior",
        "vfx": "vfx_historical_warm_sepia_grain",
        "caption": "cap_documentary_clean_box",
        "typography": "typo_historical_archival_serif",
        "requires_hero_character": True,
        "pacing_wpm": 136,
    },
    "dokumenter": {
        "hook_formula": "measured_contrast_or_field_evidence_0_3s",
        "lighting": "light_crisp_tropical_daylight",
        "vfx": "vfx_aces_diorama_clean",
        "caption": "cap_documentary_clean_box",
        "typography": "typo_historical_archival_serif",
        "requires_hero_character": False,
        "pacing_wpm": 138,
    },
    "storytelling": {
        "hook_formula": "in_medias_res_character_dilemma_0_3s",
        "lighting": "light_cozy_warm_interior",
        "vfx": "vfx_aces_diorama_clean",
        "caption": "cap_xdx_bold_stroke_9x16",
        "typography": "typo_jakarta_modern_explainer",
        "requires_hero_character": True,
        "pacing_wpm": 140,
    },
    "horor": {
        "hook_formula": "uncanny_sensory_detail_in_familiar_space_0_3s",
        "lighting": "light_horror_chiaroscuro",
        "vfx": "vfx_horror_desat_fog",
        "caption": "cap_horror_minimal_serif",
        "typography": "typo_horror_cinzel_tension",
        "requires_hero_character": True,
        "pacing_wpm": 128,
    },
    "komedi_absurd": {
        "hook_formula": "deadpan_mundane_setup_with_absurd_scale_0_3s",
        "lighting": "light_crisp_tropical_daylight",
        "vfx": "vfx_aces_diorama_clean",
        "caption": "cap_xdx_bold_stroke_9x16",
        "typography": "typo_jakarta_modern_explainer",
        "requires_hero_character": True,
        "pacing_wpm": 150,
    },
}


class UnverifiedResearchError(ValueError):
    """Raised when factual production claims lack verifiable https:// citations or remain pending."""


class PlaceholderScriptError(ValueError):
    """Raised when narration, dialogue, or visual action contains placeholders or lacks topic relevance."""


class UniversalMasterPromptEngine:
    """Synthesizes multi-genre parameters, operational guardrails, and Global Style Bible."""

    def blend_genres(self, genres: list[str]) -> dict[str, Any]:
        if not genres:
            raise ValueError("At least one genre must be specified")
        for g in genres:
            if g not in GENRE_PROFILES:
                raise ValueError(f"Unsupported genre '{g}'. Supported: {SUPPORTED_GENRES}")

        lead = GENRE_PROFILES[genres[0]]
        avg_wpm = round(sum(GENRE_PROFILES[g]["pacing_wpm"] for g in genres) / len(genres))
        needs_hero = any(GENRE_PROFILES[g]["requires_hero_character"] for g in genres)
        return {
            "genres": genres,
            "is_hybrid_genre": len(genres) > 1,
            "requires_factual_verification": any(g in FACTUAL_GENRES for g in genres),
            "dominant_genre": genres[0],
            "hook_formula": lead["hook_formula"],
            "default_lighting_preset": "light_horror_chiaroscuro" if "horor" in genres else lead["lighting"],
            "default_vfx_preset": "vfx_horror_desat_fog" if "horor" in genres else lead["vfx"],
            "default_caption_preset": lead["caption"],
            "default_typography_preset": lead["typography"],
            "requires_hero_character": needs_hero,
            "target_wpm": max(128, min(155, avg_wpm)),
            "style_bible": GLOBAL_STYLE_BIBLE_V3_4,
        }


class TopicResearchEngine:
    """Validates AI-authored research dossiers and computes empirical verification metrics (no fixed scores)."""

    DISALLOWED_URL_MARKERS = ("pending", "todo", "tbd", "example.com", "placeholder", "localhost", "unverified")

    def validate_and_compile_research(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        genres = payload["genres"]
        requires_facts = any(g in FACTUAL_GENRES for g in genres)
        res = payload["topic_research"]

        if res["research_status"] == "INCOMPLETE_BLOCKED":
            raise UnverifiedResearchError("Research dossier is marked INCOMPLETE_BLOCKED; cannot compile production package.")
        if requires_facts and res["research_status"] != "VERIFIED_COMPLETE":
            raise UnverifiedResearchError(
                f"Factual genres {genres} require research_status='VERIFIED_COMPLETE' (got '{res['research_status']}')."
            )

        claims = res["claims"]
        verified_count = 0
        unique_urls: set[str] = set()

        for c in claims:
            url = str(c["source_url"]).strip()
            title = str(c["source_title"]).strip()
            stmt = str(c["statement"]).strip()
            status = str(c["epistemic_status"])

            if PLACEHOLDER_PATTERNS.search(stmt) or PLACEHOLDER_PATTERNS.search(title):
                raise UnverifiedResearchError(f"Placeholder detected in research claim {c['claim_id']}.")

            if requires_facts:
                if status in {"unverified_claim", "declared_fiction"}:
                    raise UnverifiedResearchError(
                        f"Claim {c['claim_id']} has epistemic_status='{status}', unacceptable for factual genre {genres}."
                    )
                if not url.startswith("https://") or any(m in url.lower() for m in self.DISALLOWED_URL_MARKERS):
                    raise UnverifiedResearchError(
                        f"Claim {c['claim_id']} lacks a verifiable https:// primary/institutional source URL: {url!r}"
                    )
                verified_count += 1
                unique_urls.add(url)
            else:
                if status != "unverified_claim":
                    verified_count += 1

        citation_coverage_ratio = round(verified_count / max(1, len(claims)), 4)
        topic_obj = {
            "topic": payload["topic_title"],
            "genres": genres,
            "epistemic_mode": res["epistemic_mode"],
            "research_status": res["research_status"],
            "metrics_measured": {
                "total_claims": len(claims),
                "verified_claims": verified_count,
                "unique_verified_sources": len(unique_urls),
                "citation_coverage_ratio": citation_coverage_ratio,
            },
            "claims": claims,
        }

        md = "\n".join(
            [
                f"# Dossier Riset Terverifikasi — {payload['topic_title']}",
                "",
                f"- **Genre Aktif**: `{', '.join(genres)}`",
                f"- **Status Riset**: `{res['research_status']}` (`{res['epistemic_mode']}`)",
                f"- **Rasio Cakupan Sitasi Terukur**: `{citation_coverage_ratio * 100:.1f}%` ({verified_count}/{len(claims)} klaim, {len(unique_urls)} sumber unik)",
                "",
                "## Ringkasan Kajian",
                res["summary"],
                "",
                "## Klaim Faktual & Sumber Primer/Institusional",
                *[
                    f"- **`{c['claim_id']}` [{c['epistemic_status']}]**: {c['statement']}\n"
                    f"  - Sumber: *{c['source_title']}* ({c['publication_year']}) — {c['source_url']}"
                    for c in claims
                ],
                "",
            ]
        )
        return topic_obj, md


class CreativePayloadValidator:
    """Validates structured AI creative payloads against JSON Schema, anti-placeholder rules, and topic relevance."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        sdir = schemas_dir or SCHEMAS_DIR
        self._schema = json.loads((sdir / "creative_intelligence.schema.json").read_text(encoding="utf-8"))

    @staticmethod
    def _extract_domain_keywords(text: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Z]{4,}", text.lower())
        return {t for t in tokens if t not in INDONESIAN_STOPWORDS}

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        jsonschema.validate(instance=payload, schema=self._schema)

        topic_title = payload["topic_title"].strip()
        domain_terms = (
            self._extract_domain_keywords(topic_title)
            | self._extract_domain_keywords(payload["blueprint"]["premise"])
            | self._extract_domain_keywords(" ".join(c["statement"] for c in payload["topic_research"]["claims"]))
        )

        all_spoken_words: list[str] = []
        all_actions_text: list[str] = []

        for beat in payload["narrative_beats"]:
            vo = beat["narration_vo"].strip()
            if PLACEHOLDER_PATTERNS.search(vo):
                raise PlaceholderScriptError(f"Placeholder or beat-label instruction detected in {beat['beat_id']} narration: {vo!r}")
            if vo.lower() == topic_title.lower() or len(vo.split()) < 6:
                raise PlaceholderScriptError(f"Narration in {beat['beat_id']} is too short or merely repeats topic title.")
            all_spoken_words.extend(vo.split())

            for dlg in beat.get("dialogue_lines", []):
                line = dlg["line"].strip()
                if PLACEHOLDER_PATTERNS.search(line):
                    raise PlaceholderScriptError(f"Placeholder detected in character dialogue ({dlg['speaker_id']}): {line!r}")
                all_spoken_words.extend(line.split())

            for sb in beat["shot_blueprints"]:
                act = sb["concrete_action"].strip()
                subj = sb["visual_subject"].strip()
                if PLACEHOLDER_PATTERNS.search(act) or PLACEHOLDER_PATTERNS.search(subj):
                    raise PlaceholderScriptError(f"Generic/placeholder visual action in {beat['beat_id']}: {act!r}")
                if not sb.get("props"):
                    raise PlaceholderScriptError(f"Shot blueprint in {beat['beat_id']} must specify concrete 3D/visual props.")
                all_actions_text.append(f"{subj} {act}")

        script_keywords = self._extract_domain_keywords(" ".join(all_spoken_words))
        action_keywords = self._extract_domain_keywords(" ".join(all_actions_text))

        if domain_terms and len(script_keywords & domain_terms) < 2:
            raise PlaceholderScriptError("Spoken narration/dialogue lacks lexical relevance to the researched topic.")
        if domain_terms and len(action_keywords & domain_terms) < 1:
            raise PlaceholderScriptError("Visual actions lack concrete relevance to the researched topic/premise.")

        return {
            "spoken_word_count": len(all_spoken_words),
            "domain_keyword_overlap_script": len(script_keywords & domain_terms),
            "domain_keyword_overlap_actions": len(action_keywords & domain_terms),
        }


class StoryScriptIntelligence:
    """Formats validated AI-authored Blueprint & Natural Indonesian Script into Markdown artifacts."""

    def compile_blueprint_and_script_markdown(
        self,
        payload: dict[str, Any],
        *,
        genre_blend: dict[str, Any],
    ) -> tuple[str, str]:
        bp = payload["blueprint"]
        beats = payload["narrative_beats"]

        blueprint_md = "\n".join(
            [
                f"# Universal Production Blueprint v3.4 — {payload['topic_title']}",
                "",
                f"- **Genre Terpadu**: `{', '.join(payload['genres'])}`",
                f"- **Target Durasi Master**: `{payload['target_duration_s']} detik`",
                f"- **Premis Utama**: {bp['premise']}",
                f"- **Hook Visual (0–3s)**: {bp['hook_0_3s_visual']}",
                f"- **Hook Lisan (0–3s)**: \"{bp['hook_0_3s_spoken']}\"",
                f"- **Mekanisme Explainer**: {bp['explainer_mechanism']}",
                f"- **Strategi Humor**: {bp['humor_strategy']}",
                f"- **Catatan Sejarah & Biografi**: {bp['historical_biography_notes']}",
                f"- **Payoff & Callback**: {bp['payoff_callback']}",
                "",
                "## Story Arc Tiga Babak",
                f"1. **Act I (Setup & Anomali)**: {bp['story_arc']['act_1_setup']}",
                f"2. **Act II (Investigasi & Eskalasi)**: {bp['story_arc']['act_2_escalation']}",
                f"3. **Act III (Klimaks & Callback)**: {bp['story_arc']['act_3_resolution']}",
                "",
            ]
        )

        script_lines = [
            f"# Naskah Produksi Siap Baca (VO, Dialog & Aksi Konkret) — {payload['topic_title']}",
            "",
        ]
        cursor = 0.0
        for b in beats:
            end_t = cursor + float(b["target_duration_s"])
            script_lines.append(
                f"## {b['beat_id']} · `{b['sequence_id']}/{b['scene_id']}` · `{cursor:.1f}s – {end_t:.1f}s` ({b['beat_role']})"
            )
            script_lines.append(f"- **Narasi VO (Bahasa Indonesia)**: {b['narration_vo']}")
            for dlg in b.get("dialogue_lines", []):
                script_lines.append(f"- **Dialog `{dlg['speaker_id']}`** *({dlg['delivery']})*: \"{dlg['line']}\"")
            if b.get("humor_beat"):
                script_lines.append(f"- **Catatan Humor Situasional**: {b['humor_beat']}")
            script_lines.append("- **Rangkaian Aksi Visual Per-Shot**:")
            for idx_s, sb in enumerate(b["shot_blueprints"], 1):
                script_lines.append(
                    f"  {idx_s}. `[{sb['preferred_engine'].upper()} · {sb['shot_size']}]` **{sb['visual_subject']}** — {sb['concrete_action']}"
                )
            script_lines.append("")
            cursor = end_t

        return blueprint_md, "\n".join(script_lines)


class NarrationDialogueEngine:
    """Builds frame-aligned VO segments, character dialogue tracks, LUFS audio targets, and SRT captions."""

    def __init__(self) -> None:
        self.caption_adapter = WhisperCaptionAdapter()
        self.lipsync_adapter = RhubarbLipSyncAdapter()

    def build_plan_from_storyboard(
        self,
        payload: dict[str, Any],
        storyboard: dict[str, Any],
        *,
        target_wpm: int = 142,
        caption_preset_id: str = "cap_xdx_bold_stroke_9x16",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        beat_by_id = {b["beat_id"]: b for b in payload["narrative_beats"]}
        vo_segments: list[dict[str, Any]] = []
        all_dialogues: list[dict[str, Any]] = []
        any_onscreen_speech = False

        for idx, nb in enumerate(storyboard["narrative_beats"], 1):
            src_beat = beat_by_id[nb["beat_id"]]
            first_shot_id = nb["shot_ids"][0]
            start_s = round(nb["start_frame"] / storyboard["fps"], 3)
            end_s = round(nb["end_frame"] / storyboard["fps"], 3)
            vo_text = src_beat["narration_vo"]
            vo_segments.append(
                {
                    "segment_id": f"VO_{idx:03d}",
                    "beat_id": nb["beat_id"],
                    "shot_id": first_shot_id,
                    "shot_ids": nb["shot_ids"],
                    "speaker": "narrator_id_offscreen",
                    "text": vo_text,
                    "word_count": len(vo_text.split()),
                    "start_time_s": start_s,
                    "end_time_s": end_s,
                    "breath_pause_ms": 200,
                }
            )
            for dlg in src_beat.get("dialogue_lines", []):
                if dlg.get("onscreen_speaking"):
                    any_onscreen_speech = True
                all_dialogues.append(
                    {
                        "beat_id": nb["beat_id"],
                        "shot_id": nb["shot_ids"][min(1, len(nb["shot_ids"]) - 1)],
                        **dlg,
                    }
                )

        captions = self.caption_adapter.build_script_estimated_captions(vo_segments, max_words_per_cue=6)
        lipsync = self.lipsync_adapter.extract_visemes_or_fallback(None, has_onscreen_dialogue=any_onscreen_speech)

        total_words = sum(seg["word_count"] for seg in vo_segments) + sum(len(d["line"].split()) for d in all_dialogues)
        measured_wpm = round(total_words / max(0.1, storyboard["duration_s"] / 60.0), 1)

        narration_plan = {
            "schema_version": "3.4.0",
            "language": "id-ID",
            "target_wpm": target_wpm,
            "measured_script_wpm": measured_wpm,
            "voice_delivery_mode": "hybrid_vo_and_character_dialogue" if all_dialogues else "offscreen_narrator",
            "vo_segments": vo_segments,
            "dialogue_lines": all_dialogues,
            "lip_sync_plan": lipsync,
        }
        caption_audio_plan = {
            "schema_version": "3.4.0",
            "caption_preset_id": caption_preset_id,
            "audio_master_preset_id": "aud_master_vo_indonesia_15lufs",
            "sample_rate_hz": 48000,
            "target_lufs": -15.0,
            "true_peak_dbtp": -1.0,
            "asr_backends_detected": self.caption_adapter.detect_backends(),
            "cues": captions["cues"],
            "srt_preview": captions["srt"],
        }
        return narration_plan, caption_audio_plan


class CinematographyCameraEngine:
    """Assigns deterministic 36mm-sensor camera rigs, focal lengths, and shot-size trajectories."""

    SHOT_SIZE_LENS_MAP: dict[str, tuple[str, float, str, list[float], list[float], float]] = {
        "establishing": ("cam_establishing_diorama_28mm", 28.0, "isometric_high_18deg", [2.3, 2.1, 4.7], [1.9, 1.9, 4.0], 5.6),
        "wide": ("cam_establishing_diorama_28mm", 30.0, "wide_eye_12deg", [1.6, 1.7, 4.4], [1.2, 1.6, 3.9], 5.6),
        "medium": ("cam_medium_storyteller_40mm", 40.0, "eye_level", [0.0, 1.42, 3.5], [0.14, 1.42, 3.25], 4.0),
        "reaction": ("cam_medium_storyteller_40mm", 45.0, "three_quarter_eye", [-0.35, 1.40, 3.1], [-0.25, 1.40, 2.95], 3.5),
        "close_up": ("cam_insert_evidence_macro_70mm", 65.0, "intimate_eye_level", [0.0, 1.48, 2.25], [0.0, 1.48, 2.05], 2.8),
        "insert": ("cam_insert_evidence_macro_70mm", 72.0, "tabletop_35deg", [0.22, 1.25, 1.85], [0.12, 1.20, 1.68], 2.8),
        "cutaway": ("cam_insert_evidence_macro_70mm", 50.0, "orthographic_feel_25deg", [0.0, 1.65, 3.8], [0.28, 1.55, 3.4], 4.0),
    }

    def build_camera_spec(self, shot_size: str, genres: list[str], shot_index: int) -> dict[str, Any]:
        if "horor" in genres and shot_size in {"wide", "establishing"} and shot_index % 2 == 0:
            return {
                "preset_id": "cam_horror_dutch_corridor_32mm",
                "shot_size": shot_size,
                "angle": "low_dutch_tilt",
                "focal_length_mm": 32.0,
                "sensor_width_mm": 36.0,
                "position_start": [0.0, 1.32, 4.6],
                "position_end": [0.0, 1.28, 3.7],
                "target": [0.0, 1.18, 0.0],
                "motion_curve": "mot_horror_creeping_tension",
                "dof_fstop": 2.8,
                "roll_deg": -7.5,
            }

        preset_id, lens, angle, p0, p1, fstop = self.SHOT_SIZE_LENS_MAP.get(
            shot_size, self.SHOT_SIZE_LENS_MAP["medium"]
        )
        curve = "mot_snappy_spring_pop" if shot_index == 0 else "mot_cinematic_ease_inout"
        return {
            "preset_id": preset_id,
            "shot_size": shot_size,
            "angle": angle,
            "focal_length_mm": lens,
            "sensor_width_mm": 36.0,
            "position_start": list(p0),
            "position_end": list(p1),
            "target": [0.0, 1.15, 0.0],
            "motion_curve": curve,
            "dof_fstop": fstop,
        }


class StoryboardDirector:
    """Hierarchical Storyboard Compiler (Story Arc -> Sequence -> Scene -> Beat -> Shot <= 10s -> Events)."""

    MIN_SHOT_FRAMES_30FPS = 45    # 1.5s minimum
    TARGET_MAX_SHOT_FRAMES = 180  # 6.0s target sweet-spot (2-6s general target)
    HARD_MAX_SHOT_FRAMES = 300    # 10.0s absolute maximum allowed by Master Prompt

    def __init__(self, camera_engine: CinematographyCameraEngine | None = None) -> None:
        self.camera_engine = camera_engine or CinematographyCameraEngine()
        self._schema = json.loads((SCHEMAS_DIR / "storyboard.schema.json").read_text(encoding="utf-8"))

    @staticmethod
    def _apportion_integer_frames(total_frames: int, weights: list[float], *, min_each: int = 45) -> list[int]:
        n = len(weights)
        if n == 0:
            raise ValueError("Cannot apportion frames across empty list")
        if total_frames < n * min_each:
            min_each = max(1, total_frames // n)
        w_sum = sum(max(1e-6, float(w)) for w in weights)
        raw = [(max(1e-6, float(w)) / w_sum) * total_frames for w in weights]
        floors = [max(min_each, int(math.floor(x))) for x in raw]
        diff = total_frames - sum(floors)

        if diff > 0:
            order = sorted(range(n), key=lambda i: (raw[i] - math.floor(raw[i])), reverse=True)
            for idx in range(diff):
                floors[order[idx % n]] += 1
        elif diff < 0:
            order = sorted(range(n), key=lambda i: floors[i], reverse=True)
            rem = -diff
            ptr = 0
            while rem > 0:
                cand = order[ptr % n]
                if floors[cand] > min_each:
                    floors[cand] -= 1
                    rem -= 1
                ptr += 1
        assert sum(floors) == total_frames
        return floors

    def compile_hierarchical_storyboard(
        self,
        payload: dict[str, Any],
        *,
        genre_blend: dict[str, Any],
        fps: int = 30,
        width: int = 1080,
        height: int = 1920,
        aspect_ratio: str = "9:16",
    ) -> dict[str, Any]:
        total_frames = int(round(float(payload["target_duration_s"]) * fps))
        max_shot_frames = int(round(10.0 * fps))
        preferred_split_frames = int(round(5.5 * fps))  # keeps shots comfortably inside 2-6s range!
        min_shot_frames = max(15, int(round(1.5 * fps)))

        beats_in = payload["narrative_beats"]
        beat_weights = [float(b["target_duration_s"]) for b in beats_in]
        beat_frame_budgets = self._apportion_integer_frames(total_frames, beat_weights, min_each=min_shot_frames)

        hero_chars = [c["character_id"] for c in payload["characters"] if c["role"] in {"hero", "supporting"}]
        lead_char = hero_chars[0] if hero_chars else "char_raka_protagonist"

        shots: list[dict[str, Any]] = []
        narrative_beats_out: list[dict[str, Any]] = []
        scenes_map: dict[str, dict[str, Any]] = {}
        sequences_map: dict[str, dict[str, Any]] = {}

        global_cursor = 0
        shot_counter = 1
        caption_counter = 1

        angle_cycle = ("medium", "close_up", "insert", "reaction")

        for b_idx, (beat, b_frames) in enumerate(zip(beats_in, beat_frame_budgets)):
            bps = list(beat["shot_blueprints"])
            # Expand shot_blueprints if beat duration would force any shot over preferred_split_frames (5.5s)
            expanded_bps: list[dict[str, Any]] = []
            bp_weights = [float(sb.get("duration_weight", 1.0)) for sb in bps]
            prelim_alloc = self._apportion_integer_frames(b_frames, bp_weights, min_each=min_shot_frames)

            for sb, alloc_f in zip(bps, prelim_alloc):
                if alloc_f <= preferred_split_frames:
                    expanded_bps.append({**sb, "_target_f": alloc_f})
                else:
                    sub_count = max(2, math.ceil(alloc_f / preferred_split_frames))
                    sub_frames = self._apportion_integer_frames(alloc_f, [1.0] * sub_count, min_each=min_shot_frames)
                    for sub_i, sf in enumerate(sub_frames):
                        alt_size = sb["shot_size"] if sub_i == 0 else angle_cycle[(b_idx + sub_i) % len(angle_cycle)]
                        detail_suffix = (
                            ""
                            if sub_i == 0
                            else f" Kamera beralih ke sudut {alt_size.replace('_', ' ')} menyoroti interaksi detail {', '.join(sb['props'][:2])}."
                        )
                        expanded_bps.append(
                            {
                                **sb,
                                "shot_size": alt_size,
                                "concrete_action": sb["concrete_action"] + detail_suffix,
                                "transition_in": sb.get("transition_in", "trans_hard_cut_zero") if sub_i == 0 else "trans_hard_cut_zero",
                                "_target_f": sf,
                            }
                        )

            beat_start_f = global_cursor
            beat_shot_ids: list[str] = []
            vo_words = beat["narration_vo"].split()
            n_shots_in_beat = len(expanded_bps)

            for local_idx, sb in enumerate(expanded_bps):
                dur_f = int(sb["_target_f"])
                assert 1 <= dur_f <= max_shot_frames, f"Shot exceeded 10s max ({dur_f} frames)"
                s_start = global_cursor
                s_end = s_start + dur_f
                global_cursor = s_end

                sid = f"S{shot_counter:03d}"
                shot_counter += 1
                beat_shot_ids.append(sid)

                # Slice beat VO naturally across shots in the beat
                w0 = round((local_idx / n_shots_in_beat) * len(vo_words))
                w1 = round(((local_idx + 1) / n_shots_in_beat) * len(vo_words))
                shot_vo = " ".join(vo_words[w0:w1]).strip() or beat["narration_vo"]

                eng = sb["preferred_engine"]
                char_ids = [lead_char] if eng == "blender" else []
                props = list(sb["props"])
                asset_ids = list(dict.fromkeys([*char_ids, *props, "font_plus_jakarta_sans_v1"]))

                cam = self.camera_engine.build_camera_spec(sb["shot_size"], payload["genres"], shot_counter - 2)
                trans_in = str(sb.get("transition_in", "trans_hard_cut_zero"))
                if shot_counter == 2:
                    trans_in = "trans_hard_cut_zero"
                ov_in = TRANSITION_OVERLAP_FRAMES.get(trans_in, 0)

                concrete_act = sb["concrete_action"]
                subj = sb["visual_subject"]
                subject_ref = char_ids[0] if char_ids else props[0]

                cue_id = f"CAP_{caption_counter:03d}"
                caption_counter += 1

                shot_dialogues = beat.get("dialogue_lines", []) if local_idx == n_shots_in_beat - 1 else []
                audio_events = [
                    {
                        "event_id": f"AUD_{sid}_VO",
                        "kind": "vo",
                        "start_frame": s_start,
                        "end_frame": s_end,
                        "ref_id": f"VO_{beat['beat_id']}_{local_idx + 1}",
                        "gain_db": 0.0,
                    },
                    {
                        "event_id": f"AUD_{sid}_BGM",
                        "kind": "bgm_duck",
                        "start_frame": s_start,
                        "end_frame": s_end,
                        "ref_id": "aud_master_vo_indonesia_15lufs",
                        "gain_db": -11.0,
                    },
                    {
                        "event_id": f"AUD_{sid}_SFX",
                        "kind": "sfx",
                        "start_frame": s_start,
                        "end_frame": min(s_end, s_start + 8),
                        "ref_id": "sfx_horror_sub_drone" if "horor" in payload["genres"] else "sfx_cutaway_soft_whoosh",
                        "gain_db": -12.0,
                    },
                ]
                for d_i, dl in enumerate(shot_dialogues, 1):
                    audio_events.append(
                        {
                            "event_id": f"AUD_{sid}_DLG_{d_i}",
                            "kind": "dialogue",
                            "start_frame": max(s_start, s_end - min(dur_f, 45)),
                            "end_frame": s_end,
                            "ref_id": dl["speaker_id"],
                            "gain_db": 0.0,
                        }
                    )

                shots.append(
                    {
                        "shot_id": sid,
                        "sequence_id": beat["sequence_id"],
                        "scene_id": beat["scene_id"],
                        "beat_id": beat["beat_id"],
                        "start_frame": s_start,
                        "end_frame": s_end,
                        "duration_frames": dur_f,
                        "start_time_s": round(s_start / fps, 4),
                        "end_time_s": round(s_end / fps, 4),
                        "duration_s": round(dur_f / fps, 4),
                        "primary_engine": eng,
                        "overlay_engine": "remotion",
                        "narration_segment": shot_vo,
                        "dialogue_lines": shot_dialogues,
                        "action_start": f"{subj} berada pada posisi kontak terukur bersama {props[0]}.",
                        "action_mid": concrete_act,
                        "action_end": f"Gerak {subj.lower()} mereda stabil menjaga arah pandang ke titik fokus shot berikutnya.",
                        "action_events": [
                            {
                                "event_id": f"ACT_{sid}_01",
                                "start_frame": s_start,
                                "end_frame": s_end,
                                "subject_id": subject_ref,
                                "concrete_action": concrete_act,
                                "ik_or_contact": "ik_foot_and_prop_contact_locked",
                            }
                        ],
                        "camera": cam,
                        "camera_event": cam,
                        "audio_events": audio_events,
                        "caption_events": [
                            {
                                "cue_id": cue_id,
                                "start_frame": s_start,
                                "end_frame": s_end,
                                "text": " ".join(shot_vo.split()[:8]),
                                "preset_id": genre_blend["default_caption_preset"],
                            }
                        ],
                        "vfx_events": [
                            {
                                "event_id": f"VFX_{sid}_GRADE",
                                "kind": "grade",
                                "preset_id": genre_blend["default_vfx_preset"],
                                "start_frame": s_start,
                                "end_frame": s_end,
                            },
                            {
                                "event_id": f"VFX_{sid}_PART",
                                "kind": "particle",
                                "preset_id": "part_horror_ash_mist" if "horor" in payload["genres"] else "part_warm_dust_motes",
                                "start_frame": s_start,
                                "end_frame": s_end,
                            },
                        ],
                        "cutaway": {
                            "is_cutaway": bool(sb.get("is_cutaway", False)),
                            "purpose": str(sb.get("cutaway_purpose") or concrete_act),
                        },
                        "transition_in": trans_in,
                        "transition_out": "trans_hard_cut_zero",
                        "transition_spec": {
                            "transition_in_id": trans_in,
                            "transition_out_id": "trans_hard_cut_zero",
                            "overlap_frames_in": ov_in,
                            "overlap_frames_out": 0,
                            "render_handle_frames_head": ov_in,
                            "render_handle_frames_tail": 0,
                        },
                        "character_ids": char_ids,
                        "environment_id": beat["environment_id"],
                        "asset_ids": asset_ids,
                        "lighting_preset_id": genre_blend["default_lighting_preset"],
                        "material_preset_ids": ["mat_diorama_matte_clay", "mat_warm_teak_wood"],
                        "vfx_preset_ids": [genre_blend["default_vfx_preset"]],
                        "particle_preset_ids": ["part_warm_dust_motes"],
                        "sfx_cues": ["sfx_cutaway_soft_whoosh"],
                        "caption_cue_ids": [cue_id],
                        "qc_criteria": [
                            "Exact integer frame continuity [start_frame, end_frame)",
                            "Duration strictly <= 10.0s (<= 300 frames)",
                            "Concrete prop & character contact without clipping",
                        ],
                    }
                )

            # Propagate outgoing overlap handle onto preceding shot when incoming shot uses overlap transition
            beat_end_f = global_cursor
            narrative_beats_out.append(
                {
                    "beat_id": beat["beat_id"],
                    "scene_id": beat["scene_id"],
                    "beat_role": beat["beat_role"],
                    "start_frame": beat_start_f,
                    "end_frame": beat_end_f,
                    "duration_s": round((beat_end_f - beat_start_f) / fps, 4),
                    "shot_ids": beat_shot_ids,
                }
            )

            scn_id = beat["scene_id"]
            seq_id = beat["sequence_id"]
            if scn_id not in scenes_map:
                scenes_map[scn_id] = {
                    "scene_id": scn_id,
                    "sequence_id": seq_id,
                    "environment_id": beat["environment_id"],
                    "start_frame": beat_start_f,
                    "end_frame": beat_end_f,
                    "beat_ids": [beat["beat_id"]],
                }
            else:
                scenes_map[scn_id]["end_frame"] = beat_end_f
                scenes_map[scn_id]["beat_ids"].append(beat["beat_id"])

            if seq_id not in sequences_map:
                sequences_map[seq_id] = {
                    "sequence_id": seq_id,
                    "act": beat["act"],
                    "start_frame": beat_start_f,
                    "end_frame": beat_end_f,
                    "scene_ids": [scn_id],
                }
            else:
                sequences_map[seq_id]["end_frame"] = beat_end_f
                if scn_id not in sequences_map[seq_id]["scene_ids"]:
                    sequences_map[seq_id]["scene_ids"].append(scn_id)

        # Link outgoing transition handles cleanly between adjacent shots
        for idx in range(len(shots) - 1):
            next_ov = shots[idx + 1]["transition_spec"]["overlap_frames_in"]
            if next_ov > 0:
                next_tid = shots[idx + 1]["transition_spec"]["transition_in_id"]
                shots[idx]["transition_out"] = next_tid
                shots[idx]["transition_spec"]["transition_out_id"] = next_tid
                shots[idx]["transition_spec"]["overlap_frames_out"] = next_ov
                shots[idx]["transition_spec"]["render_handle_frames_tail"] = next_ov

        assert global_cursor == total_frames, f"Frame total mismatch: {global_cursor} != {total_frames}"

        storyboard = {
            "schema_version": "3.4.0",
            "project_id": payload["project_id"],
            "fps": fps,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "total_frames": total_frames,
            "duration_s": round(total_frames / fps, 4),
            "style_bible_id": GLOBAL_STYLE_BIBLE_V3_4["id"],
            "story_arc": payload["blueprint"]["story_arc"],
            "sequences": list(sequences_map.values()),
            "scenes": list(scenes_map.values()),
            "narrative_beats": narrative_beats_out,
            "shots": shots,
        }
        jsonschema.validate(instance=storyboard, schema=self._schema)
        return storyboard


class CharacterDesignIntelligence:
    """Formats AI-authored character specifications and ethical/biographical disclaimers."""

    def compile_character_bible(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        chars = payload["characters"]
        lines = [
            f"# Character Bible — {payload['topic_title']}",
            "",
            f"- **Catatan Sejarah & Biografi**: {payload['blueprint']['historical_biography_notes']}",
            "",
            "## Daftar Karakter Produksi",
        ]
        for c in chars:
            lines.extend(
                [
                    f"### `{c['character_id']}` — {c['name']} (`{c['role']}`)",
                    f"- **Siluet & Proporsi**: {c['silhouette_and_proportions']}",
                    f"- **Pakaian & Properti Melekat**: {c['wardrobe']}",
                    f"- **Palet Warna**: `{', '.join(c['palette'])}`",
                    f"- **Spesifikasi Rig**: `{c['rig_spec']}`",
                    f"- **Batas Representasi**: {c['biography_disclaimer']}",
                    "",
                ]
            )
        return chars, "\n".join(lines)


class MotionIntelligence:
    """Generates per-shot object, character, blink/gaze, IK, and camera motion plans."""

    def build_motion_plan(self, storyboard: dict[str, Any]) -> dict[str, Any]:
        shot_motions: list[dict[str, Any]] = []
        for s in storyboard["shots"]:
            has_onscreen_dlg = any(d.get("onscreen_speaking") for d in s.get("dialogue_lines", []))
            shot_motions.append(
                {
                    "shot_id": s["shot_id"],
                    "frame_range": [s["start_frame"], s["end_frame"]],
                    "render_handles_head_tail": [
                        s["transition_spec"]["render_handle_frames_head"],
                        s["transition_spec"]["render_handle_frames_tail"],
                    ],
                    "action_events": s["action_events"],
                    "character_motion": {
                        "character_ids": s["character_ids"],
                        "body_preset": "anim_explainer_gesture_present" if s["character_ids"] else None,
                        "anticipation_frames": 6,
                        "follow_through_frames": 8,
                        "ik_foot_plant": True,
                        "blink_frames_local": [24, 78] if s["duration_frames"] >= 90 else [20],
                        "lip_sync_mode": "rhubarb_viseme_required" if has_onscreen_dlg else "offscreen_vo",
                    },
                    "camera_motion_curve": s["camera"]["motion_curve"],
                    "deterministic_time_source": "frame_over_fps",
                }
            )
        return {
            "schema_version": "3.4.0",
            "project_id": storyboard["project_id"],
            "shots": shot_motions,
        }


class HybridEngineOrchestrator:
    """Builds schema-validated engine_plan.json and execution_plan.md across Blender, Three.js, Remotion, REA-Video, and FFmpeg."""

    def __init__(self) -> None:
        self._schema = json.loads((SCHEMAS_DIR / "engine_plan.schema.json").read_text(encoding="utf-8"))

    def build_engine_plan(self, storyboard: dict[str, Any]) -> tuple[dict[str, Any], str]:
        routing: list[dict[str, Any]] = []
        primary_used: set[str] = set()
        for idx, s in enumerate(storyboard["shots"], 1):
            eng = s["primary_engine"]
            primary_used.add(eng)
            rationale_map = {
                "blender": f"Acting karakter diorama ({', '.join(s['character_ids']) or 'scene'}) & pencahayaan ruang via XDX Blender Studio MCP.",
                "threejs": f"Visualisasi mekanisme/properti 3D deterministik ({', '.join(s['asset_ids'][:2])}) berbasis frame/fps.",
                "remotion": "Grafis data perbandingan & kartu lini masa deterministik langsung pada timeline utama.",
            }
            out_fmt = "remotion_sequence" if eng == "remotion" else "png_sequence"
            total_with_handles = (
                s["duration_frames"]
                + s["transition_spec"]["render_handle_frames_head"]
                + s["transition_spec"]["render_handle_frames_tail"]
            )
            routing.append(
                {
                    "shot_id": s["shot_id"],
                    "start_frame": s["start_frame"],
                    "end_frame": s["end_frame"],
                    "primary_engine": eng,
                    "overlay_engine": "remotion",
                    "rationale": rationale_map[eng],
                    "deterministic_seed": 202600 + idx,
                    "inputs": s["asset_ids"],
                    "output_contract": {
                        "format": out_fmt,
                        "has_alpha": False,
                        "frame_count": total_with_handles,
                    },
                    "style_consistency_notes": "ACESFilmic + sRGB, roughness 0.30-0.88, 36mm sensor matched.",
                    "proposed_fallback": "Requires explicit user re-approval if primary engine is blocked; no silent substitution.",
                }
            )

        all_engines = ["blender", "threejs", "remotion", "rea_video", "ffmpeg"]
        omitted: dict[str, str] = {}
        for cand in ("blender", "threejs"):
            if cand not in primary_used:
                omitted[cand] = f"Tidak ada shot yang membutuhkan {cand} pada naskah ini."

        plan = {
            "schema_version": "3.4.0",
            "project_id": storyboard["project_id"],
            "master_compositor": "remotion",
            "encoding_validator": "ffmpeg",
            "reference_qc_engine": "rea_video",
            "fps": storyboard["fps"],
            "resolution": {
                "width": storyboard["width"],
                "height": storyboard["height"],
                "pixel_format": "yuv420p",
            },
            "color_management": {
                "working_space": "Linear Rec.709",
                "view_transform": "ACESFilmic",
                "delivery_space": "sRGB / Rec.709",
                "alpha_interchange": "PNG RGBA 16-bit/8-bit",
            },
            "engines_used": [e for e in all_engines if e not in omitted],
            "omitted_engines_rationale": omitted,
            "shot_routing": routing,
        }
        jsonschema.validate(instance=plan, schema=self._schema)

        exec_md = "\n".join(
            [
                f"# Rencana Eksekusi Hybrid v3.4 — `{storyboard['project_id']}`",
                "",
                "> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.",
                "",
                f"- **Total Durasi**: `{storyboard['duration_s']}s` (`{storyboard['total_frames']} frame @ {storyboard['fps']} fps`)",
                f"- **Jumlah Hierarchy**: `{len(storyboard['sequences'])} Sequence` · `{len(storyboard['scenes'])} Scene` · `{len(storyboard['narrative_beats'])} Beat` · `{len(storyboard['shots'])} Shot`",
                "",
                "## Tabel Routing Shot & Handle Transisi",
                "| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |",
                "|---|---|---|---:|---|---|---:|",
                *[
                    f"| {s['shot_id']} | {s['beat_id']} | `[{s['start_frame']}, {s['end_frame']})` | {s['duration_s']:.2f}s | `{s['primary_engine']}` | `{s['transition_in']}` | {r['output_contract']['frame_count']} |"
                    for s, r in zip(storyboard["shots"], routing)
                ],
                "",
            ]
        )
        return plan, exec_md


class PreProductionPackageBuilder:
    """Validates AI-authored creative payloads, compiles the 13-item package, and stops at WAITING_APPROVAL."""

    def __init__(self) -> None:
        self.master = UniversalMasterPromptEngine()
        self.validator = CreativePayloadValidator()
        self.research = TopicResearchEngine()
        self.story = StoryScriptIntelligence()
        self.narration = NarrationDialogueEngine()
        self.storyboard_dir = StoryboardDirector()
        self.character = CharacterDesignIntelligence()
        self.motion = MotionIntelligence()
        self.orchestrator = HybridEngineOrchestrator()
        self.presets = PresetLibraryRegistry()
        self._approval_schema = json.loads((SCHEMAS_DIR / "approval_package.schema.json").read_text(encoding="utf-8"))

    def build_waiting_approval_package(
        self,
        *,
        package_dir: Path,
        project_id: str,
        topic: str | None = None,
        genres: list[str] | None = None,
        target_duration_s: int = 150,
        package_version: str = "v1",
        authored_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        package_dir.mkdir(parents=True, exist_ok=True)
        self.presets.load_all(validate=True)

        if authored_payload is not None:
            payload = copy.deepcopy(authored_payload)
            payload["project_id"] = project_id
            if genres is not None:
                payload["genres"] = genres
            if topic is not None:
                payload["topic_title"] = topic
            payload["target_duration_s"] = target_duration_s
        else:
            payload = build_authored_time_perception_payload(
                project_id=project_id,
                target_duration_s=target_duration_s,
                genres=genres or ["explainer", "edukasi", "sejarah", "biografi", "komedi_absurd"],
            )
            if topic is not None and topic.strip():
                # Keep full authored narrative if default topic, or attach custom subtitle cleanly
                if "waktu" not in topic.lower() and "jam" not in topic.lower():
                    payload["topic_title"] = f"{topic.strip()} — Studi Persepsi Waktu & Memori"
                else:
                    payload["topic_title"] = topic.strip()

        creative_metrics = self.validator.validate(payload)
        blend = self.master.blend_genres(payload["genres"])
        topic_obj, research_md = self.research.validate_and_compile_research(payload)
        blueprint_md, script_md = self.story.compile_blueprint_and_script_markdown(payload, genre_blend=blend)

        storyboard = self.storyboard_dir.compile_hierarchical_storyboard(
            payload,
            genre_blend=blend,
        )
        narration_plan, caption_audio_plan = self.narration.build_plan_from_storyboard(
            payload,
            storyboard,
            target_wpm=blend["target_wpm"],
            caption_preset_id=blend["default_caption_preset"],
        )
        chars, char_bible_md = self.character.compile_character_bible(payload)
        motion_plan = self.motion.build_motion_plan(storyboard)
        engine_plan, exec_md = self.orchestrator.build_engine_plan(storyboard)

        asset_manifest = {
            "schema_version": "3.4.0",
            "project_id": project_id,
            "style_bible": GLOBAL_STYLE_BIBLE_V3_4,
            "characters": chars,
            "required_assets": sorted({aid for s in storyboard["shots"] for aid in [s["environment_id"], *s["asset_ids"]]}),
        }
        prod_config = {
            "schema_version": "3.4.0",
            "project_id": project_id,
            "package_version": package_version,
            "topic": topic_obj,
            "creative_validation_metrics": creative_metrics,
            "fps": storyboard["fps"],
            "width": storyboard["width"],
            "height": storyboard["height"],
            "aspect_ratio": storyboard["aspect_ratio"],
            "total_frames": storyboard["total_frames"],
        }
        ref_md = (
            "# Analisis Referensi Pra-Produksi\n\n"
            "Produksi orisinal menggunakan Global Style Bible `xdx_stylized_diorama_v3_4` tanpa menyalin dialog atau aset pihak ketiga.\n"
        )

        files_text = {
            "blueprint.md": blueprint_md + "\n",
            "research.md": research_md + "\n",
            "script.md": script_md + "\n",
            "character_bible.md": char_bible_md + "\n",
            "execution_plan.md": exec_md + "\n",
            "reference_analysis.md": ref_md,
            "storyboard.json": json.dumps(storyboard, indent=2) + "\n",
            "asset_manifest.json": json.dumps(asset_manifest, indent=2) + "\n",
            "motion_plan.json": json.dumps(motion_plan, indent=2) + "\n",
            "production_config.json": json.dumps(prod_config, indent=2) + "\n",
            "engine_plan.json": json.dumps(engine_plan, indent=2) + "\n",
            "narration_dialogue.json": json.dumps(narration_plan, indent=2) + "\n",
            "caption_audio_plan.json": json.dumps(caption_audio_plan, indent=2) + "\n",
            "authored_creative_payload.json": json.dumps(payload, indent=2) + "\n",
        }
        for fname, content in files_text.items():
            atomic_write_bytes(package_dir / fname, content.encode("utf-8"))

        digest, file_hashes = compute_package_digest(package_dir)

        approval_manifest = {
            "schema_version": "3.4.0",
            "project_id": project_id,
            "package_version": package_version,
            "status": "WAITING_APPROVAL",
            "package_digest": digest,
            "mandatory_13_items": {
                "01_topic_and_concept": {"present": True, "artifact_file": "blueprint.md", "summary": f"{payload['topic_title']} ({', '.join(payload['genres'])})"},
                "02_research_results": {"present": True, "artifact_file": "research.md", "summary": f"{len(topic_obj['claims'])} klaim terverifikasi sumber primer/institusional"},
                "03_full_script": {"present": True, "artifact_file": "script.md", "summary": f"{len(payload['narrative_beats'])} beat naskah natural siap dibacakan"},
                "04_narration_and_dialogue": {"present": True, "artifact_file": "narration_dialogue.json", "summary": f"{len(narration_plan['vo_segments'])} VO & {len(narration_plan['dialogue_lines'])} dialog ({narration_plan['measured_script_wpm']} WPM)"},
                "05_clip_by_clip_storyboard": {"present": True, "artifact_file": "storyboard.json", "summary": f"{len(storyboard['sequences'])} seq / {len(storyboard['scenes'])} scene / {len(storyboard['narrative_beats'])} beat / {len(storyboard['shots'])} shot"},
                "06_shot_timestamps_and_durations": {"present": True, "artifact_file": "storyboard.json", "summary": f"{storyboard['total_frames']} frame ({storyboard['duration_s']}s @ {storyboard['fps']}fps, semua shot <= 10s)"},
                "07_camera_framing_cutaway_transitions": {"present": True, "artifact_file": "storyboard.json", "summary": "Kamera 36mm, cutaway bukti, dan handle transisi eksplisit"},
                "08_complete_asset_list": {"present": True, "artifact_file": "asset_manifest.json", "summary": f"{len(asset_manifest['required_assets'])} kebutuhan aset semantik"},
                "09_character_designs": {"present": True, "artifact_file": "character_bible.md", "summary": f"{len(chars)} karakter orisinal lengkap"},
                "10_motion_plan": {"present": True, "artifact_file": "motion_plan.json", "summary": f"{len(motion_plan['shots'])} rencana gerak shot & kontak IK"},
                "11_caption_and_audio_plan": {"present": True, "artifact_file": "caption_audio_plan.json", "summary": f"{len(caption_audio_plan['cues'])} cue subtitle & mastering -15 LUFS"},
                "12_engine_selection_per_shot": {"present": True, "artifact_file": "engine_plan.json", "summary": f"Routing hybrid ({', '.join(engine_plan['engines_used'])})"},
                "13_hybrid_execution_plan": {"present": True, "artifact_file": "execution_plan.md", "summary": "Urutan kompilasi Blender MCP, Three.js, Remotion, dan FFmpeg"},
            },
            "required_files_sha256": file_hashes,
        }
        jsonschema.validate(instance=approval_manifest, schema=self._approval_schema)
        atomic_write_bytes(
            package_dir / "approval_package_manifest.json",
            (json.dumps(approval_manifest, indent=2) + "\n").encode("utf-8"),
        )

        state_mgr = ProjectStateManager(package_dir / "project_state.json")
        state_mgr.initialize(
            project_id=project_id,
            project_title=payload["topic_title"],
            genres=payload["genres"],
            total_frames=storyboard["total_frames"],
        )
        state = state_mgr.mark_waiting_approval(digest, package_version=package_version)
        assert state["current_state"] == "WAITING_APPROVAL"
        return {
            "status": "WAITING_APPROVAL",
            "package_digest": digest,
            "package_version": package_version,
            "approval_command_example": format_structured_approval_command(
                project_id=project_id,
                package_version=package_version,
                package_digest=digest,
            ),
            "state": state,
            "approval_manifest": approval_manifest,
        }
