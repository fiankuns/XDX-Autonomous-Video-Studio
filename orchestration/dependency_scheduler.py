"""Asynchronous Task DAG Dependency Scheduler with Deterministic Completion & Checkpoint Recovery (Phase 01.6B).

Implements Section 4 requirements:
1. Topological DAG validation, deterministic ready queue, and downstream dependency resolution.
2. Concurrency control: global specialist cap (`max_parallel_specialists` <= 6, default 4) +
   per-role `max_concurrent_instances` from `AgentRegistry`.
3. Phase 01.6B hard execution guardrail: blocks live execution of `blender_specialist` or
   production renderers prior to Phase 02 / `ExecutionAuthorizationContext`.
4. Execution-boundary re-validation + `ArtifactOwnershipLockManager` (`fcntl.flock`) acquisition
   and guaranteed `finally` release on every task attempt.
5. Per-task `asyncio.wait_for` timeout, retry budget accounting, retry exhaustion -> `FAILED`,
   cancellation -> `CANCELLED`, and automatic transitive downstream failure propagation -> `BLOCKED`.
6. Deterministic `done_when` + `required_evidence` + on-disk output SHA-256 verification:
   NEVER trusts a worker's self-claimed `COMPLETED`/`SUCCEEDED` status!
7. Full integration with `SixPartitionMemoryStore` and `CheckpointManager` (including zero-duplicate
   execution upon `resume()`).
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.agent_registry import AgentRegistry
from orchestration.checkpoint_manager import CheckpointManager
from orchestration.handoff_manager import (
    ParallelWriteConflictError,
    TaskHandoffManager,
    compute_file_sha256,
)
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentFailureReport,
    NativeAgentExecutionAdapter,
    compute_idempotency_key,
    utc_now_iso,
)

ROOT_DIR = Path(__file__).resolve().parent.parent

AsyncTaskExecutor = Callable[[dict[str, Any], int], Awaitable[AgentExecutionResult]]


class SchedulerError(RuntimeError):
    """Base exception for DAG scheduler errors."""


class PhaseBoundaryExecutionBlockedError(SchedulerError):
    """Raised if live Blender / production render execution is attempted in Phase 01.6B."""


class WorkerCompletionRejectedError(SchedulerError):
    """Raised when a worker claims completion without passing deterministic artifact/evidence checks."""


class TaskDependencyScheduler:
    """Executes validated 18-field task DAGs with bounded concurrency, retries, locks, and checkpoints."""

    PHASE01_6B_BLOCKED_LIVE_ROLES: frozenset[str] = frozenset({"blender_specialist"})

    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        max_parallel_specialists: int = 4,
        handoff_manager: TaskHandoffManager | None = None,
        execution_adapter: NativeAgentExecutionAdapter | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        allow_phase02_roles: bool = False,
        timeout_override_seconds: float | None = None,
    ) -> None:
        if not (1 <= max_parallel_specialists <= 6):
            raise ValueError("max_parallel_specialists must be between 1 and 6 per XDX v4.0 governance")
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.max_parallel_specialists = max_parallel_specialists
        self.registry = AgentRegistry(root_dir=self.root_dir)
        self.handoff_manager = handoff_manager or TaskHandoffManager(
            root_dir=self.root_dir, registry=self.registry
        )
        self.execution_adapter = execution_adapter or NativeAgentExecutionAdapter(
            root_dir=self.root_dir,
            handoff_manager=self.handoff_manager,
            registry=self.registry,
        )
        self.memory_store = memory_store
        self.checkpoint_manager = checkpoint_manager
        self.allow_phase02_roles = allow_phase02_roles
        self.timeout_override_seconds = timeout_override_seconds

    @staticmethod
    def _transitive_dependents(seed_tid: str, by_id: dict[str, dict[str, Any]]) -> list[str]:
        dep_map: dict[str, list[str]] = {tid: [] for tid in by_id}
        for tid, h in by_id.items():
            for dep in h["dependencies"]:
                if dep in dep_map:
                    dep_map[dep].append(tid)
        visited: set[str] = set()
        queue = [seed_tid]
        while queue:
            cur = queue.pop(0)
            for nxt in dep_map.get(cur, []):
                if nxt not in visited and nxt != seed_tid:
                    visited.add(nxt)
                    queue.append(nxt)
        return sorted(visited)

    def _verify_worker_completion_deterministically(
        self,
        *,
        handoff: dict[str, Any],
        result: AgentExecutionResult,
        by_id: dict[str, dict[str, Any]],
        artifact_sha256: dict[str, str],
        receipts_by_task: dict[str, dict[str, Any]],
        custom_predicate: Callable[[dict[str, Any], AgentExecutionResult, Path], bool] | None = None,
    ) -> dict[str, str]:
        """Deterministically verify receipt, disk outputs, JSON parseability, evidence & verifier integrity."""
        tid = handoff["task_id"]
        if result.status != "SUCCEEDED":
            raise WorkerCompletionRejectedError(
                f"Task '{tid}' returned non-succeeded status='{result.status}'"
            )
        if not result.receipt.verify_integrity():
            raise WorkerCompletionRejectedError(f"Task '{tid}' receipt failed SHA-256 integrity check")
        if not result.receipt.actually_invoked or result.receipt.execution_mode == "dispatch_plan_only_not_invoked":
            raise WorkerCompletionRejectedError(
                f"Task '{tid}' returned a non-invoked dispatch plan; cannot mark COMPLETED!"
            )

        # Verify top-level required_evidence count and substance
        req_ev = handoff["required_evidence"]
        clean_ev = [e.strip() for e in result.evidence_items if isinstance(e, str) and len(e.strip()) >= 5]
        if len(clean_ev) < len(req_ev):
            raise WorkerCompletionRejectedError(
                f"Task '{tid}' insufficient evidence items: got {len(clean_ev)}, required {len(req_ev)}"
            )

        # Evaluate deterministic done_when file checks
        for dw in handoff["done_when"]:
            if dw.get("check_type") == "file_exists_nonempty":
                dw_path = self.handoff_manager.canonicalize_artifact_path(
                    dw["target"], base_dir=self.root_dir, is_writable_output=False
                )
                if not dw_path.is_file() or dw_path.stat().st_size == 0:
                    raise WorkerCompletionRejectedError(
                        f"Task '{tid}' failed done_when '{dw['criterion_id']}': target '{dw['target']}' missing or empty"
                    )

        # Verify every declared owned & output artifact exists on disk, is non-empty, and parses if JSON
        verified_outputs: dict[str, str] = {}
        canon_owned = self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir)
        for cpath in canon_owned:
            if not cpath.is_file():
                raise WorkerCompletionRejectedError(
                    f"Worker claimed completion for '{tid}', but owned output '{cpath}' does not exist on disk!"
                )
            if cpath.stat().st_size == 0:
                raise WorkerCompletionRejectedError(
                    f"Worker claimed completion for '{tid}', but owned output '{cpath}' is 0 bytes!"
                )
            if cpath.suffix.lower() == ".json":
                try:
                    json.loads(cpath.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise WorkerCompletionRejectedError(
                        f"Owned JSON output '{cpath}' for '{tid}' is malformed: {exc}"
                    ) from exc
            rel_posix = cpath.relative_to(self.root_dir).as_posix()
            verified_outputs[rel_posix] = compute_file_sha256(cpath)

        # If this is an Independent Verification Department task, enforce verify_independent_review_pass!
        role = self.registry.get_role(handoff["assigned_agent"])
        if role["department"] == "independent_verification_department":
            if result.review_report is None:
                raise WorkerCompletionRejectedError(
                    f"Independent verifier task '{tid}' did not return a structured AgentReviewReport!"
                )
            rep_dict = result.review_report.to_dict()
            prod_tid = rep_dict["reviewed_task_id"]
            if prod_tid not in by_id:
                raise WorkerCompletionRejectedError(
                    f"Verifier report references unknown producer task '{prod_tid}'"
                )
            prod_handoff = by_id[prod_tid]
            pre_hashes: dict[str, str] = {}
            for cp in self.handoff_manager.canonical_owned_paths(prod_handoff, base_dir=self.root_dir):
                rp = cp.relative_to(self.root_dir).as_posix()
                if rp in artifact_sha256:
                    pre_hashes[rp] = artifact_sha256[rp]
            prod_conv = (receipts_by_task.get(prod_tid) or {}).get("conversation_id")
            self.handoff_manager.verify_independent_review_pass(
                verifier_handoff=handoff,
                producer_handoff=prod_handoff,
                pre_review_hashes=pre_hashes,
                review_report=rep_dict,
                producer_conversation_id=prod_conv,
                base_dir=self.root_dir,
            )
            if rep_dict["verdict"] != "PASS":
                raise WorkerCompletionRejectedError(
                    f"Independent verifier '{tid}' returned verdict='{rep_dict['verdict']}'"
                )

        if custom_predicate is not None and not custom_predicate(handoff, result, self.root_dir):
            raise WorkerCompletionRejectedError(f"Custom deterministic done_when predicate rejected '{tid}'")

        return verified_outputs

    async def execute_dag(
        self,
        handoffs: list[dict[str, Any]],
        *,
        executor: AsyncTaskExecutor,
        task_graph_version: int = 1,
        state_version: int = 1,
        approval_status: dict[str, Any] | None = None,
        cancelled_task_ids: set[str] | None = None,
        cancel_event: asyncio.Event | None = None,
        auto_bind_upstream_hashes: bool = True,
        resume_state: dict[str, Any] | None = None,
        custom_done_predicate: Callable[[dict[str, Any], AgentExecutionResult, Path], bool] | None = None,
    ) -> dict[str, Any]:
        """Execute a validated task DAG asynchronously with full lock, retry, timeout, and checkpoint safety."""
        if not handoffs:
            raise ValueError("handoffs list cannot be empty")

        tasks_copy = [copy.deepcopy(h) for h in handoffs]
        project_ids = {h["project_id"] for h in tasks_copy}
        if len(project_ids) != 1:
            raise SchedulerError(f"All tasks in a DAG run must share one project_id; got {sorted(project_ids)}")
        project_id = next(iter(project_ids))

        # Normalize statuses if resuming from checkpoint reconciliation
        if resume_state is not None:
            comp_set = set(resume_state["completed_tasks"])
            fail_set = set(resume_state["failed_tasks"])
            blk_set = set(resume_state["blocked_tasks"])
            canc_set = set(resume_state["cancelled_tasks"])
            for h in tasks_copy:
                tid = h["task_id"]
                if tid in resume_state.get("retry_budget", {}):
                    h["retry_budget"] = copy.deepcopy(resume_state["retry_budget"][tid])
                if tid in comp_set:
                    h["status"] = "COMPLETED"
                elif tid in fail_set:
                    h["status"] = "FAILED"
                elif tid in blk_set:
                    h["status"] = "BLOCKED"
                elif tid in canc_set:
                    h["status"] = "CANCELLED"
                else:
                    h["status"] = "PENDING"

        topo_order = self.handoff_manager.validate_task_dag_and_ownership(
            tasks_copy, base_dir=self.root_dir
        )
        by_id: dict[str, dict[str, Any]] = {h["task_id"]: h for h in tasks_copy}

        completed: set[str] = {tid for tid, h in by_id.items() if h["status"] == "COMPLETED"}
        failed: set[str] = {tid for tid, h in by_id.items() if h["status"] == "FAILED"}
        blocked: set[str] = {tid for tid, h in by_id.items() if h["status"] == "BLOCKED"}
        cancelled: set[str] = {tid for tid, h in by_id.items() if h["status"] == "CANCELLED"}
        running: set[str] = set()
        pending: set[str] = set(by_id.keys()) - completed - failed - blocked - cancelled

        artifact_manifest: dict[str, dict[str, Any]] = (
            copy.deepcopy(resume_state["artifact_manifest"]) if resume_state else {}
        )
        artifact_sha256: dict[str, str] = (
            copy.deepcopy(resume_state["artifact_sha256"]) if resume_state else {}
        )
        receipts_by_task: dict[str, dict[str, Any]] = (
            copy.deepcopy(resume_state["agent_invocation_receipts"]) if resume_state else {}
        )
        idem_ledger: dict[str, str] = (
            copy.deepcopy(resume_state["idempotency_ledger"]) if resume_state else {}
        )
        eff_approval = copy.deepcopy(
            approval_status
            or (resume_state["approval_status"] if resume_state else None)
            or {"approved": False, "approved_digest": None, "approved_version": None, "revoked": False}
        )
        skipped_via_idempotency: list[str] = sorted(completed)
        failures_recorded: list[dict[str, Any]] = []
        active_role_counts: dict[str, int] = {}
        active_owned_canon: dict[str, str] = {}
        state_guard = asyncio.Lock()

        # Apply initial explicit cancellations
        for c_tid in sorted(cancelled_task_ids or set()):
            if c_tid in pending:
                pending.discard(c_tid)
                cancelled.add(c_tid)
                by_id[c_tid]["status"] = "CANCELLED"
                for dep_tid in self._transitive_dependents(c_tid, by_id):
                    if dep_tid in pending:
                        pending.discard(dep_tid)
                        blocked.add(dep_tid)
                        by_id[dep_tid]["status"] = "BLOCKED"

        def _persist_checkpoint() -> dict[str, Any] | None:
            if self.checkpoint_manager is None:
                return None
            rb_map = {tid: copy.deepcopy(h["retry_budget"]) for tid, h in by_id.items()}
            return self.checkpoint_manager.save_checkpoint(
                project_id=project_id,
                task_graph_version=task_graph_version,
                completed_tasks=sorted(completed),
                pending_tasks=sorted(pending),
                running_tasks=sorted(running),
                failed_tasks=sorted(failed),
                blocked_tasks=sorted(blocked),
                cancelled_tasks=sorted(cancelled),
                artifact_manifest=artifact_manifest,
                artifact_sha256=artifact_sha256,
                agent_invocation_receipts=receipts_by_task,
                retry_budget=rb_map,
                approval_status=eff_approval,
                state_version=state_version,
                task_definitions=by_id,
                idempotency_ledger=idem_ledger,
            )

        async def _run_single_task(tid: str) -> None:
            h = by_id[tid]
            aid = h["assigned_agent"]

            if not self.allow_phase02_roles and aid in self.PHASE01_6B_BLOCKED_LIVE_ROLES:
                async with state_guard:
                    running.discard(tid)
                    active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                    blocked.add(tid)
                    h["status"] = "BLOCKED"
                    for dep_tid in self._transitive_dependents(tid, by_id):
                        if dep_tid in pending:
                            pending.discard(dep_tid)
                            blocked.add(dep_tid)
                            by_id[dep_tid]["status"] = "BLOCKED"
                    _persist_checkpoint()
                raise PhaseBoundaryExecutionBlockedError(
                    f"Live execution of '{aid}' is strictly blocked in Phase 01.6B prior to Phase 02 authorization!"
                )

            # Auto-bind freshly generated upstream hashes if requested
            if auto_bind_upstream_hashes and h["input_artifacts"]:
                new_hashes: dict[str, str] = {}
                for raw_inp in h["input_artifacts"]:
                    cp = self.handoff_manager.canonicalize_artifact_path(
                        raw_inp, base_dir=self.root_dir, is_writable_output=False
                    )
                    rp = cp.relative_to(self.root_dir).as_posix()
                    if rp in artifact_sha256:
                        new_hashes[raw_inp] = artifact_sha256[rp]
                    elif raw_inp in h["input_artifact_hashes"]:
                        new_hashes[raw_inp] = h["input_artifact_hashes"][raw_inp]
                if len(new_hashes) == len(h["input_artifacts"]):
                    h["input_artifact_hashes"] = new_hashes

            idem_key = compute_idempotency_key(
                project_id=project_id,
                task_id=tid,
                task_graph_version=task_graph_version,
                input_artifact_hashes=h["input_artifact_hashes"],
            )

            # Check idempotency ledger before running
            async with state_guard:
                if idem_ledger.get(idem_key) == tid and tid in completed:
                    running.discard(tid)
                    active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                    if tid not in skipped_via_idempotency:
                        skipped_via_idempotency.append(tid)
                    return

            rb = h["retry_budget"]
            max_attempts = int(rb["max_attempts"])
            timeout_s = (
                float(self.timeout_override_seconds)
                if self.timeout_override_seconds is not None
                else float(rb["timeout_seconds"])
            )

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    async with state_guard:
                        running.discard(tid)
                        active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                        for ck, owner in list(active_owned_canon.items()):
                            if owner == tid:
                                active_owned_canon.pop(ck, None)
                        cancelled.add(tid)
                        h["status"] = "CANCELLED"
                        for dep_tid in self._transitive_dependents(tid, by_id):
                            if dep_tid in pending:
                                pending.discard(dep_tid)
                                blocked.add(dep_tid)
                                by_id[dep_tid]["status"] = "BLOCKED"
                        _persist_checkpoint()
                    return

                attempt_no = int(rb["attempts_used"]) + 1
                locks_acquired = False
                try:
                    # Execution-boundary re-validation + cross-process fcntl lock acquisition
                    await asyncio.to_thread(
                        self.handoff_manager.revalidate_at_execution_boundary,
                        h,
                        base_dir=self.root_dir,
                        acquire_locks=True,
                    )
                    locks_acquired = True

                    exec_result = await asyncio.wait_for(executor(h, attempt_no), timeout=timeout_s)

                    async with state_guard:
                        verified_outputs = self._verify_worker_completion_deterministically(
                            handoff=h,
                            result=exec_result,
                            by_id=by_id,
                            artifact_sha256=artifact_sha256,
                            receipts_by_task=receipts_by_task,
                            custom_predicate=custom_done_predicate,
                        )
                        rb["attempts_used"] = attempt_no
                        h["status"] = "COMPLETED"
                        running.discard(tid)
                        completed.add(tid)
                        active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                        for ck, owner in list(active_owned_canon.items()):
                            if owner == tid:
                                active_owned_canon.pop(ck, None)

                        for rel_p, sha in verified_outputs.items():
                            artifact_sha256[rel_p] = sha
                            artifact_manifest[rel_p] = {
                                "owner_task_id": tid,
                                "owner_agent": aid,
                                "sha256": sha,
                                "verified_at_utc": utc_now_iso(),
                            }
                        receipts_by_task[tid] = exec_result.receipt.to_dict()
                        idem_ledger[idem_key] = tid

                        if self.memory_store is not None:
                            self.memory_store.execution.append_record(
                                project_id=project_id,
                                record_kind="task_completed",
                                record_id=tid,
                                payload={
                                    "task_id": tid,
                                    "assigned_agent": aid,
                                    "attempt_number": attempt_no,
                                    "receipt": exec_result.receipt.to_dict(),
                                    "verified_outputs": verified_outputs,
                                },
                            )
                            if exec_result.review_report is not None:
                                rep_d = exec_result.review_report.to_dict()
                                self.memory_store.quality.record_evaluation(
                                    project_id=project_id,
                                    evaluation_id=rep_d["review_id"],
                                    target_ref=rep_d["reviewed_task_id"],
                                    review_status=rep_d["verdict"],
                                    payload=rep_d,
                                )
                        _persist_checkpoint()
                    return

                except Exception as exc:
                    if isinstance(exc, asyncio.TimeoutError):
                        err_cat = "TIMEOUT"
                        err_msg = f"Task '{tid}' timed out after {timeout_s}s on attempt {attempt_no}"
                    elif isinstance(exc, WorkerCompletionRejectedError):
                        err_cat = "VALIDATION_FAILED"
                        err_msg = str(exc)
                    elif isinstance(exc, ParallelWriteConflictError):
                        err_cat = "LOCK_CONFLICT"
                        err_msg = str(exc)
                    else:
                        err_cat = "EXECUTION_ERROR"
                        err_msg = f"{type(exc).__name__}: {exc}"

                    rb["attempts_used"] = attempt_no
                    can_retry = attempt_no < max_attempts and err_cat != "LOCK_CONFLICT"
                    fail_rep = AgentFailureReport(
                        failure_id=f"ERR-{tid}-{attempt_no}-{uuid.uuid4().hex[:6]}",
                        task_id=tid,
                        project_id=project_id,
                        assigned_agent=aid,
                        error_category=err_cat,
                        message=err_msg,
                        attempt_number=attempt_no,
                        retryable=can_retry,
                        occurred_at=utc_now_iso(),
                    )
                    async with state_guard:
                        failures_recorded.append(fail_rep.to_dict())
                        if self.memory_store is not None:
                            self.memory_store.error.record_error(
                                project_id=project_id,
                                error_id=fail_rep.failure_id,
                                task_id=tid,
                                error_category=err_cat,
                                payload=fail_rep.to_dict(),
                            )
                        if not can_retry:
                            running.discard(tid)
                            failed.add(tid)
                            h["status"] = "FAILED"
                            active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                            for ck, owner in list(active_owned_canon.items()):
                                if owner == tid:
                                    active_owned_canon.pop(ck, None)
                            # Propagate failure to all transitive downstream dependents -> BLOCKED
                            for dep_tid in self._transitive_dependents(tid, by_id):
                                if dep_tid in pending:
                                    pending.discard(dep_tid)
                                    blocked.add(dep_tid)
                                    by_id[dep_tid]["status"] = "BLOCKED"
                            _persist_checkpoint()
                            return
                finally:
                    if locks_acquired:
                        await asyncio.to_thread(self.handoff_manager.lock_manager.release_for_task, tid)

        # Main event-driven topological dispatch loop
        active_futures: dict[str, asyncio.Task[None]] = {}
        _persist_checkpoint()

        while pending or active_futures:
            if cancel_event is not None and cancel_event.is_set():
                async with state_guard:
                    for p_tid in sorted(pending):
                        pending.discard(p_tid)
                        cancelled.add(p_tid)
                        by_id[p_tid]["status"] = "CANCELLED"
                    _persist_checkpoint()

            # Dispatch eligible READY tasks respecting global cap, role cap, and canonical file ownership
            async with state_guard:
                for tid in topo_order:
                    if tid not in pending:
                        continue
                    if len(active_futures) >= self.max_parallel_specialists:
                        break
                    h = by_id[tid]
                    deps = h["dependencies"]
                    if any(d in failed or d in blocked or d in cancelled for d in deps):
                        pending.discard(tid)
                        blocked.add(tid)
                        h["status"] = "BLOCKED"
                        continue
                    if not all(d in completed for d in deps):
                        continue

                    aid = h["assigned_agent"]
                    role = self.registry.get_role(aid)
                    if active_role_counts.get(aid, 0) >= int(role["max_concurrent_instances"]):
                        continue

                    canon_paths = [
                        p.as_posix()
                        for p in self.handoff_manager.canonical_owned_paths(h, base_dir=self.root_dir)
                    ]
                    if any(ck in active_owned_canon for ck in canon_paths):
                        continue

                    # Transition PENDING -> READY -> RUNNING
                    pending.discard(tid)
                    running.add(tid)
                    h["status"] = "RUNNING"
                    active_role_counts[aid] = active_role_counts.get(aid, 0) + 1
                    for ck in canon_paths:
                        active_owned_canon[ck] = tid
                    _persist_checkpoint()
                    active_futures[tid] = asyncio.create_task(_run_single_task(tid))

            if not active_futures:
                # Check if remaining pending tasks are unschedulable due to blocked/failed upstream
                async with state_guard:
                    progressed = False
                    for p_tid in list(pending):
                        deps = by_id[p_tid]["dependencies"]
                        if any(d in failed or d in blocked or d in cancelled for d in deps):
                            pending.discard(p_tid)
                            blocked.add(p_tid)
                            by_id[p_tid]["status"] = "BLOCKED"
                            progressed = True
                    if progressed:
                        _persist_checkpoint()
                        continue
                break

            done, _ = await asyncio.wait(active_futures.values(), return_when=asyncio.FIRST_COMPLETED)
            finished_tids = [k for k, fut in active_futures.items() if fut in done]
            for f_tid in finished_tids:
                fut = active_futures.pop(f_tid)
                # Re-raise hard phase-boundary violations immediately after cleaning up remaining tasks
                exc = fut.exception()
                if isinstance(exc, PhaseBoundaryExecutionBlockedError):
                    for other in active_futures.values():
                        other.cancel()
                    if active_futures:
                        await asyncio.gather(*active_futures.values(), return_exceptions=True)
                    raise exc

        final_ckpt = _persist_checkpoint()
        overall_status = (
            "SUCCEEDED"
            if len(completed) == len(by_id)
            else ("CANCELLED" if cancelled and not failed else "PARTIAL_OR_FAILED")
        )
        return {
            "project_id": project_id,
            "overall_status": overall_status,
            "topological_order": topo_order,
            "completed_tasks": sorted(completed),
            "pending_tasks": sorted(pending),
            "running_tasks": sorted(running),
            "failed_tasks": sorted(failed),
            "blocked_tasks": sorted(blocked),
            "cancelled_tasks": sorted(cancelled),
            "skipped_via_idempotency": sorted(skipped_via_idempotency),
            "artifact_manifest": artifact_manifest,
            "artifact_sha256": artifact_sha256,
            "agent_invocation_receipts": receipts_by_task,
            "failures": failures_recorded,
            "latest_checkpoint": final_ckpt,
        }
