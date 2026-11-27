"""Asynchronous Task DAG Dependency Scheduler with Deterministic Acceptance & Checkpoint Binding (Phase 01.6C).

Implements Phase 01.6B Section 4 + Phase 01.6C Section 4.A, 4.B, 4.C, 4.D & 4.F requirements:
1. Never trusts initial task ``status``: fresh DAG tasks MUST start in ``PENDING`` (or ``READY`` normalized
   to ``PENDING``). Initial ``COMPLETED`` (or terminal/running states) is rejected fail-closed with
   ``InitialCompletedStatusRejectedError``.
2. ``COMPLETED`` can ONLY be restored via a SHA-256-sealed, verified checkpoint bound to ``project_id``,
   ``task_graph_digest``, ``task_definition_digest``, ``AgentInvocationReceipt``, and all on-disk output
   SHA-256 hashes.
3. Boolean configuration bypasses (``allow_phase02_roles=True``) are strictly rejected prior to
   Phase 01.6D Trusted Human Approval & Execution Guard.
4. Full 6-handler ``AcceptanceCriteriaEngine`` integration: unsupported ``check_type`` values transition
   tasks immediately to ``BLOCKED`` (never ignored), receipt task/project/role identity and output hashes
   are verified against actual disk files, and unrelated evidence strings are rejected.
5. Independent Verification Department tasks enforce Master Director ``ImmutableReviewCriteriaManifest``
   integrity and all 11 review bindings.
"""

from __future__ import annotations

import asyncio
import copy
import os
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.acceptance_criteria import (
    AcceptanceCriteriaEngine,
    AcceptanceCriteriaError,
    UnsupportedAcceptanceCheckError,
    snapshot_directory_hashes,
)
from orchestration.agent_registry import AgentRegistry
from orchestration.checkpoint_manager import (
    CheckpointManager,
    CrossProjectCheckpointError,
    TaskGraphMismatchError,
    UnverifiedCheckpointError,
    _compute_checkpoint_seal,
)
from orchestration.handoff_manager import (
    HandoffValidationError,
    ParallelWriteConflictError,
    SilentArtifactMutationError,
    TaskHandoffManager,
    compute_file_sha256,
)
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentFailureReport,
    AgentInvocationReceipt,
    NativeAgentExecutionAdapter,
    compute_idempotency_key,
    utc_now_iso,
)
from orchestration.task_identity import compute_task_definition_digest

ROOT_DIR = Path(__file__).resolve().parent.parent

AsyncTaskExecutor = Callable[[dict[str, Any], int], Awaitable[AgentExecutionResult]]

ALLOWED_INITIAL_TASK_STATUSES: frozenset[str] = frozenset({"PENDING", "READY"})


class SchedulerError(RuntimeError):
    """Base exception for DAG scheduler errors."""


class InitialCompletedStatusRejectedError(SchedulerError):
    """Raised when a caller attempts to inject a pre-marked COMPLETED (or non-initial) task without a verified checkpoint."""


class PhaseBoundaryExecutionBlockedError(SchedulerError):
    """Raised if live Blender / production render execution or boolean bypass is attempted before Phase 01.6D/02."""


class WorkerCompletionRejectedError(SchedulerError):
    """Raised when a worker claims completion without passing deterministic artifact/receipt/evidence checks."""


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
        acceptance_engine: AcceptanceCriteriaEngine | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        allow_phase02_roles: bool = False,
        disallow_mock_execution: bool = False,
        timeout_override_seconds: float | None = None,
    ) -> None:
        if not (1 <= max_parallel_specialists <= 6):
            raise ValueError("max_parallel_specialists must be between 1 and 6 per XDX v4.0 governance")
        if allow_phase02_roles:
            raise PhaseBoundaryExecutionBlockedError(
                "Boolean configuration 'allow_phase02_roles=True' is forbidden! "
                "Production roles are frozen prior to Phase 01.6D Trusted Human Approval & Execution Guard."
            )
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
        self.acceptance_engine = acceptance_engine or AcceptanceCriteriaEngine(
            root_dir=self.root_dir,
            handoff_manager=self.handoff_manager,
        )
        self.memory_store = memory_store
        self.checkpoint_manager = checkpoint_manager
        self.allow_phase02_roles = False
        self.disallow_mock_execution = disallow_mock_execution
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

    def _validate_and_bind_resume_state(
        self,
        *,
        resume_state: dict[str, Any],
        project_id: str,
        tasks_copy: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Verify resume_state comes from a sealed checkpoint bound to project_id, DAG digest, receipts & disk hashes."""
        if not isinstance(resume_state, dict):
            raise UnverifiedCheckpointError("resume_state must be a dictionary produced by CheckpointManager.resume()")

        if resume_state.get("project_id") != project_id:
            raise CrossProjectCheckpointError(
                f"Cross-project resume_state rejected: '{resume_state.get('project_id')}' != '{project_id}'"
            )

        src_ckpt = resume_state.get("verified_source_checkpoint")
        if not isinstance(src_ckpt, dict):
            raise UnverifiedCheckpointError(
                "Unverified resume_state rejected: missing 'verified_source_checkpoint' from CheckpointManager.resume()!"
            )

        ckpt_validator = self.checkpoint_manager or CheckpointManager(
            self.root_dir / ".xdx_locks" / "_ephemeral_ckpt_verify",
            root_dir=self.root_dir,
            handoff_manager=self.handoff_manager,
        )
        ckpt_validator.validate_checkpoint_against_dag(
            src_ckpt,
            expected_project_id=project_id,
            expected_handoffs=tasks_copy,
            min_state_version=1,
        )
        if _compute_checkpoint_seal(src_ckpt) != resume_state.get("checkpoint_sha256"):
            raise UnverifiedCheckpointError("resume_state checkpoint_sha256 does not match verified_source_checkpoint")

        by_tid = {h["task_id"]: h for h in tasks_copy}
        comp_set = set(resume_state.get("completed_tasks") or [])
        src_comp_set = set(src_ckpt.get("completed_tasks") or [])
        if not comp_set.issubset(src_comp_set):
            raise UnverifiedCheckpointError(
                f"resume_state claims completed tasks {sorted(comp_set - src_comp_set)} not completed in sealed checkpoint!"
            )

        art_sha = dict(resume_state.get("artifact_sha256") or {})
        receipts_map = dict(resume_state.get("agent_invocation_receipts") or {})

        for tid in sorted(comp_set):
            if tid not in by_tid:
                raise TaskGraphMismatchError(f"Checkpoint completed task '{tid}' does not exist in target DAG")
            h = by_tid[tid]
            raw_rcpt = receipts_map.get(tid)
            if not isinstance(raw_rcpt, dict):
                raise UnverifiedCheckpointError(
                    f"Cannot restore COMPLETED for '{tid}': missing AgentInvocationReceipt in checkpoint!"
                )
            rcpt = AgentInvocationReceipt.from_dict(raw_rcpt)
            if (
                not rcpt.verify_integrity()
                or not rcpt.actually_invoked
                or rcpt.execution_mode == "dispatch_plan_only_not_invoked"
                or rcpt.task_id != tid
                or rcpt.project_id != project_id
                or rcpt.assigned_agent != h["assigned_agent"]
            ):
                raise UnverifiedCheckpointError(
                    f"Cannot restore COMPLETED for '{tid}': invalid or mismatched AgentInvocationReceipt!"
                )
            if rcpt.task_definition_digest and rcpt.task_definition_digest != compute_task_definition_digest(h):
                raise TaskGraphMismatchError(f"Task definition digest changed for completed task '{tid}'")

            for cpath in self.handoff_manager.canonical_owned_paths(h, base_dir=self.root_dir):
                rel_posix = cpath.relative_to(self.root_dir).as_posix()
                if not cpath.is_file() or cpath.stat().st_size == 0:
                    raise UnverifiedCheckpointError(
                        f"Cannot restore COMPLETED for '{tid}': output '{rel_posix}' is missing or empty on disk!"
                    )
                live_sha = compute_file_sha256(cpath)
                if art_sha.get(rel_posix) != live_sha or rcpt.output_artifact_hashes.get(rel_posix) != live_sha:
                    raise UnverifiedCheckpointError(
                        f"Cannot restore COMPLETED for '{tid}': output SHA-256 mismatch on '{rel_posix}'!"
                    )

        return by_tid

    def _capture_pre_execution_context(
        self,
        handoff: dict[str, Any],
        by_id: dict[str, dict[str, Any]],
        artifact_sha256: dict[str, str],
    ) -> dict[str, Any]:
        pre_snapshots: dict[str, dict[str, str]] = {}
        for dw in handoff.get("done_when", []):
            if dw.get("check_type") == "no_unapproved_mutation":
                cid = dw["criterion_id"]
                tpath = self.handoff_manager.canonicalize_artifact_path(
                    dw["target"], base_dir=self.root_dir, is_writable_output=False
                )
                pre_snapshots[cid] = snapshot_directory_hashes(tpath)

        pre_review_hashes: dict[str, str] = {}
        role = self.registry.get_role(handoff["assigned_agent"])
        if role["department"] == "independent_verification_department":
            for dep_tid in handoff.get("dependencies", []):
                if dep_tid in by_id:
                    for cp in self.handoff_manager.canonical_owned_paths(by_id[dep_tid], base_dir=self.root_dir):
                        rp = cp.relative_to(self.root_dir).as_posix()
                        if cp.is_file():
                            pre_review_hashes[rp] = compute_file_sha256(cp)
                        elif rp in artifact_sha256:
                            pre_review_hashes[rp] = artifact_sha256[rp]

        return {
            "pre_execution_snapshots": pre_snapshots,
            "pre_review_hashes": pre_review_hashes,
        }

    def _verify_worker_completion_deterministically(
        self,
        *,
        handoff: dict[str, Any],
        result: AgentExecutionResult,
        by_id: dict[str, dict[str, Any]],
        artifact_sha256: dict[str, str],
        receipts_by_task: dict[str, dict[str, Any]],
        pre_exec_ctx: dict[str, Any] | None = None,
        custom_predicate: Callable[[dict[str, Any], AgentExecutionResult, Path], bool] | None = None,
    ) -> dict[str, str]:
        """Deterministically verify receipt, identity, disk outputs, all 6 done_when types, evidence & verifier integrity."""
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
        if self.disallow_mock_execution and result.receipt.execution_mode == "mock_execution":
            raise WorkerCompletionRejectedError(
                f"Task '{tid}' used 'mock_execution' while disallow_mock_execution=True!"
            )

        try:
            eval_out = self.acceptance_engine.evaluate_all(
                handoff=handoff,
                result=result,
                context_state={
                    "by_id": by_id,
                    "artifact_sha256": artifact_sha256,
                    "receipts_by_task": receipts_by_task,
                    **(pre_exec_ctx or {}),
                },
            )
        except UnsupportedAcceptanceCheckError:
            # Propagate intact so scheduler transitions task directly to BLOCKED (never retried/ignored)
            raise
        except (AcceptanceCriteriaError, HandoffValidationError, SilentArtifactMutationError) as exc:
            raise WorkerCompletionRejectedError(str(exc)) from exc

        verified_outputs: dict[str, str] = eval_out["verified_outputs"]

        # Enforce Independent Verification Department review check even if done_when used another check_type
        role = self.registry.get_role(handoff["assigned_agent"])
        has_review_dw = any(dw.get("check_type") == "independent_review_verdict" for dw in handoff["done_when"])
        if role["department"] == "independent_verification_department" and not has_review_dw:
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
            extra_tids = list(
                rep_dict.get("additional_reviewed_task_ids")
                or handoff.get("context", {}).get("additional_reviewed_task_ids")
                or []
            )
            extra_handoffs = [by_id[et] for et in extra_tids if et in by_id and et != prod_tid]
            pre_hashes: dict[str, str] = dict((pre_exec_ctx or {}).get("pre_review_hashes") or {})
            if not pre_hashes:
                for ph in [prod_handoff, *extra_handoffs]:
                    for cp in self.handoff_manager.canonical_owned_paths(ph, base_dir=self.root_dir):
                        rp = cp.relative_to(self.root_dir).as_posix()
                        if rp in artifact_sha256:
                            pre_hashes[rp] = artifact_sha256[rp]
            prod_conv = (receipts_by_task.get(prod_tid) or {}).get("conversation_id")
            try:
                self.handoff_manager.verify_independent_review_pass(
                    verifier_handoff=handoff,
                    producer_handoff=prod_handoff,
                    additional_producer_handoffs=extra_handoffs,
                    pre_review_hashes=pre_hashes,
                    review_report=rep_dict,
                    criteria_manifest=handoff.get("context", {}).get("criteria_manifest"),
                    required_criteria_ids=handoff.get("context", {}).get("required_criteria_ids"),
                    producer_conversation_id=prod_conv,
                    base_dir=self.root_dir,
                )
            except (HandoffValidationError, SilentArtifactMutationError) as exc:
                raise WorkerCompletionRejectedError(str(exc)) from exc
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

        # Detect unsupported check_types up front so even check_types outside schema enum become BLOCKED (not ignored)
        pre_unsupported_by_tid: dict[str, tuple[str, str]] = {}
        validation_view: list[dict[str, Any]] = []
        for h in tasks_copy:
            unsup = self.acceptance_engine.find_unsupported_checks(h)
            if unsup:
                pre_unsupported_by_tid[h["task_id"]] = unsup[0]
                h_val = copy.deepcopy(h)
                for dw in h_val.get("done_when", []):
                    if dw.get("check_type") not in AcceptanceCriteriaEngine.SUPPORTED_CHECK_TYPES:
                        dw["check_type"] = "file_exists_nonempty"
                validation_view.append(h_val)
            else:
                validation_view.append(h)

        # NEVER trust caller-supplied initial task status when resume_state is None!
        if resume_state is None:
            for h, hv in zip(tasks_copy, validation_view):
                init_st = str(h.get("status", ""))
                if init_st not in ALLOWED_INITIAL_TASK_STATUSES:
                    raise InitialCompletedStatusRejectedError(
                        f"Task '{h['task_id']}' has forbidden initial status='{init_st}'! "
                        "Fresh tasks must start in PENDING (or READY), and COMPLETED can ONLY be restored "
                        "from a SHA-256-sealed verified checkpoint."
                    )
                h["status"] = "PENDING"
                hv["status"] = "PENDING"
        else:
            self._validate_and_bind_resume_state(
                resume_state=resume_state,
                project_id=project_id,
                tasks_copy=validation_view,
            )
            comp_set = set(resume_state["completed_tasks"])
            fail_set = set(resume_state["failed_tasks"])
            blk_set = set(resume_state["blocked_tasks"])
            canc_set = set(resume_state["cancelled_tasks"])
            for h, hv in zip(tasks_copy, validation_view):
                tid = h["task_id"]
                if tid in resume_state.get("retry_budget", {}):
                    h["retry_budget"] = copy.deepcopy(resume_state["retry_budget"][tid])
                    hv["retry_budget"] = copy.deepcopy(resume_state["retry_budget"][tid])
                new_st = (
                    "COMPLETED"
                    if tid in comp_set
                    else (
                        "FAILED"
                        if tid in fail_set
                        else ("BLOCKED" if tid in blk_set else ("CANCELLED" if tid in canc_set else "PENDING"))
                    )
                )
                h["status"] = new_st
                hv["status"] = new_st

        topo_order = self.handoff_manager.validate_task_dag_and_ownership(
            validation_view, base_dir=self.root_dir
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
        # Production approval is frozen to False prior to Phase 01.6D
        eff_approval = {
            "approved": False,
            "approved_digest": None,
            "approved_version": (approval_status or {}).get("approved_version"),
            "revoked": bool((approval_status or {}).get("revoked", False)),
        }
        skipped_via_idempotency: list[str] = sorted(completed)
        failures_recorded: list[dict[str, Any]] = []
        active_role_counts: dict[str, int] = {}
        active_owned_canon: dict[str, str] = {}
        state_guard = asyncio.Lock()

        # Immediately transition tasks with unsupported acceptance check_type -> BLOCKED (never ignored!)
        for bad_tid, (bad_cid, bad_ctype) in sorted(pre_unsupported_by_tid.items()):
            if bad_tid in pending or bad_tid in completed:
                pending.discard(bad_tid)
                completed.discard(bad_tid)
                blocked.add(bad_tid)
                by_id[bad_tid]["status"] = "BLOCKED"
                fail_rep = AgentFailureReport(
                    failure_id=f"ERR-{bad_tid}-UNSUP-{uuid.uuid4().hex[:6]}",
                    task_id=bad_tid,
                    project_id=project_id,
                    assigned_agent=by_id[bad_tid]["assigned_agent"],
                    error_category="UNSUPPORTED_ACCEPTANCE_CHECK",
                    message=(
                        f"Task '{bad_tid}' criterion '{bad_cid}' uses unsupported check_type='{bad_ctype}'; "
                        "transitioned to BLOCKED."
                    ),
                    attempt_number=0,
                    retryable=False,
                    occurred_at=utc_now_iso(),
                )
                failures_recorded.append(fail_rep.to_dict())
                if self.memory_store is not None:
                    self.memory_store.error.record_error(
                        project_id=project_id,
                        error_id=fail_rep.failure_id,
                        task_id=bad_tid,
                        error_category="UNSUPPORTED_ACCEPTANCE_CHECK",
                        payload=fail_rep.to_dict(),
                    )
                for dep_tid in self._transitive_dependents(bad_tid, by_id):
                    if dep_tid in pending:
                        pending.discard(dep_tid)
                        blocked.add(dep_tid)
                        by_id[dep_tid]["status"] = "BLOCKED"

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

            if aid in self.PHASE01_6B_BLOCKED_LIVE_ROLES:
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
                    f"Live execution of '{aid}' is strictly blocked in Phase 01.6B/01.6C prior to Phase 02 authorization!"
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
                    elif cp.is_file() and h["input_artifact_hashes"].get(raw_inp) == "0" * 64:
                        new_hashes[raw_inp] = compute_file_sha256(cp)
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
                    await asyncio.to_thread(
                        self.handoff_manager.revalidate_at_execution_boundary,
                        h,
                        base_dir=self.root_dir,
                        acquire_locks=True,
                    )
                    locks_acquired = True

                    pre_exec_ctx = await asyncio.to_thread(
                        self._capture_pre_execution_context,
                        h,
                        by_id,
                        artifact_sha256,
                    )

                    exec_result = await asyncio.wait_for(executor(h, attempt_no), timeout=timeout_s)

                    async with state_guard:
                        verified_outputs = self._verify_worker_completion_deterministically(
                            handoff=h,
                            result=exec_result,
                            by_id=by_id,
                            artifact_sha256=artifact_sha256,
                            receipts_by_task=receipts_by_task,
                            pre_exec_ctx=pre_exec_ctx,
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

                except UnsupportedAcceptanceCheckError as unsup_exc:
                    rb["attempts_used"] = attempt_no
                    fail_rep = AgentFailureReport(
                        failure_id=f"ERR-{tid}-{attempt_no}-{uuid.uuid4().hex[:6]}",
                        task_id=tid,
                        project_id=project_id,
                        assigned_agent=aid,
                        error_category="UNSUPPORTED_ACCEPTANCE_CHECK",
                        message=str(unsup_exc),
                        attempt_number=attempt_no,
                        retryable=False,
                        occurred_at=utc_now_iso(),
                    )
                    async with state_guard:
                        failures_recorded.append(fail_rep.to_dict())
                        if self.memory_store is not None:
                            self.memory_store.error.record_error(
                                project_id=project_id,
                                error_id=fail_rep.failure_id,
                                task_id=tid,
                                error_category="UNSUPPORTED_ACCEPTANCE_CHECK",
                                payload=fail_rep.to_dict(),
                            )
                        running.discard(tid)
                        blocked.add(tid)
                        h["status"] = "BLOCKED"
                        active_role_counts[aid] = max(0, active_role_counts.get(aid, 1) - 1)
                        for ck, owner in list(active_owned_canon.items()):
                            if owner == tid:
                                active_owned_canon.pop(ck, None)
                        for dep_tid in self._transitive_dependents(tid, by_id):
                            if dep_tid in pending:
                                pending.discard(dep_tid)
                                blocked.add(dep_tid)
                                by_id[dep_tid]["status"] = "BLOCKED"
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

                    pending.discard(tid)
                    running.add(tid)
                    h["status"] = "RUNNING"
                    active_role_counts[aid] = active_role_counts.get(aid, 0) + 1
                    for ck in canon_paths:
                        active_owned_canon[ck] = tid
                    _persist_checkpoint()
                    active_futures[tid] = asyncio.create_task(_run_single_task(tid))

            if not active_futures:
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
                exc = fut.exception()
                if isinstance(exc, PhaseBoundaryExecutionBlockedError):
                    for other in active_futures.values():
                        other.cancel()
                    if active_futures:
                        await asyncio.gather(*active_futures.values(), return_exceptions=True)
                    raise exc

        final_ckpt = _persist_checkpoint()
        has_unsup = any(f["error_category"] == "UNSUPPORTED_ACCEPTANCE_CHECK" for f in failures_recorded)
        overall_status = (
            "SUCCEEDED"
            if len(completed) == len(by_id)
            else ("CANCELLED" if cancelled and not failed and not has_unsup else "PARTIAL_OR_FAILED")
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
