"""Hardened 18-Field Agent Handoff Validator, Canonical Ownership Lock & Verifier Guard (Phase 01.6B).

Fixes all Phase 01.6A Independent Audit findings:
1. Canonical Artifact Ownership (`canonicalize_artifact_path`):
   - Resolves `.` / `..` / redundant slashes / symlinks via `os.path.realpath` so two distinct path
     strings pointing to the same physical file collide deterministically.
   - Rejects workspace escapes, symlink escapes (walking every path prefix component), duplicate
     canonical paths, project-boundary escapes (`projects/<project_id>/...`), and role-pattern mismatches.
2. Atomic Cross-Process Ownership Locking (`ArtifactOwnershipLockManager`):
   - Acquires OS-level `fcntl.flock(LOCK_EX | LOCK_NB)` keyed by SHA-256 of canonical file path,
     paired with in-process tracking and PID/TTL stale lock recovery after crashes.
3. Output Boundary & Execution-Time Re-Validation:
   - Enforces `expected_output.output_artifacts <= owned_artifacts`, input/output disjointness
     (unless explicit revision), and re-validates symlinks/boundaries/hashes at execution time.
4. Independent Verifier Integrity (`verify_independent_review_pass`):
   - Validates against `schemas/review_report.schema.json`.
   - Binds `reviewed_task_id` and `producer_agent` to `producer_handoff`, binds `reviewed_artifact_hashes`
     to 100% of producer `owned_artifacts`, enforces `required_criteria_ids` with substantive evidence,
     rejects empty hashes/criteria or false `PASS`, validates reviewer `invocation_receipt`, and
     verifies pre- vs post-review SHA-256 equality (`artifacts_unchanged >= 1`).
"""

from __future__ import annotations

import fcntl
import fnmatch
import hashlib
import json
import os
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

from orchestration.agent_registry import OFFICIAL_ANTIGRAVITY_TOOLS, AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


class HandoffValidationError(ValueError):
    """Base error for invalid structured agent task handoffs."""


class ArtifactBoundaryError(HandoffValidationError):
    """Raised when an input/output/owned path escapes workspace or project boundaries or via symlink."""


class DuplicateArtifactPathError(HandoffValidationError):
    """Raised when multiple path entries in a handoff resolve to the same canonical physical file."""


class InvalidArtifactOwnershipError(HandoffValidationError):
    """Raised when owned/output artifacts violate role ownership patterns or input/output alignment."""


class InvalidTaskDependencyError(HandoffValidationError):
    """Raised when task dependencies reference unknown tasks, self-loops, cycles, or incomplete upstream tasks."""


class ParallelWriteConflictError(HandoffValidationError):
    """Raised when two tasks/processes claim write ownership of the same canonical artifact or exceed role concurrency."""


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


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _matches_role_pattern(repo_rel_posix: str, pattern: str) -> bool:
    """Match canonical repo-relative POSIX path against role owned_artifact_patterns."""
    if fnmatch.fnmatchcase(repo_rel_posix, pattern):
        return True
    # Support nested paths under wildcard directory segments such as projects/*/scenes/*.json
    p_obj = PurePosixPath(repo_rel_posix)
    return p_obj.match(pattern)


@dataclass
class HeldArtifactLock:
    canonical_path: str
    lock_key: str
    task_id: str
    agent_id: str
    fd: int
    lock_file: Path
    meta_file: Path
    stale_recovered: bool = False


class ArtifactOwnershipLockManager:
    """Cross-process (`fcntl.flock`) + intra-process canonical file ownership lock manager."""

    _in_process_guard = threading.Lock()
    _in_process_held: dict[str, str] = {}  # canonical_path_str -> task_id

    def __init__(self, lock_dir: Path | None = None) -> None:
        self.lock_dir = (lock_dir or (ROOT_DIR / ".xdx_locks")).resolve()
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._handles_by_task: dict[str, list[HeldArtifactLock]] = {}

    @staticmethod
    def _key_for_canonical(canonical_path: Path) -> str:
        return hashlib.sha256(canonical_path.as_posix().encode("utf-8")).hexdigest()

    def acquire_for_task(
        self,
        *,
        task_id: str,
        agent_id: str,
        canonical_paths: list[Path],
        ttl_seconds: int = 300,
    ) -> list[HeldArtifactLock]:
        """Atomically acquire exclusive cross-process + intra-process locks on all canonical paths."""
        if not canonical_paths:
            return []
        unique_sorted = sorted({p.resolve(strict=False) for p in canonical_paths}, key=lambda p: p.as_posix())
        if len(unique_sorted) != len(canonical_paths):
            raise DuplicateArtifactPathError(f"Duplicate canonical paths passed to lock manager for {task_id}")

        acquired: list[HeldArtifactLock] = []
        now = time.time()
        hostname = socket.gethostname()

        try:
            for cpath in unique_sorted:
                c_str = cpath.as_posix()
                key = self._key_for_canonical(cpath)
                lock_file = self.lock_dir / f"{key}.lock"
                meta_file = self.lock_dir / f"{key}.meta.json"

                with self._in_process_guard:
                    existing_owner = self._in_process_held.get(c_str)
                    if existing_owner is not None and existing_owner != task_id:
                        raise ParallelWriteConflictError(
                            f"Intra-process write lock conflict on '{c_str}': already held by '{existing_owner}'"
                        )

                fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    os.close(fd)
                    holder_info = ""
                    if meta_file.is_file():
                        try:
                            m = json.loads(meta_file.read_text(encoding="utf-8"))
                            holder_info = f" (held by pid={m.get('pid')}, task={m.get('task_id')})"
                        except Exception:
                            holder_info = ""
                    raise ParallelWriteConflictError(
                        f"Cross-process write lock conflict on '{c_str}'{holder_info}"
                    ) from exc

                # We hold the OS flock! Inspect whether a stale metadata sidecar was left by a crashed process.
                stale_recovered = False
                if meta_file.is_file():
                    try:
                        prev_meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        prev_pid = int(prev_meta.get("pid", -1))
                        prev_exp = float(prev_meta.get("acquired_at_epoch", 0.0)) + float(
                            prev_meta.get("ttl_seconds", 0)
                        )
                        if prev_meta.get("released") is not True and (
                            not _is_pid_alive(prev_pid) or now >= prev_exp or prev_pid != os.getpid()
                        ):
                            stale_recovered = True
                    except Exception:
                        stale_recovered = True

                meta_payload = {
                    "canonical_path": c_str,
                    "lock_key": key,
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "pid": os.getpid(),
                    "hostname": hostname,
                    "acquired_at_epoch": now,
                    "ttl_seconds": ttl_seconds,
                    "stale_recovered": stale_recovered,
                    "released": False,
                }
                tmp_meta = self.lock_dir / f"{key}.{os.getpid()}.tmp"
                tmp_meta.write_text(json.dumps(meta_payload, indent=2) + "\n", encoding="utf-8")
                os.replace(tmp_meta, meta_file)

                with self._in_process_guard:
                    self._in_process_held[c_str] = task_id

                acquired.append(
                    HeldArtifactLock(
                        canonical_path=c_str,
                        lock_key=key,
                        task_id=task_id,
                        agent_id=agent_id,
                        fd=fd,
                        lock_file=lock_file,
                        meta_file=meta_file,
                        stale_recovered=stale_recovered,
                    )
                )
        except Exception:
            # Roll back any partial locks acquired before the failure
            for h in reversed(acquired):
                self._release_single(h)
            raise

        self._handles_by_task[task_id] = acquired
        return acquired

    def _release_single(self, handle: HeldArtifactLock) -> None:
        try:
            if handle.meta_file.is_file():
                meta = json.loads(handle.meta_file.read_text(encoding="utf-8"))
                if meta.get("pid") == os.getpid() and meta.get("task_id") == handle.task_id:
                    meta["released"] = True
                    meta["released_at_epoch"] = time.time()
                    handle.meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
        try:
            fcntl.flock(handle.fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(handle.fd)
            except OSError:
                pass
            with self._in_process_guard:
                if self._in_process_held.get(handle.canonical_path) == handle.task_id:
                    self._in_process_held.pop(handle.canonical_path, None)

    def release_for_task(self, task_id: str) -> int:
        handles = self._handles_by_task.pop(task_id, [])
        for h in reversed(handles):
            self._release_single(h)
        return len(handles)


class TaskHandoffManager:
    """Validates 18-field task contracts, canonical paths, project boundaries, locks, and independent reviews."""

    ACTIVE_CONCURRENT_STATES: frozenset[str] = frozenset({"READY", "RUNNING", "WAITING_REVIEW"})

    def __init__(
        self,
        root_dir: Path | None = None,
        registry: AgentRegistry | None = None,
        lock_dir: Path | None = None,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.registry = registry or AgentRegistry(root_dir=self.root_dir)
        self.lock_manager = ArtifactOwnershipLockManager(lock_dir=lock_dir or (self.root_dir / ".xdx_locks"))
        self._schema = json.loads(
            (self.root_dir / "schemas" / "task_handoff.schema.json").read_text(encoding="utf-8")
        )
        self._review_schema = json.loads(
            (self.root_dir / "schemas" / "review_report.schema.json").read_text(encoding="utf-8")
        )

    def canonicalize_artifact_path(
        self,
        raw_path: str,
        *,
        base_dir: Path | None = None,
        project_id: str | None = None,
        is_writable_output: bool = False,
        allow_audit_evidence_output: bool = False,
    ) -> Path:
        """Resolve canonical physical path and reject traversal, symlink escapes, and project boundary escapes."""
        if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
            raise ArtifactBoundaryError(f"Invalid empty or null-byte artifact path: {raw_path!r}")
        if raw_path.endswith(("/", "\\")):
            raise ArtifactBoundaryError(f"Artifact path must point to a file, not a directory: {raw_path!r}")

        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        cand_in = Path(raw_path)
        joined = cand_in if cand_in.is_absolute() else (ws_root / cand_in)

        # Lexical normalization prior to symlink walk to catch direct `..` escapes even before filesystem checks
        lexical_norm = Path(os.path.normpath(str(joined)))
        if not lexical_norm.is_relative_to(ws_root):
            raise ArtifactBoundaryError(
                f"Path traversal rejected: '{raw_path}' escapes workspace root '{ws_root}'"
            )

        # Walk every prefix component from workspace root down to target to detect any symlink escaping boundary
        rel_parts = lexical_norm.relative_to(ws_root).parts
        if not rel_parts:
            raise ArtifactBoundaryError(f"Artifact path cannot be workspace root itself: {raw_path!r}")

        allowed_write_roots: list[Path] = []
        if is_writable_output:
            if not project_id:
                raise ArtifactBoundaryError("project_id is required when validating writable output boundary")
            allowed_write_roots.append(Path(os.path.realpath(ws_root / "projects" / project_id)))
            if allow_audit_evidence_output:
                allowed_write_roots.append(Path(os.path.realpath(ws_root / "docs" / "evidence" / project_id)))
                allowed_write_roots.append(Path(os.path.realpath(ws_root / "docs" / "evidence")))

        probe = ws_root
        for part in rel_parts:
            probe = probe / part
            if os.path.islink(probe):
                link_real = Path(os.path.realpath(probe))
                if not link_real.is_relative_to(ws_root):
                    raise ArtifactBoundaryError(
                        f"Symlink escape rejected: '{probe}' points outside workspace to '{link_real}'"
                    )
                if is_writable_output and not any(link_real.is_relative_to(ar) for ar in allowed_write_roots):
                    raise ArtifactBoundaryError(
                        f"Symlink escape rejected: writable artifact '{probe}' points outside project boundary to '{link_real}'"
                    )

        canonical = Path(os.path.realpath(joined))
        if not canonical.is_relative_to(ws_root):
            raise ArtifactBoundaryError(
                f"Canonical path '{canonical}' for '{raw_path}' escapes workspace '{ws_root}'"
            )

        if is_writable_output:
            if not any(canonical.is_relative_to(ar) for ar in allowed_write_roots):
                raise ArtifactBoundaryError(
                    f"Output boundary violation: writable artifact '{raw_path}' -> '{canonical}' "
                    f"must reside inside projects/{project_id}/"
                )
            # Never allow writing inside .git, .agents, orchestration, governance, or reference_database
            rel_top = canonical.relative_to(ws_root).parts[0]
            if rel_top in {".git", ".agents", "orchestration", "governance", "reference_database", "schemas"}:
                raise ArtifactBoundaryError(
                    f"Protected directory write blocked for '{raw_path}' (target top-level='{rel_top}')"
                )

        return canonical

    def _canonicalize_list_unique(
        self,
        paths: list[str],
        *,
        field_name: str,
        base_dir: Path | None = None,
        project_id: str | None = None,
        is_writable_output: bool = False,
        allow_audit_evidence_output: bool = False,
    ) -> list[Path]:
        seen: dict[str, str] = {}
        out: list[Path] = []
        for raw in paths:
            cpath = self.canonicalize_artifact_path(
                raw,
                base_dir=base_dir,
                project_id=project_id,
                is_writable_output=is_writable_output,
                allow_audit_evidence_output=allow_audit_evidence_output,
            )
            key = cpath.as_posix()
            if key in seen:
                raise DuplicateArtifactPathError(
                    f"Duplicate canonical artifact path in '{field_name}': '{raw}' and '{seen[key]}' both resolve to '{key}'"
                )
            seen[key] = raw
            out.append(cpath)
        return out

    def validate_handoff(
        self,
        handoff: dict[str, Any],
        *,
        base_dir: Path | None = None,
        enforce_devbox_workspace_mode: bool = True,
    ) -> dict[str, Any]:
        """Validate a single 18-field task handoff contract against schema, canonical boundaries, and role contract."""
        try:
            jsonschema.validate(instance=handoff, schema=self._schema)
        except jsonschema.ValidationError as exc:
            raise HandoffValidationError(f"Task handoff schema violation: {exc.message}") from exc

        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        task_id = handoff["task_id"]
        project_id = handoff["project_id"]
        ctx = handoff["context"]
        allow_audit_ev = bool(ctx.get("allow_audit_evidence_output", False))
        allow_in_place_rev = bool(ctx.get("allow_in_place_revision", False))

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

        if role["read_only"] and (handoff["owned_artifacts"] or handoff["expected_output"]["output_artifacts"]):
            raise ReadOnlyAgentOwnershipError(
                f"Read-only agent '{role['agent_id']}' cannot own or output writable artifacts"
            )

        # Canonicalize input_artifacts & input_artifact_hashes and reject alias collisions
        canon_inputs = self._canonicalize_list_unique(
            handoff["input_artifacts"],
            field_name="input_artifacts",
            base_dir=ws_root,
            is_writable_output=False,
        )
        canon_hash_keys = self._canonicalize_list_unique(
            list(handoff["input_artifact_hashes"].keys()),
            field_name="input_artifact_hashes",
            base_dir=ws_root,
            is_writable_output=False,
        )
        if {p.as_posix() for p in canon_inputs} != {p.as_posix() for p in canon_hash_keys}:
            raise HandoffValidationError(
                f"Task {task_id} canonical input_artifacts do not match canonical input_artifact_hashes keys"
            )

        # Canonicalize owned_artifacts & expected_output.output_artifacts with strict project boundary checks
        canon_owned = self._canonicalize_list_unique(
            handoff["owned_artifacts"],
            field_name="owned_artifacts",
            base_dir=ws_root,
            project_id=project_id,
            is_writable_output=True,
            allow_audit_evidence_output=allow_audit_ev,
        )
        canon_outputs = self._canonicalize_list_unique(
            handoff["expected_output"]["output_artifacts"],
            field_name="expected_output.output_artifacts",
            base_dir=ws_root,
            project_id=project_id,
            is_writable_output=True,
            allow_audit_evidence_output=allow_audit_ev,
        )

        owned_set = {p.as_posix() for p in canon_owned}
        output_set = {p.as_posix() for p in canon_outputs}
        if not output_set.issubset(owned_set):
            unowned = sorted(output_set - owned_set)
            raise InvalidArtifactOwnershipError(
                f"Task {task_id} expected_output.output_artifacts contains path(s) not declared in owned_artifacts: {unowned}"
            )
        if owned_set and not output_set:
            raise InvalidArtifactOwnershipError(
                f"Task {task_id} declares owned_artifacts but expected_output.output_artifacts is empty"
            )

        # Check input vs owned/output overlap
        io_overlap = {p.as_posix() for p in canon_inputs} & owned_set
        if io_overlap and not allow_in_place_rev:
            raise InvalidArtifactOwnershipError(
                f"Task {task_id} has conflicting input and owned artifact(s) without allow_in_place_revision: {sorted(io_overlap)}"
            )

        # Validate owned_artifacts against role["owned_artifact_patterns"]
        patterns = list(role.get("owned_artifact_patterns", []))
        for cpath in canon_owned:
            rel_posix = cpath.relative_to(ws_root).as_posix()
            if allow_audit_ev and rel_posix.startswith("docs/evidence/"):
                continue
            if not any(_matches_role_pattern(rel_posix, pat) for pat in patterns):
                raise InvalidArtifactOwnershipError(
                    f"Artifact '{rel_posix}' does not match role '{role['agent_id']}' allowed patterns {patterns}"
                )

        if handoff["retry_budget"]["attempts_used"] > handoff["retry_budget"]["max_attempts"]:
            raise HandoffValidationError(f"Task {task_id} attempts_used exceeds max_attempts")

        if enforce_devbox_workspace_mode and ctx["workspace_mode"] != "inherit":
            raise HandoffValidationError(
                f"Workspace mode '{ctx['workspace_mode']}' is unsupported in remote devbox; must use 'inherit'."
            )

        return role

    def canonical_owned_paths(
        self,
        handoff: dict[str, Any],
        *,
        base_dir: Path | None = None,
    ) -> list[Path]:
        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        allow_audit_ev = bool(handoff.get("context", {}).get("allow_audit_evidence_output", False))
        return self._canonicalize_list_unique(
            handoff["owned_artifacts"],
            field_name="owned_artifacts",
            base_dir=ws_root,
            project_id=handoff["project_id"],
            is_writable_output=True,
            allow_audit_evidence_output=allow_audit_ev,
        )

    def verify_input_artifacts_on_disk(
        self,
        handoff: dict[str, Any],
        *,
        base_dir: Path | None = None,
    ) -> dict[str, str]:
        """Verify every input artifact resolves safely inside workspace, exists, and matches its SHA-256."""
        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        verified: dict[str, str] = {}
        for rel_path, expected_sha in handoff["input_artifact_hashes"].items():
            target = self.canonicalize_artifact_path(rel_path, base_dir=ws_root, is_writable_output=False)
            if not target.is_file():
                raise UnverifiedInputArtifactError(f"Missing input artifact for {handoff['task_id']}: {rel_path}")
            actual_sha = compute_file_sha256(target)
            if actual_sha != expected_sha:
                raise UnverifiedInputArtifactError(
                    f"Input artifact SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
                )
            verified[target.relative_to(ws_root).as_posix()] = actual_sha
        return verified

    def revalidate_at_execution_boundary(
        self,
        handoff: dict[str, Any],
        *,
        base_dir: Path | None = None,
        acquire_locks: bool = True,
    ) -> tuple[dict[str, str], list[HeldArtifactLock]]:
        """Re-verify schema, symlinks, output boundaries, input SHA-256s, and acquire fcntl locks right before execution."""
        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        self.validate_handoff(handoff, base_dir=ws_root)
        verified_inputs = self.verify_input_artifacts_on_disk(handoff, base_dir=ws_root)
        canon_owned = self.canonical_owned_paths(handoff, base_dir=ws_root)
        locks: list[HeldArtifactLock] = []
        if acquire_locks and canon_owned:
            locks = self.lock_manager.acquire_for_task(
                task_id=handoff["task_id"],
                agent_id=handoff["assigned_agent"],
                canonical_paths=canon_owned,
                ttl_seconds=int(handoff["retry_budget"]["timeout_seconds"]),
            )
        return verified_inputs, locks

    def validate_task_dag_and_ownership(
        self,
        handoffs: list[dict[str, Any]],
        *,
        base_dir: Path | None = None,
        enforce_devbox_workspace_mode: bool = True,
    ) -> list[str]:
        """Validate a batch of task handoffs: schema, DAG acyclicity, readiness, and CANONICAL single-writer locks."""
        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        by_id: dict[str, dict[str, Any]] = {}
        canon_owned_by_tid: dict[str, list[Path]] = {}

        for h in handoffs:
            self.validate_handoff(
                h,
                base_dir=ws_root,
                enforce_devbox_workspace_mode=enforce_devbox_workspace_mode,
            )
            tid = h["task_id"]
            if tid in by_id:
                raise HandoffValidationError(f"Duplicate task_id '{tid}' in task graph")
            by_id[tid] = h
            canon_owned_by_tid[tid] = self.canonical_owned_paths(h, base_dir=ws_root)

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

        # 3. Verify exclusive single-owner locks on CANONICAL RESOLVED PATHS & role concurrency caps
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
                for cpath in canon_owned_by_tid[tid]:
                    canon_key = cpath.as_posix()
                    if canon_key in artifact_owners:
                        raise ParallelWriteConflictError(
                            f"Canonical parallel write conflict on '{canon_key}' between active tasks "
                            f"'{artifact_owners[canon_key]}' and '{tid}'"
                        )
                    artifact_owners[canon_key] = tid

        return topo_order

    def verify_independent_review_pass(
        self,
        *,
        verifier_handoff: dict[str, Any],
        producer_handoff: dict[str, Any],
        pre_review_hashes: dict[str, str],
        review_report: dict[str, Any],
        required_criteria_ids: list[str] | None = None,
        producer_conversation_id: str | None = None,
        base_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Fail-closed verification of an Independent Verifier pass (Phase 01.6B hardened)."""
        ws_root = Path(os.path.realpath(base_dir or self.root_dir))
        v_role = self.validate_handoff(verifier_handoff, base_dir=ws_root)
        self.validate_handoff(producer_handoff, base_dir=ws_root)

        if v_role["department"] != "independent_verification_department" or not v_role["read_only"]:
            raise HandoffValidationError(
                f"Agent '{v_role['agent_id']}' is not an Independent Verification Department read-only reviewer"
            )

        # 1. Validate review_report strictly against review_report.schema.json
        try:
            jsonschema.validate(instance=review_report, schema=self._review_schema)
        except jsonschema.ValidationError as exc:
            raise HandoffValidationError(f"Review report schema violation: {exc.message}") from exc

        # 2. Producer & Verifier task/identity binding
        if review_report["project_id"] != producer_handoff["project_id"] or review_report["project_id"] != verifier_handoff["project_id"]:
            raise HandoffValidationError("Review report project_id mismatch against producer/verifier handoffs")
        if review_report["verifier_agent"] != verifier_handoff["assigned_agent"]:
            raise HandoffValidationError("verifier_agent mismatch against verifier_handoff")
        if review_report["reviewed_task_id"] != producer_handoff["task_id"]:
            raise HandoffValidationError(
                f"Mismatched reviewed_task_id: '{review_report['reviewed_task_id']}' != producer '{producer_handoff['task_id']}'"
            )
        if review_report["producer_agent"] != producer_handoff["assigned_agent"]:
            raise HandoffValidationError(
                f"Mismatched producer_agent: '{review_report['producer_agent']}' != '{producer_handoff['assigned_agent']}'"
            )
        if producer_handoff["assigned_agent"] == verifier_handoff["assigned_agent"]:
            raise HandoffValidationError("Self-review forbidden: producer and verifier agents must differ")
        if producer_handoff["task_id"] not in verifier_handoff["dependencies"]:
            raise HandoffValidationError(
                f"Verifier task '{verifier_handoff['task_id']}' must declare producer '{producer_handoff['task_id']}' in dependencies"
            )

        # 3. Validate reviewer runtime invocation receipt (never rely on fresh_context_confirmed boolean alone!)
        receipt = review_report["invocation_receipt"]
        if receipt["agent_id"] != verifier_handoff["assigned_agent"] or receipt.get("actually_invoked") is not True:
            raise HandoffValidationError("Invalid reviewer invocation_receipt: agent mismatch or not actually invoked")
        if receipt["execution_mode"] == "native_subagent":
            conv_id = (receipt.get("conversation_id") or "").strip()
            if len(conv_id) < 8:
                raise HandoffValidationError(
                    "native_subagent review requires a valid runtime conversation_id in invocation_receipt"
                )
            if producer_conversation_id and conv_id == producer_conversation_id:
                raise HandoffValidationError(
                    "Independent review context violation: verifier conversation_id equals producer conversation_id!"
                )

        # 4. Validate non-empty pre_review_hashes & full coverage of ALL producer owned/output artifacts
        if not pre_review_hashes:
            raise HandoffValidationError("Empty pre_review_hashes rejected; at least one artifact must be verified")

        canon_pre: dict[str, str] = {}
        for raw_p, sha in pre_review_hashes.items():
            cp = self.canonicalize_artifact_path(raw_p, base_dir=ws_root, is_writable_output=False)
            key = cp.as_posix()
            if key in canon_pre:
                raise DuplicateArtifactPathError(f"Duplicate canonical path in pre_review_hashes: {raw_p}")
            canon_pre[key] = sha

        canon_report_hashes: dict[str, str] = {}
        for raw_p, sha in review_report["reviewed_artifact_hashes"].items():
            cp = self.canonicalize_artifact_path(raw_p, base_dir=ws_root, is_writable_output=False)
            key = cp.as_posix()
            if key in canon_report_hashes:
                raise DuplicateArtifactPathError(f"Duplicate canonical path in reviewed_artifact_hashes: {raw_p}")
            canon_report_hashes[key] = sha

        producer_owned_canon = {p.as_posix() for p in self.canonical_owned_paths(producer_handoff, base_dir=ws_root)}
        if not producer_owned_canon:
            raise HandoffValidationError("Producer handoff has zero owned_artifacts to bind review against")

        missing_in_pre = sorted(producer_owned_canon - set(canon_pre.keys()))
        missing_in_report = sorted(producer_owned_canon - set(canon_report_hashes.keys()))
        if missing_in_pre or missing_in_report:
            raise HandoffValidationError(
                f"Incomplete artifact hash manifest: missing producer artifacts pre={missing_in_pre}, report={missing_in_report}"
            )

        for c_key, expected_pre_sha in canon_pre.items():
            if canon_report_hashes.get(c_key) and canon_report_hashes[c_key] != expected_pre_sha:
                raise HandoffValidationError(
                    f"Reviewed hash mismatch in report for '{c_key}': {canon_report_hashes[c_key]} != {expected_pre_sha}"
                )

        # 5. Full pre-review vs post-review disk SHA-256 comparison (blocks silent edits!)
        for c_key, before_sha in canon_pre.items():
            target = Path(c_key)
            if not target.is_file():
                raise SilentArtifactMutationError(f"Inspected artifact disappeared during review: {c_key}")
            after_sha = compute_file_sha256(target)
            if after_sha != before_sha:
                raise SilentArtifactMutationError(
                    f"Silent artifact mutation detected on '{c_key}' during independent review!"
                )

        # 6. Validate mandatory criteria manifest & reject false PASS
        effective_required = list(
            dict.fromkeys([*(required_criteria_ids or []), *review_report["required_criteria_ids"]])
        )
        if not effective_required:
            raise HandoffValidationError("required_criteria_ids cannot be empty")

        checked_by_id: dict[str, dict[str, Any]] = {}
        for item in review_report["checked_criteria"]:
            cid = item["criterion_id"]
            if cid in checked_by_id:
                raise HandoffValidationError(f"Duplicate criterion_id '{cid}' in checked_criteria")
            if len(item["evidence"].strip()) < 15:
                raise HandoffValidationError(f"Insufficient evidence on criterion '{cid}'")
            checked_by_id[cid] = item

        missing_criteria = [cid for cid in effective_required if cid not in checked_by_id]
        if missing_criteria:
            raise HandoffValidationError(f"Missing mandatory review criteria: {missing_criteria}")

        failed_criteria = [cid for cid, c in checked_by_id.items() if c["status"] != "PASS"]
        if review_report["verdict"] == "PASS":
            if failed_criteria:
                raise HandoffValidationError(
                    f"False PASS rejected: criteria failed {failed_criteria} while verdict='PASS'"
                )
            if review_report["defects"]:
                raise HandoffValidationError("False PASS rejected: defects list is non-empty")

        assert len(canon_pre) >= 1
        return {
            "verified": True,
            "review_id": review_report["review_id"],
            "reviewed_task_id": producer_handoff["task_id"],
            "producer_agent": producer_handoff["assigned_agent"],
            "verifier_agent": review_report["verifier_agent"],
            "verdict": review_report["verdict"],
            "defect_count": len(review_report["defects"]),
            "criteria_verified_count": len(checked_by_id),
            "artifacts_unchanged": len(canon_pre),
            "execution_mode": receipt["execution_mode"],
        }
