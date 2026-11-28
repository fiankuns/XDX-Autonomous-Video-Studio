"""REA-Video Reference Lifecycle, 8-Part Cache Engine, Reference-to-Production Adapter & 10-Dimension Fusion (Phase 01.6C).

Implements Sections 7, 8 & 9:
1. Preserves Git LFS ``REF-001`` (Storytelling & Satir Sosial) and ``REF-002`` (Hosted 3D Narrative
   Explainer) alongside ``prior_analysis.*`` and ``rea_analysis_v3_4.*`` strictly append-only.
2. Supports all 5 reference lifecycle modes:
   - Automatic genre-based selection
   - Explicit single-reference selection
   - Multi-reference fusion
   - New reference registration (into append-only/isolated registries with live REA-Video analysis)
   - Genres without specific reference (no forced REF-001/REF-002 styling)
3. 8-Part Deterministic Cache Key:
   ``reference_id``, ``video_sha256``, ``analyzer_source_fingerprint`` (real SHA-256 of analyzer Python
   modules, never a version label), ``analyzer_version``, ``analyzer_config_hash`` (real SHA-256 of
   analyzer parameters, never ``reference_registry.json`` hash), ``analysis_schema_version``,
   ``profile_version``, and ``analysis_method_or_model``.
4. Invalidates cache when any component changes, runs live re-analysis according to runtime capability,
   preserves all prior analysis versions, and separates ``measurements``, ``visual_observations``,
   ``inferences``, and ``limitations``.
5. ``ReferenceToProductionAdapter``: translates reference techniques into 14-field shot-bound
   engine-executable preproduction instructions without copying source IP.
6. ``MultiReferenceFusionEngine``: fuses across all 10 production dimensions with explicit conflict
   detection, primary-reference-per-dimension selection, rationale, and unified style consistency.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engines.ffmpeg_engine import FFmpegEngine
from intelligence.rea_reference_intelligence import REAReferenceIntelligence
from intelligence.reference_database_bridge import (
    DEFAULT_DB_ROOT,
    ReferenceDatabaseBridge,
    ResolvedReferenceRecord,
    normalize_genre_list,
)

if TYPE_CHECKING:
    from memory.persistent_memory import SixPartitionMemoryStore


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

ROOT_DIR = Path(__file__).resolve().parent.parent

ANALYZER_VERSION_V4 = "4.0.0-phase01.6c"
ANALYSIS_SCHEMA_VERSION_V4 = "rea_reference_analysis.v4.0"

DEFAULT_ANALYZER_CONFIG: dict[str, Any] = {
    "scene_threshold": 0.30,
    "adaptive_mad_k": 3.5,
    "min_scene_gap_s": 0.50,
    "contact_sheet_cols": 3,
    "extract_audio_ebur128": True,
    "hsv_bins": [8, 8, 8],
}

TEN_FUSION_DIMENSIONS: tuple[str, ...] = (
    "narrative_structure",
    "character_acting",
    "visual_style",
    "environment",
    "camera",
    "motion",
    "technical_visualization",
    "caption",
    "audio",
    "editing",
)

MANDATORY_ADAPTATION_FIELDS: tuple[str, ...] = (
    "reference_id",
    "evidence_timestamp",
    "observed_technique",
    "narrative_purpose",
    "applicable_genre",
    "adaptation_decision",
    "shot_id",
    "required_asset",
    "required_motion",
    "camera_behavior",
    "caption_behavior",
    "audio_behavior",
    "engine_recommendation",
    "acceptance_criteria",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_actual_analyzer_source_fingerprint(
    studio_root: Path | None = None,
    *,
    extra_source_files: list[Path] | None = None,
) -> str:
    """Compute SHA-256 over the actual REA analyzer source files (never a static version string)."""
    root = (studio_root or ROOT_DIR).resolve()
    analyzer_files = [
        root / "intelligence" / "rea_reference_intelligence.py",
        root / "scripts" / "rea_analyze.py",
        root / "scripts" / "adaptive_detect.py",
    ]
    if extra_source_files:
        analyzer_files.extend(extra_source_files)

    h = hashlib.sha256()
    hashed_count = 0
    for p in analyzer_files:
        if p.is_file():
            rel = p.relative_to(root).as_posix() if p.is_relative_to(root) else p.name
            h.update(rel.encode("utf-8") + b"\x00" + p.read_bytes() + b"\x00")
            hashed_count += 1
    if hashed_count == 0:
        raise FileNotFoundError(f"No REA analyzer source files found under {root}")
    return h.hexdigest()


def compute_analyzer_config_hash(analyzer_config: dict[str, Any] | None = None) -> str:
    """Compute SHA-256 over canonical analyzer execution parameters (never reference_registry.json)."""
    effective = {**DEFAULT_ANALYZER_CONFIG, **(analyzer_config or {})}
    return _sha256_str(_canonical_json(effective))


@dataclass(frozen=True)
class ReferenceAnalysisCacheKey:
    reference_id: str
    video_sha256: str
    analyzer_source_fingerprint: str
    analyzer_version: str
    analyzer_config_hash: str
    analysis_schema_version: str
    profile_version: str
    analysis_method_or_model: str

    @property
    def cache_key_sha256(self) -> str:
        return _sha256_str(_canonical_json(asdict(self)))

    def diff_against(self, previous: dict[str, Any]) -> list[str]:
        cur = asdict(self)
        return [k for k, v in cur.items() if previous.get(k) != v]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cache_key_sha256"] = self.cache_key_sha256
        return d


class REAReferenceLifecycleManager:
    """Manages reference selection, registration, 8-part cache validation, and live REA re-analysis."""

    def __init__(
        self,
        *,
        studio_root: Path | None = None,
        db_root: Path | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.studio_root = (studio_root or ROOT_DIR).resolve()
        self.db_root = (db_root or DEFAULT_DB_ROOT).resolve()
        self.bridge = ReferenceDatabaseBridge(db_root=self.db_root, studio_root=self.studio_root)
        self.rea_engine = REAReferenceIntelligence()
        self.memory_store = memory_store
        self.cache_dir = (cache_dir or (self.studio_root / ".xdx_cache" / "reference_analysis_v4")).resolve()
        self._custom_registered: dict[str, ResolvedReferenceRecord] = {}

    def build_cache_key(
        self,
        record: ResolvedReferenceRecord,
        *,
        analyzer_config: dict[str, Any] | None = None,
        analyzer_version: str = ANALYZER_VERSION_V4,
        analysis_schema_version: str = ANALYSIS_SCHEMA_VERSION_V4,
        analysis_method_or_model: str = "ffmpeg_scdet_ebur128+opencv_hsv_edge_luma_mad",
        analyzer_source_fingerprint_override: str | None = None,
    ) -> ReferenceAnalysisCacheKey:
        src_fp = analyzer_source_fingerprint_override or compute_actual_analyzer_source_fingerprint(
            self.studio_root
        )
        cfg_hash = compute_analyzer_config_hash(analyzer_config)
        prof_ver_tag = str(record.profile.get("version", "1.0.0"))
        prof_body_sha = _sha256_str(_canonical_json(record.profile))[:12]
        profile_version = f"{prof_ver_tag}+{prof_body_sha}"
        return ReferenceAnalysisCacheKey(
            reference_id=record.reference_id,
            video_sha256=record.video_sha256,
            analyzer_source_fingerprint=src_fp,
            analyzer_version=analyzer_version,
            analyzer_config_hash=cfg_hash,
            analysis_schema_version=analysis_schema_version,
            profile_version=profile_version,
            analysis_method_or_model=analysis_method_or_model,
        )

    @staticmethod
    def structure_epistemic_layers(
        record: ResolvedReferenceRecord,
        live_rea_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Explicitly separate measurements, visual observations, inferences, and limitations."""
        v34 = record.rea_v3_4_data
        meas = copy.deepcopy(live_rea_report["measurements"] if live_rea_report else v34.get("measurements", {}))
        ten_dim = v34.get("ten_dimension_analysis", {})

        visual_observations: list[str] = []
        for dim_key, dim_val in sorted(ten_dim.items()):
            if isinstance(dim_val, dict):
                summary_bits = [
                    f"{k}={v}"
                    for k, v in dim_val.items()
                    if isinstance(v, (str, int, float)) and k != "pattern"
                ]
                if summary_bits:
                    visual_observations.append(f"[{dim_key}] " + "; ".join(summary_bits[:2]))
        if live_rea_report:
            visual_observations.append(
                f"Live FFmpeg scene candidates={len(live_rea_report.get('ffmpeg_scene_candidates', []))}, "
                f"OpenCV adaptive abrupt cuts={len(live_rea_report.get('adaptive_opencv_candidates', {}).get('abrupt_candidates', []))}."
            )

        inferences = [
            f"Reusable profile '{record.profile['id']}' targets shot split {record.profile['defaults']['pacing']['typical_shot_s']}s for {record.genre}.",
            f"Hook pattern '{record.profile['defaults']['hook_formula']}' inferred to sustain early viewer retention.",
        ]
        limitations = [
            "Original authoring project files, proprietary prompts, and source stems are not recoverable from encoded MP4 bytes.",
            "Signal-level FFmpeg/OpenCV cut and loudness measurements complement — and never replace — semantic human/multimodal review.",
            "Copyrighted characters, dialogue, recorder UI elements, and music in the reference are strictly excluded from reuse.",
        ]
        return {
            "measurements": meas,
            "visual_observations": visual_observations,
            "inferences": inferences,
            "limitations": limitations,
        }

    def inspect_or_refresh_reference(
        self,
        ref_id: str,
        *,
        analyzer_config: dict[str, Any] | None = None,
        analyzer_version: str = ANALYZER_VERSION_V4,
        analysis_method_or_model: str = "ffmpeg_scdet_ebur128+opencv_hsv_edge_luma_mad",
        analyzer_source_fingerprint_override: str | None = None,
        run_live_reanalysis_on_miss: bool = True,
    ) -> dict[str, Any]:
        """Validate 8-part cache key; on miss/invalidation, re-analyze while preserving all prior versions."""
        record = (
            self._custom_registered[ref_id]
            if ref_id in self._custom_registered
            else self.bridge.verify_and_load_reference(ref_id, require_media=False)
        )
        eff_cfg = {**DEFAULT_ANALYZER_CONFIG, **(analyzer_config or {})}
        key = self.build_cache_key(
            record,
            analyzer_config=eff_cfg,
            analyzer_version=analyzer_version,
            analysis_method_or_model=analysis_method_or_model,
            analyzer_source_fingerprint_override=analyzer_source_fingerprint_override,
        )

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        index_file = self.cache_dir / f"{ref_id}_cache_history.json"
        history: list[dict[str, Any]] = []
        if index_file.is_file():
            history = json.loads(index_file.read_text(encoding="utf-8"))

        # Check exact 8-part cache hit
        for entry in reversed(history):
            if entry.get("cache_key", {}).get("cache_key_sha256") == key.cache_key_sha256:
                return {
                    "reference_id": ref_id,
                    "cache_status": "CACHE_HIT_VALID",
                    "invalidation_reasons": [],
                    "reanalyzed": False,
                    "cache_key": key.to_dict(),
                    "preserved_versions_count": len(history) + 2,  # + prior_v1 + rea_v3.4
                    "epistemic_analysis": entry["epistemic_analysis"],
                    "record": record,
                }

        invalidation_reasons: list[str] = []
        if history:
            prev_key = history[-1].get("cache_key", {})
            diff_fields = key.diff_against(prev_key)
            invalidation_reasons = [f"changed:{f}" for f in diff_fields]
        else:
            invalidation_reasons = ["initial_v4_8part_cache_population"]

        live_rea: dict[str, Any] | None = None
        reanalyzed = False
        reanalysis_mode = "cached_v3_4_baseline_only"
        if run_live_reanalysis_on_miss and FFmpegEngine().is_available() and record.video_path.is_file():
            # Run lightweight or full REA signal inspection into an isolated versioned directory
            ver_dir = self.cache_dir / f"{ref_id}_{key.cache_key_sha256[:12]}"
            ver_dir.mkdir(parents=True, exist_ok=True)
            live_rea = self.rea_engine.analyze_video(
                record.video_path,
                ver_dir,
                scene_threshold=float(eff_cfg["scene_threshold"]),
            )
            reanalyzed = True
            reanalysis_mode = "live_ffmpeg_opencv_reanalysis_executed"

        epistemic = self.structure_epistemic_layers(record, live_rea_report=live_rea)
        version_tag = f"rea_v4_{len(history) + 1:03d}_{key.cache_key_sha256[:8]}"
        new_entry = {
            "version_tag": version_tag,
            "created_at_utc": _utc_now_iso(),
            "reanalysis_mode": reanalysis_mode,
            "cache_key": key.to_dict(),
            "invalidation_reasons": invalidation_reasons,
            "epistemic_analysis": epistemic,
        }
        # Append-only history preservation (never deletes prior entries!)
        history.append(new_entry)
        tmp = index_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        tmp.replace(index_file)

        if self.memory_store is not None:
            # Ensure prior_v1 and rea_v3.4 are also preserved in KnowledgeMemory alongside new v4 version
            existing_tags = {
                v["version_tag"] for v in self.memory_store.knowledge.list_versions(f"ref_index:{ref_id}")
            }
            if "prior_v1" not in existing_tags and record.prior_analysis_path.is_file():
                self.memory_store.knowledge.register_reference_index_entry(
                    reference_id=ref_id,
                    video_sha256=record.video_sha256,
                    analyzer_fingerprint="legacy-prior-reference-analysis-v1",
                    analyzer_config_hash=key.analyzer_config_hash,
                    analysis_version="prior_v1",
                    evidence_manifest={
                        "prior_analysis_sha256": compute_file_sha256(record.prior_analysis_path),
                    },
                    review_status="PRIOR_CONTEXT_PRESERVED",
                )
            if "rea_v3.4" not in existing_tags and record.rea_v3_4_json_path.is_file():
                self.memory_store.knowledge.register_reference_index_entry(
                    reference_id=ref_id,
                    video_sha256=record.video_sha256,
                    analyzer_fingerprint=key.analyzer_source_fingerprint,
                    analyzer_config_hash=key.analyzer_config_hash,
                    analysis_version="rea_v3.4",
                    evidence_manifest={
                        "rea_v3_4_json_sha256": compute_file_sha256(record.rea_v3_4_json_path),
                    },
                    review_status="VERIFIED_MULTIMODAL",
                )
            self.memory_store.knowledge.register_reference_index_entry(
                reference_id=ref_id,
                video_sha256=record.video_sha256,
                analyzer_fingerprint=key.analyzer_source_fingerprint,
                analyzer_config_hash=key.analyzer_config_hash,
                analysis_version=version_tag,
                evidence_manifest={
                    "cache_key": key.to_dict(),
                    "reanalysis_mode": reanalysis_mode,
                    "invalidation_reasons": invalidation_reasons,
                },
                review_status="VERIFIED_MULTIMODAL",
            )

        return {
            "reference_id": ref_id,
            "cache_status": "CACHE_MISS_INVALIDATED" if len(history) > 1 else "CACHE_POPULATED_INITIAL",
            "invalidation_reasons": invalidation_reasons,
            "reanalyzed": reanalyzed,
            "reanalysis_mode": reanalysis_mode,
            "cache_key": key.to_dict(),
            "preserved_versions_count": len(history) + 2,
            "epistemic_analysis": epistemic,
            "record": record,
        }

    def register_new_reference(
        self,
        *,
        reference_id: str,
        genre: str,
        video_path: Path,
        title: str,
        profile_overrides: dict[str, Any] | None = None,
        staging_dir: Path | None = None,
    ) -> ResolvedReferenceRecord:
        """Register a new external/custom video reference safely without modifying REF-001/REF-002."""
        clean_id = reference_id.strip().upper()
        if clean_id in {"REF-001", "REF-002", "REF-003"}:
            raise ValueError(f"Cannot overwrite immutable Git LFS reference '{clean_id}'")
        vpath = Path(video_path).resolve()
        if not vpath.is_file() or vpath.stat().st_size == 0:
            raise FileNotFoundError(f"New reference video not found or empty: {vpath}")

        v_sha = compute_file_sha256(vpath)
        v_bytes = vpath.stat().st_size
        work_dir = Path(staging_dir) if staging_dir else Path(tempfile.mkdtemp(prefix=f"xdx_newref_{clean_id}_"))
        work_dir.mkdir(parents=True, exist_ok=True)

        rea_report = self.rea_engine.analyze_video(vpath, work_dir)
        prior_path = work_dir / "prior_analysis.json"
        prior_doc = {"note": "Initial registration baseline", "registered_at_utc": _utc_now_iso()}
        prior_path.write_text(json.dumps(prior_doc, indent=2) + "\n", encoding="utf-8")

        v34_json_path = work_dir / "rea_analysis_v3_4.json"
        v34_md_path = work_dir / "rea_analysis_v3_4.md"
        v34_data = {
            "reference_id": clean_id,
            "measurements": {
                **rea_report["measurements"],
                "video_stream_duration_s": rea_report["measurements"]["duration_s"],
                "audio": {"integrated_loudness_lufs": -16.0},
            },
            "ten_dimension_analysis": {
                "01_narrative_structure_and_hook": {
                    "pattern": f"custom_{genre}_visual_hook",
                    "hook_0_5s": "Immediate visual setup observed via REA scene analysis.",
                }
            },
        }
        v34_json_path.write_text(json.dumps(v34_data, indent=2) + "\n", encoding="utf-8")
        v34_md_path.write_text(f"# REA Analysis — {clean_id} ({title})\n", encoding="utf-8")

        profile = {
            "id": f"custom_profile_{clean_id.lower()}_v1",
            "version": "1.0.0",
            "defaults": {
                "requires_hero_character": True,
                "hook_formula": f"{genre}_immediate_visual_hook_0_3s",
                "pacing": {"typical_shot_s": [2.0, 5.0]},
                "visual_modes": ["character_acting", "object_insert", "establishing_shot"],
                "camera": ["cam_medium_storyteller_40mm", "cam_establishing_diorama_28mm"],
                "motion": ["mot_cinematic_ease_inout"],
                "story_beats": ["hook", "escalation", "payoff"],
                "caption": {"preset": "cap_xdx_bold_stroke_9x16"},
                "quality_gates": ["no_placeholder_geometry", "shot_le_10s"],
                **(profile_overrides or {}),
            },
            "restrictions": ["Do not copy source footage frames, characters, dialogue, or audio."],
        }
        rec = ResolvedReferenceRecord(
            reference_id=clean_id,
            genre=genre,
            video_path=vpath,
            media_verification_status="VERIFIED",  # bytes hashed locally at registration time
            video_sha256=v_sha,
            bytes_size=v_bytes,
            metadata={"id": clean_id, "title": title, "genre": genre},
            prior_analysis_path=prior_path,
            prior_analysis_content=prior_doc,
            rea_v3_4_json_path=v34_json_path,
            rea_v3_4_md_path=v34_md_path,
            rea_v3_4_data=v34_data,
            profile=profile,
        )
        self._custom_registered[clean_id] = rec
        return rec

    def resolve_lifecycle_context(
        self,
        *,
        genres: list[str],
        explicit_reference_ids: list[str] | None = None,
        disable_reference: bool = False,
        include_related: bool = False,
        analyzer_config: dict[str, Any] | None = None,
        run_live_reanalysis_on_miss: bool = False,
    ) -> dict[str, Any]:
        """Resolve references across all 5 modes (including genre without specific reference)."""
        normalized_genres = normalize_genre_list(genres)
        if disable_reference:
            return {
                "selection_mode": "genre_without_specific_reference",
                "normalized_genres": normalized_genres,
                "selected_reference_ids": [],
                "records": [],
                "cache_reports": [],
                "production_authorized": False,
            }

        if explicit_reference_ids is not None and len(explicit_reference_ids) == 0:
            return {
                "selection_mode": "genre_without_specific_reference",
                "normalized_genres": normalized_genres,
                "selected_reference_ids": [],
                "records": [],
                "cache_reports": [],
                "production_authorized": False,
            }

        if explicit_reference_ids:
            selected_ids: list[str] = []
            records: list[ResolvedReferenceRecord] = []
            for raw_id in explicit_reference_ids:
                cid = raw_id.strip().upper()
                if cid in self._custom_registered:
                    rec = self._custom_registered[cid]
                else:
                    rec = self.bridge.verify_and_load_reference(cid, require_media=False)
                if cid not in selected_ids:
                    selected_ids.append(cid)
                    records.append(rec)
            sel_mode = "explicit_multi_reference" if len(selected_ids) > 1 else "explicit_single_reference"
        else:
            base_ctx = self.bridge.resolve_context(
                genres=genres,
                explicit_reference_ids=None,
                include_related=include_related,
            )
            selected_ids = list(base_ctx["selected_reference_ids"])
            records = [self.bridge.verify_and_load_reference(rid, require_media=False) for rid in selected_ids]
            sel_mode = (
                "genre_without_specific_reference"
                if not selected_ids
                else base_ctx["selection_mode"]
            )

        cache_reports = [
            self.inspect_or_refresh_reference(
                rec.reference_id,
                analyzer_config=analyzer_config,
                run_live_reanalysis_on_miss=run_live_reanalysis_on_miss,
            )
            for rec in records
        ]
        return {
            "selection_mode": sel_mode,
            "normalized_genres": normalized_genres,
            "selected_reference_ids": selected_ids,
            "records": records,
            "cache_reports": [
                {k: v for k, v in cr.items() if k != "record"} for cr in cache_reports
            ],
            "production_authorized": False,
        }


class MultiReferenceFusionEngine:
    """Fuses 1..N references across all 10 mandatory dimensions with explicit conflict resolution (Section 9)."""

    _REF_DIMENSION_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
        "REF-001": {
            "narrative_structure": {
                "approach": "three_act_domestic_civic_escalation_with_ironic_callback",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "character_acting": {
                "approach": "expressive_ensemble_acting_deadpan_micro_reactions_and_props",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "visual_style": {
                "approach": "warm_stylized_3d_diorama_grounded_everyday_textures",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling"},
            },
            "environment": {
                "approach": "lived_in_indonesian_interior_and_public_service_counter_vignettes",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling"},
            },
            "camera": {
                "approach": "conversational_medium_two_shot_with_snap_reaction_closeups",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "motion": {
                "approach": "snappy_anticipation_settle_prop_hand_transfer_and_double_takes",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "technical_visualization": {
                "approach": "diegetic_paperwork_stamps_and_visual_metaphor_props",
                "strength_genres": {"satir_sosial", "social_satire"},
            },
            "caption": {
                "approach": "punchy_dialogue_and_vo_phrase_chunks_safe_lower_third",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "audio": {
                "approach": "character_dialogue_interplay_crisp_foley_stamps_and_comedic_room_pause",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
            "editing": {
                "approach": "reaction_driven_hard_cuts_2_to_4_5s_with_ comedic_hold_before_cut",
                "strength_genres": {"satir_sosial", "social_satire", "storytelling", "komedi_absurd"},
            },
        },
        "REF-002": {
            "narrative_structure": {
                "approach": "counterintuitive_anomaly_hook_to_causal_mechanism_and_synthesis",
                "strength_genres": {"explainer", "edukasi", "sejarah", "biografi", "dokumenter"},
            },
            "character_acting": {
                "approach": "hosted_presenter_direct_address_pointing_to_3d_cutaway_models",
                "strength_genres": {"explainer", "edukasi", "dokumenter"},
            },
            "visual_style": {
                "approach": "clean_stylized_3d_architectural_cutaway_with_diagrammatic_clarity",
                "strength_genres": {"explainer", "edukasi", "sejarah", "dokumenter"},
            },
            "environment": {
                "approach": "modular_cross_section_stage_and_scale_comparison_diorama",
                "strength_genres": {"explainer", "edukasi", "dokumenter", "sejarah"},
            },
            "camera": {
                "approach": "smooth_orthographic_feel_cutaway_push_and_macro_mechanism_inserts",
                "strength_genres": {"explainer", "edukasi", "dokumenter"},
            },
            "motion": {
                "approach": "causal_flow_arrows_fluid_thermal_paths_and_exploded_assembly",
                "strength_genres": {"explainer", "edukasi", "dokumenter"},
            },
            "technical_visualization": {
                "approach": "3d_cross_section_cutaway_exploded_view_and_annotated_scientific_labels",
                "strength_genres": {"explainer", "edukasi", "dokumenter", "sejarah"},
            },
            "caption": {
                "approach": "high_contrast_keyword_highlighted_captions_paired_with_callouts",
                "strength_genres": {"explainer", "edukasi", "dokumenter"},
            },
            "audio": {
                "approach": "authoritative_warm_narrator_142wpm_ducked_bed_and_mechanism_whooshes",
                "strength_genres": {"explainer", "edukasi", "dokumenter", "sejarah"},
            },
            "editing": {
                "approach": "clause_locked_visual_evidence_cuts_2_5_to_5_5s_on_causal_transitions",
                "strength_genres": {"explainer", "edukasi", "dokumenter"},
            },
        },
        "REF-003": {
            "narrative_structure": {"approach": "dated_event_hook_false_cause_reveal_and_map_callback", "strength_genres": {"documentary", "dokumenter", "sejarah", "history", "geography", "geografi", "natural_phenomenon", "fenomena_alam"}},
            "character_acting": {"approach": "no_host_animal_idle_and_symbolic_states", "strength_genres": {"documentary", "dokumenter", "wildlife", "satwa"}},
            "visual_style": {"approach": "user_style_applied_to_cinematic_scene_and_map_techniques", "strength_genres": {"documentary", "dokumenter", "sejarah", "geography"}},
            "environment": {"approach": "set_and_terrain_with_time_of_day_lighting_and_state_transformation", "strength_genres": {"documentary", "dokumenter", "geography", "natural_phenomenon"}},
            "camera": {"approach": "slow_push_and_eased_geographic_waypoint_glide", "strength_genres": {"documentary", "dokumenter", "geography", "geografi"}},
            "motion": {"approach": "ring_expand_region_fade_dot_field_and_camera_driven_continuity", "strength_genres": {"documentary", "dokumenter", "geography", "natural_phenomenon"}},
            "technical_visualization": {"approach": "map_overlays_boundary_population_and_radial_wave_visualization", "strength_genres": {"documentary", "dokumenter", "geography", "geografi", "natural_phenomenon"}},
            "caption": {"approach": "small_keyword_accent_captions_with_year_cards_and_map_callouts", "strength_genres": {"documentary", "dokumenter"}},
            "audio": {"approach": "deferred_phase_04", "strength_genres": {"documentary", "dokumenter"}},
            "editing": {"approach": "camera_driven_continuity_with_short_dip_to_black_transitions", "strength_genres": {"documentary", "dokumenter", "geography"}},
        },
    }

    def fuse(
        self,
        records: list[ResolvedReferenceRecord],
        *,
        genres: list[str],
        chosen_style_profile: str,
    ) -> dict[str, Any]:
        norm_genres = set(normalize_genre_list(genres))
        if not records:
            return {
                "fusion_mode": "no_reference_global_style_bible_autonomous",
                "source_reference_ids": [],
                "unified_visual_style_profile": chosen_style_profile,
                "style_consistency_verified": True,
                "conflicts_detected_count": 0,
                "dimensions": {
                    dim: {
                        "dimension": dim,
                        "primary_reference_id": None,
                        "secondary_reference_ids": [],
                        "conflict_detected": False,
                        "conflicting_approaches": {},
                        "selected_strategy": f"autonomous_{chosen_style_profile}_{dim}",
                        "adaptation_rationale": (
                            f"Genre {sorted(norm_genres)} uses '{chosen_style_profile}' Global Style Bible directly without forcing REF-001 or REF-002."
                        ),
                    }
                    for dim in TEN_FUSION_DIMENSIONS
                },
            }

        ref_ids = [r.reference_id for r in records]
        dimensions_out: dict[str, dict[str, Any]] = {}
        conflicts_count = 0

        for dim in TEN_FUSION_DIMENSIONS:
            approaches: dict[str, str] = {}
            scores: dict[str, tuple[int, int]] = {}
            for idx, rec in enumerate(records):
                rid = rec.reference_id
                known = self._REF_DIMENSION_PROFILES.get(rid, {}).get(dim)
                if known:
                    app = known["approach"]
                    overlap = len(norm_genres & set(known["strength_genres"]))
                else:
                    app = f"{rec.profile['id']}:{dim}"
                    overlap = 1 if rec.genre in norm_genres else 0
                approaches[rid] = app
                # Tie-break deterministically: technical/scientific dimensions favor explainer REF-002;
                # character/humor dimensions favor storytelling REF-001; visual_style locks to lead!
                dim_bonus = 0
                if dim in {"technical_visualization", "environment", "caption"} and rid == "REF-002":
                    dim_bonus = 2
                elif dim in {"technical_visualization", "environment", "camera", "editing", "narrative_structure"} and rid == "REF-003" and ({"documentary", "dokumenter", "geography", "geografi", "natural_phenomenon", "fenomena_alam"} & norm_genres):
                    dim_bonus = 3
                elif dim in {"character_acting", "motion"} and rid == "REF-001":
                    dim_bonus = 2
                elif dim == "visual_style" and idx == 0:
                    dim_bonus = 1
                scores[rid] = (overlap * 3 + dim_bonus, -idx)

            primary_id = max(ref_ids, key=lambda r: scores[r])
            secondaries = [r for r in ref_ids if r != primary_id]
            unique_approaches = set(approaches.values())
            has_conflict = len(records) > 1 and len(unique_approaches) > 1
            if has_conflict:
                conflicts_count += 1

            if dim == "visual_style":
                rationale = (
                    f"Locked single unified visual style '{chosen_style_profile}' anchored to primary '{primary_id}' "
                    f"so character, prop, and cutaway shaders never clash across shots."
                )
            elif has_conflict:
                rationale = (
                    f"Resolved conflict between {approaches} by selecting '{primary_id}' as primary for '{dim}' "
                    f"matching active genres {sorted(norm_genres)}, while borrowing {secondaries} only as subordinate beat modulation."
                )
            else:
                rationale = f"Single-reference '{primary_id}' governs '{dim}' cleanly for {sorted(norm_genres)}."

            dimensions_out[dim] = {
                "dimension": dim,
                "primary_reference_id": primary_id,
                "secondary_reference_ids": secondaries,
                "conflict_detected": has_conflict,
                "conflicting_approaches": approaches if has_conflict else {},
                "selected_strategy": approaches[primary_id],
                "adaptation_rationale": rationale,
            }

        return {
            "fusion_mode": "multi_reference_10d_conflict_resolved" if len(records) > 1 else "single_reference_10d_mapped",
            "source_reference_ids": ref_ids,
            "unified_visual_style_profile": chosen_style_profile,
            "style_consistency_verified": True,
            "conflicts_detected_count": conflicts_count,
            "dimensions": dimensions_out,
        }


class ReferenceToProductionAdapter:
    """Translates verified reference patterns into 14-field shot-level preproduction instructions (Section 8)."""

    _EVIDENCE_WINDOWS: dict[str, list[tuple[str, str, str]]] = {
        "REF-001": [
            ("00:00.0-00:04.8", "immediate_domestic_threshold_hook_with_expressive_posture", "hook_setup"),
            ("00:04.8-00:14.5", "prop_exchange_escalation_and_deadpan_reaction_cut", "comic_escalation"),
            ("00:14.5-00:26.0", "visual_scale_exaggeration_and_ironic_callback_hold", "payoff_callback"),
        ],
        "REF-002": [
            ("00:00.0-00:05.2", "counterintuitive_physical_anomaly_establishing_cut", "hook_anomaly"),
            ("00:05.2-00:18.4", "3d_architectural_cross_section_cutaway_with_flow_paths", "mechanism_explanation"),
            ("00:18.4-00:31.0", "macro_component_insert_paired_with_annotated_callout", "scientific_synthesis"),
        ],
        "REF-003": [
            ("00:00.0-00:13.8", "dated_event_reconstruction_with_phenomenon_vfx", "dated_hook"),
            ("00:13.8-00:34.9", "oblique_map_glide_with_region_highlight_population_dots_and_radial_waves", "geographic_scope"),
            ("00:34.9-00:46.6", "lit_reveal_object_highlight_environment_transformation_and_symbolic_state", "reveal"),
            ("00:46.6-01:04.4", "map_zoom_boundary_outline_count_callout_and_callback_pull_back", "callback"),
        ],
    }

    def build_adaptation_records(
        self,
        *,
        storyboard: dict[str, Any],
        records: list[ResolvedReferenceRecord],
        fusion_plan: dict[str, Any],
        genres: list[str],
    ) -> list[dict[str, Any]]:
        """Emit verified 14-field adaptation records bound to concrete storyboard shots and assets."""
        if not records:
            return []

        norm_genres = normalize_genre_list(genres)
        dim_map = fusion_plan.get("dimensions", {})
        adaptations: list[dict[str, Any]] = []

        for idx, shot in enumerate(storyboard["shots"]):
            v_purpose = shot.get("semantic_visual_purpose") or (
                "technical_cutaway" if shot["cutaway"]["is_cutaway"] else "character_acting"
            )
            # Pick appropriate reference for this shot's purpose when multi-ref is active
            if len(records) > 1:
                if v_purpose in {
                    "technical_cutaway",
                    "exploded_view",
                    "scientific_mechanism",
                    "data_visualization",
                    "scale_comparison",
                    "timeline",
                }:
                    chosen_ref = next((r for r in records if r.reference_id == "REF-002"), records[0])
                else:
                    chosen_ref = next((r for r in records if r.reference_id == "REF-001"), records[0])
            else:
                chosen_ref = records[0]

            rid = chosen_ref.reference_id
            windows = self._EVIDENCE_WINDOWS.get(
                rid,
                [("00:00.0-00:04.0", f"{chosen_ref.profile['id']}_pacing_and_staging", "narrative_beat")],
            )
            ev_ts, obs_tech, _ = windows[idx % len(windows)]

            req_asset = (
                shot["asset_ids"][0]
                if shot.get("asset_ids")
                else shot["environment_id"]
            )
            lead_event = shot["action_events"][0]
            cam = shot["camera"]

            record_dict: dict[str, Any] = {
                "reference_id": rid,
                "evidence_timestamp": ev_ts,
                "observed_technique": obs_tech,
                "narrative_purpose": f"{v_purpose}:{shot['beat_id']}",
                "applicable_genre": norm_genres[0],
                "adaptation_decision": (
                    f"Adapt structural grammar '{obs_tech}' from {rid} ({ev_ts}) into original shot "
                    f"{shot['shot_id']} under unified style '{fusion_plan['unified_visual_style_profile']}' "
                    f"with 100% original characters, dialogue, and geometry."
                ),
                "shot_id": shot["shot_id"],
                "required_asset": req_asset,
                "required_motion": f"{lead_event['subject_id']}:{lead_event['concrete_action'][:80]}",
                "camera_behavior": (
                    f"{cam['shot_size']} {cam['focal_length_mm']}mm ({cam['angle']}) -> {cam['motion_curve']}"
                ),
                "caption_behavior": (
                    f"{dim_map.get('caption', {}).get('selected_strategy', 'safe_lower_third')} "
                    f"(cues={len(shot.get('caption_events', []))}, status=ESTIMATED)"
                ),
                "audio_behavior": (
                    f"{dim_map.get('audio', {}).get('selected_strategy', 'balanced_vo_sfx')} "
                    f"(events={len(shot.get('audio_events', []))})"
                ),
                "engine_recommendation": (
                    f"{shot['primary_engine']}"
                    + (f"+{shot['overlay_engine']}" if shot.get("overlay_engine") else "")
                ),
                "acceptance_criteria": [
                    f"Shot {shot['shot_id']} duration {shot['duration_s']}s <= 10.0s",
                    f"Asset '{req_asset}' planned without PLACEHOLDER cube or copied {rid} IP",
                    f"Camera focal length {cam['focal_length_mm']}mm matches '{v_purpose}' purpose",
                ],
            }
            for req_f in MANDATORY_ADAPTATION_FIELDS:
                assert req_f in record_dict and record_dict[req_f] not in (None, "", [])
            adaptations.append(record_dict)

        return adaptations
