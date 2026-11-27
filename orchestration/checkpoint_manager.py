"""12-Field Sealed Checkpoint, Lineage, Fallback Recovery & Portable Bundle Manager (Phase 01.6C).

Implements Phase 01.6B Section 9 + Phase 01.6C Section 4.A, 4.D & Section 17 requirements:
1. Atomic, ``fcntl``-locked, ``fsync``-flushed, SHA-256-sealed checkpoints containing all 12 mandatory
   fields PLUS Phase 01.6C bindings:
   - ``checkpoint_lineage`` (``parent_checkpoint_id``, ``parent_checkpoint_sha256``, ``sequence_number``)
   - ``task_graph_digest`` and ``task_definition_digests``
   - ``durable_artifact_provenance``
2. Automatic fallback to the newest previous valid checkpoint when ``latest_checkpoint.json`` is
   corrupted or truncated (``allow_fallback_to_previous=True``).
3. Cross-project rejection (``CrossProjectCheckpointError``), task-graph/definition mismatch rejection
   (``TaskGraphMismatchError``), state-version validation (``CheckpointStateVersionError``), and
   unverified receipt/output rejection (``UnverifiedCheckpointError``).
4. Reconciliation of interrupted ``running_tasks``: unknown external side-effect tasks become ``BLOCKED``
   (never blindly retried), while safe retryable tasks obey explicit ``retry_budget``.
5. Secret-scanned, SHA-256-sealed portable checkpoint bundle export/import when cross-VM persistent
   storage is unavailable, without claiming cross-VM recovery from local/subprocess tests.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.persistent_memory import SECRET_PATTERNS, SecretLeakBlockedError, SixPartitionMemoryStore
from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256
from orchestration.native_execution_adapter import AgentInvocationReceipt
from orchestration.task_identity import (
    compute_task_definition_digest,
    compute_task_definition_digests,
    compute_task_graph_digest,
)

ROOT_DIR = Path(__file__).resolve().parent.parent

MANDATORY_CHECKPOINT_FIELDS: tuple[str, ...] = (
    "project_id",
    "task_graph_version",
    "completed_tasks",
    "pending_tasks",
    "running_tasks",
    "failed_tasks",
    "artifact_manifest",
    "artifact_sha256",
    "agent_invocation_receipts",
    "retry_budget",
    "approval_status",
    "state_version",
)


class CheckpointError(RuntimeError):
    """Base error for checkpoint persistence or recovery."""


class CorruptedCheckpointError(CheckpointError):
    """Raised when a checkpoint file is truncated, invalid JSON, missing fields, or fails SHA-256 seal check."""


class UnverifiedCheckpointError(CheckpointError):
    """Raised when a resume state lacks a valid checkpoint seal, invocation receipt, or verified disk hash."""


class CrossProjectCheckpointError(CheckpointError):
    """Raised when attempting to resume a DAG with a checkpoint belonging to a different project_id."""


class TaskGraphMismatchError(CheckpointError):
    """Raised when checkpoint task_graph_digest or task_definition_digest differs from the target DAG."""


class CheckpointStateVersionError(CheckpointError):
    """Raised when checkpoint state_version is invalid or regresses below expected minimum."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_checkpoint_seal(body: dict[str, Any]) -> str:
    clean = {k: v for k, v in body.items() if k != "checkpoint_sha256"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _transitive_dependents(seed_tasks: set[str], task_definitions: dict[str, dict[str, Any]]) -> set[str]:
    dependents_map: dict[str, list[str]] = {tid: [] for tid in task_definitions}
    for tid, h in task_definitions.items():
        for dep in h.get("dependencies", []):
            if dep in dependents_map:
                dependents_map[dep].append(tid)
    visited: set[str] = set()
    queue = list(seed_tasks)
    while queue:
        cur = queue.pop(0)
        for nxt in dependents_map.get(cur, []):
            if nxt not in visited and nxt not in seed_tasks:
                visited.add(nxt)
                queue.append(nxt)
    return visited


class CheckpointManager:
    """Manages atomic SHA-256-sealed execution checkpoints, lineage fallback, and portable bundles."""

    def __init__(
        self,
        checkpoint_dir: Path,
        *,
        root_dir: Path | None = None,
        handoff_manager: TaskHandoffManager | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.checkpoint_dir = Path(os.path.realpath(checkpoint_dir))
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.checkpoint_dir / ".checkpoint.lock"
        self.latest_file = self.checkpoint_dir / "latest_checkpoint.json"
        self.handoff_manager = handoff_manager or TaskHandoffManager(root_dir=self.root_dir)
        self.memory_store = memory_store

    def _with_lock(self, fn: Any) -> Any:
        fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return fn()
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _write_atomic(self, target: Path, doc: dict[str, Any]) -> None:
        raw_str = json.dumps(doc, indent=2) + "\n"
        if SECRET_PATTERNS.search(raw_str):
            raise SecretLeakBlockedError("Blocked attempt to store credential or secret inside checkpoint!")
        tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
        raw = raw_str.encode("utf-8")
        with tmp.open("wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)

    def _find_latest_intact_parent_unlocked(self) -> dict[str, Any] | None:
        candidates: list[Path] = []
        if self.latest_file.is_file():
            candidates.append(self.latest_file)
        candidates.extend(sorted(self.checkpoint_dir.glob("checkpoint_*.json"), reverse=True))
        for cand in candidates:
            try:
                return self.load_verified_checkpoint(cand)
            except Exception:
                continue
        return None

    def save_checkpoint(
        self,
        *,
        project_id: str,
        task_graph_version: int,
        completed_tasks: list[str],
        pending_tasks: list[str],
        running_tasks: list[str],
        failed_tasks: list[str],
        blocked_tasks: list[str] | None = None,
        cancelled_tasks: list[str] | None = None,
        artifact_manifest: dict[str, dict[str, Any]],
        artifact_sha256: dict[str, str],
        agent_invocation_receipts: dict[str, dict[str, Any]],
        retry_budget: dict[str, dict[str, Any]],
        approval_status: dict[str, Any],
        state_version: int,
        task_definitions: dict[str, dict[str, Any]],
        idempotency_ledger: dict[str, str],
    ) -> dict[str, Any]:
        """Persist a SHA-256-sealed checkpoint with lineage, graph digests, and artifact provenance."""
        if int(state_version) < 1:
            raise CheckpointStateVersionError(f"state_version must be >= 1, got {state_version}")

        def _save() -> dict[str, Any]:
            now = _utc_now_iso()
            seq_files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
            seq_num = len(seq_files) + 1
            checkpoint_id = f"CKPT-{project_id}-{seq_num:04d}"

            parent_doc = self._find_latest_intact_parent_unlocked()
            lineage = {
                "sequence_number": seq_num,
                "parent_checkpoint_id": parent_doc["checkpoint_id"] if parent_doc else None,
                "parent_checkpoint_sha256": parent_doc["checkpoint_sha256"] if parent_doc else None,
            }

            t_defs_sorted = dict(sorted(task_definitions.items()))
            t_def_digests = compute_task_definition_digests(t_defs_sorted.values()) if t_defs_sorted else {}
            t_graph_digest = compute_task_graph_digest(t_defs_sorted.values()) if t_defs_sorted else ""

            provenance: dict[str, dict[str, Any]] = {}
            for rel_p, sha in sorted(artifact_sha256.items()):
                meta = dict(artifact_manifest.get(rel_p) or {})
                owner_tid = meta.get("owner_task_id")
                rcpt = (agent_invocation_receipts.get(owner_tid) or {}) if owner_tid else {}
                size_b: int | None = None
                try:
                    cpath = self.handoff_manager.canonicalize_artifact_path(
                        rel_p, base_dir=self.root_dir, is_writable_output=False
                    )
                    if cpath.is_file():
                        size_b = cpath.stat().st_size
                except Exception:
                    size_b = None
                provenance[rel_p] = {
                    "sha256": sha,
                    "size_bytes": size_b,
                    "owner_task_id": owner_tid,
                    "owner_agent": meta.get("owner_agent") or rcpt.get("assigned_agent"),
                    "receipt_id": rcpt.get("receipt_id"),
                    "execution_mode": rcpt.get("execution_mode"),
                    "task_definition_digest": t_def_digests.get(owner_tid, "") if owner_tid else "",
                    "verified_at_utc": meta.get("verified_at_utc") or now,
                }

            doc: dict[str, Any] = {
                "schema_version": "4.0.0-phase01.6c",
                "checkpoint_id": checkpoint_id,
                "created_at_utc": now,
                "project_id": project_id,
                "task_graph_version": int(task_graph_version),
                "task_graph_digest": t_graph_digest,
                "task_definition_digests": t_def_digests,
                "checkpoint_lineage": lineage,
                "completed_tasks": sorted(set(completed_tasks)),
                "pending_tasks": sorted(set(pending_tasks)),
                "running_tasks": sorted(set(running_tasks)),
                "failed_tasks": sorted(set(failed_tasks)),
                "blocked_tasks": sorted(set(blocked_tasks or [])),
                "cancelled_tasks": sorted(set(cancelled_tasks or [])),
                "artifact_manifest": dict(sorted(artifact_manifest.items())),
                "artifact_sha256": dict(sorted(artifact_sha256.items())),
                "durable_artifact_provenance": provenance,
                "agent_invocation_receipts": dict(sorted(agent_invocation_receipts.items())),
                "retry_budget": dict(sorted(retry_budget.items())),
                "approval_status": {
                    "approved": False,  # Production approval frozen prior to Phase 01.6D
                    "approved_digest": None,
                    "approved_version": approval_status.get("approved_version"),
                    "revoked": bool(approval_status.get("revoked", False)),
                },
                "state_version": int(state_version),
                "task_definitions": t_defs_sorted,
                "idempotency_ledger": dict(sorted(idempotency_ledger.items())),
            }
            doc["checkpoint_sha256"] = _compute_checkpoint_seal(doc)

            versioned_path = self.checkpoint_dir / f"checkpoint_{seq_num:04d}.json"
            self._write_atomic(versioned_path, doc)
            self._write_atomic(self.latest_file, doc)

            if self.memory_store is not None:
                self.memory_store.execution.append_record(
                    project_id=project_id,
                    record_kind="checkpoint",
                    record_id=checkpoint_id,
                    payload={
                        "checkpoint_id": checkpoint_id,
                        "checkpoint_sha256": doc["checkpoint_sha256"],
                        "checkpoint_lineage": lineage,
                        "task_graph_version": doc["task_graph_version"],
                        "task_graph_digest": t_graph_digest,
                        "completed_tasks": doc["completed_tasks"],
                        "pending_tasks": doc["pending_tasks"],
                        "running_tasks": doc["running_tasks"],
                        "failed_tasks": doc["failed_tasks"],
                        "blocked_tasks": doc["blocked_tasks"],
                        "state_version": doc["state_version"],
                        "approved": doc["approval_status"]["approved"],
                    },
                )
            return doc

        return self._with_lock(_save)

    def load_verified_checkpoint(self, path: Path | None = None) -> dict[str, Any]:
        target = Path(path) if path else self.latest_file
        if not target.is_file():
            raise FileNotFoundError(f"Checkpoint file not found: {target}")
        try:
            raw_text = target.read_text(encoding="utf-8")
            doc = json.loads(raw_text)
        except Exception as exc:
            raise CorruptedCheckpointError(f"Checkpoint JSON parse failed for '{target}': {exc}") from exc

        if not isinstance(doc, dict):
            raise CorruptedCheckpointError("Checkpoint root must be a JSON object")

        missing = [f for f in MANDATORY_CHECKPOINT_FIELDS if f not in doc]
        if missing:
            raise CorruptedCheckpointError(f"Checkpoint missing mandatory fields: {missing}")

        if not isinstance(doc.get("state_version"), int) or int(doc["state_version"]) < 1:
            raise CheckpointStateVersionError(f"Invalid state_version in checkpoint '{target}': {doc.get('state_version')!r}")

        recorded_seal = doc.get("checkpoint_sha256")
        if not recorded_seal or _compute_checkpoint_seal(doc) != recorded_seal:
            raise CorruptedCheckpointError(
                f"Checkpoint SHA-256 integrity seal mismatch in '{target}' — tampered or corrupted checkpoint rejected!"
            )

        # Verify internal task_graph_digest consistency if present
        t_defs = doc.get("task_definitions") or {}
        if doc.get("task_graph_digest") and t_defs:
            actual_g_dig = compute_task_graph_digest(t_defs.values())
            if actual_g_dig != doc["task_graph_digest"]:
                raise CorruptedCheckpointError(
                    f"Checkpoint task_graph_digest mismatch inside '{target}'"
                )
        return doc

    def load_latest_or_fallback_checkpoint(
        self,
        checkpoint_path: Path | None = None,
        *,
        allow_fallback_to_previous: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load explicit checkpoint, or ``latest_checkpoint.json`` with automatic fallback to intact history."""
        if checkpoint_path is not None:
            ckpt = self.load_verified_checkpoint(checkpoint_path)
            return ckpt, {
                "recovered_via_fallback": False,
                "corrupted_checkpoints_skipped": [],
                "source_file": Path(checkpoint_path).name,
            }

        skipped_corrupted: list[str] = []
        if self.latest_file.is_file():
            try:
                ckpt = self.load_verified_checkpoint(self.latest_file)
                return ckpt, {
                    "recovered_via_fallback": False,
                    "corrupted_checkpoints_skipped": [],
                    "source_file": self.latest_file.name,
                }
            except CheckpointError:
                if not allow_fallback_to_previous:
                    raise
                skipped_corrupted.append(self.latest_file.name)

        seq_files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"), reverse=True)
        if not seq_files and not skipped_corrupted:
            raise FileNotFoundError(f"No checkpoints found in {self.checkpoint_dir}")

        for cand in seq_files:
            try:
                ckpt = self.load_verified_checkpoint(cand)
                # Heal latest_checkpoint.json atomically under lock so subsequent reads stay consistent
                self._with_lock(lambda: self._write_atomic(self.latest_file, ckpt))
                return ckpt, {
                    "recovered_via_fallback": True,
                    "corrupted_checkpoints_skipped": skipped_corrupted,
                    "source_file": cand.name,
                }
            except CheckpointError:
                skipped_corrupted.append(cand.name)
                continue

        raise CorruptedCheckpointError(
            f"All available checkpoints in '{self.checkpoint_dir}' are missing or corrupted: {skipped_corrupted}"
        )

    def validate_checkpoint_against_dag(
        self,
        ckpt: dict[str, Any],
        *,
        expected_project_id: str,
        expected_handoffs: list[dict[str, Any]],
        min_state_version: int = 1,
    ) -> dict[str, str]:
        """Verify checkpoint seal, project_id, state_version, task_graph_digest, and per-task digests."""
        if not isinstance(ckpt, dict):
            raise UnverifiedCheckpointError("Checkpoint document must be a verified dictionary")
        recorded_seal = ckpt.get("checkpoint_sha256")
        if not recorded_seal or _compute_checkpoint_seal(ckpt) != recorded_seal:
            raise UnverifiedCheckpointError("Unverified or tampered checkpoint seal rejected")

        if ckpt.get("project_id") != expected_project_id:
            raise CrossProjectCheckpointError(
                f"Cross-project checkpoint rejected: checkpoint project_id='{ckpt.get('project_id')}' "
                f"!= target project_id='{expected_project_id}'"
            )

        st_ver = ckpt.get("state_version")
        if not isinstance(st_ver, int) or st_ver < max(1, int(min_state_version)):
            raise CheckpointStateVersionError(
                f"Checkpoint state_version={st_ver!r} is below required minimum {min_state_version}"
            )

        expected_graph_digest = compute_task_graph_digest(expected_handoffs)
        expected_def_digests = compute_task_definition_digests(expected_handoffs)

        ckpt_defs: dict[str, dict[str, Any]] = dict(ckpt.get("task_definitions") or {})
        if not ckpt_defs:
            raise TaskGraphMismatchError("Checkpoint lacks task_definitions; cannot bind to target task graph")

        ckpt_graph_digest = ckpt.get("task_graph_digest") or compute_task_graph_digest(ckpt_defs.values())
        if ckpt_graph_digest != expected_graph_digest:
            raise TaskGraphMismatchError(
                f"Task graph mismatch: checkpoint graph digest '{ckpt_graph_digest}' != "
                f"target DAG digest '{expected_graph_digest}'"
            )

        ckpt_def_digests = ckpt.get("task_definition_digests") or compute_task_definition_digests(ckpt_defs.values())
        if ckpt_def_digests != expected_def_digests:
            raise TaskGraphMismatchError("Per-task definition digests in checkpoint do not match target DAG")

        return expected_def_digests

    def resume(
        self,
        *,
        checkpoint_path: Path | None = None,
        trigger: str = "LANJUTKAN_PROJECT",
        expected_project_id: str | None = None,
        expected_handoffs: list[dict[str, Any]] | None = None,
        min_state_version: int = 1,
        require_verified_receipts: bool = False,
        allow_fallback_to_previous: bool = True,
    ) -> dict[str, Any]:
        """Execute deterministic reconciliation with lineage fallback, graph binding, and receipt checks."""
        # Step 1: Load verified checkpoint (falling back automatically if latest_checkpoint.json is corrupted)
        ckpt, fallback_meta = self.load_latest_or_fallback_checkpoint(
            checkpoint_path,
            allow_fallback_to_previous=allow_fallback_to_previous,
        )

        if expected_project_id is not None and ckpt["project_id"] != expected_project_id:
            raise CrossProjectCheckpointError(
                f"Cross-project checkpoint rejected: '{ckpt['project_id']}' != '{expected_project_id}'"
            )
        if int(ckpt["state_version"]) < max(1, int(min_state_version)):
            raise CheckpointStateVersionError(
                f"Checkpoint state_version={ckpt['state_version']} < min_state_version={min_state_version}"
            )
        if expected_handoffs is not None:
            self.validate_checkpoint_against_dag(
                ckpt,
                expected_project_id=expected_project_id or ckpt["project_id"],
                expected_handoffs=expected_handoffs,
                min_state_version=min_state_version,
            )

        task_defs: dict[str, dict[str, Any]] = dict(ckpt.get("task_definitions", {}))
        completed = set(ckpt["completed_tasks"])
        pending = set(ckpt["pending_tasks"])
        running = set(ckpt["running_tasks"])
        failed = set(ckpt["failed_tasks"])
        blocked = set(ckpt.get("blocked_tasks", []))
        cancelled = set(ckpt.get("cancelled_tasks", []))

        art_sha: dict[str, str] = dict(ckpt["artifact_sha256"])
        art_manifest: dict[str, dict[str, Any]] = dict(ckpt["artifact_manifest"])
        receipts_map: dict[str, dict[str, Any]] = dict(ckpt["agent_invocation_receipts"])
        idem_ledger: dict[str, str] = dict(ckpt.get("idempotency_ledger", {}))
        retry_budget: dict[str, dict[str, Any]] = {
            k: dict(v) for k, v in ckpt["retry_budget"].items()
        }

        # Step 2 & Step 3: Verify disk artifacts & demote completed tasks with missing/corrupt outputs
        corrupted_or_missing_artifacts: list[str] = []
        demoted_tasks: set[str] = set()

        for rel_path, expected_sha in list(art_sha.items()):
            cpath = self.handoff_manager.canonicalize_artifact_path(
                rel_path, base_dir=self.root_dir, is_writable_output=False
            )
            if not cpath.is_file() or compute_file_sha256(cpath) != expected_sha:
                corrupted_or_missing_artifacts.append(rel_path)
                art_sha.pop(rel_path, None)
                owner_tid = (art_manifest.pop(rel_path, {}) or {}).get("owner_task_id")
                if owner_tid and owner_tid in completed:
                    demoted_tasks.add(owner_tid)

        for tid in list(completed):
            h = task_defs.get(tid)
            if not h:
                if require_verified_receipts:
                    raise UnverifiedCheckpointError(
                        f"Completed task '{tid}' in checkpoint has no task_definition binding"
                    )
                demoted_tasks.add(tid)
                continue
            for cpath in self.handoff_manager.canonical_owned_paths(h, base_dir=self.root_dir):
                rel_posix = cpath.relative_to(self.root_dir).as_posix()
                if not cpath.is_file() or art_sha.get(rel_posix) != compute_file_sha256(cpath):
                    if rel_posix not in corrupted_or_missing_artifacts:
                        corrupted_or_missing_artifacts.append(rel_posix)
                    demoted_tasks.add(tid)

            if tid not in demoted_tasks and require_verified_receipts:
                raw_rcpt = receipts_map.get(tid)
                if not raw_rcpt:
                    raise UnverifiedCheckpointError(
                        f"Completed task '{tid}' in checkpoint lacks an AgentInvocationReceipt"
                    )
                rcpt = AgentInvocationReceipt.from_dict(raw_rcpt)
                if (
                    not rcpt.verify_integrity()
                    or not rcpt.actually_invoked
                    or rcpt.task_id != tid
                    or rcpt.project_id != ckpt["project_id"]
                    or rcpt.assigned_agent != h["assigned_agent"]
                ):
                    raise UnverifiedCheckpointError(
                        f"Completed task '{tid}' in checkpoint has an invalid or mismatched invocation receipt"
                    )
                if rcpt.task_definition_digest and rcpt.task_definition_digest != compute_task_definition_digest(h):
                    raise TaskGraphMismatchError(
                        f"Receipt task_definition_digest mismatch for completed task '{tid}'"
                    )
                for cpath in self.handoff_manager.canonical_owned_paths(h, base_dir=self.root_dir):
                    rel_posix = cpath.relative_to(self.root_dir).as_posix()
                    if rcpt.output_artifact_hashes.get(rel_posix) != art_sha.get(rel_posix):
                        raise UnverifiedCheckpointError(
                            f"Receipt output hash mismatch in checkpoint for '{tid}' artifact '{rel_posix}'"
                        )

        # Step 4: Transitively invalidate downstream dependents of demoted tasks
        downstream_invalidated = _transitive_dependents(demoted_tasks, task_defs)
        all_invalidated = demoted_tasks | downstream_invalidated
        for tid in all_invalidated:
            completed.discard(tid)
            blocked.discard(tid)
            pending.add(tid)
            idem_keys_to_drop = [k for k, v in idem_ledger.items() if v == tid]
            for k in idem_keys_to_drop:
                idem_ledger.pop(k, None)

        # Step 5: Reconcile interrupted `running_tasks` (never blindly re-run unknown external side-effects!)
        reconciled_unknown_external: list[str] = []
        requeued_interrupted: list[str] = []
        exhausted_interrupted: list[str] = []

        for tid in sorted(running):
            running.discard(tid)
            h = task_defs.get(tid, {})
            ctx = h.get("context", {})
            ext_unknown = (
                ctx.get("external_side_effect_status") == "unknown"
                or ctx.get("idempotent_retry_safe", True) is False
            )
            if ext_unknown:
                blocked.add(tid)
                reconciled_unknown_external.append(tid)
                for dep_tid in _transitive_dependents({tid}, task_defs):
                    pending.discard(dep_tid)
                    blocked.add(dep_tid)
            else:
                rb = retry_budget.get(tid, {"max_attempts": 2, "attempts_used": 0, "timeout_seconds": 60})
                rb["attempts_used"] = int(rb.get("attempts_used", 0)) + 1
                retry_budget[tid] = rb
                if rb["attempts_used"] >= int(rb.get("max_attempts", 2)):
                    failed.add(tid)
                    exhausted_interrupted.append(tid)
                    for dep_tid in _transitive_dependents({tid}, task_defs):
                        pending.discard(dep_tid)
                        blocked.add(dep_tid)
                else:
                    pending.add(tid)
                    requeued_interrupted.append(tid)

        # Step 6: Build idempotent skip set so completed tasks are NEVER duplicated
        already_completed_skip_list = sorted(completed)

        # Step 7: Production approval freeze & LANJUTKAN_PROJECT safety — NEVER grant or restore approved=True!
        saved_approval = dict(ckpt["approval_status"])
        if saved_approval.get("approved"):
            saved_approval["approved"] = False
            saved_approval["revoked"] = True
        else:
            saved_approval["approved"] = False

        return {
            "project_id": ckpt["project_id"],
            "resumed_from_checkpoint_id": ckpt["checkpoint_id"],
            "checkpoint_sha256": ckpt["checkpoint_sha256"],
            "checkpoint_lineage": ckpt.get("checkpoint_lineage"),
            "task_graph_digest": ckpt.get("task_graph_digest")
            or (compute_task_graph_digest(task_defs.values()) if task_defs else ""),
            "recovery_scope": "same_vm_workspace_filesystem",
            "cross_vm_verified": False,
            "fallback_recovery": fallback_meta,
            "trigger": trigger,
            "task_graph_version": ckpt["task_graph_version"],
            "state_version": ckpt["state_version"],
            "completed_tasks": sorted(completed),
            "pending_tasks": sorted(pending - completed - blocked - failed - cancelled),
            "running_tasks": [],
            "failed_tasks": sorted(failed),
            "blocked_tasks": sorted(blocked),
            "cancelled_tasks": sorted(cancelled),
            "demoted_due_to_missing_or_corrupt_artifacts": sorted(demoted_tasks),
            "downstream_invalidated_tasks": sorted(downstream_invalidated),
            "corrupted_or_missing_artifacts": sorted(corrupted_or_missing_artifacts),
            "reconciled_unknown_external_tasks": reconciled_unknown_external,
            "requeued_interrupted_tasks": requeued_interrupted,
            "exhausted_interrupted_tasks": exhausted_interrupted,
            "already_completed_skip_list": already_completed_skip_list,
            "artifact_manifest": art_manifest,
            "artifact_sha256": art_sha,
            "durable_artifact_provenance": dict(ckpt.get("durable_artifact_provenance") or {}),
            "agent_invocation_receipts": receipts_map,
            "retry_budget": retry_budget,
            "approval_status": saved_approval,
            "idempotency_ledger": idem_ledger,
            "task_definitions": copy.deepcopy(task_defs),
            "verified_source_checkpoint": copy.deepcopy(ckpt),
        }

    def export_portable_bundle(self, bundle_path: Path) -> dict[str, Any]:
        """Export a secret-scanned, SHA-256-sealed portable checkpoint & memory bundle for safe transfer."""
        ckpt, fallback_meta = self.load_latest_or_fallback_checkpoint(allow_fallback_to_previous=True)
        project_id = ckpt["project_id"]
        memory_snapshot: dict[str, Any] = {"present": False}
        if self.memory_store is not None:
            memory_snapshot = {
                "present": True,
                "execution_records": self.memory_store.execution.list_records(project_id),
                "errors": self.memory_store.error.list_errors(project_id),
                "quality_evaluations": self.memory_store.quality.list_evaluations(project_id),
            }

        body: dict[str, Any] = {
            "bundle_schema_version": "4.0.0-phase01.6c-portable",
            "exported_at_utc": _utc_now_iso(),
            "project_id": project_id,
            "cross_vm_automatic_storage_available": False,
            "fallback_recovery_used": fallback_meta["recovered_via_fallback"],
            "checkpoint": ckpt,
            "memory_snapshot": memory_snapshot,
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if SECRET_PATTERNS.search(canonical):
            raise SecretLeakBlockedError("Secret or credential detected during portable checkpoint bundle export!")
        body["bundle_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_atomic(bundle_path, body)
        return body

    def import_portable_bundle(self, bundle_path: Path, *, expected_project_id: str | None = None) -> dict[str, Any]:
        """Verify and import a portable checkpoint bundle into ``checkpoint_dir`` without trusting credentials."""
        raw_text = Path(bundle_path).read_text(encoding="utf-8")
        if SECRET_PATTERNS.search(raw_text):
            raise SecretLeakBlockedError("Refusing to import portable bundle containing secret/token patterns!")
        doc = json.loads(raw_text)
        recorded_sha = doc.get("bundle_sha256")
        clean = {k: v for k, v in doc.items() if k != "bundle_sha256"}
        actual_sha = hashlib.sha256(
            json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if not recorded_sha or actual_sha != recorded_sha:
            raise CorruptedCheckpointError("Portable checkpoint bundle SHA-256 seal mismatch!")

        ckpt = doc["checkpoint"]
        if _compute_checkpoint_seal(ckpt) != ckpt.get("checkpoint_sha256"):
            raise CorruptedCheckpointError("Embedded checkpoint inside portable bundle failed SHA-256 seal!")
        if expected_project_id and ckpt["project_id"] != expected_project_id:
            raise CrossProjectCheckpointError(
                f"Portable bundle project_id '{ckpt['project_id']}' != expected '{expected_project_id}'"
            )

        def _persist_imported() -> dict[str, Any]:
            seq_num = len(list(self.checkpoint_dir.glob("checkpoint_*.json"))) + 1
            self._write_atomic(self.checkpoint_dir / f"checkpoint_{seq_num:04d}.json", ckpt)
            self._write_atomic(self.latest_file, ckpt)
            return ckpt

        self._with_lock(_persist_imported)
        return self.resume(expected_project_id=expected_project_id or ckpt["project_id"])
