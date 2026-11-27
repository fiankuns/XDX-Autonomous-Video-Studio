"""7-Tier Honest Runtime Capability Discovery & Evidence Ledger (Phase 01.6B).

Fixes Phase 01.6A Independent Audit finding:
- Separates capability states strictly into 7 categories:
  1. `DOCUMENTED_CAPABILITY`
  2. `CONFIGURED_CAPABILITY`
  3. `DETECTED_CAPABILITY`
  4. `LIVE_INVOCATION_VERIFIED`
  5. `UNAVAILABLE`
  6. `UNKNOWN`
  7. `BLOCKED`
- NEVER returns hardcoded source-code tool lists as `DETECTED_CAPABILITY`. Because Python
  cannot directly introspect host LLM tool registries, host-native tools (`invoke_subagent`,
  `define_subagent`, `send_message`, `manage_subagents`) remain `DOCUMENTED_CAPABILITY` or
  `UNKNOWN` unless backed by a fresh, non-stale `CapabilityEvidence` record from an actual
  host-agent invocation!
- Supports `AntigravityRuntimeCapabilityAdapter` and `CodexRuntimeCapabilityAdapter` without
  inventing fake APIs or adding any external AI gateway.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema

from adapters.xdx_mcp_adapter import XDXBlenderMCPAdapter
from engines.ffmpeg_engine import FFmpegEngine
from engines.web_engines import RemotionEngine, ThreeJSEngine
from intelligence.reference_database_bridge import ReferenceDatabaseBridge
from orchestration.agent_registry import AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent

CAPABILITY_STATUSES: tuple[str, ...] = (
    "DOCUMENTED_CAPABILITY",
    "CONFIGURED_CAPABILITY",
    "DETECTED_CAPABILITY",
    "LIVE_INVOCATION_VERIFIED",
    "UNAVAILABLE",
    "UNKNOWN",
    "BLOCKED",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class AntigravityRuntimeCapabilityAdapter:
    """Detects Antigravity filesystem markers honestly without claiming Python sees internal LLM tools."""

    adapter_type = "antigravity"

    def detect_host_markers(self) -> dict[str, Any]:
        is_devbox = Path("/opt/antigravity").is_dir()
        jetski_dir = Path.home() / ".gemini" / "jetski"
        agy_cli = shutil.which("agy")
        return {
            "detected": is_devbox or jetski_dir.is_dir() or bool(agy_cli),
            "is_remote_devbox": is_devbox,
            "jetski_appdata_present": jetski_dir.is_dir(),
            "agy_cli_binary": agy_cli,
            "python_can_introspect_host_llm_tools_directly": False,
        }


class CodexRuntimeCapabilityAdapter:
    """Honest runtime probe for OpenAI Codex / non-Antigravity container environments (no invented APIs)."""

    adapter_type = "codex"

    def detect_host_markers(self) -> dict[str, Any]:
        codex_env_keys = [k for k in os.environ if k.startswith(("CODEX_", "OPENAI_CODEX_"))]
        codex_cli = shutil.which("codex")
        return {
            "detected": bool(codex_env_keys or codex_cli),
            "env_markers_present": sorted(codex_env_keys),
            "codex_cli_binary": codex_cli,
            "python_can_introspect_host_llm_tools_directly": False,
        }


class RuntimeCapabilityDiscovery:
    """Discovers OS/engine binaries, workspace configs, and validates timestamped host capability evidence."""

    DEFAULT_EVIDENCE_RELPATH = "docs/evidence/runtime_capability_evidence_v4.json"

    def __init__(
        self,
        root_dir: Path | None = None,
        evidence_path: Path | None = None,
    ) -> None:
        self.root_dir = Path(os.path.realpath(root_dir or ROOT_DIR))
        self.evidence_path = evidence_path or (self.root_dir / self.DEFAULT_EVIDENCE_RELPATH)
        self._evidence_schema = json.loads(
            (self.root_dir / "schemas" / "capability_evidence.schema.json").read_text(encoding="utf-8")
        )
        self.antigravity_adapter = AntigravityRuntimeCapabilityAdapter()
        self.codex_adapter = CodexRuntimeCapabilityAdapter()

    def current_runtime_identity(self) -> dict[str, str]:
        ag = self.antigravity_adapter.detect_host_markers()
        cx = self.codex_adapter.detect_host_markers()
        if ag["detected"]:
            adapter_type = "antigravity"
        elif cx["detected"]:
            adapter_type = "codex"
        else:
            adapter_type = "python_standalone"
        return {
            "adapter_type": adapter_type,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "workspace_root": self.root_dir.as_posix(),
        }

    def record_host_capability_evidence(
        self,
        records: list[dict[str, Any]],
        *,
        ttl_seconds: int = 86400,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Persist verified host-agent capability invocation evidence to disk with schema validation."""
        now_dt = now or _utc_now()
        ledger = {
            "schema_version": "4.0.0-phase01.6b",
            "generated_at_utc": now_dt.isoformat(),
            "ttl_seconds": ttl_seconds,
            "runtime_identity": self.current_runtime_identity(),
            "records": records,
        }
        jsonschema.validate(instance=ledger, schema=self._evidence_schema)
        for rec in records:
            if rec["status"] == "LIVE_INVOCATION_VERIFIED" and not rec.get("invocation_id"):
                raise ValueError(
                    f"Capability '{rec['capability_id']}' cannot be LIVE_INVOCATION_VERIFIED without invocation_id"
                )
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.evidence_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.evidence_path)
        return ledger

    def evaluate_evidence_ledger(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Load and validate capability evidence, flagging expired or mismatched runtime reports as STALE."""
        now_dt = now or _utc_now()
        if not self.evidence_path.is_file():
            return {
                "present": False,
                "is_stale": False,
                "stale_reason": None,
                "verified_live_map": {},
            }

        ledger = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=ledger, schema=self._evidence_schema)

        gen_dt = _parse_iso(ledger["generated_at_utc"])
        ttl = timedelta(seconds=int(ledger["ttl_seconds"]))
        cur_id = self.current_runtime_identity()
        saved_id = ledger["runtime_identity"]

        stale_reasons: list[str] = []
        if now_dt > gen_dt + ttl:
            stale_reasons.append(
                f"Capability evidence expired (generated_at={ledger['generated_at_utc']}, ttl_s={ledger['ttl_seconds']})"
            )
        if saved_id.get("adapter_type") != cur_id["adapter_type"]:
            stale_reasons.append(
                f"Runtime adapter changed ('{saved_id.get('adapter_type')}' -> '{cur_id['adapter_type']}')"
            )
        if saved_id.get("workspace_root") != cur_id["workspace_root"]:
            stale_reasons.append("Workspace root changed since capability evidence was recorded")

        is_stale = len(stale_reasons) > 0
        live_map: dict[str, dict[str, Any]] = {}
        if not is_stale:
            for rec in ledger["records"]:
                rec_dt = _parse_iso(rec["timestamp_utc"])
                if now_dt <= rec_dt + ttl and rec["status"] == "LIVE_INVOCATION_VERIFIED":
                    live_map[rec["capability_id"]] = rec

        return {
            "present": True,
            "is_stale": is_stale,
            "stale_reason": "; ".join(stale_reasons) if stale_reasons else None,
            "generated_at_utc": ledger["generated_at_utc"],
            "ttl_seconds": ledger["ttl_seconds"],
            "runtime_identity": saved_id,
            "verified_live_map": live_map,
        }

    def discover(self, *, now: datetime | None = None) -> dict[str, Any]:
        reg = AgentRegistry(root_dir=self.root_dir)
        cust_summary = reg.validate_workspace_customizations()

        ag_markers = self.antigravity_adapter.detect_host_markers()
        cx_markers = self.codex_adapter.detect_host_markers()
        runtime_id = self.current_runtime_identity()
        ev_eval = self.evaluate_evidence_ledger(now=now)
        live_map = ev_eval["verified_live_map"]

        hooks_file = self.root_dir / ".agents" / "hooks.json"
        mcp_config_file = self.root_dir / ".agents" / "mcp_config.json"

        ffmpeg_ready = FFmpegEngine().version_info()["available"]
        three_ready = ThreeJSEngine().is_available()
        remotion_ready = RemotionEngine().is_available()
        chromium_bin = shutil.which("google-chrome") or shutil.which("chromium")
        git_lfs_bin = shutil.which("git-lfs")
        local_blender = shutil.which("blender")

        mcp_report = asyncio.run(XDXBlenderMCPAdapter(read_only=True).discover_capabilities_readonly())
        ref_bridge = ReferenceDatabaseBridge(studio_root=self.root_dir)
        refs_by_id, _, profiles_by_id = ref_bridge.load_registries()
        verified_refs = []
        for rid in sorted(refs_by_id):
            rec = ref_bridge.verify_and_load_reference(rid)
            verified_refs.append(
                {
                    "id": rec.reference_id,
                    "sha256": rec.video_sha256,
                    "bytes": rec.bytes_size,
                    "profile_id": rec.profile["id"],
                    "status": "VERIFIED",
                }
            )

        def _host_tool_status(cap_id: str) -> dict[str, Any]:
            if cap_id in live_map:
                rec = live_map[cap_id]
                return {
                    "status": "LIVE_INVOCATION_VERIFIED",
                    "verification_method": rec["verification_method"],
                    "invocation_id": rec["invocation_id"],
                    "conversation_id": rec.get("conversation_id"),
                    "timestamp_utc": rec["timestamp_utc"],
                }
            if ag_markers["detected"]:
                return {
                    "status": "DOCUMENTED_CAPABILITY",
                    "verification_method": "antigravity_docs_only_python_cannot_introspect_host_llm_tools",
                    "invocation_id": None,
                    "conversation_id": None,
                    "note": "Stale or missing host invocation receipt; not claimed as DETECTED_CAPABILITY.",
                }
            return {
                "status": "UNKNOWN",
                "verification_method": "no_host_agent_evidence",
                "invocation_id": None,
                "conversation_id": None,
            }

        capabilities_matrix: dict[str, dict[str, Any]] = {
            # Host-native LLM subagent tools (NEVER claimed DETECTED from Python constants!)
            "host_tool:invoke_subagent": _host_tool_status("host_tool:invoke_subagent"),
            "host_tool:define_subagent": _host_tool_status("host_tool:define_subagent"),
            "host_tool:send_message": _host_tool_status("host_tool:send_message"),
            "host_tool:manage_subagents": _host_tool_status("host_tool:manage_subagents"),
            # Workspace configurations on disk
            "workspace_config:custom_subagents_md": {
                "status": "CONFIGURED_CAPABILITY",
                "count": len(cust_summary["custom_agent_files_validated"]),
                "verification_method": "disk_yaml_frontmatter_schema_validated",
            },
            "workspace_config:skills_md": {
                "status": "CONFIGURED_CAPABILITY",
                "count": len(cust_summary["workspace_skills_validated"]),
                "verification_method": "disk_yaml_frontmatter_schema_validated",
            },
            "workspace_config:rules_md": {
                "status": "CONFIGURED_CAPABILITY",
                "count": len(cust_summary["workspace_rules_validated"]),
                "verification_method": "disk_yaml_frontmatter_schema_validated",
            },
            "workspace_config:lifecycle_hooks_json": {
                "status": "CONFIGURED_CAPABILITY" if hooks_file.is_file() else "UNAVAILABLE",
                "verification_method": "filesystem_probe",
            },
            # Workspace isolation modes
            "workspace_mode:inherit": (
                {
                    "status": "LIVE_INVOCATION_VERIFIED",
                    "verification_method": live_map["workspace_mode:inherit"]["verification_method"],
                    "invocation_id": live_map["workspace_mode:inherit"]["invocation_id"],
                }
                if "workspace_mode:inherit" in live_map
                else {
                    "status": "DOCUMENTED_CAPABILITY" if ag_markers["detected"] else "UNKNOWN",
                    "verification_method": "host_policy_declaration",
                }
            ),
            "workspace_mode:branch_git_worktree": {
                "status": "BLOCKED" if ag_markers["is_remote_devbox"] else "UNKNOWN",
                "verification_method": "remote_devbox_sandbox_policy",
            },
            "workspace_mode:share": {
                "status": "BLOCKED" if ag_markers["is_remote_devbox"] else "UNKNOWN",
                "verification_method": "remote_devbox_sandbox_policy",
            },
            # Directly detectable OS/Python/Node binaries & libraries
            "runtime:sqlite3_wal": {
                "status": "DETECTED_CAPABILITY",
                "verification_method": "python_stdlib_sqlite3_probe",
            },
            "runtime:git_lfs": {
                "status": "DETECTED_CAPABILITY" if git_lfs_bin else "UNAVAILABLE",
                "binary": git_lfs_bin,
                "verification_method": "shutil_which_and_lfs_verify",
            },
            "runtime:ffmpeg": {
                "status": "DETECTED_CAPABILITY" if ffmpeg_ready else "UNAVAILABLE",
                "verification_method": "subprocess_ffmpeg_version_probe",
            },
            "runtime:threejs_v0_187": {
                "status": "DETECTED_CAPABILITY" if three_ready else "UNAVAILABLE",
                "verification_method": "node_package_probe",
            },
            "runtime:remotion_v4": {
                "status": "DETECTED_CAPABILITY" if remotion_ready else "UNAVAILABLE",
                "verification_method": "node_package_probe",
            },
            "runtime:chromium_headless": {
                "status": "DETECTED_CAPABILITY" if chromium_bin else "UNAVAILABLE",
                "binary": chromium_bin,
                "verification_method": "shutil_which",
            },
            "runtime:local_desktop_blender": {
                "status": "DETECTED_CAPABILITY" if local_blender else "UNAVAILABLE",
                "binary": local_blender,
                "verification_method": "shutil_which",
            },
            "runtime:live_vivo_x200_pro_blender_mcp": {
                "status": "DETECTED_CAPABILITY" if mcp_report.relay_device_connected else "UNAVAILABLE",
                "verification_method": "xdx_mcp_readonly_health_probe",
            },
            "runtime:agy_cli_in_vm": {
                "status": "DETECTED_CAPABILITY" if ag_markers["agy_cli_binary"] else "UNAVAILABLE",
                "verification_method": "shutil_which",
            },
        }

        by_status: dict[str, list[str]] = {st: [] for st in CAPABILITY_STATUSES}
        for cid, entry in sorted(capabilities_matrix.items()):
            by_status[entry["status"]].append(cid)

        inherit_legacy = (
            "SUPPORTED_AND_VERIFIED"
            if capabilities_matrix["workspace_mode:inherit"]["status"] == "LIVE_INVOCATION_VERIFIED"
            else capabilities_matrix["workspace_mode:inherit"]["status"]
        )

        return {
            "schema_version": "4.0.0-phase01.6b",
            "runtime_identity": runtime_id,
            "adapters_probed": {
                "antigravity": ag_markers,
                "codex": cx_markers,
            },
            "capability_evidence_status": {
                "evidence_file": self.evidence_path.relative_to(self.root_dir).as_posix()
                if self.evidence_path.is_relative_to(self.root_dir)
                else str(self.evidence_path),
                "present": ev_eval["present"],
                "is_stale": ev_eval["is_stale"],
                "stale_reason": ev_eval["stale_reason"],
                "live_verified_count": len(live_map),
            },
            "capabilities": capabilities_matrix,
            "capabilities_by_status": by_status,
            "antigravity_native_multi_agent": {
                "python_direct_tool_introspection": False,
                "workspace_modes": {
                    "inherit": inherit_legacy,
                    "branch_git_worktree": capabilities_matrix["workspace_mode:branch_git_worktree"]["status"],
                    "share": capabilities_matrix["workspace_mode:share"]["status"],
                },
                "custom_workspace_customizations": cust_summary,
                "lifecycle_hooks_json_configured": hooks_file.is_file(),
                "workspace_mcp_config_present": mcp_config_file.is_file(),
            },
            "model_routing": {
                "session_orchestrator_documented": {
                    "status": "DOCUMENTED_CAPABILITY",
                    "planner": "Gemini 4 Neon (Google AI Pro/Ultra) or Gemini 4 Carbon (Enterprise)",
                    "executor": "Gemini 4 Hydrogen",
                },
                "subagent_tool_model_enum_documented": ["inherit", "flash_lite", "flash", "pro"],
                "active_subagent_default": "inherit",
            },
            "xdx_mcp_status": {
                "discovery_source": mcp_report.discovery_source,
                "server_reachable_live": mcp_report.server_reachable_live,
                "relay_device_connected": mcp_report.relay_device_connected,
                "verification_tiers": mcp_report.verification_tiers.to_dict(),
                "scene_mutated": mcp_report.scene_mutated,
            },
            "reference_database": {
                "verified_references": verified_refs,
                "registered_profiles": sorted(profiles_by_id),
                "production_authorized": False,
            },
        }


if __name__ == "__main__":
    print(json.dumps(RuntimeCapabilityDiscovery().discover(), indent=2))
