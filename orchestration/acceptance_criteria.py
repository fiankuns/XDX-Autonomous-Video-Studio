"""Deterministic Acceptance Criteria Engine & Check Handler Registry (Phase 01.6C).

Implements Section 4.B requirements:
1. Explicit check handler registry covering all 6 ``done_when`` ``check_type`` values in
   ``schemas/task_handoff.schema.json``:
   - ``file_exists_nonempty``
   - ``sha256_verified``
   - ``json_schema_valid``
   - ``pytest_pass``
   - ``no_unapproved_mutation``
   - ``independent_review_verdict``
2. Any unsupported or unregistered ``check_type`` raises ``UnsupportedAcceptanceCheckError`` so the
   scheduler transitions the task to ``BLOCKED`` instead of ignoring it.
3. Missing JSON schema targets or missing schema files are rejected deterministically.
4. Binds ``required_evidence`` and ``criterion_evidence`` to criterion IDs and inspected artifacts,
   rejecting unrelated filler strings and foreign task references.
5. Validates worker task/project/role identity and ``receipt.output_artifact_hashes`` against actual
   on-disk SHA-256 digests.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import jsonschema

from orchestration.handoff_manager import TaskHandoffManager, compute_file_sha256
from orchestration.native_execution_adapter import AgentExecutionResult

_SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_TASK_ID_TOKEN_RE = re.compile(r"\bTASK-[A-Za-z0-9_-]{3,48}\b")
_WORD_TOKEN_RE = re.compile(r"[a-zA-Z0-9_-]{4,}")

_GENERIC_EVIDENCE_FILLER_WORDS: frozenset[str] = frozenset(
    {
        "completed",
        "complete",
        "done",
        "valid",
        "validated",
        "verified",
        "verify",
        "verification",
        "output",
        "outputs",
        "evidence",
        "item",
        "items",
        "task",
        "tasks",
        "passed",
        "pass",
        "success",
        "succeeded",
        "successfully",
        "check",
        "checked",
        "file",
        "files",
        "test",
        "tests",
        "deterministic",
        "deterministically",
        "result",
        "results",
        "artifact",
        "artifacts",
        "with",
        "without",
        "from",
        "into",
        "this",
        "that",
        "have",
        "been",
        "were",
        "some",
        "lorem",
        "ipsum",
        "random",
        "unrelated",
        "generic",
        "placeholder",
    }
)


class AcceptanceCriteriaError(RuntimeError):
    """Base error for deterministic acceptance criteria failures."""


class UnsupportedAcceptanceCheckError(AcceptanceCriteriaError):
    """Raised when a done_when criterion specifies an unsupported/unregistered check_type (-> BLOCKED)."""

    def __init__(self, criterion_id: str, check_type: str) -> None:
        self.criterion_id = criterion_id
        self.check_type = check_type
        super().__init__(
            f"Unsupported acceptance check_type '{check_type}' on criterion '{criterion_id}' — task must be BLOCKED"
        )


class AcceptanceCheckFailedError(AcceptanceCriteriaError):
    """Raised when a supported deterministic acceptance check fails."""


class MissingSchemaTargetError(AcceptanceCheckFailedError):
    """Raised when json_schema_valid lacks a resolvable schema file or data target."""


class UnrelatedEvidenceError(AcceptanceCheckFailedError):
    """Raised when worker evidence items are generic filler, unrelated, or reference wrong task/hash."""


class WorkerIdentityMismatchError(AcceptanceCheckFailedError):
    """Raised when worker result or receipt task_id, project_id, or assigned_agent does not match handoff."""


class ReceiptOutputHashMismatchError(AcceptanceCheckFailedError):
    """Raised when receipt.output_artifact_hashes are missing or do not match actual disk SHA-256."""


CheckHandlerFn = Callable[
    [dict[str, Any], dict[str, Any], AgentExecutionResult, dict[str, Any]],
    dict[str, Any],
]


def snapshot_directory_hashes(root: Path, *, max_files: int = 2000) -> dict[str, str]:
    """Snapshot SHA-256 of regular files under ``root`` (excluding transient lock/cache dirs)."""
    excluded_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", ".xdx_locks", ".xdx_memory"}
    snaps: dict[str, str] = {}
    if root.is_file():
        snaps[root.as_posix()] = compute_file_sha256(root)
        return snaps
    if not root.is_dir():
        return snaps
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in excluded_dirs]
        for fname in sorted(filenames):
            if fname.endswith((".lock", ".tmp", ".pyc")):
                continue
            fpath = Path(os.path.realpath(os.path.join(dirpath, fname)))
            if fpath.is_file():
                snaps[fpath.as_posix()] = compute_file_sha256(fpath)
                count += 1
                if count >= max_files:
                    return snaps
    return snaps


class AcceptanceCriteriaEngine:
    """Evaluates all 6 deterministic check_types, receipt hashes, and criterion-bound evidence."""

    SUPPORTED_CHECK_TYPES: tuple[str, ...] = (
        "file_exists_nonempty",
        "sha256_verified",
        "json_schema_valid",
        "pytest_pass",
        "no_unapproved_mutation",
        "independent_review_verdict",
    )

    def __init__(
        self,
        *,
        root_dir: Path,
        handoff_manager: TaskHandoffManager,
        handlers: dict[str, CheckHandlerFn] | None = None,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir))
        self.handoff_manager = handoff_manager
        default_registry: dict[str, CheckHandlerFn] = {
            "file_exists_nonempty": self._check_file_exists_nonempty,
            "sha256_verified": self._check_sha256_verified,
            "json_schema_valid": self._check_json_schema_valid,
            "pytest_pass": self._check_pytest_pass,
            "no_unapproved_mutation": self._check_no_unapproved_mutation,
            "independent_review_verdict": self._check_independent_review_verdict,
        }
        self._handlers: dict[str, CheckHandlerFn] = dict(handlers) if handlers is not None else default_registry

    @property
    def registered_check_types(self) -> frozenset[str]:
        return frozenset(self._handlers.keys())

    def find_unsupported_checks(self, handoff: dict[str, Any]) -> list[tuple[str, str]]:
        unsupported: list[tuple[str, str]] = []
        for dw in handoff.get("done_when", []):
            cid = str(dw.get("criterion_id", "UNKNOWN"))
            ctype = str(dw.get("check_type", ""))
            if ctype not in self._handlers:
                unsupported.append((cid, ctype))
        return unsupported

    def verify_worker_identity_and_receipt_hashes(
        self,
        *,
        handoff: dict[str, Any],
        result: AgentExecutionResult,
    ) -> dict[str, str]:
        """Verify worker task/project/role identity and exact receipt output hashes on disk."""
        tid = handoff["task_id"]
        pid = handoff["project_id"]
        aid = handoff["assigned_agent"]

        if result.task_id != tid:
            raise WorkerIdentityMismatchError(
                f"Worker result task_id '{result.task_id}' does not match handoff task_id '{tid}'"
            )
        if result.project_id != pid:
            raise WorkerIdentityMismatchError(
                f"Worker result project_id '{result.project_id}' does not match handoff project_id '{pid}'"
            )
        if result.receipt.task_id != tid:
            raise WorkerIdentityMismatchError(
                f"Receipt task_id '{result.receipt.task_id}' does not match handoff task_id '{tid}'"
            )
        if result.receipt.project_id != pid:
            raise WorkerIdentityMismatchError(
                f"Receipt project_id '{result.receipt.project_id}' does not match handoff project_id '{pid}'"
            )
        if result.receipt.assigned_agent != aid:
            raise WorkerIdentityMismatchError(
                f"Receipt assigned_agent '{result.receipt.assigned_agent}' does not match '{aid}'"
            )

        verified_outputs: dict[str, str] = {}
        canon_owned = self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir)
        receipt_hashes_canon: dict[str, str] = {}
        for raw_rp, r_sha in result.receipt.output_artifact_hashes.items():
            cp = self.handoff_manager.canonicalize_artifact_path(
                raw_rp, base_dir=self.root_dir, is_writable_output=False
            )
            rel_k = cp.relative_to(self.root_dir).as_posix()
            receipt_hashes_canon[rel_k] = r_sha

        for cpath in canon_owned:
            if not cpath.is_file():
                raise AcceptanceCheckFailedError(
                    f"Worker claimed completion for '{tid}', but owned output '{cpath}' does not exist on disk!"
                )
            if cpath.stat().st_size == 0:
                raise AcceptanceCheckFailedError(
                    f"Worker claimed completion for '{tid}', but owned output '{cpath}' is 0 bytes!"
                )
            if cpath.suffix.lower() == ".json":
                try:
                    json.loads(cpath.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise AcceptanceCheckFailedError(
                        f"Owned JSON output '{cpath}' for '{tid}' is malformed: {exc}"
                    ) from exc

            rel_posix = cpath.relative_to(self.root_dir).as_posix()
            actual_sha = compute_file_sha256(cpath)
            if rel_posix not in receipt_hashes_canon:
                raise ReceiptOutputHashMismatchError(
                    f"Receipt for '{tid}' is missing output_artifact_hashes entry for owned output '{rel_posix}'"
                )
            if receipt_hashes_canon[rel_posix] != actual_sha:
                raise ReceiptOutputHashMismatchError(
                    f"Receipt output hash mismatch for '{rel_posix}' on '{tid}': "
                    f"receipt={receipt_hashes_canon[rel_posix]} vs disk={actual_sha}"
                )
            verified_outputs[rel_posix] = actual_sha

        extra_receipt_paths = sorted(set(receipt_hashes_canon.keys()) - set(verified_outputs.keys()))
        if extra_receipt_paths:
            raise ReceiptOutputHashMismatchError(
                f"Receipt for '{tid}' claims unowned output_artifact_hashes: {extra_receipt_paths}"
            )

        return verified_outputs

    def verify_bound_evidence(
        self,
        *,
        handoff: dict[str, Any],
        result: AgentExecutionResult,
        verified_outputs: dict[str, str],
        criterion_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Verify evidence is bound to criterion IDs and inspected artifacts — never count/length alone."""
        tid = handoff["task_id"]
        req_ev = handoff["required_evidence"]
        clean_ev = [e.strip() for e in result.evidence_items if isinstance(e, str) and e.strip()]
        if len(clean_ev) < len(req_ev):
            raise UnrelatedEvidenceError(
                f"Task '{tid}' insufficient evidence items: got {len(clean_ev)}, required {len(req_ev)}"
            )

        # Reject any foreign TASK-* reference inside evidence strings
        for ev_str in clean_ev:
            foreign_tasks = [m for m in _TASK_ID_TOKEN_RE.findall(ev_str) if m != tid]
            if foreign_tasks:
                raise UnrelatedEvidenceError(
                    f"Evidence item for '{tid}' references foreign task(s) {foreign_tasks}: {ev_str!r}"
                )

        # Build concrete task anchors: task_id, criterion_ids, artifact paths/basenames, SHA prefixes, domain terms
        criterion_ids = {dw["criterion_id"] for dw in handoff["done_when"]}
        artifact_tokens: set[str] = set()
        for raw_p in [
            *handoff.get("owned_artifacts", []),
            *handoff.get("input_artifacts", []),
            *(dw["target"].split("::")[0] for dw in handoff["done_when"]),
            *handoff.get("context", {}).get("reference_ids", []),
        ]:
            clean_p = raw_p.strip()
            if clean_p:
                artifact_tokens.add(clean_p.lower())
                artifact_tokens.add(Path(clean_p).name.lower())
                stem = Path(clean_p).stem.lower()
                if len(stem) >= 4:
                    artifact_tokens.add(stem)

        valid_sha_prefixes: set[str] = set()
        for sha in [
            *verified_outputs.values(),
            *handoff.get("input_artifact_hashes", {}).values(),
        ]:
            if len(sha) >= 8:
                valid_sha_prefixes.add(sha[:8].lower())
                valid_sha_prefixes.add(sha[:12].lower())
                valid_sha_prefixes.add(sha.lower())

        domain_vocab: set[str] = set()
        for text_src in [*req_ev, handoff.get("goal", ""), *(dw.get("description", "") for dw in handoff["done_when"])]:
            for tok in _WORD_TOKEN_RE.findall(text_src.lower()):
                if tok not in _GENERIC_EVIDENCE_FILLER_WORDS and tok != tid.lower():
                    domain_vocab.add(tok)

        for ev_str in clean_ev:
            ev_low = ev_str.lower()
            has_tid = tid.lower() in ev_low
            has_cid = any(cid.lower() in ev_low for cid in criterion_ids)
            has_art = any(at in ev_low for at in artifact_tokens if len(at) >= 4)
            has_sha = any(sp in ev_low for sp in valid_sha_prefixes)
            ev_tokens = {
                tok
                for tok in _WORD_TOKEN_RE.findall(ev_low)
                if tok not in _GENERIC_EVIDENCE_FILLER_WORDS
            }
            shared_domain = ev_tokens & domain_vocab
            has_domain_match = len(shared_domain) >= 2 or (len(domain_vocab) == 1 and len(shared_domain) == 1)

            if not (has_tid or has_cid or has_art or has_sha or has_domain_match):
                raise UnrelatedEvidenceError(
                    f"Unrelated or generic filler evidence rejected for '{tid}': {ev_str!r} "
                    "does not bind to criterion_id, inspected artifact, SHA-256, task_id, or required domain terms."
                )

        # Validate structured criterion_evidence map when provided
        crit_ev_in = dict(result.criterion_evidence or result.payload.get("criterion_evidence") or {})
        bound_map: dict[str, dict[str, Any]] = {}
        if crit_ev_in:
            unknown_cids = sorted(set(crit_ev_in.keys()) - criterion_ids)
            if unknown_cids:
                raise UnrelatedEvidenceError(
                    f"Structured criterion_evidence for '{tid}' references unknown criterion_id(s): {unknown_cids}"
                )
            for dw in handoff["done_when"]:
                cid = dw["criterion_id"]
                if cid not in crit_ev_in:
                    raise UnrelatedEvidenceError(
                        f"Structured criterion_evidence for '{tid}' is missing mandatory criterion '{cid}'"
                    )
                entry = crit_ev_in[cid]
                if entry.get("task_id") and entry["task_id"] != tid:
                    raise UnrelatedEvidenceError(
                        f"criterion_evidence['{cid}'] task_id '{entry.get('task_id')}' != '{tid}'"
                    )
                expected_sha = criterion_results.get(cid, {}).get("sha256")
                if expected_sha and entry.get("verified_sha256") and entry["verified_sha256"] != expected_sha:
                    raise UnrelatedEvidenceError(
                        f"criterion_evidence['{cid}'] SHA-256 '{entry['verified_sha256']}' != actual '{expected_sha}'"
                    )
                bound_map[cid] = {
                    **criterion_results.get(cid, {}),
                    "evidence_bound": True,
                }
        else:
            for cid, cinfo in criterion_results.items():
                bound_map[cid] = {**cinfo, "evidence_bound": True}

        return bound_map

    def evaluate_all(
        self,
        *,
        handoff: dict[str, Any],
        result: AgentExecutionResult,
        context_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Run worker identity, receipt output hash, all done_when handlers, and bound evidence checks."""
        # 1. Fail-closed check for unsupported check_types FIRST so task transitions to BLOCKED
        unsupported = self.find_unsupported_checks(handoff)
        if unsupported:
            cid, ctype = unsupported[0]
            raise UnsupportedAcceptanceCheckError(cid, ctype)

        # 2. Verify worker task/project/role identity & receipt output SHA-256s against actual files
        verified_outputs = self.verify_worker_identity_and_receipt_hashes(handoff=handoff, result=result)

        # 3. Execute registered handler for every done_when criterion
        exec_ctx = {**context_state, "verified_outputs": verified_outputs}
        criterion_results: dict[str, dict[str, Any]] = {}
        for dw in handoff["done_when"]:
            cid = dw["criterion_id"]
            ctype = dw["check_type"]
            handler = self._handlers.get(ctype)
            if handler is None:
                raise UnsupportedAcceptanceCheckError(cid, ctype)
            criterion_results[cid] = handler(handoff, dw, result, exec_ctx)

        # 4. Bind required_evidence & structured criterion_evidence against criteria and artifacts
        bound_evidence = self.verify_bound_evidence(
            handoff=handoff,
            result=result,
            verified_outputs=verified_outputs,
            criterion_results=criterion_results,
        )

        return {
            "verified_outputs": verified_outputs,
            "criterion_results": bound_evidence,
        }

    # ------------------------------------------------------------------
    # Six Deterministic Check Handlers
    # ------------------------------------------------------------------

    def _check_file_exists_nonempty(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        _result: AgentExecutionResult,
        _ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        target_raw = dw["target"]
        cpath = self.handoff_manager.canonicalize_artifact_path(
            target_raw, base_dir=self.root_dir, is_writable_output=False
        )
        if not cpath.is_file() or cpath.stat().st_size == 0:
            raise AcceptanceCheckFailedError(
                f"Task '{handoff['task_id']}' failed '{cid}' (file_exists_nonempty): '{target_raw}' missing or empty"
            )
        if cpath.suffix.lower() == ".json":
            try:
                json.loads(cpath.read_text(encoding="utf-8"))
            except Exception as exc:
                raise AcceptanceCheckFailedError(
                    f"Task '{handoff['task_id']}' failed '{cid}': malformed JSON at '{target_raw}': {exc}"
                ) from exc
        elif cpath.suffix.lower() in {".md", ".txt"}:
            if not cpath.read_text(encoding="utf-8").strip():
                raise AcceptanceCheckFailedError(
                    f"Task '{handoff['task_id']}' failed '{cid}': whitespace-only file at '{target_raw}'"
                )
        rel = cpath.relative_to(self.root_dir).as_posix()
        return {
            "criterion_id": cid,
            "check_type": "file_exists_nonempty",
            "target": rel,
            "sha256": compute_file_sha256(cpath),
            "size_bytes": cpath.stat().st_size,
        }

    def _check_sha256_verified(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        result: AgentExecutionResult,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        tid = handoff["task_id"]
        raw_target = dw["target"]
        explicit_expected: str | None = None
        if "::" in raw_target:
            file_part, explicit_expected = raw_target.split("::", 1)
            explicit_expected = explicit_expected.strip().lower()
        else:
            file_part = raw_target

        cpath = self.handoff_manager.canonicalize_artifact_path(
            file_part, base_dir=self.root_dir, is_writable_output=False
        )
        if not cpath.is_file():
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (sha256_verified): target '{file_part}' missing on disk"
            )
        rel = cpath.relative_to(self.root_dir).as_posix()
        actual_sha = compute_file_sha256(cpath)

        expected_map = handoff.get("context", {}).get("expected_sha256_map") or {}
        expected_sha = (
            explicit_expected
            or expected_map.get(file_part)
            or expected_map.get(rel)
            or handoff.get("input_artifact_hashes", {}).get(file_part)
            or handoff.get("input_artifact_hashes", {}).get(rel)
            or result.receipt.output_artifact_hashes.get(rel)
            or (ctx.get("artifact_sha256") or {}).get(rel)
        )
        if not expected_sha or not _SHA256_HEX_RE.match(str(expected_sha)):
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (sha256_verified): missing or invalid expected SHA-256 for '{rel}'"
            )
        if actual_sha != expected_sha:
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (sha256_verified): '{rel}' expected {expected_sha}, got {actual_sha}"
            )
        return {
            "criterion_id": cid,
            "check_type": "sha256_verified",
            "target": rel,
            "sha256": actual_sha,
        }

    def _resolve_json_schema_path(self, handoff: dict[str, Any], raw_target: str, file_rel: str) -> Path:
        schema_hint: str | None = None
        if "::" in raw_target:
            _, schema_hint = raw_target.split("::", 1)
            schema_hint = schema_hint.strip()
        if not schema_hint:
            schema_map = handoff.get("context", {}).get("schema_map") or {}
            schema_hint = schema_map.get(raw_target) or schema_map.get(file_rel)
        if not schema_hint:
            ret_schema = str(handoff.get("return_schema", "")).strip()
            if ret_schema.endswith(".json"):
                schema_hint = ret_schema
            elif (self.root_dir / "schemas" / f"{ret_schema}.schema.json").is_file():
                schema_hint = f"schemas/{ret_schema}.schema.json"

        if not schema_hint:
            raise MissingSchemaTargetError(
                f"Task '{handoff['task_id']}' json_schema_valid criterion for '{raw_target}' "
                "has no schema target (use 'data.json::schemas/x.schema.json', context.schema_map, or return_schema path)."
            )

        schema_path = self.handoff_manager.canonicalize_artifact_path(
            schema_hint, base_dir=self.root_dir, is_writable_output=False
        )
        if not schema_path.is_file():
            raise MissingSchemaTargetError(
                f"Task '{handoff['task_id']}' json_schema_valid schema file does not exist: '{schema_hint}'"
            )
        return schema_path

    def _check_json_schema_valid(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        _result: AgentExecutionResult,
        _ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        tid = handoff["task_id"]
        raw_target = dw["target"]
        data_part = raw_target.split("::", 1)[0].strip()
        if not data_part:
            raise MissingSchemaTargetError(f"Task '{tid}' failed '{cid}': empty JSON target")

        data_path = self.handoff_manager.canonicalize_artifact_path(
            data_part, base_dir=self.root_dir, is_writable_output=False
        )
        if not data_path.is_file():
            raise MissingSchemaTargetError(
                f"Task '{tid}' failed '{cid}' (json_schema_valid): JSON target '{data_part}' does not exist"
            )
        rel_data = data_path.relative_to(self.root_dir).as_posix()
        schema_path = self._resolve_json_schema_path(handoff, raw_target, rel_data)

        try:
            instance = json.loads(data_path.read_text(encoding="utf-8"))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(instance=instance, schema=schema)
        except Exception as exc:
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (json_schema_valid) on '{rel_data}' vs "
                f"'{schema_path.relative_to(self.root_dir).as_posix()}': {exc}"
            ) from exc

        return {
            "criterion_id": cid,
            "check_type": "json_schema_valid",
            "target": rel_data,
            "schema": schema_path.relative_to(self.root_dir).as_posix(),
            "sha256": compute_file_sha256(data_path),
        }

    def _check_pytest_pass(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        _result: AgentExecutionResult,
        _ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        tid = handoff["task_id"]
        raw_target = dw["target"].strip()
        if raw_target.startswith("-"):
            raise AcceptanceCheckFailedError(f"Task '{tid}' failed '{cid}': invalid pytest target flag '{raw_target}'")

        parts = raw_target.split("::")
        file_part = parts[0]
        test_file = self.handoff_manager.canonicalize_artifact_path(
            file_part, base_dir=self.root_dir, is_writable_output=False
        )
        tests_root = Path(os.path.realpath(self.root_dir / "tests"))
        if not test_file.is_relative_to(tests_root) or not test_file.is_file():
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (pytest_pass): target '{file_part}' must be an existing file inside tests/"
            )
        rel_file = test_file.relative_to(self.root_dir).as_posix()
        nodeid = "::".join([rel_file, *parts[1:]]) if len(parts) > 1 else rel_file

        timeout_s = min(180, max(10, int(handoff["retry_budget"]["timeout_seconds"])))
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=str(self.root_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0 or "passed" not in proc.stdout:
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (pytest_pass) for '{nodeid}' (rc={proc.returncode}): "
                f"{(proc.stdout + proc.stderr)[-400:]}"
            )
        return {
            "criterion_id": cid,
            "check_type": "pytest_pass",
            "target": nodeid,
            "sha256": compute_file_sha256(test_file),
        }

    def _check_no_unapproved_mutation(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        _result: AgentExecutionResult,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        tid = handoff["task_id"]
        raw_target = dw["target"].strip()
        owned_canon = {
            p.as_posix() for p in self.handoff_manager.canonical_owned_paths(handoff, base_dir=self.root_dir)
        }
        pre_snaps: dict[str, str] = dict(ctx.get("pre_execution_snapshots", {}).get(cid) or {})

        target_path = self.handoff_manager.canonicalize_artifact_path(
            raw_target, base_dir=self.root_dir, is_writable_output=False
        )
        post_snaps = snapshot_directory_hashes(target_path)

        # Every file recorded before execution outside owned_artifacts must remain identical
        for f_posix, before_sha in pre_snaps.items():
            if f_posix in owned_canon:
                continue
            after_sha = post_snaps.get(f_posix)
            if after_sha != before_sha:
                raise AcceptanceCheckFailedError(
                    f"Task '{tid}' failed '{cid}' (no_unapproved_mutation): unowned file '{f_posix}' "
                    f"was mutated or deleted (before={before_sha}, after={after_sha})!"
                )

        # Any newly created file inside the monitored target that is not owned is also unapproved!
        if pre_snaps or target_path.exists():
            for f_posix in post_snaps:
                if f_posix not in pre_snaps and f_posix not in owned_canon:
                    raise AcceptanceCheckFailedError(
                        f"Task '{tid}' failed '{cid}' (no_unapproved_mutation): unapproved file created at '{f_posix}'!"
                    )

        return {
            "criterion_id": cid,
            "check_type": "no_unapproved_mutation",
            "target": target_path.relative_to(self.root_dir).as_posix(),
            "files_verified_unchanged": len([k for k in post_snaps if k not in owned_canon]),
        }

    def _check_independent_review_verdict(
        self,
        handoff: dict[str, Any],
        dw: dict[str, Any],
        result: AgentExecutionResult,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        cid = dw["criterion_id"]
        tid = handoff["task_id"]
        by_id: dict[str, dict[str, Any]] = ctx.get("by_id") or {}
        artifact_sha256: dict[str, str] = ctx.get("artifact_sha256") or {}
        receipts_by_task: dict[str, dict[str, Any]] = ctx.get("receipts_by_task") or {}

        rep_dict: dict[str, Any] | None = None
        if result.review_report is not None:
            rep_dict = result.review_report.to_dict()
        else:
            cand = self.handoff_manager.canonicalize_artifact_path(
                dw["target"], base_dir=self.root_dir, is_writable_output=False
            )
            if cand.is_file() and cand.suffix.lower() == ".json":
                loaded = json.loads(cand.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and "verdict" in loaded and "reviewed_task_id" in loaded:
                    rep_dict = loaded

        if rep_dict is None:
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}' (independent_review_verdict): missing structured review report"
            )

        prod_tid = rep_dict["reviewed_task_id"]
        if prod_tid not in by_id:
            raise AcceptanceCheckFailedError(
                f"Task '{tid}' failed '{cid}': review references unknown producer task '{prod_tid}'"
            )
        prod_handoff = by_id[prod_tid]
        extra_tids = list(
            rep_dict.get("additional_reviewed_task_ids")
            or handoff.get("context", {}).get("additional_reviewed_task_ids")
            or []
        )
        extra_handoffs = [by_id[et] for et in extra_tids if et in by_id and et != prod_tid]

        pre_hashes: dict[str, str] = dict(ctx.get("pre_review_hashes") or {})
        if not pre_hashes:
            for ph in [prod_handoff, *extra_handoffs]:
                for cp in self.handoff_manager.canonical_owned_paths(ph, base_dir=self.root_dir):
                    rp = cp.relative_to(self.root_dir).as_posix()
                    if rp in artifact_sha256:
                        pre_hashes[rp] = artifact_sha256[rp]
                    elif cp.is_file():
                        pre_hashes[rp] = compute_file_sha256(cp)

        prod_conv = (receipts_by_task.get(prod_tid) or {}).get("conversation_id")
        ver_res = self.handoff_manager.verify_independent_review_pass(
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
        if rep_dict["verdict"] != "PASS":
            raise AcceptanceCheckFailedError(
                f"Independent verifier '{tid}' returned verdict='{rep_dict['verdict']}'"
            )
        return {
            "criterion_id": cid,
            "check_type": "independent_review_verdict",
            "target": prod_tid,
            "review_id": ver_res["review_id"],
            "artifacts_unchanged": ver_res["artifacts_unchanged"],
        }
