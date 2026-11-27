"""Automatic Reference Intelligence Bridge for XDX Internal Reference Database (v3.4).

Integrates `reference_database/` (`REF-001`, `REF-002`, future append-only entries) with
`CreativePipeline`, `UniversalMasterPromptEngine`, `StoryboardDirector`, and `PreProductionPackageBuilder`.

Enforces all rules in `reference_database/integration/AGENT_REFERENCE_RULES.md`:
1. Automatic genre routing:
   - `explainer` (including `explainair`, `explaner`, `explain er`) -> `REF-002` (`hosted_3d_explainer_cutaway_v1`)
   - `storytelling` / `social_satire` (`satir_sosial`, `satir sosial`, `cerita`) -> `REF-001` (`satirical_3d_vignette_storytelling_v1`)
   - Multi-genre combinations of both automatically fuse `["REF-002", "REF-001"]`.
   - Other genres preserve existing defaults and surface `related_candidates` only as non-forced suggestions unless `include_related=True`.
2. Explicit `--ref-id` single or multi-reference selection overrides genre defaults.
3. Simultaneous fusion of (a) verified original MP4 bytes & `ffprobe`, (b) REA-Video v3.4 multimodal analysis,
   (c) reusable production profile, and (d) preserved prior analysis/research — NEVER asking the user to re-upload
   reachable database videos.
4. Fail-closed verification: missing media or unhydrated Git LFS pointers raise `ReferenceMediaIntegrityError` (`MEDIA_MISSING` / `INTEGRITY_FAILED`).
5. Read-only governance: `production_authorized` is ALWAYS `False`; never bypasses `ApprovalGate`.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_ROOT = ROOT_DIR / "reference_database"


class ReferenceMediaIntegrityError(RuntimeError):
    """Raised when a registered reference MP4 is missing, corrupt, or still an unhydrated Git LFS pointer."""


def _load_reference_db_module(db_root: Path) -> Any:
    script_path = db_root / "scripts" / "reference_db.py"
    if not script_path.is_file():
        raise FileNotFoundError(f"reference_db.py not found at {script_path}")
    spec = importlib.util.spec_from_file_location("xdx_reference_db_cli", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GENRE_NORMALIZATION_MAP: dict[str, str] = {
    "explainair": "explainer",
    "explaner": "explainer",
    "explain er": "explainer",
    "satir sosial": "social_satire",
    "cerita": "storytelling",
    "education": "edukasi",
    "history": "sejarah",
}


def normalize_genre_token(raw_genre: str, db_aliases: dict[str, str] | None = None) -> str:
    """Normalize user genre strings (including 'explainair' and 'satir sosial') into Studio canonical tokens."""
    token = (raw_genre or "").strip().lower()
    if token == "satir_sosial":
        # Keep satir_sosial valid in Studio schemas while mapping cleanly to social_satire in DB lookup
        return "satir_sosial"
    if token in GENRE_NORMALIZATION_MAP:
        return GENRE_NORMALIZATION_MAP[token]
    if db_aliases and token in db_aliases:
        mapped = db_aliases[token]
        if mapped == "education":
            return "edukasi"
        if mapped == "history":
            return "sejarah"
        return mapped
    return token


def normalize_genre_list(raw_genres: list[str], db_aliases: dict[str, str] | None = None) -> list[str]:
    """Deduplicate and normalize a list of genres while preserving user priority order."""
    out: list[str] = []
    for g in raw_genres:
        norm = normalize_genre_token(g, db_aliases=db_aliases)
        if norm and norm not in out:
            out.append(norm)
    return out


@dataclass(frozen=True)
class ResolvedReferenceRecord:
    reference_id: str
    genre: str
    video_path: Path
    video_sha256: str
    bytes_size: int
    metadata: dict[str, Any]
    prior_analysis_path: Path
    prior_analysis_content: Any
    rea_v3_4_json_path: Path
    rea_v3_4_md_path: Path
    rea_v3_4_data: dict[str, Any]
    profile: dict[str, Any]


class ReferenceDatabaseBridge:
    """Read-only selector, verifier, and multi-reference profile synthesizer for `reference_database/`."""

    def __init__(
        self,
        db_root: Path | None = None,
        studio_root: Path | None = None,
    ) -> None:
        self.db_root = (db_root or DEFAULT_DB_ROOT).resolve()
        self.studio_root = (studio_root or ROOT_DIR).resolve()
        self._db_mod = _load_reference_db_module(self.db_root)

    def load_registries(self) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
        ref_reg = json.loads((self.db_root / "reference_registry.json").read_text(encoding="utf-8"))
        refs_by_id = {entry["id"]: entry for entry in ref_reg["references"]}
        if len(refs_by_id) != len(ref_reg["references"]):
            raise ValueError("Duplicate reference ID in reference_registry.json")

        genre_reg = json.loads((self.db_root / "genre_registry.json").read_text(encoding="utf-8"))
        pattern_reg = json.loads(
            (self.db_root / "profiles" / "reference_pattern_registry.json").read_text(encoding="utf-8")
        )
        profiles_by_id = {p["id"]: p for p in pattern_reg.get("profiles", [])}
        return refs_by_id, genre_reg, profiles_by_id

    def verify_and_load_reference(self, ref_id: str, *, hydrate: bool = False) -> ResolvedReferenceRecord:
        refs_by_id, _, profiles_by_id = self.load_registries()
        if ref_id not in refs_by_id:
            raise KeyError(f"Unknown reference ID '{ref_id}'. Available: {sorted(refs_by_id)}")
        entry = refs_by_id[ref_id]

        try:
            video_path = Path(self._db_mod.get_video(self.db_root, entry, hydrate=hydrate))
        except (FileNotFoundError, ValueError) as exc:
            raise ReferenceMediaIntegrityError(str(exc)) from exc

        meta_path = Path(self._db_mod.safe_path(self.db_root, entry["metadata"]))
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        prior_rel = entry.get("prior_analysis") or metadata.get("prior_analysis")
        if not prior_rel:
            # Fallback discovery for additive compatibility
            cand_json = video_path.parent / "prior_analysis.json"
            cand_md = video_path.parent / "prior_analysis.md"
            prior_path = cand_json if cand_json.is_file() else cand_md
        else:
            prior_path = Path(self._db_mod.safe_path(self.db_root, prior_rel))

        if not prior_path.is_file():
            raise FileNotFoundError(f"Preserved prior analysis missing for {ref_id}: {prior_path}")
        prior_content: Any = (
            json.loads(prior_path.read_text(encoding="utf-8"))
            if prior_path.suffix == ".json"
            else prior_path.read_text(encoding="utf-8")
        )

        v34_json_rel = metadata.get("rea_analysis_v3_4_json")
        v34_md_rel = metadata.get("rea_analysis_v3_4_md")
        v34_json_path = (
            Path(self._db_mod.safe_path(self.db_root, v34_json_rel))
            if v34_json_rel
            else video_path.parent / "rea_analysis_v3_4.json"
        )
        v34_md_path = (
            Path(self._db_mod.safe_path(self.db_root, v34_md_rel))
            if v34_md_rel
            else video_path.parent / "rea_analysis_v3_4.md"
        )
        if not v34_json_path.is_file() or not v34_md_path.is_file():
            raise FileNotFoundError(f"Versioned REA v3.4 analysis missing for {ref_id}")
        rea_v3_4_data = json.loads(v34_json_path.read_text(encoding="utf-8"))

        profile_id = entry.get("profile_id") or metadata.get("profile_id") or rea_v3_4_data.get("reusable_production_profile_id")
        if not profile_id or profile_id not in profiles_by_id:
            raise KeyError(f"Production profile '{profile_id}' not found for {ref_id}")

        return ResolvedReferenceRecord(
            reference_id=ref_id,
            genre=entry["genre"],
            video_path=video_path,
            video_sha256=entry["sha256"],
            bytes_size=int(entry["bytes"]),
            metadata=metadata,
            prior_analysis_path=prior_path,
            prior_analysis_content=prior_content,
            rea_v3_4_json_path=v34_json_path,
            rea_v3_4_md_path=v34_md_path,
            rea_v3_4_data=rea_v3_4_data,
            profile=profiles_by_id[profile_id],
        )

    def resolve_context(
        self,
        *,
        genres: list[str],
        explicit_reference_ids: list[str] | None = None,
        include_related: bool = False,
        hydrate: bool = False,
    ) -> dict[str, Any]:
        """Resolve single, multi, or genre-routed references and fuse all 4 intelligence layers."""
        refs_by_id, genre_reg, _ = self.load_registries()
        aliases = genre_reg.get("aliases", {})
        defaults_map = genre_reg.get("defaults", {})
        related_map = genre_reg.get("related_candidates", {})

        normalized_genres = normalize_genre_list(genres, db_aliases=aliases)
        selected_ids: list[str] = []
        related_candidates: list[str] = []
        selection_mode = "genre_retained_existing_default"

        if explicit_reference_ids:
            for rid in explicit_reference_ids:
                clean_id = rid.strip().upper()
                if clean_id not in refs_by_id:
                    raise KeyError(f"Explicit reference ID '{clean_id}' does not exist in reference_registry.json")
                if clean_id not in selected_ids:
                    selected_ids.append(clean_id)
            selection_mode = (
                "explicit_multi_reference" if len(selected_ids) > 1 else "explicit_single_reference"
            )
        else:
            for raw_g in genres:
                g_key = (raw_g or "").strip().lower()
                db_genre = aliases.get(g_key, g_key)
                if db_genre in defaults_map:
                    for rid in defaults_map[db_genre]:
                        if rid not in selected_ids:
                            selected_ids.append(rid)
                elif db_genre in related_map:
                    for rid in related_map[db_genre]:
                        if include_related:
                            if rid not in selected_ids:
                                selected_ids.append(rid)
                        elif rid not in related_candidates:
                            related_candidates.append(rid)

            if len(selected_ids) > 1:
                selection_mode = "automatic_multi_genre_reference_fusion"
            elif len(selected_ids) == 1:
                selection_mode = "automatic_genre_default"
            elif related_candidates:
                selection_mode = "existing_genre_profile_with_optional_related_candidates"

        records = [self.verify_and_load_reference(rid, hydrate=hydrate) for rid in selected_ids]
        fingerprint = self._db_mod.analyzer_fingerprint(self.studio_root)

        fused_profile = self._fuse_profiles(records)
        markdown_report = self._render_package_reference_markdown(
            normalized_genres=normalized_genres,
            selection_mode=selection_mode,
            records=records,
            related_candidates=related_candidates,
            analyzer_fingerprint=fingerprint,
            fused_profile=fused_profile,
        )

        return {
            "schema_version": "3.4.0",
            "database_integrated": True,
            "selection_mode": selection_mode,
            "normalized_genres": normalized_genres,
            "selected_reference_ids": selected_ids,
            "related_candidate_ids": [r for r in related_candidates if r not in selected_ids],
            "upload_prompt_suppressed": bool(selected_ids),
            "production_authorized": False,
            "analyzer_fingerprint": fingerprint,
            "references": [
                {
                    "id": rec.reference_id,
                    "genre": rec.genre,
                    "video_relpath": str(rec.video_path.relative_to(self.studio_root)),
                    "video_sha256": rec.video_sha256,
                    "bytes": rec.bytes_size,
                    "verification_status": "VERIFIED",
                    "profile_id": rec.profile["id"],
                    "prior_analysis_relpath": str(rec.prior_analysis_path.relative_to(self.studio_root)),
                    "rea_analysis_v3_4_relpath": str(rec.rea_v3_4_json_path.relative_to(self.studio_root)),
                    "measurements": rec.rea_v3_4_data["measurements"],
                    "narrative_pattern": rec.rea_v3_4_data["ten_dimension_analysis"]["01_narrative_structure_and_hook"]["pattern"],
                }
                for rec in records
            ],
            "fused_production_profile": fused_profile,
            "reference_analysis_markdown": markdown_report,
        }

    @staticmethod
    def _fuse_profiles(records: list[ResolvedReferenceRecord]) -> dict[str, Any] | None:
        if not records:
            return None

        visual_modes: list[str] = []
        camera_modes: list[str] = []
        motion_modes: list[str] = []
        story_beats: list[str] = []
        quality_gates: list[str] = []
        restrictions: list[str] = []
        typical_mins: list[float] = []
        typical_maxs: list[float] = []

        for rec in records:
            defs = rec.profile["defaults"]
            typical = defs["pacing"]["typical_shot_s"]
            typical_mins.append(float(typical[0]))
            typical_maxs.append(float(typical[1]))
            for item, acc in (
                (defs.get("visual_modes", []), visual_modes),
                (defs.get("camera", []), camera_modes),
                (defs.get("motion", []), motion_modes),
                (defs.get("story_beats", []), story_beats),
                (defs.get("quality_gates", []), quality_gates),
                (rec.profile.get("restrictions", []), restrictions),
            ):
                for val in item:
                    if val not in acc:
                        acc.append(val)

        lead_defs = records[0].profile["defaults"]
        return {
            "is_multi_reference_blend": len(records) > 1,
            "source_reference_ids": [r.reference_id for r in records],
            "profile_ids": [r.profile["id"] for r in records],
            "requires_hero_character": any(bool(r.profile["defaults"].get("requires_hero_character")) for r in records),
            "hook_formula": lead_defs["hook_formula"],
            "pacing_benchmark": {
                "typical_shot_s": [round(min(typical_mins), 2), round(max(typical_maxs), 2)],
                "preferred_split_s": round(min(4.5, sum(typical_maxs) / len(typical_maxs)), 2),
                "hard_max_shot_s": 10.0,
            },
            "story_beats": story_beats,
            "visual_modes": visual_modes,
            "camera_vocabulary": camera_modes,
            "motion_vocabulary": motion_modes,
            "caption_preset": lead_defs["caption"]["preset"],
            "quality_gates": quality_gates,
            "restrictions": restrictions,
        }

    @staticmethod
    def _render_package_reference_markdown(
        *,
        normalized_genres: list[str],
        selection_mode: str,
        records: list[ResolvedReferenceRecord],
        related_candidates: list[str],
        analyzer_fingerprint: str,
        fused_profile: dict[str, Any] | None,
    ) -> str:
        lines = [
            "# Analisis Referensi Pra-Produksi Terintegrasi (`reference_database` v3.4)",
            "",
            f"- **Mode Pemilihan Referensi**: `{selection_mode}`",
            f"- **Genre Terkompilasi**: `{', '.join(normalized_genres)}`",
            f"- **Sidik Jari Analyzer REA (`SHA-256`)**: `{analyzer_fingerprint}`",
            "- **Status Otorisasi Produksi**: `False` *(Referensi tidak pernah menggantikan persetujuan eksplisit pengguna)*",
        ]
        if not records:
            lines.extend(
                [
                    "",
                    "Tidak ada video referensi wajib yang dipilih untuk kombinasi genre ini; sistem mempertahankan profil bawaan genre pada Global Style Bible `xdx_stylized_diorama_v3_4`.",
                ]
            )
            if related_candidates:
                lines.append(
                    f"- **Kandidat Referensi Terkait (Opsional, Tidak Dipaksakan)**: `{', '.join(related_candidates)}`"
                )
            lines.append("")
            return "\n".join(lines)

        lines.extend(
            [
                f"- **Referensi Aktif Terverifikasi (`VERIFIED`)**: `{', '.join(r.reference_id for r in records)}` *(File asli tersedia di repositori lokal via Git LFS; sistem tidak meminta unggah ulang)*",
                "",
                "## Bukti Sumber & Lapisan Analisis Terpadu",
            ]
        )
        for rec in records:
            m = rec.rea_v3_4_data["measurements"]
            td = rec.rea_v3_4_data["ten_dimension_analysis"]
            lines.extend(
                [
                    f"### `{rec.reference_id}` (`{rec.profile['id']}`)",
                    f"- **SHA-256 Terverifikasi**: `{rec.video_sha256}` (`{rec.bytes_size:,}` byte)",
                    f"- **Spesifikasi Sinyal**: `{m['width']}x{m['height']}` · `{m['video_codec']}` · `{m['fps']:.2f} fps` · `{m['video_stream_duration_s']}s` · Audio `{m['audio']['integrated_loudness_lufs']} LUFS`",
                    f"- **Data Riset/Analisis Sebelumnya**: `{rec.prior_analysis_path.name}` dipertahankan dan digabungkan sebagai konteks.",
                    f"- **Pola Narasi & Hook**: `{td['01_narrative_structure_and_hook']['pattern']}` — {td['01_narrative_structure_and_hook']['hook_0_5s' if 'hook_0_5s' in td['01_narrative_structure_and_hook'] else 'hook_0_6s']}",
                    f"- **Benchmark Pacing**: Rentang shot tipikal `{rec.profile['defaults']['pacing']['typical_shot_s'][0]}–{rec.profile['defaults']['pacing']['typical_shot_s'][1]} detik` (`<= 10s` batas mutlak).",
                    f"- **Mode Visual & Cutaway**: `{', '.join(rec.profile['defaults']['visual_modes'][:6])}`",
                    "",
                ]
            )

        if fused_profile:
            lines.extend(
                [
                    "## Sintesis Profil Produksi & Batas Hak Cipta",
                    f"- **Penggabungan Multi-Referensi**: `{fused_profile['is_multi_reference_blend']}` (`{', '.join(fused_profile['profile_ids'])}`)",
                    f"- **Target Pemecahan Shot Storyboard**: `<= {fused_profile['pacing_benchmark']['preferred_split_s']} detik` per shot (seluruh shot `<= 10,0 detik`).",
                    "- **Aturan Anti-Plagiarisme**: Hanya mengabstraksi tata bahasa sinematografi, struktur kausal/satir, pacing klausa, dan mekanisme cutaway 3D; **dilarang keras** menyalin karakter, dialog, merek/UI aplikasi perekam layar, musik, atau aset visual sumber.",
                    "",
                ]
            )
        return "\n".join(lines)
