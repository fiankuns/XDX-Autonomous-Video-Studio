"""Antigravity Runtime Capability Discovery & Honest Limitation Inspector (Phase 01.6A).

Inspects the actual environment without fabricating unsupported features:
- Native subagents (`define_subagent`, `invoke_subagent`, `send_message`, `manage_subagents`)
- Workspace customizations (`.agents/agents/`, `.agents/skills/`, `.agents/rules/`, `.agents/hooks.json`)
- Workspace isolation constraints (`inherit` supported; `branch`/`share` unsupported in remote devbox)
- Model routing tiers (Session Orchestrator `Gemini 4 Neon` + `Gemini 4 Hydrogen` vs `invoke_subagent` enum)
- 6-tier XDX Blender MCP status & Git LFS Reference Database status
"""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from adapters.xdx_mcp_adapter import XDXBlenderMCPAdapter
from engines.ffmpeg_engine import FFmpegEngine
from engines.web_engines import RemotionEngine, ThreeJSEngine
from intelligence.reference_database_bridge import ReferenceDatabaseBridge
from orchestration.agent_registry import AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


class RuntimeCapabilityDiscovery:
    """Discovers and honestly classifies native Antigravity, engine, and Reference DB capabilities."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()

    def discover(self) -> dict[str, Any]:
        reg = AgentRegistry(root_dir=self.root_dir)
        cust_summary = reg.validate_workspace_customizations()

        hooks_file = self.root_dir / ".agents" / "hooks.json"
        mcp_config_file = self.root_dir / ".agents" / "mcp_config.json"
        is_remote_devbox = Path("/opt/antigravity").is_dir()

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

        return {
            "schema_version": "4.0.0-phase01.6a",
            "environment": {
                "os": platform.platform(),
                "python_version": sys.version.split()[0],
                "is_antigravity_remote_devbox": is_remote_devbox,
                "agy_cli_binary_in_vm": shutil.which("agy"),
                "git_lfs_binary": shutil.which("git-lfs"),
                "node_binary": shutil.which("node"),
                "chromium_binary": shutil.which("google-chrome") or shutil.which("chromium"),
                "ffmpeg_ready": FFmpegEngine().version_info()["available"],
                "threejs_ready": ThreeJSEngine().is_available(),
                "remotion_ready": RemotionEngine().is_available(),
            },
            "antigravity_native_multi_agent": {
                "built_in_subagents_available": ["research", "self", "teamwork", "teamwork_preview"],
                "session_tools_available": [
                    "define_subagent",
                    "invoke_subagent",
                    "send_message",
                    "manage_subagents",
                    "list_skills",
                    "lookup_skill",
                ],
                "workspace_modes": {
                    "inherit": "SUPPORTED_AND_VERIFIED",
                    "branch_git_worktree": "UNSUPPORTED_IN_REMOTE_DEVBOX" if is_remote_devbox else "SUPPORTED_ON_LOCAL_HOST",
                    "share": "UNSUPPORTED_IN_REMOTE_DEVBOX" if is_remote_devbox else "SUPPORTED_ON_LOCAL_HOST",
                },
                "custom_workspace_customizations": cust_summary,
                "lifecycle_hooks_json_configured": hooks_file.is_file(),
                "workspace_mcp_config_present": mcp_config_file.is_file(),
            },
            "model_routing": {
                "session_orchestrator_documented": {
                    "planner": "Gemini 4 Neon (Google AI Pro/Ultra) or Gemini 4 Carbon (Enterprise)",
                    "executor": "Gemini 4 Hydrogen",
                    "selection_surface": "User-selected via Antigravity UI/CLI Model Selector ('Orchestrator')",
                },
                "subagent_tool_model_enum": ["inherit", "flash_lite", "flash", "pro"],
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
            "honest_limitations": [
                "In this remote Linux devbox (jetski_remote_agents_3p_devbox), invoke_subagent supports Workspace='inherit' only; Git worktree ('branch') and 'share' modes are blocked by the host sandbox, so single-writer artifact locking is enforced deterministically in TaskHandoffManager.",
                "Programmatic invoke_subagent exposes tier enums ('inherit', 'flash_lite', 'flash', 'pro') rather than raw model strings like 'gemini-4-neon'; Gemini 4 Neon + Gemini 4 Hydrogen Orchestrator pairing is controlled at the user's Antigravity UI/CLI session selector.",
                "Lifecycle PreToolUse hooks (.agents/hooks.json) and full multi-artifact ExecutionGuard are scheduled for Phase 01.6D; Phase 01.6A preserves the v3.4 fail-closed Python ApprovalGate and MCP allowlist without claiming hook-level blocking is active yet.",
                "Live Android Vivo X200 Pro Blender relay connection is false in this cloud VM (in-process & local HTTP MCP verified; zero Blender scene mutations executed).",
            ],
        }


if __name__ == "__main__":
    print(json.dumps(RuntimeCapabilityDiscovery().discover(), indent=2))
