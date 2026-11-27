"""Native Agent Execution Adapter, 5-Mode Invocation Receipts & Immutable Review Criteria Manifest (Phase 01.6C).

Separates Python task planning from host-native subagent execution so Python NEVER claims
to have invoked a native subagent when it only generated a dispatch request or replayed a recording.

Five explicit execution modes (Section 16):
1. ``native_subagent``: Genuine host-invoked subagent backed by a runtime ``conversation_id`` AND
   host dispatch/transcript proof (never a bare hardcoded ``conversation_id`` alone when host proof is required).
2. ``recorded_workflow_replay``: Deterministic replay of a previously recorded host receipt ledger
   against verified on-disk SHA-256 artifacts (honestly marked as replay, not a new live LLM call).
3. ``sequential_fallback_honest``: Deterministic Python callable execution (``conversation_id=None``).
4. ``mock_execution``: Controlled simulated worker for ``@pytest.mark.mock_test`` suites (``conversation_id=None``).
5. ``dispatch_plan_only_not_invoked``: Non-invoking planner output (``actually_invoked=False``),
   always rejected as task completion by ``TaskDependencyScheduler``.

Also provides ``ImmutableReviewCriteriaManifest`` (Section 4.C), created and SHA-256-sealed by
``master_director`` BEFORE any Independent Verification Department reviewer is invoked.
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
from orchestration.task_identity import canonical_json, compute_task_definition_digest, sha256_text

ROOT_DIR = Path(__file__).resolve().parent.parent

VALID_EXECUTION_MODES: frozenset[str] = frozenset(
    {
        "native_subagent",
        "recorded_workflow_replay",
        "sequential_fallback_honest",
        "mock_execution",
        "dispatch_plan_only_not_invoked",
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_idempotency_key(
    *,
    project_id: str,
    task_id: str,
    task_graph_version: int,
    input_artifact_hashes: dict[str, str],
    task_definition_digest: str | None = None,
) -> str:
    canonical_inputs = json.dumps(dict(sorted(input_artifact_hashes.items())), separators=(",", ":"))
    raw = f"{project_id}|{task_id}|v{task_graph_version}|{canonical_inputs}"
    if task_definition_digest:
        raw = f"{raw}|{task_definition_digest}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_host_transcript_contains_subagent(
    transcript_path: Path,
    *,
    conversation_id: str,
    subagent_type_name: str | None = None,
) -> dict[str, Any]:
    """Inspect an Antigravity host ``transcript.jsonl`` to verify genuine ``invoke_subagent`` proof."""
    if not transcript_path.is_file():
        return {"verified": False, "reason": f"Transcript file not found: {transcript_path}"}
    clean_cid = conversation_id.strip()
    if not clean_cid:
        return {"verified": False, "reason": "Empty conversation_id"}

    matched_lines = 0
    saw_invoke_tool = False
    raw_text = transcript_path.read_text(encoding="utf-8", errors="replace")
    for line in raw_text.splitlines():
        if "invoke_subagent" in line:
            saw_invoke_tool = True
        if clean_cid in line:
            if subagent_type_name is None or subagent_type_name in raw_text:
                matched_lines += 1

    return {
        "verified": bool(saw_invoke_tool and matched_lines > 0),
        "saw_invoke_subagent_tool": saw_invoke_tool,
        "conversation_id_occurrences": matched_lines,
        "transcript_sha256": compute_file_sha256(transcript_path),
    }


@dataclass(frozen=True)
class ImmutableReviewCriteriaManifest:
    """Immutable mandatory review criteria manifest sealed by Master Director BEFORE review begins."""

    manifest_id: str
    project_id: str
    producer_task_id: str
    reviewer_task_id: str
    additional_reviewed_task_ids: list[str]
    created_by: str
    created_at_utc: str
    required_criteria: list[dict[str, Any]]
    manifest_sha256: str

    @staticmethod
    def _compute_digest(body: dict[str, Any]) -> str:
        clean = {k: v for k, v in body.items() if k != "manifest_sha256"}
        return sha256_text(canonical_json(clean))

    @classmethod
    def create_sealed(
        cls,
        *,
        project_id: str,
        producer_task_id: str,
        reviewer_task_id: str,
        required_criteria: list[dict[str, Any]],
        additional_reviewed_task_ids: list[str] | None = None,
        created_by: str = "master_director",
        created_at_utc: str | None = None,
    ) -> ImmutableReviewCriteriaManifest:
        if created_by != "master_director":
            raise ValueError("Only 'master_director' may create an ImmutableReviewCriteriaManifest")
        if not required_criteria:
            raise ValueError("ImmutableReviewCriteriaManifest requires at least one mandatory criterion")

        seen_ids: set[str] = set()
        normalized_criteria: list[dict[str, Any]] = []
        for item in required_criteria:
            cid = str(item.get("criterion_id", "")).strip()
            desc = str(item.get("description", "")).strip()
            if len(cid) < 3 or len(desc) < 5:
                raise ValueError(f"Invalid criterion definition in manifest: {item!r}")
            if cid in seen_ids:
                raise ValueError(f"Duplicate criterion_id '{cid}' in ImmutableReviewCriteriaManifest")
            seen_ids.add(cid)
            normalized_criteria.append(
                {
                    "criterion_id": cid,
                    "category": str(item.get("category", "mandatory_gate")).strip(),
                    "description": desc,
                    "required_artifacts": sorted(set(item.get("required_artifacts") or [])),
                }
            )

        now = created_at_utc or utc_now_iso()
        manifest_id = f"CRITMAN-{project_id[:24]}-{uuid.uuid4().hex[:8]}"
        extra_tids = sorted({t for t in (additional_reviewed_task_ids or []) if t != producer_task_id})
        body: dict[str, Any] = {
            "manifest_id": manifest_id,
            "project_id": project_id,
            "producer_task_id": producer_task_id,
            "reviewer_task_id": reviewer_task_id,
            "additional_reviewed_task_ids": extra_tids,
            "created_by": created_by,
            "created_at_utc": now,
            "required_criteria": normalized_criteria,
        }
        digest = cls._compute_digest(body)
        return cls(**body, manifest_sha256=digest)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImmutableReviewCriteriaManifest:
        inst = cls(
            manifest_id=str(data["manifest_id"]),
            project_id=str(data["project_id"]),
            producer_task_id=str(data["producer_task_id"]),
            reviewer_task_id=str(data["reviewer_task_id"]),
            additional_reviewed_task_ids=list(data.get("additional_reviewed_task_ids", [])),
            created_by=str(data["created_by"]),
            created_at_utc=str(data["created_at_utc"]),
            required_criteria=list(data["required_criteria"]),
            manifest_sha256=str(data["manifest_sha256"]),
        )
        if not inst.verify_integrity():
            raise ValueError("ImmutableReviewCriteriaManifest SHA-256 integrity seal mismatch (tampered!)")
        return inst

    def verify_integrity(self) -> bool:
        if self.created_by != "master_director" or not self.required_criteria:
            return False
        return self._compute_digest(asdict(self)) == self.manifest_sha256

    @property
    def required_criteria_ids(self) -> list[str]:
        return [c["criterion_id"] for c in self.required_criteria]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    task_definition_digest: str = ""

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
    execution_mode: str
    actually_invoked: bool
    conversation_id: str | None
    known_model_routing: str
    started_at: str
    completed_at: str | None
    output_artifact_hashes: dict[str, str] = field(default_factory=dict)
    task_definition_digest: str = ""
    host_invocation_evidence: dict[str, Any] = field(default_factory=dict)
    receipt_sha256: str = ""

    def _canonical_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
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
        if self.task_definition_digest:
            body["task_definition_digest"] = self.task_definition_digest
        if self.host_invocation_evidence:
            body["host_invocation_evidence"] = self.host_invocation_evidence
        return body

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
        host_invocation_evidence: dict[str, Any] | None = None,
    ) -> AgentInvocationReceipt:
        if execution_mode not in VALID_EXECUTION_MODES:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        if execution_mode == "dispatch_plan_only_not_invoked" and actually_invoked:
            raise ValueError("Dispatch plan cannot claim actually_invoked=True!")
        if execution_mode == "native_subagent":
            if not actually_invoked or not conversation_id or len(conversation_id.strip()) < 8:
                raise ValueError("native_subagent receipt requires actually_invoked=True and valid conversation_id")
        if execution_mode in {"sequential_fallback_honest", "mock_execution"} and conversation_id is not None:
            raise ValueError(f"{execution_mode} must not fabricate a native subagent conversation_id")
        if execution_mode == "recorded_workflow_replay":
            if not actually_invoked:
                raise ValueError("recorded_workflow_replay requires actually_invoked=True from recorded receipt")

        receipt_id = f"RCPT-{uuid.uuid4().hex[:12]}"
        temp = cls(
            receipt_id=receipt_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            task_id=request.task_id,
            project_id=request.project_id,
            assigned_agent=request.assigned_agent,
            runtime_name=runtime_name,
            execution_mode=execution_mode,
            actually_invoked=actually_invoked,
            conversation_id=conversation_id,
            known_model_routing=known_model_routing,
            started_at=started_at,
            completed_at=completed_at,
            output_artifact_hashes=dict(sorted(output_artifact_hashes.items())),
            task_definition_digest=request.task_definition_digest,
            host_invocation_evidence=dict(host_invocation_evidence or {}),
            receipt_sha256="",
        )
        sig = hashlib.sha256(
            json.dumps(temp._canonical_body(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(**{**asdict(temp), "receipt_sha256": sig})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentInvocationReceipt:
        return cls(
            receipt_id=str(data["receipt_id"]),
            request_id=str(data["request_id"]),
            idempotency_key=str(data["idempotency_key"]),
            task_id=str(data["task_id"]),
            project_id=str(data["project_id"]),
            assigned_agent=str(data["assigned_agent"]),
            runtime_name=str(data["runtime_name"]),
            execution_mode=str(data["execution_mode"]),
            actually_invoked=bool(data["actually_invoked"]),
            conversation_id=data.get("conversation_id"),
            known_model_routing=str(data.get("known_model_routing", "")),
            started_at=str(data["started_at"]),
            completed_at=data.get("completed_at"),
            output_artifact_hashes=dict(data.get("output_artifact_hashes") or {}),
            task_definition_digest=str(data.get("task_definition_digest") or ""),
            host_invocation_evidence=dict(data.get("host_invocation_evidence") or {}),
            receipt_sha256=str(data.get("receipt_sha256") or ""),
        )

    def verify_integrity(self) -> bool:
        if self.execution_mode not in VALID_EXECUTION_MODES:
            return False
        if self.execution_mode == "dispatch_plan_only_not_invoked" and self.actually_invoked:
            return False
        if self.execution_mode == "native_subagent" and (
            not self.actually_invoked or not self.conversation_id or len(self.conversation_id.strip()) < 8
        ):
            return False
        expected = hashlib.sha256(
            json.dumps(self._canonical_body(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
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
    error_category: str
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
    reviewer_task_id: str | None = None
    additional_reviewed_task_ids: list[str] | None = None
    producer_conversation_id: str | None = None
    reviewer_conversation_id: str | None = None
    criteria_manifest_digest: str | None = None
    reviewed_artifact_manifest: dict[str, dict[str, Any]] | None = None
    pre_review_hashes: dict[str, str] | None = None
    post_review_hashes: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "project_id": self.project_id,
            "verifier_agent": self.verifier_agent,
            "reviewed_task_id": self.reviewed_task_id,
            "producer_agent": self.producer_agent,
            "verdict": self.verdict,
            "invocation_receipt": self.invocation_receipt,
            "reviewed_artifact_hashes": self.reviewed_artifact_hashes,
            "required_criteria_ids": list(self.required_criteria_ids),
            "checked_criteria": list(self.checked_criteria),
            "defects": list(self.defects),
        }
        optional_fields = (
            ("reviewer_task_id", self.reviewer_task_id),
            ("additional_reviewed_task_ids", self.additional_reviewed_task_ids),
            ("producer_conversation_id", self.producer_conversation_id),
            ("reviewer_conversation_id", self.reviewer_conversation_id),
            ("criteria_manifest_digest", self.criteria_manifest_digest),
            ("reviewed_artifact_manifest", self.reviewed_artifact_manifest),
            ("pre_review_hashes", self.pre_review_hashes),
            ("post_review_hashes", self.post_review_hashes),
        )
        for key, val in optional_fields:
            if val is not None or self.schema_version == "4.0.0-phase01.6c" and key in {
                "producer_conversation_id",
                "reviewer_conversation_id",
            }:
                out[key] = val
        return out


@dataclass(frozen=True)
class AgentExecutionResult:
    task_id: str
    project_id: str
    status: str  # "SUCCEEDED" | "DISPATCH_PENDING_HOST" | "FAILED"
    receipt: AgentInvocationReceipt
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_items: list[str] = field(default_factory=list)
    criterion_evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
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
            "criterion_evidence": dict(self.criterion_evidence),
            "failure": self.failure.to_dict() if self.failure else None,
            "review_report": self.review_report.to_dict() if self.review_report else None,
        }


class NativeAgentExecutionAdapter:
    """Builds dispatch requests, records verified host receipts, replays recordings, or runs honest fallbacks."""

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

    def _build_default_criterion_evidence(
        self, handoff: dict[str, Any], out_hashes: dict[str, str]
    ) -> dict[str, dict[str, Any]]:
        ev_map: dict[str, dict[str, Any]] = {}
        for dw in handoff.get("done_when", []):
            cid = dw["criterion_id"]
            target_raw = dw["target"].split("::")[0]
            try:
                cp = self.handoff_manager.canonicalize_artifact_path(
                    target_raw, base_dir=self.root_dir, is_writable_output=False
                )
                rel = cp.relative_to(self.root_dir).as_posix()
            except Exception:
                rel = target_raw
            sha = out_hashes.get(rel)
            if sha is None:
                try:
                    cand = self.root_dir / rel
                    if cand.is_file():
                        sha = compute_file_sha256(cand)
                except Exception:
                    sha = None
            ev_map[cid] = {
                "criterion_id": cid,
                "check_type": dw["check_type"],
                "target": rel,
                "verified_sha256": sha,
                "task_id": handoff["task_id"],
            }
        return ev_map

    def build_invocation_request(
        self,
        handoff: dict[str, Any],
        *,
        task_graph_version: int = 1,
        prompt_override: str | None = None,
    ) -> AgentInvocationRequest:
        role = self.handoff_manager.validate_handoff(handoff, base_dir=self.root_dir)
        subagent_md = Path(role["custom_subagent_file"]).stem
        tdef_digest = compute_task_definition_digest(handoff)
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
            task_definition_digest=tdef_digest,
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

    def _hash_owned_outputs(self, handoff: dict[str, Any], *, require_present: bool) -> dict[str, str]:
        out_hashes: dict[str, str] = {}
        for cpath in self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir):
            if not cpath.is_file():
                if require_present:
                    raise FileNotFoundError(
                        f"Expected output artifact missing on disk after execution: {cpath}"
                    )
                continue
            rel_posix = cpath.relative_to(self.root_dir).as_posix()
            out_hashes[rel_posix] = compute_file_sha256(cpath)
        return out_hashes

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
        host_invocation_evidence: dict[str, Any] | None = None,
        transcript_path: Path | None = None,
        require_live_host_proof: bool = False,
        criterion_evidence: dict[str, dict[str, Any]] | None = None,
    ) -> AgentExecutionResult:
        """Record a genuine host-dispatched native subagent execution and hash all owned outputs on disk.

        When ``require_live_host_proof=True`` (Phase 01.6C strict mode), a bare ``conversation_id``
        string is NOT accepted as sufficient proof: either ``transcript_path`` must verify an actual
        ``invoke_subagent`` record on the Antigravity host, or ``host_invocation_evidence`` must
        provide a sealed dispatcher receipt with ``host_dispatch_verified=True``.
        """
        out_hashes = self._hash_owned_outputs(handoff, require_present=True)
        ev_proof = dict(host_invocation_evidence or {})
        if transcript_path is not None:
            t_check = verify_host_transcript_contains_subagent(
                transcript_path,
                conversation_id=conversation_id,
                subagent_type_name=request.subagent_type_name,
            )
            ev_proof["transcript_verification"] = t_check
            if require_live_host_proof and not t_check["verified"]:
                raise ValueError(
                    f"Live host proof required for '{handoff['task_id']}', but transcript verification failed: {t_check}"
                )
        elif require_live_host_proof and not ev_proof.get("host_dispatch_verified"):
            raise ValueError(
                f"Cannot claim live 'native_subagent' for '{handoff['task_id']}' from a static conversation_id "
                "alone without verified host transcript or host dispatcher receipt!"
            )

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
            host_invocation_evidence=ev_proof,
        )
        crit_ev = criterion_evidence or self._build_default_criterion_evidence(handoff, out_hashes)
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=payload,
            evidence_items=evidence_items,
            criterion_evidence=crit_ev,
            review_report=review_report,
        )

    def record_workflow_replay_completion(
        self,
        *,
        handoff: dict[str, Any],
        recorded_receipt: dict[str, Any],
        payload: dict[str, Any],
        evidence_items: list[str],
        task_graph_version: int = 1,
        runtime_name: str = "python_local_test",
        review_report: AgentReviewReport | None = None,
        criterion_evidence: dict[str, dict[str, Any]] | None = None,
    ) -> AgentExecutionResult:
        """Replay a previously recorded host receipt honestly (`execution_mode='recorded_workflow_replay'`)."""
        req = self.build_invocation_request(handoff, task_graph_version=task_graph_version)
        out_hashes = self._hash_owned_outputs(handoff, require_present=True)
        orig_hashes = dict(recorded_receipt.get("output_artifact_hashes") or {})
        if orig_hashes and orig_hashes != out_hashes:
            raise ValueError(
                f"Recorded workflow replay output hash drift on '{handoff['task_id']}': "
                f"recorded={orig_hashes} vs actual={out_hashes}"
            )
        replay_meta = {
            "replayed_from_receipt_id": recorded_receipt.get("receipt_id"),
            "original_execution_mode": recorded_receipt.get("execution_mode"),
            "original_conversation_id": recorded_receipt.get("conversation_id"),
            "original_runtime_name": recorded_receipt.get("runtime_name"),
        }
        receipt = AgentInvocationReceipt.create_verified(
            request=req,
            runtime_name=runtime_name,
            execution_mode="recorded_workflow_replay",
            actually_invoked=True,
            conversation_id=recorded_receipt.get("conversation_id"),
            known_model_routing="recorded_receipt_replay_verified_hashes",
            started_at=str(recorded_receipt.get("started_at") or utc_now_iso()),
            completed_at=utc_now_iso(),
            output_artifact_hashes=out_hashes,
            host_invocation_evidence=replay_meta,
        )
        crit_ev = criterion_evidence or self._build_default_criterion_evidence(handoff, out_hashes)
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=payload,
            evidence_items=evidence_items,
            criterion_evidence=crit_ev,
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
        out_hashes = self._hash_owned_outputs(handoff, require_present=False)

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
        crit_ev = out.get("criterion_evidence") or self._build_default_criterion_evidence(handoff, out_hashes)
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=out.get("payload", {}),
            evidence_items=list(out.get("evidence_items", [f"Sequential fallback completed {handoff['task_id']}"])),
            criterion_evidence=crit_ev,
            review_report=out.get("review_report"),
        )

    def execute_mock_worker(
        self,
        *,
        handoff: dict[str, Any],
        worker_fn: Callable[[dict[str, Any], Path], dict[str, Any]],
        task_graph_version: int = 1,
    ) -> AgentExecutionResult:
        """Execute a controlled mock worker (`execution_mode='mock_execution'`), explicitly tagged for mock tests."""
        req = self.build_invocation_request(handoff, task_graph_version=task_graph_version)
        started_at = utc_now_iso()
        out = worker_fn(handoff, self.root_dir)
        completed_at = utc_now_iso()
        out_hashes = self._hash_owned_outputs(handoff, require_present=False)

        receipt = AgentInvocationReceipt.create_verified(
            request=req,
            runtime_name="python_local_test",
            execution_mode="mock_execution",
            actually_invoked=True,
            conversation_id=None,
            known_model_routing="controlled_mock_worker",
            started_at=started_at,
            completed_at=completed_at,
            output_artifact_hashes=out_hashes,
            host_invocation_evidence={"is_mock": True},
        )
        crit_ev = out.get("criterion_evidence") or self._build_default_criterion_evidence(handoff, out_hashes)
        return AgentExecutionResult(
            task_id=handoff["task_id"],
            project_id=handoff["project_id"],
            status="SUCCEEDED",
            receipt=receipt,
            payload=out.get("payload", {}),
            evidence_items=list(out.get("evidence_items", [f"Mock execution completed {handoff['task_id']}"])),
            criterion_evidence=crit_ev,
            review_report=out.get("review_report"),
        )
