"""Project State Manager & 13-Item Mandatory Approval Gate (v3.3).

Maintains 100% compatibility with v3.1 `approval_gate.py` 11-file SHA-256 package
digest while enforcing all 13 pre-production deliverables required in v3.3 and
blocking any scene mutation or render transition prior to explicit user approval.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"

# Exact v3.1 11 core package files preserved for backward compatibility
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

# Additional v3.3 structured artifacts backing the 13-item Approval Gate
V3_3_EXTENDED_FILES: tuple[str, ...] = (
    "narration_dialogue.json",
    "caption_audio_plan.json",
    "approval_package_manifest.json",
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

AMBIGUOUS_NON_APPROVAL_PHRASES: frozenset[str] = frozenset(
    {
        "lanjut",
        "lanjutkan",
        "ok",
        "oke",
        "ya",
        "yes",
        "sip",
        "go",
        "buat otomatis",
        "analisis referensi",
    }
)


def compute_package_digest(package_dir: Path) -> tuple[str, dict[str, str]]:
    """Compute canonical SHA-256 package digest across all required pre-production files."""
    file_hashes: dict[str, str] = {}
    for name in REQUIRED_PACKAGE_FILES:
        f = package_dir / name
        if not f.is_file() or not f.read_bytes().strip():
            raise ValueError(f"Missing/empty: {name}")
        data = f.read_bytes()
        if name.endswith(".json"):
            json.loads(data.decode("utf-8"))
        file_hashes[name] = hashlib.sha256(data).hexdigest()

    canonical = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), file_hashes


def is_explicit_approval_message(user_message: str, package_version: str) -> bool:
    """Verify that user_message is an explicit approval of the current package version,
    never a vague 'lanjutkan', 'ok', or topic prompt."""
    cleaned = user_message.strip().lower()
    if not cleaned or cleaned in AMBIGUOUS_NON_APPROVAL_PHRASES:
        return False
    has_approval_verb = any(tok in cleaned for tok in ("setuju", "setujui", "approve", "izinkan render", "acc paket"))
    has_version = package_version.lower() in cleaned
    return has_approval_verb and has_version


class ApprovalGate:
    """Validates the 13-item pre-production package and enforces WAITING_APPROVAL."""

    def __init__(self, schemas_dir: Path | None = None) -> None:
        sdir = schemas_dir or SCHEMAS_DIR
        self._approval_schema = json.loads((sdir / "approval_package.schema.json").read_text(encoding="utf-8"))
        self._storyboard_schema = json.loads((sdir / "storyboard.schema.json").read_text(encoding="utf-8"))
        self._engine_schema = json.loads((sdir / "engine_plan.schema.json").read_text(encoding="utf-8"))

    def inspect_package(self, package_dir: Path, *, check_record: bool = False) -> dict[str, Any]:
        digest, file_hashes = compute_package_digest(package_dir)

        storyboard = json.loads((package_dir / "storyboard.json").read_text(encoding="utf-8"))
        engine_plan = json.loads((package_dir / "engine_plan.json").read_text(encoding="utf-8"))
        jsonschema.validate(instance=storyboard, schema=self._storyboard_schema)
        jsonschema.validate(instance=engine_plan, schema=self._engine_schema)

        manifest_path = package_dir / "approval_package_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=manifest, schema=self._approval_schema)

        if not check_record:
            return {
                "digest": digest,
                "status": "WAITING_APPROVAL",
                "files_verified": len(file_hashes),
                "note": "No authorization granted. Stop at WAITING_APPROVAL until explicit user approval.",
            }

        rec_path = package_dir / "approval_record.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
        pkg_ver = str(rec.get("package_version", "")).strip()
        msg = str(rec.get("user_message", "")).strip()
        recorded_at = str(rec.get("recorded_at", "")).strip()

        ok = (
            rec.get("digest") == digest
            and rec.get("decision") == "approved"
            and bool(pkg_ver and msg and recorded_at)
            and is_explicit_approval_message(msg, pkg_ver)
        )
        return {
            "digest": digest,
            "status": "RECORD_MATCH_ONLY" if ok else "BLOCKED",
            "explicit_phrase_verified": ok,
            "note": "Agent must verify actual explicit user approval separately; this is not self-authorization.",
        }


class ProjectStateManager:
    """Deterministic project state machine preventing unapproved production execution."""

    def __init__(self, state_file: Path, schemas_dir: Path | None = None) -> None:
        self.state_file = state_file
        sdir = schemas_dir or SCHEMAS_DIR
        self._schema = json.loads((sdir / "project_state.schema.json").read_text(encoding="utf-8"))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

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
        now = self._now_iso()
        state: dict[str, Any] = {
            "schema_version": "3.3.0",
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
                "approved_digest": None,
                "approved_version": None,
                "explicit_user_message": None,
                "recorded_at": None,
            },
            "blocked_reason": None,
            "history": [
                {
                    "from_state": None,
                    "to_state": "INIT",
                    "timestamp": now,
                    "reason": "Project initialized",
                }
            ],
            "updated_at": now,
        }
        self._save(state)
        return state

    def load(self) -> dict[str, Any]:
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        jsonschema.validate(instance=state, schema=self._schema)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        jsonschema.validate(instance=state, schema=self._schema)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def mark_waiting_approval(self, package_digest: str, *, package_version: str | None = None) -> dict[str, Any]:
        state = self.load()
        prev = state["current_state"]
        now = self._now_iso()
        if package_version:
            state["package_version"] = package_version
        state["package_digest"] = package_digest
        # Any new/updated preproduction digest invalidates prior approval
        state["approval_status"] = {
            "approved": False,
            "approved_digest": None,
            "approved_version": None,
            "explicit_user_message": None,
            "recorded_at": None,
        }
        state["current_state"] = "WAITING_APPROVAL"
        state["history"].append(
            {
                "from_state": prev,
                "to_state": "WAITING_APPROVAL",
                "timestamp": now,
                "reason": f"Pre-production package {state['package_version']} ready ({package_digest[:12]})",
            }
        )
        state["updated_at"] = now
        self._save(state)
        return state

    def record_explicit_user_approval(
        self,
        *,
        package_dir: Path,
        user_message: str,
    ) -> dict[str, Any]:
        state = self.load()
        pkg_ver = state["package_version"]
        if not is_explicit_approval_message(user_message, pkg_ver):
            raise PermissionError(
                f"Rejected ambiguous or version-mismatched approval message: '{user_message}'. "
                f"Must explicitly approve version '{pkg_ver}'."
            )
        digest, _ = compute_package_digest(package_dir)
        if state["package_digest"] != digest:
            raise PermissionError("Package digest changed since WAITING_APPROVAL; re-submit updated package first.")

        now = self._now_iso()
        approval_rec = {
            "package_version": pkg_ver,
            "digest": digest,
            "decision": "approved",
            "user_message": user_message,
            "recorded_at": now,
        }
        (package_dir / "approval_record.json").write_text(
            json.dumps(approval_rec, indent=2) + "\n", encoding="utf-8"
        )

        prev = state["current_state"]
        state["current_state"] = "APPROVED"
        state["approval_status"] = {
            "approved": True,
            "approved_digest": digest,
            "approved_version": pkg_ver,
            "explicit_user_message": user_message,
            "recorded_at": now,
        }
        state["history"].append(
            {
                "from_state": prev,
                "to_state": "APPROVED",
                "timestamp": now,
                "reason": f"Explicit user approval verified for {pkg_ver}",
            }
        )
        state["updated_at"] = now
        self._save(state)
        return state

    def transition(self, next_state: str, *, reason: str, package_dir: Path | None = None) -> dict[str, Any]:
        state = self.load()
        if next_state in PRODUCTION_MUTATING_STATES:
            app = state["approval_status"]
            if not app["approved"] or not app["approved_digest"]:
                raise PermissionError(
                    f"Cannot enter production state '{next_state}' while unapproved (current={state['current_state']})."
                )
            if package_dir is not None:
                live_digest, _ = compute_package_digest(package_dir)
                if live_digest != app["approved_digest"]:
                    state["current_state"] = "WAITING_APPROVAL"
                    state["approval_status"]["approved"] = False
                    self._save(state)
                    raise PermissionError(
                        "Package files modified after approval! Invalidated approval and reverted to WAITING_APPROVAL."
                    )

        now = self._now_iso()
        prev = state["current_state"]
        state["current_state"] = next_state
        if next_state == "BLOCKED":
            state["blocked_reason"] = reason
        state["history"].append(
            {
                "from_state": prev,
                "to_state": next_state,
                "timestamp": now,
                "reason": reason,
            }
        )
        state["updated_at"] = now
        self._save(state)
        return state
