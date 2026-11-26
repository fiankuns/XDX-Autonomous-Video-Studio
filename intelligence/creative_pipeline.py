"""Universal Creative, Narrative, Cinematography, Motion & Hybrid Orchestration Intelligence (v3.3).

Implements:
- UniversalMasterPromptEngine (multi-genre & hybrid genre rules)
- TopicResearchEngine
- StoryScriptIntelligence
- NarrationDialogueEngine
- CinematographyCameraEngine
- StoryboardDirector
- CharacterDesignIntelligence
- MotionIntelligence
- HybridEngineOrchestrator
- PreProductionPackageBuilder (generates all 13 mandatory Approval Gate items & stops at WAITING_APPROVAL)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import jsonschema

from adapters.caption_lipsync_adapter import RhubarbLipSyncAdapter, WhisperCaptionAdapter
from intelligence.asset_management import GLOBAL_STYLE_BIBLE_V3_3
from intelligence.state_and_approval import ProjectStateManager, compute_package_digest
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


class UniversalMasterPromptEngine:
    """Synthesizes multi-genre rules, operational modes, and Global Style Bible."""

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
            "dominant_genre": genres[0],
            "hook_formula": lead["hook_formula"],
            "default_lighting_preset": lead["lighting"],
            "default_vfx_preset": lead["vfx"],
            "default_caption_preset": lead["caption"],
            "default_typography_preset": lead["typography"],
            "requires_hero_character": needs_hero,
            "target_wpm": max(130, min(155, avg_wpm)),
            "style_bible": GLOBAL_STYLE_BIBLE_V3_3,
        }


class TopicResearchEngine:
    """Produces structured topic evaluation and epistemic-tagged research dossiers."""

    def research_topic(
        self,
        *,
        topic: str,
        genres: list[str],
        verified_claims: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], str]:
        is_fiction = any(g in {"horor", "storytelling", "komedi_absurd"} for g in genres) and not any(
            g in {"sejarah", "biografi", "dokumenter", "edukasi", "explainer"} for g in genres
        )
        claims = verified_claims or [
            {
                "claim": f"Konteks utama topik '{topic}' disajikan sebagai studi konseptual pra-produksi.",
                "epistemic_status": "dramatization_or_fiction" if is_fiction else "needs_primary_source_verification",
                "source_url": "pending_external_verification",
            }
        ]
        topic_obj = {
            "topic": topic,
            "genres": genres,
            "epistemic_mode": "fictional_narrative" if is_fiction else "factual_with_explicit_boundaries",
            "visual_potential_score": 4.6,
            "asset_feasibility": "high_modular_diorama",
            "claims": claims,
        }
        md = "\n".join(
            [
                f"# Riset Topik & Verifikasi Klaim — {topic}",
                "",
                f"- **Genre**: {', '.join(genres)}",
                f"- **Mode Epistemik**: `{topic_obj['epistemic_mode']}`",
                "- **Prinsip Anti-Halusinasi**: Membedakan fakta terverifikasi, rekonstruksi sejarah, dramatisasi, dan fiksi; dilarang mengarang kutipan sejarah atau statistik palsu.",
                "",
                "## Daftar Klaim & Status Bukti",
                *[
                    f"- **{c['claim']}** — Status: `{c['epistemic_status']}` (Sumber: `{c['source_url']}`)"
                    for c in claims
                ],
                "",
            ]
        )
        return topic_obj, md


class StoryScriptIntelligence:
    """Generates Universal Blueprint and beat-structured Indonesian scripts."""

    def build_blueprint_and_script(
        self,
        *,
        topic: str,
        genre_blend: dict[str, Any],
        target_duration_s: int = 24,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        # 6 narrative beats bounded cleanly inside target_duration_s (each shot 3-5s <= 10s rule)
        beat_Count = max(4, min(8, round(target_duration_s / 4)))
        base_dur = target_duration_s / beat_Count
        roles = [
            ("B01", "hook_anomaly", "Hook visual langsung 0-3 detik di ruang miniatur tanpa basa-basi salam."),
            ("B02", "core_question", "Pertanyaan inti yang memicu rasa penasaran konkret penonton Indonesia."),
            ("B03", "mechanism_cutaway", "Cutaway penjelasan visual 3D/data yang membuktikan cara kerja konsep."),
            ("B04", "everyday_consequence", "Konsekuensi nyata atau kontras situasi sehari-hari karakter."),
            ("B05", "escalation_or_twist", "Eskalasi tensi, kilas balik sejarah, atau kontras komedi absurd."),
            ("B06", "payoff_callback", "Payoff penutup yang menjawab hook awal secara memuaskan."),
        ]
        selected_roles = roles[:beat_Count]
        beats: list[dict[str, Any]] = []
        cursor = 0.0
        for idx, (bid, role, desc) in enumerate(selected_roles):
            end_t = target_duration_s if idx == len(selected_roles) - 1 else round(cursor + base_dur, 2)
            beats.append(
                {
                    "beat_id": bid,
                    "role": role,
                    "start_s": round(cursor, 2),
                    "end_s": round(end_t, 2),
                    "narration": f"[{role.upper()}] {topic}: {desc}",
                    "visual_action": desc,
                    "emotion": "curious_engaged" if idx < 2 else ("shocked_absurd" if "komedi_absurd" in genre_blend["genres"] else "solemn_historical"),
                }
            )
            cursor = end_t

        blueprint_md = "\n".join(
            [
                f"# Universal Production Blueprint v3.3 — {topic}",
                "",
                f"- **Kombinasi Genre**: `{', '.join(genre_blend['genres'])}`",
                f"- **Formula Hook**: `{genre_blend['hook_formula']}`",
                f"- **Target Kecepatan Narasi**: {genre_blend['target_wpm']} kata/menit (Bahasa Indonesia lisan alami)",
                f"- **Global Style Bible**: `{genre_blend['style_bible']['id']}`",
                "",
                "## Struktur Beat Naratif",
                *[f"- **{b['beat_id']} ({b['start_s']}s–{b['end_s']}s) [{b['role']}]**: {b['visual_action']}" for b in beats],
                "",
            ]
        )

        script_md = "\n".join(
            [
                f"# Naskah Produksi Lengkap — {topic}",
                "",
                "| Beat | Estimasi Waktu | Narasi (VO Off-Screen) | Aksi Visual | Intent Emosi |",
                "|---|---|---|---|---|",
                *[
                    f"| {b['beat_id']} | {b['start_s']:.1f}s - {b['end_s']:.1f}s | {b['narration']} | {b['visual_action']} | `{b['emotion']}` |"
                    for b in beats
                ],
                "",
            ]
        )
        return blueprint_md, script_md, beats


class NarrationDialogueEngine:
    """Separates VO narration and character dialogue; computes WPM, LUFS, and captions."""

    def __init__(self) -> None:
        self.caption_adapter = WhisperCaptionAdapter()
        self.lipsync_adapter = RhubarbLipSyncAdapter()

    def build_plan(
        self,
        beats: list[dict[str, Any]],
        *,
        target_wpm: int = 142,
        caption_preset_id: str = "cap_xdx_bold_stroke_9x16",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        vo_segments: list[dict[str, Any]] = []
        for idx, b in enumerate(beats, 1):
            shot_id = f"S{idx:03d}"
            words = len(b["narration"].split())
            vo_segments.append(
                {
                    "segment_id": f"VO_{idx:03d}",
                    "shot_id": shot_id,
                    "speaker": "narrator_id_offscreen",
                    "text": b["narration"],
                    "word_count": words,
                    "start_time_s": b["start_s"],
                    "end_time_s": b["end_s"],
                    "breath_pause_ms": 180,
                }
            )

        captions = self.caption_adapter.build_script_estimated_captions(vo_segments)
        lipsync = self.lipsync_adapter.extract_visemes_or_fallback(None, has_onscreen_dialogue=False)

        narration_plan = {
            "language": "id-ID",
            "target_wpm": target_wpm,
            "voice_delivery_mode": "offscreen_narrator",
            "vo_segments": vo_segments,
            "dialogue_lines": [],
            "lip_sync_plan": lipsync,
        }
        caption_audio_plan = {
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
    """Assigns lens, sensor, framing, cutaway purpose, and deterministic motion curves."""

    def plan_camera_for_beat(self, beat: dict[str, Any], index: int, genres: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
        role = beat["role"]
        if "horor" in genres and index in (0, 4):
            return (
                {
                    "preset_id": "cam_horror_dutch_corridor_32mm",
                    "shot_size": "wide",
                    "angle": "low_dutch_tilt",
                    "focal_length_mm": 32.0,
                    "sensor_width_mm": 36.0,
                    "position_start": [0.0, 1.35, 4.8],
                    "position_end": [0.0, 1.30, 3.9],
                    "target": [0.0, 1.2, 0.0],
                    "motion_curve": "mot_horror_creeping_tension",
                    "dof_fstop": 2.8,
                },
                {"is_cutaway": False, "purpose": "Primary suspense staging"},
            )
        if role == "hook_anomaly":
            return (
                {
                    "preset_id": "cam_establishing_diorama_28mm",
                    "shot_size": "establishing",
                    "angle": "isometric_high_18deg",
                    "focal_length_mm": 28.0,
                    "sensor_width_mm": 36.0,
                    "position_start": [2.2, 2.1, 4.6],
                    "position_end": [1.8, 1.9, 3.8],
                    "target": [0.0, 1.0, 0.0],
                    "motion_curve": "mot_snappy_spring_pop",
                    "dof_fstop": 5.6,
                },
                {"is_cutaway": False, "purpose": "Establish world scale and visual hook in 0-3s"},
            )
        if role == "mechanism_cutaway":
            return (
                {
                    "preset_id": "cam_insert_evidence_macro_70mm",
                    "shot_size": "cutaway",
                    "angle": "three_quarter_technical_35deg",
                    "focal_length_mm": 70.0,
                    "sensor_width_mm": 36.0,
                    "position_start": [0.0, 1.8, 4.2],
                    "position_end": [0.4, 1.6, 3.5],
                    "target": [0.0, 0.9, 0.0],
                    "motion_curve": "mot_cinematic_ease_inout",
                    "dof_fstop": 4.0,
                },
                {"is_cutaway": True, "purpose": "Prove causal mechanism with 3D procedural cutaway"},
            )
        return (
            {
                "preset_id": "cam_medium_storyteller_40mm",
                "shot_size": "medium",
                "angle": "eye_level",
                "focal_length_mm": 40.0,
                "sensor_width_mm": 36.0,
                "position_start": [0.0, 1.45, 3.6],
                "position_end": [0.15, 1.45, 3.4],
                "target": [0.0, 1.25, 0.0],
                "motion_curve": "mot_cinematic_ease_inout",
                "dof_fstop": 4.0,
            },
            {"is_cutaway": False, "purpose": "Advance character reaction and narrative consequence"},
        )


class CharacterDesignIntelligence:
    """Designs original stylized 3D characters with historical/biographical safeguards."""

    def build_characters(self, topic: str, genre_blend: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        is_bio_hist = any(g in {"sejarah", "biografi"} for g in genre_blend["genres"])
        chars: list[dict[str, Any]] = [
            {
                "character_id": "char_hero_diorama_base_v1",
                "name": "Raka (Original Stylized Protagonist)",
                "role": "hero" if genre_blend["requires_hero_character"] else "optional_presenter",
                "proportions": "head_0.34_compact_torso_slender_limbs",
                "palette": ["#F4D8B8", "#2563EB", "#1E293B"],
                "rig_spec": "xdx_diorama_humanoid_v1_ik_hands_feet",
                "facial_controls": ["brow_inner_up", "brow_furrow", "eye_wide", "blink", "smile_soft", "jaw_drop"],
            }
        ]
        disclaimer = (
            "Rekonstruksi visual bergaya diorama; bukan rekaman dokumentasi asli dan tidak meniru kemiripan wajah privat tanpa izin."
            if is_bio_hist
            else "Desain karakter 100% orisinal XDX Studio; tidak menyalin karakter hak cipta pihak ketiga."
        )
        md = "\n".join(
            [
                f"# Character Bible — {topic}",
                "",
                f"> **Catatan Etika & Keaslian**: {disclaimer}",
                "",
                "## Karakter Utama & Pendukung",
                *[
                    f"- **`{c['character_id']}` — {c['name']}** (`{c['role']}`): proporsi `{c['proportions']}`, rig `{c['rig_spec']}`, palet `{', '.join(c['palette'])}`."
                    for c in chars
                ],
                "",
            ]
        )
        return chars, md


class MotionIntelligence:
    """Generates per-shot object, character, blink/gaze, IK, and camera motion plans."""

    def build_motion_plan(self, storyboard: dict[str, Any]) -> dict[str, Any]:
        shot_motions: list[dict[str, Any]] = []
        for s in storyboard["shots"]:
            shot_motions.append(
                {
                    "shot_id": s["shot_id"],
                    "frame_range": [s["start_frame"], s["end_frame"]],
                    "character_motion": {
                        "character_ids": s["character_ids"],
                        "body_preset": "anim_explainer_gesture_present" if s["character_ids"] else None,
                        "anticipation_frames": 6,
                        "follow_through_frames": 8,
                        "ik_foot_plant": True,
                        "blink_frames_local": [24, 78] if s["duration_frames"] >= 90 else [20],
                        "lip_sync_mode": "offscreen_vo",
                    },
                    "camera_motion_curve": s["camera"]["motion_curve"],
                    "deterministic_time_source": "frame_over_fps",
                }
            )
        return {
            "schema_version": "3.3.0",
            "project_id": storyboard["project_id"],
            "shots": shot_motions,
        }


class StoryboardDirector:
    """Compiles beats into a zero-gap, zero-overlap integer-frame master storyboard."""

    def __init__(self, camera_engine: CinematographyCameraEngine | None = None) -> None:
        self.camera_engine = camera_engine or CinematographyCameraEngine()
        self._schema = json.loads((SCHEMAS_DIR / "storyboard.schema.json").read_text(encoding="utf-8"))

    def build_storyboard(
        self,
        *,
        project_id: str,
        beats: list[dict[str, Any]],
        genre_blend: dict[str, Any],
        caption_cues: list[dict[str, Any]],
        fps: int = 30,
        width: int = 1080,
        height: int = 1920,
        aspect_ratio: str = "9:16",
    ) -> dict[str, Any]:
        shots: list[dict[str, Any]] = []
        frame_cursor = 0
        genres = genre_blend["genres"]

        env_id = (
            "env_dark_corridor_horror_v1"
            if "horor" in genres
            else ("env_historical_archive_hall_v1" if any(g in {"sejarah", "biografi"} for g in genres) else "env_kamar_indonesia_modular_v1")
        )

        for idx, beat in enumerate(beats, 1):
            sid = f"S{idx:03d}"
            raw_dur_s = max(2.0, min(10.0, float(beat["end_s"]) - float(beat["start_s"])))
            dur_frames = max(30, min(300, round(raw_dur_s * fps)))
            start_f = frame_cursor
            end_f = start_f + dur_frames
            frame_cursor = end_f

            cam, cutaway = self.camera_engine.plan_camera_for_beat(beat, idx - 1, genres)
            if beat["role"] == "mechanism_cutaway":
                primary_engine = "threejs"
            elif idx == len(beats) - 1 and any(g in {"dokumenter", "explainer", "edukasi"} for g in genres):
                primary_engine = "remotion"
            else:
                primary_engine = "blender"

            matched_cues = [c["cue_id"] for c in caption_cues if c.get("shot_id") == sid]
            char_ids = ["char_hero_diorama_base_v1"] if primary_engine == "blender" else []
            asset_ids = [*char_ids, "prop_data_pedestal_compare_v1", "font_plus_jakarta_sans_v1"]

            shots.append(
                {
                    "shot_id": sid,
                    "scene_id": f"SCN_{(idx + 1) // 2:02d}",
                    "beat_id": beat["beat_id"],
                    "start_frame": start_f,
                    "end_frame": end_f,
                    "duration_frames": dur_frames,
                    "start_time_s": round(start_f / fps, 4),
                    "end_time_s": round(end_f / fps, 4),
                    "duration_s": round(dur_frames / fps, 4),
                    "primary_engine": primary_engine,
                    "overlay_engine": "remotion",
                    "narration_segment": beat["narration"],
                    "dialogue_lines": [],
                    "action_start": f"Pembukaan beat {beat['beat_id']}: staging awal",
                    "action_mid": beat["visual_action"],
                    "action_end": "Settle pose & transisi bersih ke shot berikutnya",
                    "camera": cam,
                    "cutaway": cutaway,
                    "transition_in": "trans_hard_cut_zero" if idx == 1 else "trans_whip_pan_cutaway_6f",
                    "transition_out": "trans_hard_cut_zero",
                    "character_ids": char_ids,
                    "environment_id": env_id,
                    "asset_ids": asset_ids,
                    "lighting_preset_id": genre_blend["default_lighting_preset"],
                    "material_preset_ids": ["mat_diorama_matte_clay", "mat_warm_teak_wood"],
                    "vfx_preset_ids": [genre_blend["default_vfx_preset"]],
                    "particle_preset_ids": ["part_warm_dust_motes"],
                    "sfx_cues": ["sfx_cutaway_soft_whoosh"],
                    "caption_cue_ids": matched_cues,
                    "qc_criteria": [
                        "Zero frame gap/overlap",
                        "No clipping or foot sliding",
                        "Safe-zone Indonesian caption legibility",
                    ],
                }
            )

        storyboard = {
            "schema_version": "3.3.0",
            "project_id": project_id,
            "fps": fps,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "total_frames": frame_cursor,
            "duration_s": round(frame_cursor / fps, 4),
            "style_bible_id": GLOBAL_STYLE_BIBLE_V3_3["id"],
            "shots": shots,
        }
        jsonschema.validate(instance=storyboard, schema=self._schema)
        return storyboard


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
                "blender": "Acting karakter 3D bergaya diorama, rig IK, dan pencahayaan PBR melalui XDX Blender Studio MCP.",
                "threejs": "Cutaway mekanisme/simulasi 3D prosedural deterministik berbasis frame/fps dengan seed terkunci.",
                "remotion": "Grafis perbandingan data & tipografi kinetik 2D deterministik langsung pada timeline utama.",
            }
            out_fmt = "remotion_sequence" if eng == "remotion" else "png_sequence"
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
                        "frame_count": s["duration_frames"],
                    },
                    "style_consistency_notes": "ACESFilmic + sRGB, roughness 0.30-0.88, matched focal length & palette.",
                    "proposed_fallback": "Requires explicit user re-approval if primary engine is blocked; no silent substitution.",
                }
            )

        all_engines = ["blender", "threejs", "remotion", "rea_video", "ffmpeg"]
        omitted: dict[str, str] = {}
        for cand in ("blender", "threejs"):
            if cand not in primary_used:
                omitted[cand] = f"Tidak ada shot yang membutuhkan {cand} pada naskah ini."

        plan = {
            "schema_version": "3.3.0",
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
                f"# Rencana Eksekusi Hybrid (Blender MCP + Three.js + Remotion) — `{storyboard['project_id']}`",
                "",
                "> **PERINGATAN KERAS**: Eksekusi produksi DILARANG dimulai sebelum status berubah dari `WAITING_APPROVAL` ke `APPROVED` melalui persetujuan eksplisit pengguna.",
                "",
                "## Urutan Eksekusi Pasca-Approval",
                "1. **MCP Preflight (Read-Only -> Smoke Test)**: Verifikasi koneksi XDX Blender Studio (`get_mobile_device_profile`, `get_scene_info`) dengan `mobile_guard` aktif pada Vivo X200 Pro.",
                "2. **Pengadaan Aset 9 Tahap**: Registry -> Cache -> Discovery CC0 -> Validasi Lisensi -> Unduh Terarah -> Fallback Prosedural -> Harmonisasi Style Bible -> QC -> Simpan Ulang.",
                "3. **Render Shot Blender & Three.js**: Render frame deterministik `[0, duration_frames)` sesuai `engine_plan.json`.",
                "4. **Master Compositing Remotion**: Susun seluruh `Sequence` `[start_frame, end_frame)`, caption aman 9:16, BGM ducking, dan VO 48 kHz.",
                "5. **FFmpeg Validasi & REA-Video Visual QC**: Verifikasi decode penuh H.264 `yuv420p` + AAC dan jalankan Self-Correction maksimal 3 percobaan per shot bila diperlukan.",
                "",
                "## Tabel Routing Shot",
                "| Shot | Frame `[start, end)` | Engine Utama | Overlay | Seed |",
                "|---|---|---|---|---:|",
                *[
                    f"| {r['shot_id']} | `[{r['start_frame']}, {r['end_frame']})` | `{r['primary_engine']}` | `{r['overlay_engine']}` | {r['deterministic_seed']} |"
                    for r in routing
                ],
                "",
            ]
        )
        return plan, exec_md


class PreProductionPackageBuilder:
    """Generates a complete, schema-validated 13-item pre-production package and halts at WAITING_APPROVAL."""

    def __init__(self) -> None:
        self.master = UniversalMasterPromptEngine()
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
        topic: str,
        genres: list[str],
        target_duration_s: int = 24,
        package_version: str = "v1",
    ) -> dict[str, Any]:
        package_dir.mkdir(parents=True, exist_ok=True)
        self.presets.load_all(validate=True)

        blend = self.master.blend_genres(genres)
        topic_obj, research_md = self.research.research_topic(topic=topic, genres=genres)
        blueprint_md, script_md, beats = self.story.build_blueprint_and_script(
            topic=topic,
            genre_blend=blend,
            target_duration_s=target_duration_s,
        )
        narration_plan, caption_audio_plan = self.narration.build_plan(
            beats,
            target_wpm=blend["target_wpm"],
            caption_preset_id=blend["default_caption_preset"],
        )
        storyboard = self.storyboard_dir.build_storyboard(
            project_id=project_id,
            beats=beats,
            genre_blend=blend,
            caption_cues=caption_audio_plan["cues"],
        )
        chars, char_bible_md = self.character.build_characters(topic, blend)
        motion_plan = self.motion.build_motion_plan(storyboard)
        engine_plan, exec_md = self.orchestrator.build_engine_plan(storyboard)

        asset_manifest = {
            "schema_version": "3.3.0",
            "project_id": project_id,
            "style_bible": GLOBAL_STYLE_BIBLE_V3_3,
            "characters": chars,
            "required_assets": sorted({aid for s in storyboard["shots"] for aid in [s["environment_id"], *s["asset_ids"]]}),
        }
        prod_config = {
            "schema_version": "3.3.0",
            "project_id": project_id,
            "package_version": package_version,
            "topic": topic_obj,
            "fps": storyboard["fps"],
            "width": storyboard["width"],
            "height": storyboard["height"],
            "aspect_ratio": storyboard["aspect_ratio"],
            "total_frames": storyboard["total_frames"],
        }
        ref_md = (
            "# Analisis Referensi Pra-Produksi\n\n"
            "Tidak ada video referensi eksternal yang disalin; menggunakan Global Style Bible `xdx_stylized_diorama_v3_3`.\n"
        )

        # Write all 11 core v3.1-compatible files + extended v3.3 files
        (package_dir / "blueprint.md").write_text(blueprint_md, encoding="utf-8")
        (package_dir / "research.md").write_text(research_md, encoding="utf-8")
        (package_dir / "script.md").write_text(script_md, encoding="utf-8")
        (package_dir / "character_bible.md").write_text(char_bible_md, encoding="utf-8")
        (package_dir / "execution_plan.md").write_text(exec_md, encoding="utf-8")
        (package_dir / "reference_analysis.md").write_text(ref_md, encoding="utf-8")
        (package_dir / "storyboard.json").write_text(json.dumps(storyboard, indent=2) + "\n", encoding="utf-8")
        (package_dir / "asset_manifest.json").write_text(json.dumps(asset_manifest, indent=2) + "\n", encoding="utf-8")
        (package_dir / "motion_plan.json").write_text(json.dumps(motion_plan, indent=2) + "\n", encoding="utf-8")
        (package_dir / "production_config.json").write_text(json.dumps(prod_config, indent=2) + "\n", encoding="utf-8")
        (package_dir / "engine_plan.json").write_text(json.dumps(engine_plan, indent=2) + "\n", encoding="utf-8")
        (package_dir / "narration_dialogue.json").write_text(json.dumps(narration_plan, indent=2) + "\n", encoding="utf-8")
        (package_dir / "caption_audio_plan.json").write_text(json.dumps(caption_audio_plan, indent=2) + "\n", encoding="utf-8")

        digest, file_hashes = compute_package_digest(package_dir)

        approval_manifest = {
            "schema_version": "3.3.0",
            "project_id": project_id,
            "package_version": package_version,
            "status": "WAITING_APPROVAL",
            "package_digest": digest,
            "mandatory_13_items": {
                "01_topic_and_concept": {"present": True, "artifact_file": "blueprint.md", "summary": f"Topik '{topic}' ({', '.join(genres)})"},
                "02_research_results": {"present": True, "artifact_file": "research.md", "summary": f"{len(topic_obj['claims'])} klaim terpetakan dengan batas epistemik"},
                "03_full_script": {"present": True, "artifact_file": "script.md", "summary": f"{len(beats)} beat naskah lengkap"},
                "04_narration_and_dialogue": {"present": True, "artifact_file": "narration_dialogue.json", "summary": f"{len(narration_plan['vo_segments'])} segmen VO ({blend['target_wpm']} WPM)"},
                "05_clip_by_clip_storyboard": {"present": True, "artifact_file": "storyboard.json", "summary": f"{len(storyboard['shots'])} shot deterministik tanpa gap"},
                "06_shot_timestamps_and_durations": {"present": True, "artifact_file": "storyboard.json", "summary": f"Total {storyboard['total_frames']} frame ({storyboard['duration_s']}s @ {storyboard['fps']}fps)"},
                "07_camera_framing_cutaway_transitions": {"present": True, "artifact_file": "storyboard.json", "summary": "Lensa, sensor 36mm, cutaway bukti, dan transisi tiap shot"},
                "08_complete_asset_list": {"present": True, "artifact_file": "asset_manifest.json", "summary": f"{len(asset_manifest['required_assets'])} kebutuhan aset unik"},
                "09_character_designs": {"present": True, "artifact_file": "character_bible.md", "summary": f"{len(chars)} spesifikasi karakter orisinal"},
                "10_motion_plan": {"present": True, "artifact_file": "motion_plan.json", "summary": "Pose, anticipation, blink, IK foot-lock, dan kurva kamera"},
                "11_caption_and_audio_plan": {"present": True, "artifact_file": "caption_audio_plan.json", "summary": f"{len(caption_audio_plan['cues'])} cue subtitle & target -15 LUFS"},
                "12_engine_selection_per_shot": {"present": True, "artifact_file": "engine_plan.json", "summary": f"Routing per shot ({', '.join(engine_plan['engines_used'])})"},
                "13_hybrid_execution_plan": {"present": True, "artifact_file": "execution_plan.md", "summary": "Urutan eksekusi Blender MCP, Three.js, Remotion, dan FFmpeg"},
            },
            "required_files_sha256": file_hashes,
        }
        jsonschema.validate(instance=approval_manifest, schema=self._approval_schema)
        (package_dir / "approval_package_manifest.json").write_text(
            json.dumps(approval_manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        state_mgr = ProjectStateManager(package_dir / "project_state.json")
        state_mgr.initialize(
            project_id=project_id,
            project_title=topic,
            genres=genres,
            total_frames=storyboard["total_frames"],
        )
        state = state_mgr.mark_waiting_approval(digest, package_version=package_version)
        assert state["current_state"] == "WAITING_APPROVAL"
        return {
            "status": "WAITING_APPROVAL",
            "package_digest": digest,
            "package_version": package_version,
            "state": state,
            "approval_manifest": approval_manifest,
        }
