"""26-State Explicit v4.0 Shared Project State Machine (Phase 01.6B).

Implements Section 6 requirements:
1. Full 26-state v4.0 graph (16 primary linear states + 10 auxiliary/exception states).
2. Optimistic concurrency (`expected_version`) + cross-process `fcntl.flock` preventing lost updates.
3. Strict separation of `ProjectState` (`SharedProjectStateMachine`) vs `TaskState` (`TASK_STATES`).
4. Every transition records: `previous_state`, `next_state`, `trigger`, `actor`, `task_id`,
   `evidence`, `timestamp`, `state_version`, and `artifact_manifest`.
5. Blocks direct agent self-transitions into `APPROVED` or `COMPLETED` without required gate
   evidence, and NEVER auto-grants `APPROVED` upon `LANJUTKAN_PROJECT` / checkpoint recovery.
6. Preserves bidirectional compatibility with v3.4 `ProjectStateManager`.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.state_and_approval import InvalidStateTransitionError

PRIMARY_STATES_V4: tuple[str, ...] = (
    "IDLE",
    "REQUEST_RECEIVED",
    "RESEARCHING",
    "REFERENCE_ANALYSIS",
    "CREATIVE_DEVELOPMENT",
    "STORYBOARDING",
    "PREPRODUCTION_QC",
    "WAITING_APPROVAL",
    "APPROVED",
    "ASSET_PRODUCTION",
    "ANIMATING",
    "RENDERING",
    "POST_PRODUCTION",
    "TECHNICAL_QC",
    "VISUAL_QC",
    "COMPLETED",
)

AUXILIARY_STATES_V4: tuple[str, ...] = (
    "CREATIVE_PAYLOAD_REQUIRED",
    "REFERENCE_UNAVAILABLE",
    "WAITING_RESOURCE",
    "WAITING_CONNECTION",
    "WAITING_REAPPROVAL",
    "REVISION_REQUIRED",
    "PAUSED",
    "FAILED",
    "CANCELLED",
    "BLOCKED",
)

ALL_26_PROJECT_STATES_V4: frozenset[str] = frozenset((*PRIMARY_STATES_V4, *AUXILIARY_STATES_V4))
assert len(ALL_26_PROJECT_STATES_V4) == 26

TASK_STATES_V4: frozenset[str] = frozenset(
    {
        "PENDING",
        "READY",
        "RUNNING",
        "WAITING_REVIEW",
        "REVISION_REQUIRED",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "CANCELLED",
    }
)

COMMON_INTERRUPTS: frozenset[str] = frozenset(
    {"PAUSED", "FAILED", "CANCELLED", "BLOCKED", "WAITING_RESOURCE", "WAITING_CONNECTION"}
)

ALLOWED_V4_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "IDLE": frozenset({"REQUEST_RECEIVED", "CANCELLED"}),
    "REQUEST_RECEIVED": frozenset(
        {"RESEARCHING", "REFERENCE_ANALYSIS", "CREATIVE_PAYLOAD_REQUIRED", *COMMON_INTERRUPTS}
    ),
    "RESEARCHING": frozenset({"REFERENCE_ANALYSIS", "CREATIVE_DEVELOPMENT", *COMMON_INTERRUPTS}),
    "REFERENCE_ANALYSIS": frozenset(
        {"RESEARCHING", "CREATIVE_DEVELOPMENT", "REFERENCE_UNAVAILABLE", *COMMON_INTERRUPTS}
    ),
    "REFERENCE_UNAVAILABLE": frozenset({"REFERENCE_ANALYSIS", "CREATIVE_DEVELOPMENT", "BLOCKED", "CANCELLED"}),
    "CREATIVE_DEVELOPMENT": frozenset(
        {"STORYBOARDING", "CREATIVE_PAYLOAD_REQUIRED", "REVISION_REQUIRED", *COMMON_INTERRUPTS}
    ),
    "CREATIVE_PAYLOAD_REQUIRED": frozenset({"CREATIVE_DEVELOPMENT", "CANCELLED", "BLOCKED"}),
    "STORYBOARDING": frozenset({"PREPRODUCTION_QC", "REVISION_REQUIRED", *COMMON_INTERRUPTS}),
    "PREPRODUCTION_QC": frozenset({"WAITING_APPROVAL", "REVISION_REQUIRED", *COMMON_INTERRUPTS}),
    "REVISION_REQUIRED": frozenset(
        {"RESEARCHING", "CREATIVE_DEVELOPMENT", "STORYBOARDING", "PREPRODUCTION_QC", *COMMON_INTERRUPTS}
    ),
    "WAITING_APPROVAL": frozenset({"APPROVED", "REVISION_REQUIRED", "PAUSED", "CANCELLED", "BLOCKED"}),
    "WAITING_REAPPROVAL": frozenset({"APPROVED", "REVISION_REQUIRED", "PAUSED", "CANCELLED", "BLOCKED"}),
    "APPROVED": frozenset({"ASSET_PRODUCTION", "WAITING_REAPPROVAL", *COMMON_INTERRUPTS}),
    "ASSET_PRODUCTION": frozenset({"ANIMATING", "WAITING_REAPPROVAL", *COMMON_INTERRUPTS}),
    "ANIMATING": frozenset({"RENDERING", "WAITING_REAPPROVAL", *COMMON_INTERRUPTS}),
    "RENDERING": frozenset({"POST_PRODUCTION", "WAITING_REAPPROVAL", *COMMON_INTERRUPTS}),
    "POST_PRODUCTION": frozenset({"TECHNICAL_QC", "WAITING_REAPPROVAL", *COMMON_INTERRUPTS}),
    "TECHNICAL_QC": frozenset({"VISUAL_QC", "REVISION_REQUIRED", "ANIMATING", "RENDERING", *COMMON_INTERRUPTS}),
    "VISUAL_QC": frozenset({"COMPLETED", "REVISION_REQUIRED", "ANIMATING", "RENDERING", *COMMON_INTERRUPTS}),
    "COMPLETED": frozenset({"WAITING_REAPPROVAL"}),
    "PAUSED": frozenset(
        {
            "REQUEST_RECEIVED",
            "RESEARCHING",
            "REFERENCE_ANALYSIS",
            "CREATIVE_DEVELOPMENT",
            "STORYBOARDING",
            "PREPRODUCTION_QC",
            "WAITING_APPROVAL",
            "WAITING_REAPPROVAL",
            "CANCELLED",
        }
    ),
    "WAITING_RESOURCE": frozenset(
        {"RESEARCHING", "ASSET_PRODUCTION", "ANIMATING", "RENDERING", "PAUSED", "BLOCKED", "CANCELLED"}
    ),
    "WAITING_CONNECTION": frozenset(
        {"ASSET_PRODUCTION", "ANIMATING", "RENDERING", "PAUSED", "BLOCKED", "CANCELLED"}
    ),
    "FAILED": frozenset({"REQUEST_RECEIVED", "REVISION_REQUIRED", "PAUSED", "CANCELLED", "BLOCKED"}),
    "BLOCKED": frozenset({"REQUEST_RECEIVED", "REVISION_REQUIRED", "WAITING_APPROVAL", "WAITING_REAPPROVAL", "CANCELLED"}),
    "CANCELLED": frozenset({"IDLE", "REQUEST_RECEIVED"}),
}

POST_APPROVAL_PRODUCTION_STATES: frozenset[str] = frozenset(
    {"ASSET_PRODUCTION", "ANIMATING", "RENDERING", "POST_PRODUCTION", "TECHNICAL_QC", "VISUAL_QC", "COMPLETED"}
)

V4_TO_V34_STATE_MAP: dict[str, str] = {
    "IDLE": "INIT",
    "REQUEST_RECEIVED": "INIT",
    "RESEARCHING": "TOPIC_RESEARCH",
    "REFERENCE_ANALYSIS": "REFERENCE_REVIEW",
    "CREATIVE_DEVELOPMENT": "BLUEPRINT",
    "CREATIVE_PAYLOAD_REQUIRED": "BLOCKED",
    "REFERENCE_UNAVAILABLE": "BLOCKED",
    "STORYBOARDING": "PREPRODUCTION",
    "PREPRODUCTION_QC": "PREPRODUCTION",
    "REVISION_REQUIRED": "PREPRODUCTION",
    "WAITING_APPROVAL": "WAITING_APPROVAL",
    "WAITING_REAPPROVAL": "WAITING_APPROVAL",
    "APPROVED": "APPROVED",
    "ASSET_PRODUCTION": "ASSET_PROCUREMENT",
    "ANIMATING": "ANIMATIC",
    "RENDERING": "SHOT_RENDER",
    "POST_PRODUCTION": "COMPOSITE",
    "TECHNICAL_QC": "QC",
    "VISUAL_QC": "QC",
    "COMPLETED": "DELIVERED",
    "WAITING_RESOURCE": "BLOCKED",
    "WAITING_CONNECTION": "BLOCKED",
    "PAUSED": "BLOCKED",
    "FAILED": "BLOCKED",
    "CANCELLED": "BLOCKED",
    "BLOCKED": "BLOCKED",
}


class StateVersionConflictError(RuntimeError):
    """Raised when optimistic concurrency `expected_version` does not match current persisted `state_version`."""


class ProductionApprovalFrozenError(InvalidStateTransitionError):
    """Raised prior to Phase 01.6D when any caller attempts to enter APPROVED or production states."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SharedProjectStateMachine:
    """Atomic, cross-process locked 26-state project state machine with Phase 01.6C production approval freeze."""

    def __init__(self, state_file: Path, *, allow_production_approval: bool = False) -> None:
        if allow_production_approval:
            raise ProductionApprovalFrozenError(
                "Boolean configuration cannot authorize production approval! "
                "Full Trusted Human Approval & Execution Guard are scheduled for Phase 01.6D."
            )
        self.state_file = Path(os.path.realpath(state_file))
        self.lock_file = self.state_file.with_suffix(".state.lock")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _with_exclusive_lock(self, fn: Any) -> Any:
        fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return fn()
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _write_atomic_unlocked(self, data: dict[str, Any]) -> None:
        tmp = self.state_file.parent / f".{self.state_file.name}.{os.getpid()}.tmp"
        payload = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        with tmp.open("wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.state_file)

    def initialize(
        self,
        *,
        project_id: str,
        project_title: str,
        genres: list[str],
        actor: str = "master_director",
    ) -> dict[str, Any]:
        def _init() -> dict[str, Any]:
            now = _utc_now_iso()
            doc = {
                "schema_version": "4.0.0-phase01.6c",
                "entity_kind": "project_state",
                "project_id": project_id,
                "project_title": project_title,
                "genres": list(genres),
                "current_state": "IDLE",
                "state_version": 1,
                "approval_status": {
                    "approved": False,
                    "approved_digest": None,
                    "approved_version": None,
                    "trusted_channel_verified": False,
                    "production_approval_frozen_until": "Phase 01.6D",
                    "revoked": False,
                },
                "artifact_manifest": {},
                "transitions": [
                    {
                        "previous_state": None,
                        "next_state": "IDLE",
                        "trigger": "project_initialized",
                        "actor": actor,
                        "task_id": None,
                        "evidence": "Initial project state created",
                        "timestamp": now,
                        "state_version": 1,
                        "artifact_manifest": {},
                    }
                ],
                "updated_at": now,
            }
            self._write_atomic_unlocked(doc)
            return doc

        return self._with_exclusive_lock(_init)

    def load(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            raise FileNotFoundError(f"Shared project state file not found: {self.state_file}")
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        if data.get("current_state") not in ALL_26_PROJECT_STATES_V4:
            raise ValueError(f"Corrupt or unrecognized v4 project state: {data.get('current_state')}")
        return data

    def transition(
        self,
        next_state: str,
        *,
        expected_version: int,
        trigger: str,
        actor: str,
        task_id: str | None = None,
        evidence: str,
        artifact_manifest: dict[str, str] | None = None,
        verified_human_approval: dict[str, Any] | None = None,
        verified_success_auditor_pass: bool = False,
    ) -> dict[str, Any]:
        if next_state in TASK_STATES_V4 and next_state not in ALL_26_PROJECT_STATES_V4:
            raise InvalidStateTransitionError(
                f"'{next_state}' is a TaskState, not a ProjectState! Keep task and project states separate."
            )
        if next_state not in ALL_26_PROJECT_STATES_V4:
            raise InvalidStateTransitionError(f"Unknown v4.0 project state '{next_state}'")
        if not trigger.strip() or not actor.strip() or not evidence.strip():
            raise ValueError("trigger, actor, and evidence must all be non-empty strings")

        def _do_transition() -> dict[str, Any]:
            doc = self.load()
            cur_ver = int(doc["state_version"])
            if cur_ver != int(expected_version):
                raise StateVersionConflictError(
                    f"Optimistic concurrency conflict on project '{doc['project_id']}': "
                    f"expected_version={expected_version}, actual state_version={cur_ver}"
                )

            prev = str(doc["current_state"])
            allowed = ALLOWED_V4_STATE_TRANSITIONS.get(prev, frozenset())
            if next_state not in allowed:
                raise InvalidStateTransitionError(
                    f"Illegal v4.0 state transition '{prev}' -> '{next_state}'. Allowed: {sorted(allowed)}"
                )

            # Phase 01.6C Section 4.F: Production Approval Freeze prior to Phase 01.6D!
            # Rejects actor labels ('trusted_human_approval_gate'), agent-crafted approval dicts,
            # invalid digests, trusted_channel_verified=False, and any transition to APPROVED or production!
            if next_state == "APPROVED":
                if actor != "trusted_human_approval_gate" or not verified_human_approval:
                    raise ProductionApprovalFrozenError(
                        "Agents cannot transition directly to 'APPROVED'; requires trusted_human_approval_gate "
                        "and production approval is frozen until Phase 01.6D."
                    )
                raise ProductionApprovalFrozenError(
                    "Production transition to 'APPROVED' is strictly frozen in Phase 01.6C! "
                    "Actor labels and agent-supplied approval dictionaries are not accepted as proof of "
                    "human identity prior to Phase 01.6D Trusted Human Approval & Execution Guard."
                )

            # Block direct COMPLETED without Success Auditor + freeze all post-approval production states
            if next_state == "COMPLETED":
                if actor != "success_auditor" or not verified_success_auditor_pass:
                    raise InvalidStateTransitionError(
                        "Cannot transition to 'COMPLETED' without verified 'success_auditor' sign-off."
                    )

            if next_state in POST_APPROVAL_PRODUCTION_STATES:
                raise ProductionApprovalFrozenError(
                    f"Production state '{next_state}' is strictly frozen prior to Phase 01.6D "
                    "(rendering, modeling, animation, and Blender mutations are prohibited in Phase 01.6C)."
                )

            # Invalidate approval automatically if entering WAITING_REAPPROVAL or REVISION_REQUIRED
            if next_state in {"WAITING_REAPPROVAL", "REVISION_REQUIRED"}:
                doc["approval_status"]["approved"] = False
                doc["approval_status"]["revoked"] = True

            new_ver = cur_ver + 1
            now = _utc_now_iso()
            merged_manifest = dict(doc.get("artifact_manifest", {}))
            if artifact_manifest is not None:
                merged_manifest = dict(sorted(artifact_manifest.items()))

            entry = {
                "previous_state": prev,
                "next_state": next_state,
                "trigger": trigger.strip(),
                "actor": actor.strip(),
                "task_id": task_id,
                "evidence": evidence.strip(),
                "timestamp": now,
                "state_version": new_ver,
                "artifact_manifest": merged_manifest,
            }
            doc["current_state"] = next_state
            doc["state_version"] = new_ver
            doc["artifact_manifest"] = merged_manifest
            doc["transitions"].append(entry)
            doc["updated_at"] = now
            self._write_atomic_unlocked(doc)
            return doc

        return self._with_exclusive_lock(_do_transition)

    def restore_after_interruption(
        self,
        *,
        expected_version: int,
        resume_target_state: str,
        actor: str = "master_director",
        evidence: str = "LANJUTKAN_PROJECT checkpoint recovery",
    ) -> dict[str, Any]:
        """Resume from PAUSED / WAITING_CONNECTION / WAITING_RESOURCE WITHOUT ever granting auto-approval."""
        if resume_target_state == "APPROVED" or resume_target_state in POST_APPROVAL_PRODUCTION_STATES:
            doc = self.load()
            if not doc["approval_status"].get("approved"):
                raise InvalidStateTransitionError(
                    f"LANJUTKAN_PROJECT cannot auto-approve or enter '{resume_target_state}' without prior valid approval"
                )
        return self.transition(
            resume_target_state,
            expected_version=expected_version,
            trigger="LANJUTKAN_PROJECT",
            actor=actor,
            evidence=evidence,
        )

    def export_v3_4_compatible_view(self) -> dict[str, Any]:
        """Project v4.0 26-state document onto v3.4 state vocabulary for backward compatibility."""
        doc = self.load()
        return {
            "project_id": doc["project_id"],
            "v4_state": doc["current_state"],
            "v3_4_compatible_state": V4_TO_V34_STATE_MAP[doc["current_state"]],
            "state_version": doc["state_version"],
            "approved": bool(doc["approval_status"]["approved"]),
            "updated_at": doc["updated_at"],
        }
