"""Fail-Closed Project State Manager, Structured Approval Gate & Live Execution Authorization (v3.4).

Fixes Phase 01.5 Critical Audit Findings:
- Replaces naive substring matching with a fail-closed structured approval parser + lexical negation,
  conditional, quote/meta-example, and ambiguity rejection.
- Binds every approval to `project_id`, `package_version`, `package_digest` (SHA-256), `approved_scopes`,
  `actor_role == "human_user"`, `approved_at`, `expires_at`, `revoked`, and `project_state_at_approval`.
- Enforces strict directed graph state transitions (`ALLOWED_STATE_TRANSITIONS`).
- Re-verifies live disk SHA-256 digest and authorization scope on every production transition or MCP mutation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"

REQUIRED_PACKAGE_FILES: tuple[str, ...] = (
    "blueprint.md",
    "script.md",
    "storyboard.json",
    "asset_manifest.json",
    "character_bible.md",
    "motion_plan.json",
    "execution_plan.md",
    "production_config.json",
    "engine_plan.json",
    "research.md",
    "reference_analysis.md",
)

VALID_APPROVAL_SCOPES: frozenset[str] = frozenset(
    {
        "mcp_preflight",
        "asset_procurement",
        "blender_scene_mutation",
        "style_frame",
        "animatic",
        "render_production",
        "all_production",
    }
)

PRODUCTION_MUTATING_STATES: frozenset[str] = frozenset(
    {
        "APPROVED",
        "MCP_PREFLIGHT",
        "ASSET_PROCUREMENT",
        "STYLE_FRAME",
        "ANIMATIC",
        "SHOT_RENDER",
        "COMPOSITE",
        "QC",
        "SELF_CORRECTION",
        "DELIVERED",
    }
)

# Strict directed state transition graph (WAITING_APPROVAL -> APPROVED is exclusively via record_explicit_user_approval)
ALLOWED_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "INIT": frozenset({"REFERENCE_REVIEW", "TOPIC_RESEARCH", "BLUEPRINT", "PREPRODUCTION", "WAITING_APPROVAL", "BLOCKED"}),
    "REFERENCE_REVIEW": frozenset({"TOPIC_RESEARCH", "BLUEPRINT", "BLOCKED"}),
    "TOPIC_RESEARCH": frozenset({"BLUEPRINT", "PREPRODUCTION", "BLOCKED"}),
    "BLUEPRINT": frozenset({"PREPRODUCTION", "WAITING_APPROVAL", "BLOCKED"}),
    "PREPRODUCTION": frozenset({"WAITING_APPROVAL", "BLOCKED"}),
    "WAITING_APPROVAL": frozenset({"PREPRODUCTION", "BLOCKED"}),
    "APPROVED": frozenset({"MCP_PREFLIGHT", "ASSET_PROCUREMENT", "WAITING_APPROVAL", "BLOCKED"}),
    "MCP_PREFLIGHT": frozenset({"ASSET_PROCUREMENT", "STYLE_FRAME", "WAITING_APPROVAL", "BLOCKED"}),
    "ASSET_PROCUREMENT": frozenset({"STYLE_FRAME", "ANIMATIC", "SHOT_RENDER", "WAITING_APPROVAL", "BLOCKED"}),
    "STYLE_FRAME": frozenset({"ANIMATIC", "SHOT_RENDER", "WAITING_APPROVAL", "BLOCKED"}),
    "ANIMATIC": frozenset({"SHOT_RENDER", "WAITING_APPROVAL", "BLOCKED"}),
    "SHOT_RENDER": frozenset({"COMPOSITE", "QC", "SELF_CORRECTION", "WAITING_APPROVAL", "BLOCKED"}),
    "COMPOSITE": frozenset({"QC", "WAITING_APPROVAL", "BLOCKED"}),
    "QC": frozenset({"DELIVERED", "SELF_CORRECTION", "WAITING_APPROVAL", "BLOCKED"}),
    "SELF_CORRECTION": frozenset({"SHOT_RENDER", "COMPOSITE", "QC", "WAITING_APPROVAL", "BLOCKED"}),
    "DELIVERED": frozenset({"WAITING_APPROVAL"}),
    "BLOCKED": frozenset({"INIT", "TOPIC_RESEARCH", "PREPRODUCTION", "WAITING_APPROVAL"}),
}

STATE_REQUIRED_SCOPE: dict[str, str] = {
    "MCP_PREFLIGHT": "mcp_preflight",
    "ASSET_PROCUREMENT": "asset_procurement",
    "STYLE_FRAME": "style_frame",
    "ANIMATIC": "animatic",
    "SHOT_RENDER": "render_production",
    "COMPOSITE": "render_production",
    "QC": "render_production",
    "SELF_CORRECTION": "render_production",
    "DELIVERED": "render_production",
}

NEGATION_WORDS_REGEX = re.compile(
    r"\b("
    r"tidak|tak|bukan|jangan|belum|batal|batalkan|tolak|ditolak|menolak|kurang|tunda|hentikan|stop|cabut|"
    r"no|not|never|dont|don't|do\s+not|reject|rejected|deny|denied|cancel|abort|refuse|hold|revoke"
    r")\b",
    re.IGNORECASE,
)

CONDITIONAL_WORDS_REGEX = re.compile(
    r"\b("
    r"jika|kalau|bila|apabila|asalkan|asal|tapi|tetapi|namun|kecuali|sebelum|nanti|mungkin|syarat|revisi|ubah|"
    r"if|unless|but|however|except|maybe|later|wait|condition|pending|change\s+first"
    r")\b",
    re.IGNORECASE,
)

META_OR_EXAMPLE_REGEX = re.compile(
    r"\b(contoh|misalnya|misal|seperti|umpama|format|ketik|tuliskan|example|sample|template|e\.g\.)\b",
    re.IGNORECASE,
)

STRUCTURED_KV_REGEX = re.compile(
    r"^XDX-APPROVE\s+"
    r"project=(?P<project>[A-Za-z0-9_\-]+)\s+"
    r"version=(?P<version>v[0-9]+(?:\.[0-9]+)*)\s+"
    r"digest=(?P<digest>[a-f0-9]{12,64})\s+"
    r"scopes=(?P<scopes>[a-z_,]+)$"
)


class InvalidStateTransitionError(PermissionError):
    """Raised when attempting a state transition outside ALLOWED_STATE_TRANSITIONS."""


from governance.canonical_manifest import compute_canonical_package_digest  # noqa: E402
from governance.trusted_approval import (  # noqa: E402
    ApprovalAuthorizationError,
    PhaseBoundaryBlockedError,
    TrustedApprovalError,
    TrustedApprovalGuard,
    assert_phase_boundary,
    default_guard,
)


# Phase 01.6D: the unconditional 01.6C freeze is replaced by the Trusted Human Approval guard
# (governance/trusted_approval.py). APPROVED is reachable ONLY with an Ed25519-signed token from a
# registered human key; without a usable trusted channel, approval stays BLOCKED. Production execution
# scopes remain blocked by the Phase 02 boundary (assert_phase_boundary).


class ProductionApprovalFrozenError(InvalidStateTransitionError):
    """Raised when a caller tries to enter APPROVED/production outside the trusted approval gate."""


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via same-directory temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def compute_package_digest(package_dir: Path) -> tuple[str, dict[str, str]]:
    """Canonical SHA-256 manifest digest over EVERY production-input artifact (Phase 01.6D).

    Delegates to governance.canonical_manifest: all regular files are hashed (narration, captions,
    character/style bibles, camera, semantic storyboard, research, reference adaptation included);
    only runtime state/lock/ledger files are excluded.
    """
    return compute_canonical_package_digest(Path(package_dir))


def format_structured_approval_command(
    *,
    project_id: str,
    package_version: str,
    package_digest: str,
    scopes: list[str] | None = None,
) -> str:
    """Return the exact canonical approval command string to present to the user at WAITING_APPROVAL."""
    scope_list = scopes or ["all_production"]
    return (
        f"XDX-APPROVE project={project_id} version={package_version} "
        f"digest={package_digest[:16]} scopes={','.join(scope_list)}"
    )


def parse_and_validate_approval_message(
    user_message: str,
    *,
    expected_version: str,
    expected_project_id: str | None = None,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    """Fail-closed parser for explicit user approval messages.

    Rejects:
    - Empty, multi-line, quoted, backticked, or blockquoted text
    - Any negation/refusal word ('tidak', 'jangan', 'tolak', 'batal', 'no', 'not', etc.)
    - Any conditional/hedging word ('jika', 'kalau', 'tapi', 'namun', 'kecuali', 'if', 'unless', etc.)
    - Any example/meta framing ('contoh', 'misalnya', 'example', etc.)
    - Missing or mismatched project_id, package_version, digest prefix (>=12 hex), or scope.
    """
    if not isinstance(user_message, str):
        raise ApprovalAuthorizationError("Approval message must be a string.")
    raw = user_message.strip()
    if not raw or "\n" in raw or "\r" in raw:
        raise ApprovalAuthorizationError("Approval message must be a non-empty single-line statement.")

    if any(ch in raw for ch in ('"', "'", "`", "“", "”", "‘", "’")) or raw.startswith(">"):
        raise ApprovalAuthorizationError("Quoted, backticked, or blockquoted approval messages are rejected.")

    if "?" in raw:
        raise ApprovalAuthorizationError("Interrogative/question messages cannot grant approval.")

    if NEGATION_WORDS_REGEX.search(raw):
        raise ApprovalAuthorizationError("Negative or refusal terms detected in message; approval rejected.")

    if CONDITIONAL_WORDS_REGEX.search(raw):
        raise ApprovalAuthorizationError("Conditional or hedging terms detected in message; approval rejected.")

    if META_OR_EXAMPLE_REGEX.search(raw):
        raise ApprovalAuthorizationError("Example/meta phrasing detected in message; approval rejected.")

    # Format 1 (Primary Canonical): XDX-APPROVE project=<id> version=<vX> digest=<hex12..64> scopes=<s1,s2>
    m = STRUCTURED_KV_REGEX.match(raw)
    if m:
        proj = m.group("project")
        ver = m.group("version")
        dig = m.group("digest").lower()
        scopes = [s for s in m.group("scopes").split(",") if s]

        if ver != expected_version:
            raise ApprovalAuthorizationError(f"Version mismatch: message approved '{ver}', expected '{expected_version}'.")
        if expected_project_id is not None and proj != expected_project_id:
            raise ApprovalAuthorizationError(
                f"Project ID mismatch: message approved '{proj}', expected '{expected_project_id}'."
            )
        if expected_digest is not None and not expected_digest.lower().startswith(dig):
            raise ApprovalAuthorizationError("Package SHA-256 digest mismatch in approval message.")
        if not scopes or any(s not in VALID_APPROVAL_SCOPES for s in scopes):
            raise ApprovalAuthorizationError(f"Invalid approval scopes: {scopes}")

        return {
            "valid": True,
            "format": "canonical_xdx_approve",
            "project_id": proj,
            "package_version": ver,
            "digest_prefix": dig,
            "scopes": scopes,
        }

    # Format 2 (Strict Explicit Bound Indonesian Statement — only when project/digest aren't omitted if required)
    # Example: "SAYA SETUJUI PAKET proyek=demo_01 versi=v1 digest=abcdef012345 scope=all_production"
    id_match = re.match(
        r"^SAYA\s+SETUJUI\s+PAKET\s+"
        r"proyek=(?P<project>[A-Za-z0-9_\-]+)\s+"
        r"versi=(?P<version>v[0-9]+(?:\.[0-9]+)*)\s+"
        r"digest=(?P<digest>[a-f0-9]{12,64})\s+"
        r"scope=(?P<scopes>[a-z_,]+)$",
        raw,
    )
    if id_match:
        proj = id_match.group("project")
        ver = id_match.group("version")
        dig = id_match.group("digest").lower()
        scopes = [s for s in id_match.group("scopes").split(",") if s]
        if ver != expected_version:
            raise ApprovalAuthorizationError("Version mismatch in approval statement.")
        if expected_project_id is not None and proj != expected_project_id:
            raise ApprovalAuthorizationError("Project ID mismatch in approval statement.")
        if expected_digest is not None and not expected_digest.lower().startswith(dig):
            raise ApprovalAuthorizationError("Digest mismatch in approval statement.")
        if not scopes or any(s not in VALID_APPROVAL_SCOPES for s in scopes):
            raise ApprovalAuthorizationError(f"Invalid scopes: {scopes}")
        return {
            "valid": True,
            "format": "structured_indonesian_approve",
            "project_id": proj,
            "package_version": ver,
            "digest_prefix": dig,
            "scopes": scopes,
        }

    raise ApprovalAuthorizationError(
        "Approval message rejected: must use structured fail-closed format "
        "'XDX-APPROVE project=<id> version=<vX> digest=<sha256_prefix12+> scopes=<scopes>'."
    )


def is_explicit_approval_message(
    user_message: str,
    package_version: str,
    *,
    project_id: str | None = None,
    package_digest: str | None = None,
) -> bool:
    """Boolean wrapper around fail-closed `parse_and_validate_approval_message`."""
    try:
        parse_and_validate_approval_message(
            user_message,
            expected_version=package_version,
            expected_project_id=project_id,
            expected_digest=package_digest,
        )
        return True
    except ApprovalAuthorizationError:
        return False


@dataclass(frozen=True)
class ExecutionAuthorizationContext:
    """Live execution authorization context verified against disk state & SHA-256 on every mutating call."""

    package_dir: Path
    state_file: Path
    project_id: str
    package_version: str
    expected_digest: str


class ApprovalGate:
    """Validates the 13-item pre-production package, approval records, and live execution contexts."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        sdir = schemas_dir or SCHEMAS_DIR
        self._approval_schema = json.loads((sdir / "approval_package.schema.json").read_text(encoding="utf-8"))
        self._storyboard_schema = json.loads((sdir / "storyboard.schema.json").read_text(encoding="utf-8"))
        self._engine_schema = json.loads((sdir / "engine_plan.schema.json").read_text(encoding="utf-8"))

    @staticmethod
    def _parse_iso_utc(ts: str) -> datetime:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def verify_approval_record_dict(
        self,
        rec: dict[str, Any],
        *,
        live_digest: str,
        expected_project_id: str | None = None,
        required_scope: str | None = None,
        now: datetime | None = None,
        package_dir: Path | None = None,
        expected_package_version: str | None = None,
    ) -> dict[str, Any]:
        """Fail-closed validation of approval_record.json via the central Trusted Approval guard.

        A record is valid only if it carries an Ed25519-signed token from a registered human key that binds
        project, version, full canonical manifest digest, scopes, nonce and expiry, and the hash-chained
        ledger shows it was consumed exactly once and never revoked.
        """
        if not isinstance(rec, dict) or not rec:
            raise ApprovalAuthorizationError("Missing or empty approval_record.json")
        if rec.get("decision") != "approved":
            raise ApprovalAuthorizationError("Approval decision is not 'approved'")
        if rec.get("revoked") is True:
            raise ApprovalAuthorizationError("Approval has been explicitly revoked")
        if rec.get("actor_role") != "human_user":
            raise ApprovalAuthorizationError(
                f"Self-approval by '{rec.get('actor_role')}' is forbidden; actor_role must be 'human_user'."
            )
        if rec.get("project_state_at_approval") != "WAITING_APPROVAL":
            raise ApprovalAuthorizationError(
                f"Approval was recorded in invalid state '{rec.get('project_state_at_approval')}' (must be WAITING_APPROVAL)."
            )
        if package_dir is None:
            raise ApprovalAuthorizationError("package_dir is required to verify the approval ledger.")
        rec_proj = str(rec.get("project_id", "")).strip()
        if expected_project_id is not None and rec_proj != expected_project_id:
            raise ApprovalAuthorizationError(f"Project ID mismatch: '{rec_proj}' != '{expected_project_id}'")
        if str(rec.get("digest", "")) != live_digest:
            raise ApprovalAuthorizationError("Live package SHA-256 digest does not match approved digest (tampered/modified)")

        va = self._guard().verify_recorded_approval(
            Path(package_dir),
            rec,
            expected_project_id=expected_project_id or rec_proj,
            expected_package_version=expected_package_version or str(rec.get("package_version", "")),
            live_manifest_digest=live_digest,
            required_scope=required_scope or "mcp_preflight",
            now=now,
        )
        return {
            "approval_id": va.approval_id,
            "key_id": va.key_id,
            "project_id": va.project_id,
            "version": va.package_version,
            "digest": va.manifest_digest,
            "scopes": list(va.scopes),
            "expires_at": va.expires_at,
            "trusted_channel": "ed25519_offline_signature",
        }

    @staticmethod
    def _guard() -> TrustedApprovalGuard:
        return default_guard()

    def inspect_package(self, package_dir: Path, *, check_record: bool = False) -> dict[str, Any]:
        digest, file_hashes = compute_package_digest(package_dir)

        storyboard = json.loads((package_dir / "storyboard.json").read_text(encoding="utf-8"))
        engine_plan = json.loads((package_dir / "engine_plan.json").read_text(encoding="utf-8"))
        prod_cfg = json.loads((package_dir / "production_config.json").read_text(encoding="utf-8"))
        project_id = str(prod_cfg.get("project_id") or storyboard.get("project_id") or "unknown")
        pkg_ver = str(prod_cfg.get("package_version", "v1"))

        jsonschema.validate(instance=storyboard, schema=self._storyboard_schema)
        jsonschema.validate(instance=engine_plan, schema=self._engine_schema)

        manifest_path = package_dir / "approval_package_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=manifest, schema=self._approval_schema)

        if not check_record:
            return {
                "digest": digest,
                "project_id": project_id,
                "package_version": pkg_ver,
                "status": "WAITING_APPROVAL",
                "files_verified": len(file_hashes),
                "approval_command_template": format_structured_approval_command(
                    project_id=project_id,
                    package_version=pkg_ver,
                    package_digest=digest,
                ),
                "note": "No authorization granted. Stop at WAITING_APPROVAL until explicit structured user approval.",
            }

        rec_path = package_dir / "approval_record.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
        try:
            self.verify_approval_record_dict(
                rec,
                live_digest=digest,
                expected_project_id=project_id,
                package_dir=package_dir,
                expected_package_version=pkg_ver,
            )
            return {
                "digest": digest,
                "project_id": project_id,
                "package_version": pkg_ver,
                "status": "RECORD_MATCH_ONLY",
                "explicit_phrase_verified": True,
                "note": "Ed25519-signed trusted approval verified against live canonical manifest, project, version, TTL, ledger and revocation.",
            }
        except (ApprovalAuthorizationError, ValueError) as exc:
            return {
                "digest": digest,
                "project_id": project_id,
                "package_version": pkg_ver,
                "status": "BLOCKED",
                "explicit_phrase_verified": False,
                "error": str(exc),
                "note": "Fail-closed rejection.",
            }

    def verify_live_execution_context(
        self,
        ctx: ExecutionAuthorizationContext,
        *,
        required_scope: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Verify live authorization context before ANY scene mutation or render step."""
        if not isinstance(ctx, ExecutionAuthorizationContext):
            raise ApprovalAuthorizationError("Missing valid ExecutionAuthorizationContext object.")

        live_digest, _ = compute_package_digest(ctx.package_dir)
        if live_digest != ctx.expected_digest:
            raise ApprovalAuthorizationError("Package files modified on disk since authorization context was created.")

        if not ctx.state_file.is_file():
            raise ApprovalAuthorizationError("Missing project_state.json for authorization verification.")
        state = json.loads(ctx.state_file.read_text(encoding="utf-8"))

        if state.get("project_id") != ctx.project_id or state.get("package_version") != ctx.package_version:
            raise ApprovalAuthorizationError("State project_id or package_version mismatch.")

        allowed_exec_states = {"APPROVED", "MCP_PREFLIGHT", "ASSET_PROCUREMENT", "STYLE_FRAME", "ANIMATIC", "SHOT_RENDER"}
        if state.get("current_state") not in allowed_exec_states:
            raise ApprovalAuthorizationError(
                f"Project state '{state.get('current_state')}' is not authorized for execution (allowed: {sorted(allowed_exec_states)})."
            )

        app_status = state.get("approval_status") or {}
        if not app_status.get("approved") or app_status.get("revoked") is True:
            raise ApprovalAuthorizationError("Project state approval_status is inactive or revoked.")
        if app_status.get("approved_digest") != live_digest:
            raise ApprovalAuthorizationError("State approved_digest does not match live package SHA-256.")

        rec_path = ctx.package_dir / "approval_record.json"
        if not rec_path.is_file():
            raise ApprovalAuthorizationError("Missing approval_record.json on disk.")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))

        verified = self.verify_approval_record_dict(
            rec,
            live_digest=live_digest,
            expected_project_id=ctx.project_id,
            required_scope=required_scope,
            now=now,
            package_dir=ctx.package_dir,
            expected_package_version=ctx.package_version,
        )
        # Trusted approval proven -> still enforce the Phase 02 execution boundary.
        assert_phase_boundary(required_scope, action="ApprovalGate.verify_live_execution_context")
        return verified


class ProjectStateManager:
    """Deterministic project state machine with strict transition graph and live tamper invalidation."""

    def __init__(self, state_file: Path, schemas_dir: Path | None = None) -> None:
        self.state_file = state_file
        sdir = schemas_dir or SCHEMAS_DIR
        self._schema = json.loads((sdir / "project_state.schema.json").read_text(encoding="utf-8"))
        self._gate = ApprovalGate(schemas_dir=sdir)

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def initialize(
        self,
        *,
        project_id: str,
        project_title: str,
        genres: list[str],
        mode: str = "topik",
        fps: int = 30,
        width: int = 1080,
        height: int = 1920,
        aspect_ratio: str = "9:16",
        total_frames: int = 450,
    ) -> dict[str, Any]:
        now_s = self._now_utc().isoformat()
        state: dict[str, Any] = {
            "schema_version": "3.4.0",
            "project_id": project_id,
            "project_title": project_title,
            "mode": mode,
            "current_state": "INIT",
            "package_version": "v1",
            "package_digest": None,
            "genres": genres,
            "timeline_spec": {
                "fps": fps,
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "total_frames": total_frames,
            },
            "approval_status": {
                "approved": False,
                "approval_id": None,
                "actor_role": None,
                "approved_digest": None,
                "approved_version": None,
                "approved_scopes": [],
                "explicit_user_message": None,
                "recorded_at": None,
                "expires_at": None,
                "revoked": False,
            },
            "blocked_reason": None,
            "history": [
                {
                    "from_state": None,
                    "to_state": "INIT",
                    "timestamp": now_s,
                    "reason": "Project initialized",
                }
            ],
            "updated_at": now_s,
        }
        self._save(state)
        return state

    def load(self) -> dict[str, Any]:
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        jsonschema.validate(instance=state, schema=self._schema)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        jsonschema.validate(instance=state, schema=self._schema)
        atomic_write_json(self.state_file, state)

    def mark_waiting_approval(self, package_digest: str, *, package_version: str | None = None) -> dict[str, Any]:
        state = self.load()
        prev = state["current_state"]
        if prev != "WAITING_APPROVAL" and "WAITING_APPROVAL" not in ALLOWED_STATE_TRANSITIONS.get(prev, frozenset()):
            raise InvalidStateTransitionError(f"Transition '{prev}' -> 'WAITING_APPROVAL' is not allowed.")

        now_s = self._now_utc().isoformat()
        if package_version:
            state["package_version"] = package_version
        state["package_digest"] = package_digest
        state["approval_status"] = {
            "approved": False,
            "approval_id": None,
            "actor_role": None,
            "approved_digest": None,
            "approved_version": None,
            "approved_scopes": [],
            "explicit_user_message": None,
            "recorded_at": None,
            "expires_at": None,
            "revoked": False,
        }
        state["current_state"] = "WAITING_APPROVAL"
        state["history"].append(
            {
                "from_state": prev,
                "to_state": "WAITING_APPROVAL",
                "timestamp": now_s,
                "reason": f"Pre-production package {state['package_version']} locked ({package_digest[:12]})",
            }
        )
        state["updated_at"] = now_s
        self._save(state)
        return state

    def record_explicit_user_approval(
        self,
        *,
        package_dir: Path,
        user_message: str,
        actor_role: str = "human_user",
        ttl_hours: float = 24.0,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Record approval ONLY from an Ed25519-signed trusted token (Phase 01.6D).

        ``user_message`` must be the ``XDX-SIGNED-APPROVAL ...`` token produced on the human's device.
        Unsigned chat text / ``XDX-APPROVE`` commands are rejected. ``ttl_hours`` can only shorten, never
        extend, the signed expiry. If the trusted channel is unavailable, approval is BLOCKED.
        """
        state = self.load()
        if state["current_state"] != "WAITING_APPROVAL":
            raise InvalidStateTransitionError(
                f"Approval can only be recorded when project is in WAITING_APPROVAL (current={state['current_state']})."
            )
        if actor_role != "human_user":
            raise ApprovalAuthorizationError(
                f"AI/system self-approval rejected (actor_role='{actor_role}'). Only 'human_user' is permitted."
            )
        if ttl_hours <= 0:
            raise ApprovalAuthorizationError("Approval TTL must be positive.")

        digest, _ = compute_package_digest(package_dir)
        if state["package_digest"] != digest:
            raise ApprovalAuthorizationError("Package digest changed since WAITING_APPROVAL; re-submit updated package first.")

        guard = ApprovalGate._guard()
        va = guard.verify_token(
            (user_message or "").strip(),
            expected_project_id=state["project_id"],
            expected_package_version=state["package_version"],
            live_manifest_digest=digest,
            now=now,
        )
        consumed_hist = [h.get("approval_nonce") for h in state["history"] if h.get("approval_nonce")]
        guard.consume(package_dir, va, state_consumed_nonces=consumed_hist)

        now_dt = now or self._now_utc()
        expires_dt = min(
            datetime.fromisoformat(va.expires_at).astimezone(timezone.utc), now_dt + timedelta(hours=ttl_hours)
        )
        approval_rec = {
            "approval_id": va.approval_id,
            "project_id": state["project_id"],
            "package_version": state["package_version"],
            "digest": digest,
            "decision": "approved",
            "actor_role": "human_user",
            "approved_scopes": list(va.scopes),
            "project_state_at_approval": "WAITING_APPROVAL",
            "trusted_channel": "ed25519_offline_signature",
            "approver_key_id": va.key_id,
            "nonce": va.nonce,
            "signed_token": va.token,
            "recorded_at": now_dt.isoformat(),
            "expires_at": expires_dt.isoformat(),
            "revoked": False,
        }
        atomic_write_json(package_dir / "approval_record.json", approval_rec)

        state["current_state"] = "APPROVED"
        state["approval_status"] = {
            "approved": True,
            "approval_id": va.approval_id,
            "actor_role": "human_user",
            "approved_digest": digest,
            "approved_version": state["package_version"],
            "approved_scopes": list(va.scopes),
            "explicit_user_message": f"<signed approval {va.approval_id} by key {va.key_id}>",
            "recorded_at": now_dt.isoformat(),
            "expires_at": expires_dt.isoformat(),
            "revoked": False,
        }
        state["history"].append(
            {
                "from_state": "WAITING_APPROVAL",
                "to_state": "APPROVED",
                "timestamp": now_dt.isoformat(),
                "reason": f"Trusted Ed25519 human approval verified ({va.approval_id}, key={va.key_id})",
                "approval_nonce": va.nonce,
            }
        )
        state["updated_at"] = now_dt.isoformat()
        self._save(state)
        return state

    def revoke_approval(self, *, package_dir: Path, reason: str = "User revoked approval") -> dict[str, Any]:
        state = self.load()
        now_s = self._now_utc().isoformat()
        rec_path = package_dir / "approval_record.json"
        if rec_path.is_file():
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            rec["revoked"] = True
            rec["revoked_at"] = now_s
            atomic_write_json(rec_path, rec)
            if rec.get("approval_id"):
                ApprovalGate._guard().revoke(package_dir, str(rec["approval_id"]), reason=reason)

        prev = state["current_state"]
        state["current_state"] = "WAITING_APPROVAL"
        state["approval_status"]["approved"] = False
        state["approval_status"]["revoked"] = True
        state["history"].append(
            {"from_state": prev, "to_state": "WAITING_APPROVAL", "timestamp": now_s, "reason": reason}
        )
        state["updated_at"] = now_s
        self._save(state)
        return state

    def build_authorization_context(self, package_dir: Path) -> ExecutionAuthorizationContext:
        state = self.load()
        digest, _ = compute_package_digest(package_dir)
        ctx = ExecutionAuthorizationContext(
            package_dir=package_dir,
            state_file=self.state_file,
            project_id=state["project_id"],
            package_version=state["package_version"],
            expected_digest=digest,
        )
        # Build-time check uses the minimal read-only scope; every execution step re-verifies with its own scope.
        self._gate.verify_live_execution_context(ctx, required_scope="mcp_preflight")
        return ctx

    def transition(self, next_state: str, *, reason: str, package_dir: Path | None = None) -> dict[str, Any]:
        state = self.load()
        prev = state["current_state"]

        if next_state == "APPROVED":
            raise InvalidStateTransitionError(
                "Direct transition to 'APPROVED' via transition() is forbidden; use record_explicit_user_approval()."
            )

        allowed_targets = ALLOWED_STATE_TRANSITIONS.get(prev, frozenset())
        if next_state not in allowed_targets:
            raise InvalidStateTransitionError(
                f"Illegal state transition '{prev}' -> '{next_state}'. Allowed from '{prev}': {sorted(allowed_targets)}"
            )

        if next_state in PRODUCTION_MUTATING_STATES:
            if package_dir is None:
                raise ApprovalAuthorizationError(
                    f"package_dir is mandatory when entering production state '{next_state}' to verify live SHA-256."
                )
            try:
                live_digest, _ = compute_package_digest(package_dir)
                rec_path = package_dir / "approval_record.json"
                rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
                req_scope = STATE_REQUIRED_SCOPE.get(next_state, "render_production")
                self._gate.verify_approval_record_dict(
                    rec,
                    live_digest=live_digest,
                    expected_project_id=state["project_id"],
                    required_scope=req_scope,
                    package_dir=package_dir,
                    expected_package_version=state["package_version"],
                )
                if state["approval_status"].get("approved_digest") != live_digest or not state["approval_status"].get("approved"):
                    raise ApprovalAuthorizationError("State approval_status mismatch against live package SHA-256.")
            except PhaseBoundaryBlockedError:
                raise
            except (ApprovalAuthorizationError, ValueError) as exc:
                now_s = self._now_utc().isoformat()
                state["current_state"] = "WAITING_APPROVAL"
                state["approval_status"]["approved"] = False
                state["history"].append(
                    {
                        "from_state": prev,
                        "to_state": "WAITING_APPROVAL",
                        "timestamp": now_s,
                        "reason": f"Authorization/tamper failure blocked '{next_state}': {exc}",
                    }
                )
                state["updated_at"] = now_s
                self._save(state)
                if isinstance(exc, ApprovalAuthorizationError):
                    raise
                raise ApprovalAuthorizationError(str(exc)) from exc

        if next_state in PRODUCTION_MUTATING_STATES:
            # Approval verified; production execution scopes remain behind the Phase 02 boundary.
            assert_phase_boundary(
                STATE_REQUIRED_SCOPE.get(next_state, "render_production"),
                action=f"ProjectStateManager.transition({next_state})",
            )

        now_s = self._now_utc().isoformat()
        state["current_state"] = next_state
        if next_state == "BLOCKED":
            state["blocked_reason"] = reason
        state["history"].append(
            {"from_state": prev, "to_state": next_state, "timestamp": now_s, "reason": reason}
        )
        state["updated_at"] = now_s
        self._save(state)
        return state
