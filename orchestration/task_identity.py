"""Deterministic task-definition and task-graph fingerprints (Phase 01.6C).

Used to bind checkpoints, invocation receipts and review reports to the exact task graph that
produced them. Runtime-mutable fields (``status``, ``retry_budget.attempts_used`` and the
auto-bound ``input_artifact_hashes``) are excluded so that a fingerprint identifies the *contract*,
not the execution progress.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable

TASK_FINGERPRINT_VERSION = "xdx.task_fingerprint.v1"

_EXCLUDED_TOP_LEVEL_FIELDS: frozenset[str] = frozenset({"status", "input_artifact_hashes"})


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contract_view(handoff: dict[str, Any]) -> dict[str, Any]:
    view = {k: copy.deepcopy(v) for k, v in handoff.items() if k not in _EXCLUDED_TOP_LEVEL_FIELDS}
    rb = dict(view.get("retry_budget") or {})
    rb.pop("attempts_used", None)
    view["retry_budget"] = rb
    return view


def compute_task_definition_digest(handoff: dict[str, Any]) -> str:
    """SHA-256 over the immutable contract portion of one 18-field task handoff."""
    return sha256_text(f"{TASK_FINGERPRINT_VERSION}|{canonical_json(_contract_view(handoff))}")


def compute_task_definition_digests(handoffs: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {h["task_id"]: compute_task_definition_digest(h) for h in sorted(handoffs, key=lambda x: x["task_id"])}


def compute_task_graph_digest(handoffs: Iterable[dict[str, Any]]) -> str:
    """SHA-256 over (project_id, sorted task-definition digests, dependency edges)."""
    items = sorted(handoffs, key=lambda x: x["task_id"])
    if not items:
        raise ValueError("Cannot fingerprint an empty task graph")
    project_ids = sorted({h["project_id"] for h in items})
    body = {
        "fingerprint_version": TASK_FINGERPRINT_VERSION,
        "project_ids": project_ids,
        "tasks": {h["task_id"]: compute_task_definition_digest(h) for h in items},
        "edges": sorted([[d, h["task_id"]] for h in items for d in h.get("dependencies", [])]),
    }
    return sha256_text(canonical_json(body))
