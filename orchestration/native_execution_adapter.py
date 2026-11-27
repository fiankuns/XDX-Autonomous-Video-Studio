"""Native Agent Execution Adapter & Invocation Contracts (Phase 01.6B).

Separates Python task planning from host-native subagent execution so Python NEVER claims
to have invoked a native subagent when it only generated a dispatch request.

Contracts provided:
- `AgentInvocationRequest`
- `AgentInvocationReceipt`
- `AgentExecutionResult`
- `AgentFailureReport`
- `AgentReviewReport`
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from orchestration.agent_registry import AgentRegistry
from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256

ROOT_DIR = Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_idempotency_key(
    *,
    project_id: str,
    task_id: str,
    task_graph_version: int,
    input_artifact_hashes: dict[str, str],
) -> str:
    canonical_inputs = json.dumps(dict(sorted(input_artifact_hashes.items())), separators=(",", ":"))
    raw = f"{project_id}|{task_id}|v{task_graph_version}|{canonical_inputs}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgentInvocationRequest:
    request_id: str
    idempotency_key: str
    task_id: str
    project_id: str
    assigned_agent: str
    subagent_type_name: str
    workspace_mode: str
    requested_model: str
    prompt: str
    input_artifact_hashes: dict[str, str]
    owned_artifacts: list[str]
    timeout_seconds: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentInvocationReceipt:
    receipt_id: str
    request_id: str
    idempotency_key: str
    task_id: str
    project_id: str
    assigned_agent: str
    runtime_name: str
    execution_mode: str  # "native_subagent" | "sequential_fallback_honest" | "dispatch_plan_only_not_invoked"
    actually_invoked: bool
    conversation_id: str | None
    known_model_routing: str
    started_at: str
    completed_at: str | None
    output_artifact_hashes: dict[str, str] = field(default_factory=dict)
    receipt_sha256: str = ""

    @classmethod
    def create_verified(
        cls,
        *,
        request: AgentInvocationRequest,
        runtime_name: str,
        execution_mode: str,
        actually_invoked: bool,
        conversation_id: str | None,
        known_model_routing: str,
        started_at: str,
        completed_at: str | None,
        output_artifact_hashes: dict[str, str],
    ) -> AgentInvocationReceipt:
        if execution_mode not in {
            "native_subagent",
            "sequential_fallback_honest",
            "dispatch_plan_only_not_invoked",
        }:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        if execution_mode == "dispatch_plan_only_not_invoked" and actually_invoked:
            raise ValueError("Dispatch plan cannot claim actually_invoked=True!")
        if execution_mode == "native_subagent":
            if not actually_invoked or not conversation_id or len(conversation_id.strip()) < 8:
                raise ValueError("native_subagent receipt requires actually_invoked=True and valid conversation_id")
        if execution_mode == "sequential_fallback_honest" and conversation_id is not None:
            raise ValueError("sequential_fallback_honest must not fabricate a native subagent conversation_id")

        receipt_id = f"RCPT-{uuid.uuid4().hex[:12]}"
        body = {
            "receipt_id": receipt_id,
            "request_id": request.request_id,
            "idempotency_key": request.idempotency_key,
            "task_id": request.task_id,
            "project_id": request.project_id,
            "assigned_agent": request.assigned_agent,
            "runtime_name": runtime_name,
            "execution_mode": execution_mode,
            "actually_invoked": actually_invoked,
            "conversation_id": conversation_id,
            "known_model_routing": known_model_routing,
            "started_at": started_at,
            "completed_at": completed_at,
            "output_artifact_hashes": dict(sorted(output_artifact_hashes.items())),
        }
        sig = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return cls(**body, receipt_sha256=sig)

    def verify_integrity(self) -> bool:
        body = {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "assigned_agent": self.assigned_agent,
            "runtime_name": self.runtime_name,
            "execution_mode": self.execution_mode,
            "actually_invoked": self.actually_invoked,
            "conversation_id": self.conversation_id,
            "known_model_routing": self.known_model_routing,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output_artifact_hashes": dict(sorted(self.output_artifact_hashes.items())),
        }
        expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return expected == self.receipt_sha256

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_review_receipt_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["invocation_id"] = self.receipt_id
        d["agent_id"] = self.assigned_agent
        return d


@dataclass(frozen=True)
class AgentFailureReport:
    failure_id: str
    task_id: str
    project_id: str
    assigned_agent: str
    error_category: str  # "TIMEOUT" | "EXECUTION_ERROR" | "VALIDATION_FAILED" | "CANCELLED" | "RESOURCE_UNAVAILABLE"
    message: str
    attempt_number: int
    retryable: bool
    occurred_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentReviewReport:
    review_id: str
    project_id: str
    verifier_agent: str
    reviewed_task_id: str
    producer_agent: str
    verdict: str
    invocation_receipt: dict[str, Any]
    reviewed_artifact_hashes: dict[str, str]
    required_criteria_ids: list[str]
    checked_criteria: list[dict[str, Any]]
    defects: list[dict[str, Any]]
    schema_version: str = "4.0.0-phase01.6b"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentExecutionResult:
    task_id: str
    project_id: str
    status: str  # "SUCCEEDED" | "DISPATCH_PENDING_HOST" | "FAILED"
    receipt: AgentInvocationReceipt
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_items: list[str] = field(default_factory=list)
    failure: AgentFailureReport | None = None
    review_report: AgentReviewReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "status": self.status,
            "receipt": self.receipt.to_dict(),
            "payload": self.payload,
            "evidence_items": list(self.evidence_items),
            "failure": self.failure.to_dict() if self.failure else None,
            "review_report": self.review_report.to_dict() if self.review_report else None,
        }


class NativeAgentExecutionAdapter:
    """Builds dispatch requests, records verified host subagent receipts, or executes honest sequential fallbacks."""

    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        handoff_manager: TaskHandoffManager | None = None,
        registry: AgentRegistry | None = None,
    ) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self.registry = registry or AgentRegistry(root_dir=self.root_dir)
        self.handoff_manager = handoff_manager or TaskHandoffManager(root_dir=self.root_dir, registry=self.registry)

    def build_invocation_request(
        self,
        handoff: dict[str, Any],
        *,
        task_graph_version: int = 1,
        prompt_override: str | None = None,
    ) -> AgentInvocationRequest:
        role = self.handoff_manager.validate_handoff(handoff, base_dir=self.root_dir)
        subagent_md = Path(role["custom_subagent_file"]).stem  # e.g. xdx-rea-reference-analyst
        idem = compute_idempotency_key(
            project_id=handoff["project_id"],
            task_id=handoff["task_id"],
            task_graph_version=task_graph_version,
            input_artifact_hashes=handoff["input_artifact_hashes"],
        )
        default_prompt = (
            f"Execute structured task {handoff['task_id']} for project {handoff['project_id']}: {handoff['goal']}"
        )
        return AgentInvocationRequest(
            request_id=f"REQ-{uuid.uuid4().hex[:12]}",
            idempotency_key=idem,
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            assigned_agent=handoff["assigned_agent"],
            subagent_type_name=subagent_md,
            workspace_mode=handoff["context"]["workspace_mode"],
            requested_model=role["preferred_model_routing"]["subagent_tool_model_arg"],
            prompt=prompt_override or default_prompt,
            input_artifact_hashes=dict(handoff["input_artifact_hashes"]),
            owned_artifacts=list(handoff["owned_artifacts"]),
            timeout_seconds=int(handoff["retry_budget"]["timeout_seconds"]),
            created_at=utc_now_iso(),
        )

    def emit_host_dispatch_plan_only(
        self,
        handoff: dict[str, Any],
        *,
        task_graph_version: int = 1,
    ) -> AgentExecutionResult:
        """Honest non-invoking planner output when Python prepares a request for the host Master Director."""
        req = self.build_invocation_request(handoff, task_graph_version=task_graph_version)
        receipt = AgentInvocationReceipt.create_verified(
            request=req,
            runtime_name="antigravity",
            execution_mode="dispatch_plan_only_not_invoked",
            actually_invoked=False,
            conversation_id=None,
            known_model_routing="pending_host_invoke_subagent",
            started_at=req.created_at,
            completed_at=None,
            output_artifact_hashes={},
        )
        return AgentExecutionResult(
            task_id=req.task_id,
            project_id=req.project_id,
            status="DISPATCH_PENDING_HOST",
            receipt=receipt,
            payload={"request": req.to_dict()},
            evidence_items=[],
        )

    def record_host_subagent_completion(
        self,
        *,
        handoff: dict[str, Any],
        request: AgentInvocationRequest,
        conversation_id: str,
        known_model_routing: str,
        started_at: str,
        completed_at: str,
        payload: dict[str, Any],
        evidence_items: list[str],
        runtime_name: str = "antigravity",
        review_report: AgentReviewReport | None = None,
    ) -> AgentExecutionResult:
        """Record a genuine host-dispatched native subagent execution and hash all owned outputs on disk."""
        out_hashes: dict[str, str] = {}
        for cpath in self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir):
            if not cpath.is_file():
                raise FileNotFoundError(f"Expected output artifact missing on disk after host subagent run: {cpath}")
            rel_posix = cpath.relative_to(self.root_dir).as_posix()
            out_hashes[rel_posix] = compute_file_sha256(cpath)

        receipt = AgentInvocationReceipt.create_verified(
            request=request,
            runtime_name=runtime_name,
            execution_mode="native_subagent",
            actually_invoked=True,
            conversation_id=conversation_id,
            known_model_routing=known_model_routing,
            started_at=started_at,
            completed_at=completed_at,
            output_artifact_hashes=out_hashes,
        )
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=payload,
            evidence_items=evidence_items,
            review_report=review_report,
        )

    def execute_sequential_fallback(
        self,
        *,
        handoff: dict[str, Any],
        worker_fn: Callable[[dict[str, Any], Path], dict[str, Any]],
        task_graph_version: int = 1,
        runtime_name: str = "python_local_test",
    ) -> AgentExecutionResult:
        """Execute a Python worker sequentially with full honesty (`execution_mode='sequential_fallback_honest'`)."""
        req = self.build_invocation_request(handoff, task_graph_version=task_graph_version)
        started_at = utc_now_iso()
        out = worker_fn(handoff, self.root_dir)
        completed_at = utc_now_iso()

        out_hashes: dict[str, str] = {}
        for cpath in self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir):
            if cpath.is_file():
                rel_posix = cpath.relative_to(self.root_dir).as_posix()
                out_hashes[rel_posix] = compute_file_sha256(cpath)

        receipt = AgentInvocationReceipt.create_verified(
            request=req,
            runtime_name=runtime_name,
            execution_mode="sequential_fallback_honest",
            actually_invoked=True,
            conversation_id=None,
            known_model_routing="local_sequential_python_callable",
            started_at=started_at,
            completed_at=completed_at,
            output_artifact_hashes=out_hashes,
        )
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=out.get("payload", {}),
            evidence_items=list(out.get("evidence_items", ["Sequential fallback execution completed"])),
            review_report=out.get("review_report"),
        )
