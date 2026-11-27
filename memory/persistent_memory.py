"""Six-Partition Transactional Persistent Memory Engine (Phase 01.6B).

Implements Section 7, Section 8 & Section 11 requirements using Python's built-in
transactional `sqlite3` (`WAL` mode + `BEGIN IMMEDIATE` + auxiliary `fcntl` lock):
1. `KnowledgeMemory` (Reference DB index, REA versions, verified research, production profiles)
2. `ProductionMemory` (Tested animation/camera/asset/material presets & engine compatibility)
3. `ProjectMemory` (User request, topic, genre, script, storyboard, Character/Style Bibles, decisions)
4. `ExecutionMemory` (Task graph, invocation receipts, task status, attempts, manifests, checkpoints)
5. `ErrorMemory` (Error classification, failed task, root cause, defect report, correction history, regression test)
6. `QualityMemory` (Technical QC evidence, visual QC evidence, benchmark results, review status)

Guarantees:
- Atomic ACID transactions & cross-process concurrency safety (`WAL` + `busy_timeout=10000` + `fcntl.flock`)
- Per-row canonical JSON `record_sha256` verification on every read (`CorruptedMemoryRecordError`)
- Strict `project_id` isolation across projects
- Secret/token & raw-transcript leak blocker (`SecretLeakBlockedError`)
- Append-only versioning on `KnowledgeMemory` so prior reference analyses are never overwritten
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
MEMORY_SCHEMA_VERSION = "4.0.0-phase01.6b"

SECRET_PATTERNS = re.compile(
    r"("
    r"ghp_[A-Za-z0-9]{20,}|"
    r"gho_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z_-]{30,}|"
    r"Bearer\s+[A-Za-z0-9._\-]{16,}|"
    r"/opt/antigravity/tokens|"
    r"\"(?:access_token|refresh_token|client_secret|private_key|api_key|auth_token)\"\s*:\s*\"[^\"]+\""
    r")"
)

MAX_RECORD_PAYLOAD_BYTES = 256_000  # Blocks dumping huge raw conversation transcripts into structured memory


class MemoryIntegrityError(RuntimeError):
    """Base exception for persistent memory integrity or security violations."""


class CorruptedMemoryRecordError(MemoryIntegrityError):
    """Raised when a stored memory row fails SHA-256 verification or JSON deserialization."""


class SecretLeakBlockedError(MemoryIntegrityError):
    """Raised when attempting to persist tokens, credentials, secrets, or oversized raw transcripts."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_and_sha(payload: dict[str, Any]) -> tuple[str, str]:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_RECORD_PAYLOAD_BYTES:
        raise SecretLeakBlockedError(
            f"Memory record payload ({len(raw)} chars) exceeds {MAX_RECORD_PAYLOAD_BYTES}B limit (raw conversation dumps forbidden)"
        )
    if SECRET_PATTERNS.search(raw):
        raise SecretLeakBlockedError("Blocked attempt to store secret, token, or credential in persistent memory!")
    dig = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, dig


def _verify_and_parse_row(payload_json: str, expected_sha256: str, table_name: str, row_key: str) -> dict[str, Any]:
    actual_sha = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    if actual_sha != expected_sha256:
        raise CorruptedMemoryRecordError(
            f"Corrupted record detected in '{table_name}' for key='{row_key}': "
            f"expected sha256={expected_sha256}, actual={actual_sha}"
        )
    try:
        obj = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise CorruptedMemoryRecordError(f"Malformed JSON in '{table_name}' key='{row_key}'") from exc
    if not isinstance(obj, dict):
        raise CorruptedMemoryRecordError(f"Expected JSON object in '{table_name}' key='{row_key}'")
    return obj


class SixPartitionMemoryStore:
    """SQLite WAL + fcntl cross-process persistent store hosting all 6 structured memory partitions."""

    def __init__(self, db_path: Path | None = None) -> None:
        default_path = ROOT_DIR / ".xdx_memory" / "xdx_agent_memory_v4.sqlite3"
        self.db_path = Path(os.path.realpath(db_path or default_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.db_path.with_suffix(".db.lock")
        self._init_schema()

        self.knowledge = KnowledgeMemory(self)
        self.production = ProductionMemory(self)
        self.project = ProjectMemory(self)
        self.execution = ExecutionMemory(self)
        self.error = ErrorMemory(self)
        self.quality = QualityMemory(self)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=15000;")
        return conn

    def execute_write(self, fn: Any) -> Any:
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                res = fn(conn)
                if conn.in_transaction:
                    conn.execute("COMMIT;")
                return res
            except Exception:
                try:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK;")
                except sqlite3.Error:
                    pass
                raise
            finally:
                conn.close()
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def execute_read(self, fn: Any) -> Any:
        conn = self._connect()
        try:
            return fn(conn)
        finally:
            conn.close()

    def _init_schema(self) -> None:
        ddl_statements = (
            """
            CREATE TABLE IF NOT EXISTS memory_schema_meta (
                schema_version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_memory (
                entry_id TEXT NOT NULL,
                version_tag TEXT NOT NULL,
                category TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (entry_id, version_tag)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS production_memory (
                technique_id TEXT NOT NULL,
                version_tag TEXT NOT NULL,
                domain TEXT NOT NULL,
                test_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (technique_id, version_tag)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS project_memory (
                project_id TEXT NOT NULL,
                slot_key TEXT NOT NULL,
                version_num INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_id, slot_key, version_num)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_memory (
                project_id TEXT NOT NULL,
                record_kind TEXT NOT NULL,
                record_id TEXT NOT NULL,
                seq_num INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, record_kind, record_id, seq_num)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS error_memory (
                project_id TEXT NOT NULL,
                error_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                error_category TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, error_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS quality_memory (
                project_id TEXT NOT NULL,
                evaluation_id TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                review_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, evaluation_id)
            );
            """,
        )

        def _setup(conn: sqlite3.Connection) -> None:
            for stmt in ddl_statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT OR IGNORE INTO memory_schema_meta (schema_version, applied_at) VALUES (?, ?);",
                (MEMORY_SCHEMA_VERSION, _utc_now_iso()),
            )

        self.execute_write(_setup)

    def verify_database_integrity(self) -> dict[str, Any]:
        """Run SQLite PRAGMA integrity_check AND verify every stored row's SHA-256 across all 6 tables."""
        tables = (
            ("knowledge_memory", "entry_id"),
            ("production_memory", "technique_id"),
            ("project_memory", "slot_key"),
            ("execution_memory", "record_id"),
            ("error_memory", "error_id"),
            ("quality_memory", "evaluation_id"),
        )

        def _check(conn: sqlite3.Connection) -> dict[str, Any]:
            pragma_res = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            if pragma_res != "ok":
                raise CorruptedMemoryRecordError(f"SQLite integrity_check failed: {pragma_res}")

            counts: dict[str, int] = {}
            for tbl, key_col in tables:
                rows = conn.execute(f"SELECT {key_col}, payload_json, record_sha256 FROM {tbl};").fetchall()
                for r in rows:
                    _verify_and_parse_row(r["payload_json"], r["record_sha256"], tbl, str(r[key_col]))
                counts[tbl] = len(rows)
            return {
                "schema_version": MEMORY_SCHEMA_VERSION,
                "sqlite_integrity": pragma_res,
                "partition_row_counts": counts,
                "all_rows_sha256_verified": True,
            }

        return self.execute_read(_check)


class KnowledgeMemory:
    """Append-only versioned store for Reference DB indexes, REA versions, verified research & profiles."""

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def register_reference_index_entry(
        self,
        *,
        reference_id: str,
        video_sha256: str,
        analyzer_fingerprint: str,
        analyzer_config_hash: str,
        analysis_version: str,
        evidence_manifest: dict[str, Any],
        review_status: str,
    ) -> dict[str, Any]:
        if review_status not in {"VERIFIED_MULTIMODAL", "PRIOR_CONTEXT_PRESERVED", "PENDING_REVIEW"}:
            raise ValueError(f"Invalid knowledge review_status: {review_status}")
        payload = {
            "reference_id": reference_id,
            "video_sha256": video_sha256,
            "analyzer_fingerprint": analyzer_fingerprint,
            "analyzer_config_hash": analyzer_config_hash,
            "analysis_version": analysis_version,
            "evidence_manifest": evidence_manifest,
            "review_status": review_status,
        }
        return self.put_versioned(
            entry_id=f"ref_index:{reference_id}",
            version_tag=analysis_version,
            category="reference_index",
            payload=payload,
        )

    def put_versioned(
        self,
        *,
        entry_id: str,
        version_tag: str,
        category: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> None:
            existing = conn.execute(
                "SELECT record_sha256 FROM knowledge_memory WHERE entry_id=? AND version_tag=?;",
                (entry_id, version_tag),
            ).fetchone()
            if existing is not None and existing["record_sha256"] != sig:
                raise MemoryIntegrityError(
                    f"Append-only violation: knowledge entry '{entry_id}'@{version_tag} already exists with different digest; increment version_tag instead of overwriting!"
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO knowledge_memory
                (entry_id, version_tag, category, payload_json, record_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (entry_id, version_tag, category, raw, sig, now),
            )

        self._store.execute_write(_write)
        return {"entry_id": entry_id, "version_tag": version_tag, "record_sha256": sig}

    def list_versions(self, entry_id: str) -> list[dict[str, Any]]:
        def _read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT version_tag, category, payload_json, record_sha256, created_at FROM knowledge_memory WHERE entry_id=? ORDER BY created_at ASC;",
                (entry_id,),
            ).fetchall()
            return [
                {
                    "entry_id": entry_id,
                    "version_tag": r["version_tag"],
                    "category": r["category"],
                    "payload": _verify_and_parse_row(r["payload_json"], r["record_sha256"], "knowledge_memory", entry_id),
                    "record_sha256": r["record_sha256"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

        return self._store.execute_read(_read)


class ProductionMemory:
    """Stores verified/tested animation, camera, asset, material, and engine compatibility techniques."""

    ALLOWED_VERIFIED_STATUSES: frozenset[str] = frozenset(
        {"UNIT_TESTED", "INTEGRATION_TESTED", "RUNTIME_TESTED", "RENDER_TESTED", "VISUAL_QC_PASSED"}
    )

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def record_tested_technique(
        self,
        *,
        technique_id: str,
        version_tag: str,
        domain: str,
        test_status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if test_status not in self.ALLOWED_VERIFIED_STATUSES:
            raise MemoryIntegrityError(
                f"Cannot promote unverified technique '{technique_id}' with status='{test_status}' into ProductionMemory"
            )
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT OR REPLACE INTO production_memory
                (technique_id, version_tag, domain, test_status, payload_json, record_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (technique_id, version_tag, domain, test_status, raw, sig, now),
            )

        self._store.execute_write(_write)
        return {"technique_id": technique_id, "version_tag": version_tag, "record_sha256": sig}

    def get_technique(self, technique_id: str, version_tag: str = "v1") -> dict[str, Any] | None:
        def _read(conn: sqlite3.Connection) -> dict[str, Any] | None:
            r = conn.execute(
                "SELECT domain, test_status, payload_json, record_sha256, created_at FROM production_memory WHERE technique_id=? AND version_tag=?;",
                (technique_id, version_tag),
            ).fetchone()
            if r is None:
                return None
            return {
                "technique_id": technique_id,
                "version_tag": version_tag,
                "domain": r["domain"],
                "test_status": r["test_status"],
                "payload": _verify_and_parse_row(
                    r["payload_json"], r["record_sha256"], "production_memory", technique_id
                ),
                "record_sha256": r["record_sha256"],
            }

        return self._store.execute_read(_read)


class ProjectMemory:
    """Strictly project-isolated versioned slot store (request, topic, script, storyboard, bibles, decisions)."""

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def put_slot(self, project_id: str, slot_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not project_id.strip() or not slot_key.strip():
            raise ValueError("project_id and slot_key must be non-empty")
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COALESCE(MAX(version_num), 0) AS max_v FROM project_memory WHERE project_id=? AND slot_key=?;",
                (project_id, slot_key),
            ).fetchone()
            next_v = int(row["max_v"]) + 1
            conn.execute(
                """
                INSERT INTO project_memory (project_id, slot_key, version_num, payload_json, record_sha256, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (project_id, slot_key, next_v, raw, sig, now),
            )
            return next_v

        ver = self._store.execute_write(_write)
        return {"project_id": project_id, "slot_key": slot_key, "version_num": ver, "record_sha256": sig}

    def get_latest_slot(self, project_id: str, slot_key: str) -> dict[str, Any] | None:
        def _read(conn: sqlite3.Connection) -> dict[str, Any] | None:
            r = conn.execute(
                """
                SELECT version_num, payload_json, record_sha256, updated_at
                FROM project_memory
                WHERE project_id=? AND slot_key=?
                ORDER BY version_num DESC LIMIT 1;
                """,
                (project_id, slot_key),
            ).fetchone()
            if r is None:
                return None
            return {
                "project_id": project_id,
                "slot_key": slot_key,
                "version_num": int(r["version_num"]),
                "payload": _verify_and_parse_row(
                    r["payload_json"], r["record_sha256"], "project_memory", f"{project_id}:{slot_key}"
                ),
                "record_sha256": r["record_sha256"],
                "updated_at": r["updated_at"],
            }

        return self._store.execute_read(_read)


class ExecutionMemory:
    """Append-only project-isolated ledger for task graphs, receipts, task transitions, and checkpoints."""

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def append_record(
        self,
        *,
        project_id: str,
        record_kind: str,
        record_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq_num), 0) AS max_s FROM execution_memory WHERE project_id=? AND record_kind=? AND record_id=?;",
                (project_id, record_kind, record_id),
            ).fetchone()
            seq = int(row["max_s"]) + 1
            conn.execute(
                """
                INSERT INTO execution_memory
                (project_id, record_kind, record_id, seq_num, payload_json, record_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (project_id, record_kind, record_id, seq, raw, sig, now),
            )
            return seq

        seq_num = self._store.execute_write(_write)
        return {
            "project_id": project_id,
            "record_kind": record_kind,
            "record_id": record_id,
            "seq_num": seq_num,
            "record_sha256": sig,
        }

    def list_records(self, project_id: str, record_kind: str | None = None) -> list[dict[str, Any]]:
        def _read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            if record_kind:
                rows = conn.execute(
                    """
                    SELECT record_kind, record_id, seq_num, payload_json, record_sha256, created_at
                    FROM execution_memory
                    WHERE project_id=? AND record_kind=?
                    ORDER BY created_at ASC, seq_num ASC;
                    """,
                    (project_id, record_kind),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT record_kind, record_id, seq_num, payload_json, record_sha256, created_at
                    FROM execution_memory
                    WHERE project_id=?
                    ORDER BY created_at ASC, seq_num ASC;
                    """,
                    (project_id,),
                ).fetchall()
            return [
                {
                    "project_id": project_id,
                    "record_kind": r["record_kind"],
                    "record_id": r["record_id"],
                    "seq_num": int(r["seq_num"]),
                    "payload": _verify_and_parse_row(
                        r["payload_json"], r["record_sha256"], "execution_memory", r["record_id"]
                    ),
                    "record_sha256": r["record_sha256"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

        return self._store.execute_read(_read)


class ErrorMemory:
    """Project-isolated error, defect, root-cause, and regression test ledger."""

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def record_error(
        self,
        *,
        project_id: str,
        error_id: str,
        task_id: str,
        error_category: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT OR REPLACE INTO error_memory
                (project_id, error_id, task_id, error_category, payload_json, record_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (project_id, error_id, task_id, error_category, raw, sig, now),
            )

        self._store.execute_write(_write)
        return {"project_id": project_id, "error_id": error_id, "record_sha256": sig}

    def list_errors(self, project_id: str) -> list[dict[str, Any]]:
        def _read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT error_id, task_id, error_category, payload_json, record_sha256, created_at FROM error_memory WHERE project_id=? ORDER BY created_at ASC;",
                (project_id,),
            ).fetchall()
            return [
                {
                    "project_id": project_id,
                    "error_id": r["error_id"],
                    "task_id": r["task_id"],
                    "error_category": r["error_category"],
                    "payload": _verify_and_parse_row(r["payload_json"], r["record_sha256"], "error_memory", r["error_id"]),
                    "record_sha256": r["record_sha256"],
                }
                for r in rows
            ]

        return self._store.execute_read(_read)


class QualityMemory:
    """Project-isolated store for technical QC, visual QC, benchmarks, and independent review verdicts."""

    def __init__(self, store: SixPartitionMemoryStore) -> None:
        self._store = store

    def record_evaluation(
        self,
        *,
        project_id: str,
        evaluation_id: str,
        target_ref: str,
        review_status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raw, sig = _canonical_json_and_sha(payload)
        now = _utc_now_iso()

        def _write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT OR REPLACE INTO quality_memory
                (project_id, evaluation_id, target_ref, review_status, payload_json, record_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (project_id, evaluation_id, target_ref, review_status, raw, sig, now),
            )

        self._store.execute_write(_write)
        return {"project_id": project_id, "evaluation_id": evaluation_id, "record_sha256": sig}

    def list_evaluations(self, project_id: str) -> list[dict[str, Any]]:
        def _read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT evaluation_id, target_ref, review_status, payload_json, record_sha256, created_at FROM quality_memory WHERE project_id=? ORDER BY created_at ASC;",
                (project_id,),
            ).fetchall()
            return [
                {
                    "project_id": project_id,
                    "evaluation_id": r["evaluation_id"],
                    "target_ref": r["target_ref"],
                    "review_status": r["review_status"],
                    "payload": _verify_and_parse_row(
                        r["payload_json"], r["record_sha256"], "quality_memory", r["evaluation_id"]
                    ),
                    "record_sha256": r["record_sha256"],
                }
                for r in rows
            ]

        return self._store.execute_read(_read)
