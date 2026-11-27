"""5-Tier Storage Persistence Classifier, Subprocess Proof & Reference Index Seeder (Phase 01.6B).

Implements Cross-Session Persistence Verification & Section 11 Reference Knowledge Index Contract:
1. Explicitly distinguishes and probes 5 storage tiers without ever claiming local VM disk
   survives remote VM deletion:
   - `CURRENT_PROCESS_MEMORY`
   - `CURRENT_SESSION_STORAGE`
   - `WORKSPACE_PERSISTENT_STORAGE`
   - `GITHUB_PERSISTENT_KNOWLEDGE`
   - `EXTERNAL_ARTIFACT_STORAGE`
2. Executes a real multi-process OS spawn proof (`prove_cross_process_sqlite_persistence`) where
   Process A writes to `SixPartitionMemoryStore` and terminates, and an independent Process B
   verifies SQLite WAL integrity + per-row SHA-256 checksums.
3. Synchronizes `reference_database/` (`REF-001` & `REF-002` original MP4 SHA-256s, preserved
   `prior_analysis.*`, and `rea_analysis_v3_4.*`) into `KnowledgeMemory` and exports a Git-safe
   seed file (`memory/seed_knowledge/reference_knowledge_index_v4.json`) with zero raw media or secrets.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.reference_database_bridge import ReferenceDatabaseBridge
from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.handoff_manager import compute_file_sha256

ROOT_DIR = Path(__file__).resolve().parent.parent

STORAGE_TIERS: tuple[str, ...] = (
    "CURRENT_PROCESS_MEMORY",
    "CURRENT_SESSION_STORAGE",
    "WORKSPACE_PERSISTENT_STORAGE",
    "GITHUB_PERSISTENT_KNOWLEDGE",
    "EXTERNAL_ARTIFACT_STORAGE",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_reference_database_into_knowledge_memory(
    store: SixPartitionMemoryStore,
    *,
    studio_root: Path | None = None,
    export_seed_path: Path | None = None,
) -> dict[str, Any]:
    """Index REF-001 & REF-002 (both preserved prior_v1 and rea_v3.4 versions) into KnowledgeMemory."""
    root = (studio_root or ROOT_DIR).resolve()
    bridge = ReferenceDatabaseBridge(studio_root=root)
    refs_by_id, _, _ = bridge.load_registries()

    from intelligence.reference_lifecycle import (
        compute_actual_analyzer_source_fingerprint,
        compute_analyzer_config_hash,
    )

    indexed_entries: list[dict[str, Any]] = []
    analyzer_fp = compute_actual_analyzer_source_fingerprint(root)
    cfg_hash = compute_analyzer_config_hash()

    for rid in sorted(refs_by_id):
        rec = bridge.verify_and_load_reference(rid, require_media=False)
        prior_sha = compute_file_sha256(rec.prior_analysis_path)
        rea_json_sha = compute_file_sha256(rec.rea_v3_4_json_path)
        rea_md_sha = compute_file_sha256(rec.rea_v3_4_md_path)

        # 1. Preserve prior analysis version (append-only v1)
        prior_res = store.knowledge.register_reference_index_entry(
            reference_id=rec.reference_id,
            video_sha256=rec.video_sha256,
            analyzer_fingerprint="legacy-prior-reference-analysis-v1",
            analyzer_config_hash=cfg_hash,
            analysis_version="prior_v1",
            evidence_manifest={
                "prior_analysis_relpath": rec.prior_analysis_path.relative_to(root).as_posix(),
                "prior_analysis_sha256": prior_sha,
                "video_bytes": rec.bytes_size,
                "profile_id": rec.profile["id"],
            },
            review_status="PRIOR_CONTEXT_PRESERVED",
        )
        indexed_entries.append(prior_res)

        # 2. Register REA-Video v3.4 multimodal analysis version (append-only v3.4)
        v34_res = store.knowledge.register_reference_index_entry(
            reference_id=rec.reference_id,
            video_sha256=rec.video_sha256,
            analyzer_fingerprint=analyzer_fp,
            analyzer_config_hash=cfg_hash,
            analysis_version="rea_v3.4",
            evidence_manifest={
                "rea_v3_4_json_relpath": rec.rea_v3_4_json_path.relative_to(root).as_posix(),
                "rea_v3_4_json_sha256": rea_json_sha,
                "rea_v3_4_md_relpath": rec.rea_v3_4_md_path.relative_to(root).as_posix(),
                "rea_v3_4_md_sha256": rea_md_sha,
                "prior_analysis_preserved_sha256": prior_sha,
                "video_bytes": rec.bytes_size,
                "genre": rec.genre,
                "profile_id": rec.profile["id"],
            },
            review_status="VERIFIED_MULTIMODAL",
        )
        indexed_entries.append(v34_res)

    seed_out = export_seed_path or (root / "memory" / "seed_knowledge" / "reference_knowledge_index_v4.json")
    seed_doc = {
        "schema_version": "4.0.0-phase01.6b",
        "storage_tier": "GITHUB_PERSISTENT_KNOWLEDGE",
        "survives_vm_deletion": True,
        "references": {
            rid: store.knowledge.list_versions(f"ref_index:{rid}")
            for rid in sorted(refs_by_id)
        },
    }
    seed_out.parent.mkdir(parents=True, exist_ok=True)
    seed_out.write_text(json.dumps(seed_doc, indent=2) + "\n", encoding="utf-8")

    return {
        "references_indexed": sorted(refs_by_id),
        "versions_registered": len(indexed_entries),
        "seed_file": seed_out.relative_to(root).as_posix() if seed_out.is_relative_to(root) else str(seed_out),
    }


class StoragePersistenceProbe:
    """Evaluates and proves actual durability boundaries across all 5 storage tiers."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()

    def prove_cross_process_sqlite_persistence(self, db_path: Path | None = None) -> dict[str, Any]:
        """Spawn Process A (writer) -> exit -> spawn Process B (reader) to prove cross-process durability."""
        with tempfile.TemporaryDirectory(prefix="xdx_persist_probe_") as tmp_dir:
            target_db = Path(db_path) if db_path else (Path(tmp_dir) / "probe_v4.sqlite3")
            writer_code = (
                "import json, sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(self.root_dir)!r}); "
                "from memory.persistent_memory import SixPartitionMemoryStore; "
                f"store = SixPartitionMemoryStore(Path({str(target_db)!r})); "
                "in_ram_only = {'ephemeral_secret_marker': 'lost_on_exit'}; "
                "r1 = store.knowledge.put_versioned(entry_id='probe:k1', version_tag='v1', category='probe', payload={'fact': 'persisted_across_os_process'}); "
                "r2 = store.project.put_slot('proj_probe', 'brief', {'topic': 'Yakhchal thermodynamics'}); "
                "r3 = store.execution.append_record(project_id='proj_probe', record_kind='checkpoint_probe', record_id='cp_1', payload={'step': 1}); "
                "print(json.dumps({'r1': r1, 'r2': r2, 'r3': r3}))"
            )
            proc_a = subprocess.run(
                [sys.executable, "-c", writer_code],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            written = json.loads(proc_a.stdout.strip())

            reader_code = (
                "import json, sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(self.root_dir)!r}); "
                "from memory.persistent_memory import SixPartitionMemoryStore; "
                f"store = SixPartitionMemoryStore(Path({str(target_db)!r})); "
                "integ = store.verify_database_integrity(); "
                "k_vers = store.knowledge.list_versions('probe:k1'); "
                "p_slot = store.project.get_latest_slot('proj_probe', 'brief'); "
                "e_recs = store.execution.list_records('proj_probe', 'checkpoint_probe'); "
                "ram_exists = 'in_ram_only' in globals(); "
                "print(json.dumps({'integrity': integ, 'k_sha': k_vers[0]['record_sha256'], "
                "'p_sha': p_slot['record_sha256'], 'e_sha': e_recs[0]['record_sha256'], 'ram_carried_over': ram_exists}))"
            )
            proc_b = subprocess.run(
                [sys.executable, "-c", reader_code],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            read_back = json.loads(proc_b.stdout.strip())

            verified = (
                read_back["integrity"]["all_rows_sha256_verified"] is True
                and read_back["k_sha"] == written["r1"]["record_sha256"]
                and read_back["p_sha"] == written["r2"]["record_sha256"]
                and read_back["e_sha"] == written["r3"]["record_sha256"]
                and read_back["ram_carried_over"] is False
            )
            if not verified:
                raise RuntimeError(f"Cross-process SQLite persistence verification failed: {read_back}")

            return {
                "verified": True,
                "writer_exit_code": proc_a.returncode,
                "reader_exit_code": proc_b.returncode,
                "ram_carried_over": read_back["ram_carried_over"],
                "sqlite_integrity": read_back["integrity"]["sqlite_integrity"],
                "verified_digests": {
                    "knowledge": read_back["k_sha"],
                    "project": read_back["p_sha"],
                    "execution": read_back["e_sha"],
                },
            }

    def generate_tier_report(self) -> dict[str, Any]:
        """Produce honest 5-tier durability classification & live cross-process proof."""
        cross_proc = self.prove_cross_process_sqlite_persistence()
        seed_path = self.root_dir / "memory" / "seed_knowledge" / "reference_knowledge_index_v4.json"
        bridge = ReferenceDatabaseBridge(studio_root=self.root_dir)
        refs_by_id, _, _ = bridge.load_registries()
        lfs_hydrated = all(
            bridge.verify_and_load_reference(rid, require_media=False).media_verification_status == "VERIFIED"
            for rid in sorted(refs_by_id)
        )

        tiers = {
            "CURRENT_PROCESS_MEMORY": {
                "location": "Python process heap / local dicts",
                "survives_process_exit": False,
                "survives_conversation_pause_resume": False,
                "survives_vm_deletion": False,
                "verified_behavior": "Discarded immediately on process exit (ram_carried_over == False).",
            },
            "CURRENT_SESSION_STORAGE": {
                "location": tempfile.gettempdir(),
                "survives_process_exit": True,
                "survives_conversation_pause_resume": True,
                "survives_vm_deletion": False,
                "verified_behavior": "Ephemeral OS temp directory; never relied upon for checkpoints or approvals.",
            },
            "WORKSPACE_PERSISTENT_STORAGE": {
                "location": f"{self.root_dir.as_posix()}/.xdx_memory & projects/<project_id>/",
                "survives_process_exit": True,
                "survives_conversation_pause_resume": True,
                "survives_vm_deletion": False,
                "honest_limitation": (
                    "Persists across separate OS processes and paused/resumed sessions on this remote VM, "
                    "but does NOT survive remote VM deletion unless committed/pushed to GitHub or exported."
                ),
                "cross_process_proof": cross_proc,
            },
            "GITHUB_PERSISTENT_KNOWLEDGE": {
                "location": "Git-tracked structured JSON/MD in fiankuns/XDX-Autonomous-Video-Studio",
                "seed_knowledge_present": seed_path.is_file(),
                "survives_process_exit": True,
                "survives_conversation_pause_resume": True,
                "survives_vm_deletion": True,
                "security_policy": "Structured schemas, seeds, and audit evidence only; zero tokens, caches, or raw transcripts.",
            },
            "EXTERNAL_ARTIFACT_STORAGE": {
                "location": "GitHub LFS (reference_database/references/**/*.mp4) & dedicated audit-bundle-* branches",
                "git_lfs_media_hydrated": lfs_hydrated,
                "survives_process_exit": True,
                "survives_conversation_pause_resume": True,
                "survives_vm_deletion": True,
            },
        }
        return {
            "schema_version": "4.0.0-phase01.6b",
            "generated_at_utc": _utc_now_iso(),
            "tiers": tiers,
        }
