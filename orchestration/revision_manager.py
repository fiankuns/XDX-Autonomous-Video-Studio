"""Non-Destructive Artifact Revision, Downstream Invalidation & Re-Approval Guard (Phase 01.6B).

Implements Section 10 requirements:
1. Archives previous versions non-destructively inside `projects/<project_id>/.revisions/` before
   committing any revised artifact.
2. Computes exact `previous_digest` and `new_digest` (SHA-256), binds `task_owner`, computes
   transitive `affected_downstream_tasks` across the task graph, and lists `required_revalidation`.
3. Appends an immutable audit entry to `projects/<project_id>/.revisions/revision_history.json`
   and `SixPartitionMemoryStore` (`ProjectMemory` + `ExecutionMemory`).
4. Enforces mandatory approval invalidation (`approved=False`, `revoked=True`, and transitioning
   `SharedProjectStateMachine` to `WAITING_REAPPROVAL`) whenever `narration_dialogue.json`,
   `caption_audio_plan.json`, `storyboard.json`, `research_report.json`, `asset_manifest.json`,
   or any approved package artifact changes!
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json

from memory.persistent_memory import SixPartitionMemoryStore
from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256
from orchestration.shared_state import POST_APPROVAL_PRODUCTION_STATES, SharedProjectStateMachine

ROOT_DIR = Path(__file__).resolve().parent.parent

APPROVAL_SENSITIVE_FILENAMES: frozenset[str] = frozenset(
    {
        "narration_dialogue.json",
        "caption_audio_plan.json",
        "storyboard.json",
        "research_report.json",
        "production_blueprint.json",
        "character_bible.json",
        "style_bible.json",
        "asset_manifest.json",
        "engine_routing_plan.json",
        "preproduction_package.json",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RevisionManager:
    """Applies non-destructive versioned revisions, invalidates downstream tasks, and revokes stale approvals."""

    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        handoff_manager: TaskHandoffManager | None = None,
        memory_store: SixPartitionMemoryStore | None = None,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.handoff_manager = handoff_manager or TaskHandoffManager(root_dir=self.root_dir)
        self.memory_store = memory_store

    @staticmethod
    def compute_affected_downstream_tasks(
        *,
        owner_task_id: str,
        changed_rel_posix: str,
        task_definitions: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Find all tasks transitively depending on `owner_task_id` or consuming `changed_rel_posix`."""
        direct_consumers: set[str] = set()
        dependents_map: dict[str, list[str]] = {tid: [] for tid in task_definitions}

        for tid, h in task_definitions.items():
            for dep in h.get("dependencies", []):
                if dep in dependents_map:
                    dependents_map[dep].append(tid)
                if dep == owner_task_id:
                    direct_consumers.add(tid)
            for inp in h.get("input_artifacts", []):
                if inp.strip("./") == changed_rel_posix or inp.endswith(f"/{Path(changed_rel_posix).name}"):
                    if tid != owner_task_id:
                        direct_consumers.add(tid)

        visited = set(direct_consumers)
        queue = list(direct_consumers)
        while queue:
            cur = queue.pop(0)
            for nxt in dependents_map.get(cur, []):
                if nxt not in visited and nxt != owner_task_id:
                    visited.add(nxt)
                    queue.append(nxt)
        return sorted(visited)

    def apply_revision(
        self,
        *,
        project_id: str,
        artifact_relpath: str,
        new_content_bytes: bytes,
        task_owner: str,
        owner_agent: str,
        reason: str,
        task_definitions: dict[str, dict[str, Any]],
        state_machine: SharedProjectStateMachine | None = None,
        package_covered_artifacts: set[str] | None = None,
    ) -> dict[str, Any]:
        """Archive old file version, write new version atomically, compute downstream invalidation & revoke approval."""
        if not reason.strip():
            raise ValueError("Revision reason must be non-empty")

        target_path = self.handoff_manager.canonicalize_artifact_path(
            artifact_relpath,
            base_dir=self.root_dir,
            project_id=project_id,
            is_writable_output=True,
        )
        rel_posix = target_path.relative_to(self.root_dir).as_posix()

        revisions_root = self.root_dir / "projects" / project_id / ".revisions"
        revisions_root.mkdir(parents=True, exist_ok=True)
        history_file = revisions_root / "revision_history.json"

        history: list[dict[str, Any]] = []
        if history_file.is_file():
            history = json.loads(history_file.read_text(encoding="utf-8"))

        rev_num = len(history) + 1
        revision_id = f"REV-{project_id}-{rev_num:04d}-{uuid.uuid4().hex[:6]}"
        archived_previous_relpath: str | None = None
        previous_digest: str | None = None

        if target_path.is_file():
            previous_digest = compute_file_sha256(target_path)
            archive_dest = revisions_root / revision_id / target_path.relative_to(
                self.root_dir / "projects" / project_id
            )
            archive_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_path, archive_dest)
            archived_previous_relpath = archive_dest.relative_to(self.root_dir).as_posix()

        # Write new revision atomically
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_path.parent / f".{target_path.name}.{os.getpid()}.rev.tmp"
        with tmp.open("wb") as f:
            f.write(new_content_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target_path)
        new_digest = compute_file_sha256(target_path)

        digest_changed = previous_digest != new_digest
        affected_downstream = (
            self.compute_affected_downstream_tasks(
                owner_task_id=task_owner,
                changed_rel_posix=rel_posix,
                task_definitions=task_definitions,
            )
            if digest_changed
            else []
        )

        # Determine required revalidation gates
        required_revalidation: list[str] = []
        if digest_changed:
            required_revalidation.append("preproduction_verifier")
            fname = target_path.name
            if fname in {"narration_dialogue.json", "caption_audio_plan.json"}:
                required_revalidation.extend(["audio_director", "caption_specialist", "human_approval_gate"])
            elif fname in APPROVAL_SENSITIVE_FILENAMES or (
                package_covered_artifacts and rel_posix in package_covered_artifacts
            ):
                required_revalidation.append("human_approval_gate")
        required_revalidation = list(dict.fromkeys(required_revalidation))

        # Enforce mandatory approval invalidation if digest changed on approval-covered artifact
        approval_invalidated = False
        is_approval_covered = (
            target_path.name in APPROVAL_SENSITIVE_FILENAMES
            or (package_covered_artifacts is not None and rel_posix in package_covered_artifacts)
        )
        if digest_changed and is_approval_covered and state_machine is not None:
            st_doc = state_machine.load()
            cur_state = st_doc["current_state"]
            was_approved = bool(st_doc["approval_status"].get("approved", False))
            if was_approved or cur_state == "APPROVED" or cur_state in POST_APPROVAL_PRODUCTION_STATES:
                state_machine.transition(
                    "WAITING_REAPPROVAL",
                    expected_version=int(st_doc["state_version"]),
                    trigger=f"revision:{revision_id}",
                    actor=owner_agent,
                    task_id=task_owner,
                    evidence=f"Artifact '{rel_posix}' revised ({previous_digest} -> {new_digest}); re-approval mandatory",
                )
                approval_invalidated = True
            elif cur_state == "WAITING_APPROVAL":
                state_machine.transition(
                    "REVISION_REQUIRED",
                    expected_version=int(st_doc["state_version"]),
                    trigger=f"revision:{revision_id}",
                    actor=owner_agent,
                    task_id=task_owner,
                    evidence=f"Artifact '{rel_posix}' revised prior to approval; pre-production QC required",
                )
                approval_invalidated = True

        entry = {
            "revision_id": revision_id,
            "revision_number": rev_num,
            "project_id": project_id,
            "artifact_path": rel_posix,
            "archived_previous_path": archived_previous_relpath,
            "previous_digest": previous_digest,
            "new_digest": new_digest,
            "digest_changed": digest_changed,
            "task_owner": task_owner,
            "owner_agent": owner_agent,
            "reason": reason.strip(),
            "affected_downstream_tasks": affected_downstream,
            "required_revalidation": required_revalidation,
            "approval_invalidated": approval_invalidated,
            "timestamp_utc": _utc_now_iso(),
        }
        history.append(entry)
        history_tmp = history_file.with_suffix(".tmp")
        history_tmp.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        os.replace(history_tmp, history_file)

        if self.memory_store is not None:
            self.memory_store.project.put_slot(project_id, f"revision:{rel_posix}", entry)
            self.memory_store.execution.append_record(
                project_id=project_id,
                record_kind="artifact_revision",
                record_id=revision_id,
                payload=entry,
            )

        return entry
