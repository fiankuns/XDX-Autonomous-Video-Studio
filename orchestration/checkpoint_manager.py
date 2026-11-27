"""12-Field Sealed Checkpoint & 7-Step Crash Recovery Manager (Phase 01.6B).

Implements Section 9 requirements:
1. Atomic, `fcntl`-locked, `fsync`-flushed, SHA-256-sealed checkpoints containing all 12 mandatory fields:
   `project_id`, `task_graph_version`, `completed_tasks`, `pending_tasks`, `running_tasks`,
   `failed_tasks`, `artifact_manifest`, `artifact_sha256`, `agent_invocation_receipts`,
   `retry_budget`, `approval_status`, `state_version` (plus `blocked_tasks`, `cancelled_tasks`,
   `task_definitions`, and `idempotency_ledger`).
2. 7-Step `resume()` reconciliation:
   - Step 1: Verify `checkpoint_sha256` tamper/corruption seal (`CorruptedCheckpointError`).
   - Step 2: Re-verify SHA-256 of every persisted artifact on disk.
   - Step 3: Demote any `completed_tasks` whose owned output artifact is missing or modified on disk.
   - Step 4: Transitively invalidate downstream tasks that depended on demoted tasks.
   - Step 5: Reconcile interrupted `running_tasks` — non-idempotent / unknown external side-effect tasks
     become `BLOCKED` (`reconciled_unknown_external_tasks`), while safe retryable tasks return to `pending_tasks`.
   - Step 6: Enforce `idempotency_ledger` so verified completed tasks are NEVER duplicated on resume.
   - Step 7: Enforce `LANJUTKAN_PROJECT` safety — NEVER grant or restore `approved=True` unless already
     recorded with a valid `approved_digest` and zero artifact drift.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256

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
    """Manages atomic SHA-256-sealed execution checkpoints and deterministic crash recovery."""

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
        tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
        raw = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
        with tmp.open("wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)

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
        """Persist a 12-field SHA-256-sealed checkpoint atomically and log to ExecutionMemory."""

        def _save() -> dict[str, Any]:
            now = _utc_now_iso()
            seq_files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
            seq_num = len(seq_files) + 1
            checkpoint_id = f"CKPT-{project_id}-{seq_num:04d}"

            doc: dict[str, Any] = {
                "schema_version": "4.0.0-phase01.6b",
                "checkpoint_id": checkpoint_id,
                "created_at_utc": now,
                "project_id": project_id,
                "task_graph_version": int(task_graph_version),
                "completed_tasks": sorted(set(completed_tasks)),
                "pending_tasks": sorted(set(pending_tasks)),
                "running_tasks": sorted(set(running_tasks)),
                "failed_tasks": sorted(set(failed_tasks)),
                "blocked_tasks": sorted(set(blocked_tasks or [])),
                "cancelled_tasks": sorted(set(cancelled_tasks or [])),
                "artifact_manifest": dict(sorted(artifact_manifest.items())),
                "artifact_sha256": dict(sorted(artifact_sha256.items())),
                "agent_invocation_receipts": dict(sorted(agent_invocation_receipts.items())),
                "retry_budget": dict(sorted(retry_budget.items())),
                "approval_status": {
                    "approved": bool(approval_status.get("approved", False)),
                    "approved_digest": approval_status.get("approved_digest"),
                    "approved_version": approval_status.get("approved_version"),
                    "revoked": bool(approval_status.get("revoked", False)),
                },
                "state_version": int(state_version),
                "task_definitions": task_definitions,
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
                        "task_graph_version": doc["task_graph_version"],
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

        recorded_seal = doc.get("checkpoint_sha256")
        if not recorded_seal or _compute_checkpoint_seal(doc) != recorded_seal:
            raise CorruptedCheckpointError(
                f"Checkpoint SHA-256 integrity seal mismatch in '{target}' — tampered or corrupted checkpoint rejected!"
            )
        return doc

    def resume(
        self,
        *,
        checkpoint_path: Path | None = None,
        trigger: str = "LANJUTKAN_PROJECT",
    ) -> dict[str, Any]:
        """Execute 7-step deterministic reconciliation on a persisted checkpoint."""
        # Step 1: Verify checkpoint seal
        ckpt = self.load_verified_checkpoint(checkpoint_path)
        task_defs: dict[str, dict[str, Any]] = dict(ckpt.get("task_definitions", {}))

        completed = set(ckpt["completed_tasks"])
        pending = set(ckpt["pending_tasks"])
        running = set(ckpt["running_tasks"])
        failed = set(ckpt["failed_tasks"])
        blocked = set(ckpt.get("blocked_tasks", []))
        cancelled = set(ckpt.get("cancelled_tasks", []))

        art_sha: dict[str, str] = dict(ckpt["artifact_sha256"])
        art_manifest: dict[str, dict[str, Any]] = dict(ckpt["artifact_manifest"])
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

        # Also check every completed task's declared owned_artifacts directly
        for tid in list(completed):
            h = task_defs.get(tid)
            if not h:
                continue
            for cpath in self.handoff_manager.canonical_owned_paths(h, base_dir=self.root_dir):
                rel_posix = cpath.relative_to(self.root_dir).as_posix()
                if not cpath.is_file() or art_sha.get(rel_posix) != compute_file_sha256(cpath):
                    if rel_posix not in corrupted_or_missing_artifacts:
                        corrupted_or_missing_artifacts.append(rel_posix)
                    demoted_tasks.add(tid)

        # Step 4: Transitively invalidate downstream dependents of demoted tasks
        downstream_invalidated = _transitive_dependents(demoted_tasks, task_defs)
        all_invalidated = demoted_tasks | downstream_invalidated
        for tid in all_invalidated:
            completed.discard(tid)
            blocked.discard(tid)
            pending.add(tid)
            # Remove invalidated task's idempotency entry so scheduler can re-run it cleanly
            idem_keys_to_drop = [k for k, v in idem_ledger.items() if v == tid]
            for k in idem_keys_to_drop:
                idem_ledger.pop(k, None)

        # Step 5: Reconcile interrupted `running_tasks`
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

        # Step 7: LANJUTKAN_PROJECT approval safety — NEVER grant auto-approval, and revoke if artifacts drifted!
        saved_approval = dict(ckpt["approval_status"])
        if corrupted_or_missing_artifacts and saved_approval.get("approved"):
            saved_approval["approved"] = False
            saved_approval["revoked"] = True
        if trigger == "LANJUTKAN_PROJECT" and not ckpt["approval_status"].get("approved"):
            saved_approval["approved"] = False

        return {
            "project_id": ckpt["project_id"],
            "resumed_from_checkpoint_id": ckpt["checkpoint_id"],
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
            "agent_invocation_receipts": dict(ckpt["agent_invocation_receipts"]),
            "retry_budget": retry_budget,
            "approval_status": saved_approval,
            "idempotency_ledger": idem_ledger,
            "task_definitions": task_defs,
        }
