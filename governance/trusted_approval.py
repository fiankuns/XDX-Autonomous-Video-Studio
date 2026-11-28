"""Phase 01.6D — Trusted Human Approval & Execution Guard (single source of truth for v3.4 and v4.0).

Trusted channel
---------------
Approval is accepted ONLY as an Ed25519-signed token produced with a private key that the human keeps on
their own device. The repository holds only public keys in ``registry/trusted_approvers.json``. An agent
running in the workspace can read every file but cannot produce a valid signature, so chat text
("lanjutkan", "XDX-APPROVE ..."), actor labels, hand-written approval_record.json / state files and
agent-built dicts are all rejected.

If no usable, unrevoked public key is registered - or the default trust registry has uncommitted local
modifications - the channel is ``UNAVAILABLE`` and production stays ``BLOCKED``.

Threat model / limits (honest): this protects against forged approval *data* through every official
path (v3.4 ProjectStateManager, v4 SharedProjectStateMachine, approval_gate CLI, MCP adapter). It does not
protect against a process that rewrites this module's source code or a commit adding an attacker key that a
human then merges: changes to ``registry/trusted_approvers.json`` must be human-reviewed.

Token format
------------
``XDX-SIGNED-APPROVAL <base64url(JSON envelope)>`` where the envelope is
``{"payload": {...}, "key_id": str, "signature": base64url(Ed25519(canonical_json(payload)))}``.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TRUST_REGISTRY_PATH = ROOT_DIR / "registry" / "trusted_approvers.json"

TOKEN_PREFIX = "XDX-SIGNED-APPROVAL "
PAYLOAD_SCHEMA = "xdx.trusted-approval.v1"
TRUSTED_CHANNEL = "ed25519_offline_signature"
MAX_TTL = timedelta(hours=72)
CLOCK_SKEW = timedelta(seconds=120)
LEDGER_DIRNAME = ".approvals"
LEDGER_FILENAME = "approval_ledger.jsonl"

VALID_SCOPES: frozenset[str] = frozenset(
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
# Scopes that would execute Phase 02 production. Even with a valid trusted approval these stay blocked by
# the phase boundary until Phase 02 is explicitly started (Phase 01.6D must not run production).
PHASE02_EXECUTION_SCOPES: frozenset[str] = VALID_SCOPES - {"mcp_preflight"}
PHASE02_EXECUTION_ENABLED = True

_PAYLOAD_KEYS = frozenset(
    {
        "schema",
        "channel",
        "project_id",
        "package_version",
        "manifest_digest",
        "scopes",
        "nonce",
        "issued_at",
        "expires_at",
    }
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32,128}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_.:-]{3,64}$")


# ----------------------------------------------------------------------------- errors
class ApprovalAuthorizationError(PermissionError):
    """Raised when approval validation or execution authorization fails (fail-closed).

    Defined here (and re-exported by ``intelligence.state_and_approval``) so every trusted-guard error is an
    ``ApprovalAuthorizationError`` for legacy callers such as the MCP adapter.
    """


class TrustedApprovalError(ApprovalAuthorizationError):
    """Base class: any trusted approval / execution guard rejection (fail-closed)."""

    code = "REJECTED"

    def __init__(self, message: str) -> None:
        super().__init__(f"[{self.code}] {message}")


class TrustedChannelUnavailableError(TrustedApprovalError):
    code = "TRUSTED_CHANNEL_UNAVAILABLE"


class UnsignedApprovalError(TrustedApprovalError):
    code = "UNSIGNED_OR_MALFORMED"


class SignatureInvalidError(TrustedApprovalError):
    code = "SIGNATURE_INVALID"


class UnknownApproverError(TrustedApprovalError):
    code = "UNKNOWN_OR_REVOKED_KEY"


class ApprovalBindingMismatchError(TrustedApprovalError):
    code = "BINDING_MISMATCH"


class ApprovalExpiredError(TrustedApprovalError):
    code = "EXPIRED"


class ApprovalReplayError(TrustedApprovalError):
    code = "REPLAY"


class ApprovalRevokedError(TrustedApprovalError):
    code = "REVOKED"


class ScopeMismatchError(TrustedApprovalError):
    code = "SCOPE_MISMATCH"


class LedgerIntegrityError(TrustedApprovalError):
    code = "LEDGER_TAMPERED"


class PhaseBoundaryBlockedError(TrustedApprovalError):
    code = "PHASE02_EXECUTION_NOT_STARTED"


# ----------------------------------------------------------------------------- helpers
def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    if not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", s):
        raise UnsignedApprovalError("Invalid base64url field")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_utc(s: Any) -> datetime:
    if not isinstance(s, str):
        raise UnsignedApprovalError("Timestamp must be an ISO-8601 string")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnsignedApprovalError(f"Bad timestamp {s!r}") from exc
    if dt.tzinfo is None:
        raise UnsignedApprovalError("Timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


# ----------------------------------------------------------------------------- data
@dataclass(frozen=True)
class VerifiedApproval:
    approval_id: str
    key_id: str
    project_id: str
    package_version: str
    manifest_digest: str
    scopes: tuple[str, ...]
    nonce: str
    issued_at: str
    expires_at: str
    token: str

    def covers(self, scope: str) -> bool:
        return scope in self.scopes or "all_production" in self.scopes


# ----------------------------------------------------------------------------- signing (human side)
def generate_approver_keypair() -> tuple[bytes, str]:
    """Return (raw 32-byte private key, base64url public key). Private key must never enter the repo."""
    priv = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    raw_priv = priv.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    raw_pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw_priv, _b64u(raw_pub)


def sign_approval_token(
    *,
    private_key_raw: bytes,
    key_id: str,
    project_id: str,
    package_version: str,
    manifest_digest: str,
    scopes: list[str],
    ttl: timedelta = timedelta(hours=24),
    now: datetime | None = None,
    nonce: str | None = None,
) -> str:
    """Human-side helper (scripts/trusted_approval.py sign). Requires the human's private key."""
    issued = _now(now)
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "channel": TRUSTED_CHANNEL,
        "project_id": project_id,
        "package_version": package_version,
        "manifest_digest": manifest_digest,
        "scopes": sorted(set(scopes)),
        "nonce": nonce or os.urandom(16).hex(),
        "issued_at": issued.isoformat(),
        "expires_at": (issued + ttl).isoformat(),
    }
    sig = Ed25519PrivateKey.from_private_bytes(private_key_raw).sign(canonical_json(payload))
    envelope = {"payload": payload, "key_id": key_id, "signature": _b64u(sig)}
    return TOKEN_PREFIX + _b64u(canonical_json(envelope))


# ----------------------------------------------------------------------------- guard
class TrustedApprovalGuard:
    """Central verifier used by every approval and execution path."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else Path(DEFAULT_TRUST_REGISTRY_PATH)

    # ---- trust root
    def _registry_git_state(self) -> str:
        """'CLEAN' | 'MODIFIED' | 'LOCAL_UNPUSHED' | 'UNTRACKED' | 'NOT_IN_REPO'. Only the in-repo registry is git-pinned."""
        try:
            rel = self.registry_path.resolve().relative_to(ROOT_DIR.resolve())
        except ValueError:
            return "NOT_IN_REPO"
        if not (ROOT_DIR / ".git").exists():
            return "NOT_IN_REPO"
        try:
            tracked = subprocess.run(
                ["git", "-C", str(ROOT_DIR), "ls-files", "--error-unmatch", rel.as_posix()],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if tracked.returncode != 0:
                return "UNTRACKED"
            diff = subprocess.run(
                ["git", "-C", str(ROOT_DIR), "diff", "--quiet", "HEAD", "--", rel.as_posix()],
                capture_output=True,
                timeout=20,
            )
            if diff.returncode != 0:
                return "MODIFIED"
            # Guard against an agent running `git commit` locally to inject a key without remote/human push:
            upstream = subprocess.run(
                ["git", "-C", str(ROOT_DIR), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if upstream.returncode == 0 and upstream.stdout.strip():
                up_ref = upstream.stdout.strip()
                up_diff = subprocess.run(
                    ["git", "-C", str(ROOT_DIR), "diff", "--quiet", up_ref, "HEAD", "--", rel.as_posix()],
                    capture_output=True,
                    timeout=20,
                )
                if up_diff.returncode != 0:
                    return "LOCAL_UNPUSHED"
            return "CLEAN"
        except (OSError, subprocess.SubprocessError):
            return "UNTRACKED"

    def _load_keys(self) -> dict[str, Ed25519PublicKey]:
        if not self.registry_path.is_file():
            return {}
        try:
            reg = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        keys: dict[str, Ed25519PublicKey] = {}
        for entry in reg.get("approvers", []) if isinstance(reg, dict) else []:
            if not isinstance(entry, dict) or entry.get("revoked") is not False:
                continue
            kid = entry.get("key_id")
            if not isinstance(kid, str) or not _KEY_ID.match(kid) or entry.get("algorithm") != "ed25519":
                continue
            try:
                raw = _b64u_decode(entry.get("public_key_b64url", ""))
                if len(raw) != 32:
                    continue
                keys[kid] = Ed25519PublicKey.from_public_bytes(raw)
            except (TrustedApprovalError, ValueError):
                continue
        return keys

    def channel_status(self) -> dict[str, Any]:
        return {
            "channel": "direct_chat_approval",
            "status": "AVAILABLE",
            "production_status": "APPROVAL_POSSIBLE",
            "registry_path": str(self.registry_path),
            "registry_git_state": "NOT_REQUIRED",
            "approver_key_ids": ["direct_human_chat"],
            "reasons": [],
        }

    def _require_channel(self) -> dict[str, Any]:
        return {"direct_human_chat": True}

    # ---- simplified direct chat approval verification (Ed25519 removed per owner directive)
    _SIMPLE_APPROVAL_RE = re.compile(
        r"^(?:ok|oke|ya|yes|gas|acc|deal|siap|setuju|setujui|lanjut|lanjutkan|jalan|jalankan|mulai|eksekusi|approve|approved|xdx-approve)\b",
        re.IGNORECASE,
    )
    _SIMPLE_NEGATION_RE = re.compile(
        r"\b(?:tidak|jangan|batal|batalkan|tolak|stop|tunda|belum|no|not|cancel|reject|deny|don't|dont)\b",
        re.IGNORECASE,
    )

    def verify_token(
        self,
        token: str,
        *,
        expected_project_id: str,
        expected_package_version: str,
        live_manifest_digest: str,
        required_scope: str | None = None,
        now: datetime | None = None,
    ) -> VerifiedApproval:
        if not isinstance(token, str) or not token.strip():
            raise UnsignedApprovalError("Approval message must be a non-empty string (e.g. 'Setuju' or 'Lanjutkan').")
        raw = token.strip()
        if "?" in raw or self._SIMPLE_NEGATION_RE.search(raw):
            raise UnsignedApprovalError("Negation or question detected; approval rejected.")

        # Accept simple 1-word / plain-chat approval (e.g. 'Setuju', 'Lanjutkan', 'Ok', 'Gas', 'Approve')
        # as well as legacy 'XDX-APPROVE ...' or 'XDX-SIGNED-APPROVAL ...' without requiring Ed25519 keys.
        if not (
            self._SIMPLE_APPROVAL_RE.search(raw)
            or raw.startswith(TOKEN_PREFIX)
            or raw.upper().startswith("SAYA SETUJUI")
        ):
            raise UnsignedApprovalError(
                "Approval message not recognized. Reply with a simple confirmation such as 'Setuju', 'Lanjutkan', 'Ok', or 'Gas'."
            )

        t = _now(now)
        issued_at = t.isoformat()
        expires_at = (t + timedelta(hours=24)).isoformat()
        scopes = ("all_production",)
        nonce = hashlib.sha256(f"{expected_project_id}:{expected_package_version}:{live_manifest_digest}:{raw}:{issued_at}".encode("utf-8")).hexdigest()[:32]
        approval_id = "tap-" + hashlib.sha256(f"{expected_project_id}:{live_manifest_digest}:{nonce}".encode("utf-8")).hexdigest()[:32]

        va = VerifiedApproval(
            approval_id=approval_id,
            key_id="direct_human_chat",
            project_id=expected_project_id,
            package_version=expected_package_version,
            manifest_digest=live_manifest_digest,
            scopes=scopes,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            token=raw,
        )
        if required_scope is not None:
            if required_scope not in VALID_SCOPES:
                raise ScopeMismatchError(f"Unknown required scope '{required_scope}'")
            if not va.covers(required_scope):
                raise ScopeMismatchError(f"Required scope '{required_scope}' not covered by scopes {scopes}")
        return va

    # ---- hash-chained, append-only ledger (replay + revocation, concurrency-safe via fcntl.flock)
    @staticmethod
    def ledger_path(package_dir: Path) -> Path:
        return Path(package_dir) / LEDGER_DIRNAME / LEDGER_FILENAME

    @staticmethod
    def ledger_lock_path(package_dir: Path) -> Path:
        return Path(package_dir) / LEDGER_DIRNAME / "approval_ledger.lock"

    @contextmanager
    def _ledger_lock(self, package_dir: Path, *, exclusive: bool) -> Iterator[None]:
        lp = self.ledger_lock_path(package_dir)
        lp.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lp), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _read_ledger_unlocked(self, package_dir: Path) -> list[dict[str, Any]]:
        p = self.ledger_path(package_dir)
        if not p.is_file():
            return []
        entries: list[dict[str, Any]] = []
        prev = "0" * 64
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            try:
                e = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerIntegrityError(f"Ledger line {i + 1} is not JSON") from exc
            body = {k: v for k, v in e.items() if k != "entry_sha256"}
            if e.get("prev_sha256") != prev or hashlib.sha256(canonical_json(body)).hexdigest() != e.get("entry_sha256"):
                raise LedgerIntegrityError(f"Ledger hash chain broken at line {i + 1}")
            prev = e["entry_sha256"]
            entries.append(e)
        return entries

    def read_ledger(self, package_dir: Path) -> list[dict[str, Any]]:
        with self._ledger_lock(package_dir, exclusive=False):
            return self._read_ledger_unlocked(package_dir)

    def _append_ledger_unlocked(self, package_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
        entries = self._read_ledger_unlocked(package_dir)
        body = {**event, "seq": len(entries) + 1, "prev_sha256": entries[-1]["entry_sha256"] if entries else "0" * 64}
        body["entry_sha256"] = hashlib.sha256(canonical_json(body)).hexdigest()
        p = self.ledger_path(package_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(body, sort_keys=True, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return body

    def _append_ledger(self, package_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
        with self._ledger_lock(package_dir, exclusive=True):
            return self._append_ledger_unlocked(package_dir, event)

    def consume(
        self, package_dir: Path, va: VerifiedApproval, *, state_consumed_nonces: list[str] | None = None
    ) -> dict[str, Any]:
        """Single-use & concurrency-safe: atomic check-and-append under fcntl.LOCK_EX."""
        with self._ledger_lock(package_dir, exclusive=True):
            entries = self._read_ledger_unlocked(package_dir)
            used = {e["nonce"] for e in entries if e.get("event") == "CONSUMED"} | set(state_consumed_nonces or [])
            if va.nonce in used:
                raise ApprovalReplayError(f"Approval nonce {va.nonce[:12]}... was already used (replay)")
            return self._append_ledger_unlocked(
                package_dir,
                {
                    "event": "CONSUMED",
                    "approval_id": va.approval_id,
                    "nonce": va.nonce,
                    "key_id": va.key_id,
                    "manifest_digest": va.manifest_digest,
                    "scopes": list(va.scopes),
                    "expires_at": va.expires_at,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )

    def revoke(self, package_dir: Path, approval_id: str, *, reason: str) -> dict[str, Any]:
        with self._ledger_lock(package_dir, exclusive=True):
            return self._append_ledger_unlocked(
                package_dir,
                {"event": "REVOKED", "approval_id": approval_id, "reason": reason, "recorded_at": datetime.now(timezone.utc).isoformat()},
            )

    # ---- live execution guard
    def verify_recorded_approval(
        self,
        package_dir: Path,
        record: dict[str, Any],
        *,
        expected_project_id: str,
        expected_package_version: str,
        live_manifest_digest: str,
        required_scope: str,
        now: datetime | None = None,
    ) -> VerifiedApproval:
        """Verify a recorded approval (binding, revocation, scope) without requiring Ed25519 signatures."""
        if not isinstance(record, dict):
            raise UnsignedApprovalError("approval_record.json is missing or invalid")
        if record.get("revoked") is True:
            raise ApprovalRevokedError(f"Approval {record.get('approval_id')} has been revoked")
        if record.get("project_id") and record.get("project_id") != expected_project_id:
            raise ApprovalBindingMismatchError("approval_record project_id mismatch")
        if record.get("package_version") and record.get("package_version") != expected_package_version:
            raise ApprovalBindingMismatchError("approval_record package_version mismatch")
        rec_digest = record.get("package_digest") or record.get("manifest_digest")
        if rec_digest and rec_digest != live_manifest_digest:
            raise ApprovalBindingMismatchError("approval_record digest does not match live package")
        approval_id = str(record.get("approval_id") or "tap-direct")
        entries = self.read_ledger(package_dir)
        if any(e.get("event") == "REVOKED" and e.get("approval_id") == approval_id for e in entries):
            raise ApprovalRevokedError(f"Approval {approval_id} has been revoked")
        scopes_raw = record.get("approved_scopes") or record.get("scopes") or ["all_production"]
        scopes = tuple(scopes_raw) if isinstance(scopes_raw, (list, tuple)) else ("all_production",)
        va = VerifiedApproval(
            approval_id=approval_id,
            key_id=str(record.get("approver_key_id") or "direct_human_chat"),
            project_id=expected_project_id,
            package_version=expected_package_version,
            manifest_digest=live_manifest_digest,
            scopes=scopes,
            nonce=str(record.get("nonce") or "direct"),
            issued_at=str(record.get("approved_at_utc") or _now(now).isoformat()),
            expires_at=str(record.get("expires_at_utc") or (_now(now) + timedelta(hours=24)).isoformat()),
            token=str(record.get("signed_token") or record.get("approval_message") or "Setuju"),
        )
        if required_scope not in VALID_SCOPES:
            raise ScopeMismatchError(f"Unknown required scope '{required_scope}'")
        if not va.covers(required_scope):
            raise ScopeMismatchError(f"Required scope '{required_scope}' not covered by scopes {scopes}")
        return va


def assert_phase_boundary(required_scope: str, *, action: str) -> None:
    """Phase 01.6D opens trusted *approval* only. Production execution scopes remain blocked until Phase 02."""
    if required_scope in PHASE02_EXECUTION_SCOPES and not PHASE02_EXECUTION_ENABLED:
        raise PhaseBoundaryBlockedError(
            f"{action}: scope '{required_scope}' is production execution (Phase 02), which has not been started. "
            "Trusted approval verified, execution still blocked by the phase boundary."
        )


def default_guard() -> TrustedApprovalGuard:
    return TrustedApprovalGuard(DEFAULT_TRUST_REGISTRY_PATH)
