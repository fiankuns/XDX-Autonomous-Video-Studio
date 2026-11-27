"""Structured 18-Field Agent Handoff Validator, DAG Dependency Checker & Ownership Guard (Phase 01.6A).

Enforces PART 12 & PART 07 invariants:
1. Validates all 18 mandatory fields against `schemas/task_handoff.schema.json`.
2. Verifies `assigned_agent` exists in `AgentRegistry` and `allowed_tools` is a strict subset of
   that role's permitted tools (and contains zero unknown Antigravity tool names).
3. Blocks read-only verification agents (`17`..`20`) from claiming mutating write ownership over
   producer artifacts (`ReadOnlyAgentOwnershipError`).
4. Enforces single-writer artifact ownership across concurrent tasks (`ParallelWriteConflictError`)
   and single-worker Blender scene exclusivity (`max_concurrent_instances`).
5. Validates the Task DAG (rejects missing dependencies, self-dependencies, cycles, and starting
   a task before its upstream dependencies are `COMPLETED`).
6. Verifies `input_artifact_hashes` SHA-256 digests on disk before task execution (`UnverifiedInputArtifactError`).
7. Verifies independent reviewer discipline (`SilentArtifactMutationError` if any producer artifact
   changes byte-for-byte during an independent review pass).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from orchestration.agent_registry import OFFICIAL_ANTIGRAVITY_TOOLS, AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


class HandoffValidationError(ValueError):
    """Base error for invalid structured agent task handoffs."""


class InvalidTaskDependencyError(HandoffValidationError):
    """Raised when task dependencies reference unknown tasks, self-loops, cycles, or incomplete upstream tasks."""


class ParallelWriteConflictError(HandoffValidationError):
    """Raised when two active/concurrent tasks claim write ownership of the same artifact or exceed role concurrency."""


class ReadOnlyAgentOwnershipError(HandoffValidationError):
    """Raised when a read-only verifier/auditor claims write ownership or mutating tools."""


class UnverifiedInputArtifactError(HandoffValidationError):
    """Raised when required input artifacts are missing or fail SHA-256 verification."""


class SilentArtifactMutationError(PermissionError):
    """Raised if an Independent Verification Agent silently modifies any producer artifact during review."""


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TaskHandoffManager:
    """Validates 18-field task contracts, DAG dependencies, single-writer ownership, and independent reviews."""

    ACTIVE_CONCURRENT_STATES: frozenset[str] = frozenset({"READY", "RUNNING", "WAITING_REVIEW"})

    def __init__(self, root_dir: Path | None = None, registry: AgentRegistry | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self.registry = registry or AgentRegistry(root_dir=self.root_dir)
        self._schema = json.loads(
            (self.root_dir / "schemas" / "task_handoff.schema.json").read_text(encoding="utf-8")
        )

    def _safe_resolve_repo_path(self, rel_or_abs: str, base_dir: Path | None = None) -> Path:
        root = (base_dir or self.root_dir).resolve()
        cand = Path(rel_or_abs)
        target = cand.resolve() if cand.is_absolute() else (root / cand).resolve()
        if not target.is_relative_to(root):
            raise HandoffValidationError(f"Artifact path escapes workspace boundary: {rel_or_abs}")
        return target

    def validate_handoff(
        self,
        handoff: dict[str, Any],
        *,
        enforce_devbox_workspace_mode: bool = True,
    ) -> dict[str, Any]:
        """Validate a single 18-field task handoff contract against schema and AgentRegistry permissions."""
        try:
            jsonschema.validate(instance=handoff, schema=self._schema)
        except jsonschema.ValidationError as exc:
            raise HandoffValidationError(f"Task handoff schema violation: {exc.message}") from exc

        task_id = handoff["task_id"]
        if handoff["parent_task_id"] == task_id:
            raise InvalidTaskDependencyError(f"Task {task_id} cannot be its own parent_task_id")
        if task_id in handoff["dependencies"]:
            raise InvalidTaskDependencyError(f"Task {task_id} cannot depend on itself")

        try:
            role = self.registry.get_role(handoff["assigned_agent"])
        except KeyError as exc:
            raise HandoffValidationError(str(exc)) from exc

        unknown_tools = [t for t in handoff["allowed_tools"] if t not in OFFICIAL_ANTIGRAVITY_TOOLS]
        if unknown_tools:
            raise HandoffValidationError(f"Task {task_id} specifies unknown tool(s): {unknown_tools}")

        role_allowed = set(role["allowed_tools"])
        disallowed_for_role = [t for t in handoff["allowed_tools"] if t not in role_allowed]
        if disallowed_for_role:
            raise HandoffValidationError(
                f"Task {task_id} grants tools {disallowed_for_role} outside {role['agent_id']} contract {sorted(role_allowed)}"
            )

        if role["read_only"] and handoff["owned_artifacts"]:
            raise ReadOnlyAgentOwnershipError(
                f"Read-only agent '{role['agent_id']}' cannot own writable artifacts: {handoff['owned_artifacts']}"
            )

        if set(handoff["input_artifacts"]) != set(handoff["input_artifact_hashes"].keys()):
            raise HandoffValidationError(
                f"Task {task_id} input_artifacts {handoff['input_artifacts']} must match keys of input_artifact_hashes"
            )

        overlap_io = set(handoff["input_artifacts"]) & set(handoff["owned_artifacts"])
        if role["read_only"] and overlap_io:
            raise ReadOnlyAgentOwnershipError(f"Read-only task {task_id} cannot write to input artifacts {overlap_io}")

        if handoff["retry_budget"]["attempts_used"] > handoff["retry_budget"]["max_attempts"]:
            raise HandoffValidationError(f"Task {task_id} attempts_used exceeds max_attempts")

        if enforce_devbox_workspace_mode and handoff["context"]["workspace_mode"] != "inherit":
            raise HandoffValidationError(
                f"Workspace mode '{handoff['context']['workspace_mode']}' is unsupported in remote devbox; must use 'inherit'."
            )

        return role

    def verify_input_artifacts_on_disk(
        self,
        handoff: dict[str, Any],
        *,
        base_dir: Path | None = None,
    ) -> dict[str, str]:
        """Verify every input artifact exists and matches its declared SHA-256 before task starts."""
        verified: dict[str, str] = {}
        for rel_path, expected_sha in handoff["input_artifact_hashes"].items():
            target = self._safe_resolve_repo_path(rel_path, base_dir=base_dir)
            if not target.is_file():
                raise UnverifiedInputArtifactError(f"Missing input artifact for {handoff['task_id']}: {rel_path}")
            actual_sha = compute_file_sha256(target)
            if actual_sha != expected_sha:
                raise UnverifiedInputArtifactError(
                    f"Input artifact SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
                )
            verified[rel_path] = actual_sha
        return verified

    def validate_task_dag_and_ownership(
        self,
        handoffs: list[dict[str, Any]],
        *,
        enforce_devbox_workspace_mode: bool = True,
    ) -> list[str]:
        """Validate a batch of task handoffs: schema, DAG acyclicity, readiness, and single-writer locks."""
        by_id: dict[str, dict[str, Any]] = {}
        for h in handoffs:
            self.validate_handoff(h, enforce_devbox_workspace_mode=enforce_devbox_workspace_mode)
            tid = h["task_id"]
            if tid in by_id:
                raise HandoffValidationError(f"Duplicate task_id '{tid}' in task graph")
            by_id[tid] = h

        # 1. Verify all dependencies exist & detect cycles via Kahn's topological sort
        in_degree: dict[str, int] = {tid: 0 for tid in by_id}
        dependents: dict[str, list[str]] = {tid: [] for tid in by_id}

        for tid, h in by_id.items():
            for dep in h["dependencies"]:
                if dep not in by_id:
                    raise InvalidTaskDependencyError(f"Task {tid} depends on unknown task '{dep}'")
                in_degree[tid] += 1
                dependents[dep].append(tid)

        queue = sorted([tid for tid, deg in in_degree.items() if deg == 0])
        topo_order: list[str] = []
        while queue:
            cur = queue.pop(0)
            topo_order.append(cur)
            for nxt in sorted(dependents[cur]):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(topo_order) != len(by_id):
            cyclic = sorted(set(by_id) - set(topo_order))
            raise InvalidTaskDependencyError(f"Cycle detected in task dependency DAG involving: {cyclic}")

        # 2. Verify no task is RUNNING/READY while an upstream dependency is incomplete
        for tid, h in by_id.items():
            if h["status"] in {"READY", "RUNNING"}:
                unmet = [dep for dep in h["dependencies"] if by_id[dep]["status"] != "COMPLETED"]
                if unmet:
                    raise InvalidTaskDependencyError(
                        f"Task {tid} has status={h['status']} before upstream dependencies completed: {unmet}"
                    )

        # 3. Verify exclusive single-owner artifact locks & per-role concurrency caps across active tasks
        artifact_owners: dict[str, str] = {}
        active_role_counts: dict[str, int] = {}

        for tid, h in by_id.items():
            if h["status"] in self.ACTIVE_CONCURRENT_STATES:
                aid = h["assigned_agent"]
                role = self.registry.get_role(aid)
                active_role_counts[aid] = active_role_counts.get(aid, 0) + 1
                if active_role_counts[aid] > int(role["max_concurrent_instances"]):
                    raise ParallelWriteConflictError(
                        f"Agent '{aid}' has {active_role_counts[aid]} concurrent active tasks "
                        f"(max_concurrent_instances={role['max_concurrent_instances']})"
                    )
                for art in h["owned_artifacts"]:
                    norm_art = Path(art).as_posix()
                    if norm_art in artifact_owners:
                        raise ParallelWriteConflictError(
                            f"Parallel write conflict on '{norm_art}' between active tasks "
                            f"'{artifact_owners[norm_art]}' and '{tid}'"
                        )
                    artifact_owners[norm_art] = tid

        return topo_order

    def verify_independent_review_pass(
        self,
        *,
        verifier_handoff: dict[str, Any],
        pre_review_hashes: dict[str, str],
        review_report: dict[str, Any],
        base_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Verify an Independent Verifier neither mutated producer files nor emitted an unstructured verdict."""
        role = self.validate_handoff(verifier_handoff)
        if role["department"] != "independent_verification_department" or not role["read_only"]:
            raise HandoffValidationError(
                f"Agent '{role['agent_id']}' is not an Independent Verification Department read-only reviewer"
            )

        # Confirm zero silent file modifications on every inspected artifact
        for rel_path, before_sha in pre_review_hashes.items():
            target = self._safe_resolve_repo_path(rel_path, base_dir=base_dir)
            if not target.is_file():
                raise SilentArtifactMutationError(f"Inspected artifact disappeared during review: {rel_path}")
            after_sha = compute_file_sha256(target)
            if after_sha != before_sha:
                raise SilentArtifactMutationError(
                    f"Silent artifact mutation detected on '{rel_path}' during independent review!"
                )

        for req in ("verifier_agent", "reviewed_task_id", "verdict", "defects", "checked_criteria"):
            if req not in review_report:
                raise HandoffValidationError(f"Independent review report missing field '{req}'")
        if review_report["verifier_agent"] != verifier_handoff["assigned_agent"]:
            raise HandoffValidationError("verifier_agent mismatch against verifier_handoff")
        if review_report["verdict"] not in {"PASS", "REVISION_REQUIRED", "BLOCKED"}:
            raise HandoffValidationError(f"Invalid review verdict: {review_report['verdict']}")
        if not isinstance(review_report["defects"], list):
            raise HandoffValidationError("defects must be a list")
        if review_report["verdict"] == "PASS" and review_report["defects"]:
            raise HandoffValidationError("Review verdict cannot be PASS when defects are non-empty")

        for defect in review_report["defects"]:
            for d_key in ("defect_id", "location", "severity", "expected_result", "observed_result", "responsible_agent"):
                if not defect.get(d_key):
                    raise HandoffValidationError(f"Defect entry missing required key '{d_key}'")

        return {
            "verified": True,
            "verifier_agent": review_report["verifier_agent"],
            "verdict": review_report["verdict"],
            "defect_count": len(review_report["defects"]),
            "artifacts_unchanged": len(pre_review_hashes),
        }
