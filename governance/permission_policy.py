"""Default-Deny Agent Permission Policy Engine (Phase 01.6A).

Enforces role-level tool allowlists, read-only verification boundaries, unknown tool rejection,
and pre-approval mutation blocks across Master Director and all 20 Specialist Agents.
Full `.agents/hooks.json` lifecycle `ExecutionGuard` & `ApprovalVerifier` expand on this in Phase 01.6D.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.xdx_mcp_adapter import KNOWN_CLASSIFIED_TOOLS, SCENE_OR_CONFIG_MUTATING_TOOLS
from orchestration.agent_registry import OFFICIAL_ANTIGRAVITY_TOOLS, AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


class PermissionDeniedError(PermissionError):
    """Raised when an agent attempts a tool or MCP call outside its default-deny policy."""


class PermissionPolicyEngine:
    """Evaluates whether a specific agent is permitted to invoke an Antigravity or XDX MCP tool."""

    WRITE_TOOLS: frozenset[str] = frozenset(
        {"write_to_file", "replace_file_content", "multi_replace_file_content"}
    )

    def __init__(self, root_dir: Path | None = None, registry: AgentRegistry | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self.registry = registry or AgentRegistry(root_dir=self.root_dir)

    def check_antigravity_tool(self, agent_id: str, tool_name: str) -> bool:
        if tool_name not in OFFICIAL_ANTIGRAVITY_TOOLS:
            raise PermissionDeniedError(f"Default-deny: unknown Antigravity tool '{tool_name}'")
        role = self.registry.get_role(agent_id)
        if role["read_only"] and tool_name in self.WRITE_TOOLS:
            raise PermissionDeniedError(
                f"Read-only agent '{agent_id}' is strictly forbidden from calling write tool '{tool_name}'"
            )
        if tool_name not in role["allowed_tools"]:
            raise PermissionDeniedError(
                f"Agent '{agent_id}' is not permitted to invoke '{tool_name}'. Allowed: {role['allowed_tools']}"
            )
        return True

    def check_blender_mcp_tool(
        self,
        agent_id: str,
        mcp_tool_name: str,
        *,
        has_live_approval_context: bool = False,
    ) -> bool:
        if mcp_tool_name not in KNOWN_CLASSIFIED_TOOLS:
            raise PermissionDeniedError(f"Default-deny: unclassified Blender MCP tool '{mcp_tool_name}'")

        role = self.registry.get_role(agent_id)
        if mcp_tool_name in SCENE_OR_CONFIG_MUTATING_TOOLS:
            if agent_id != "blender_specialist":
                raise PermissionDeniedError(
                    f"Only 'blender_specialist' may invoke mutating Blender MCP tool '{mcp_tool_name}' (caller='{agent_id}')"
                )
            if role["read_only"] or not has_live_approval_context:
                raise PermissionDeniedError(
                    f"Mutating Blender MCP tool '{mcp_tool_name}' denied without verified human ExecutionAuthorizationContext"
                )
        return True

    def export_permission_matrix(self) -> dict[str, Any]:
        matrix: dict[str, Any] = {}
        for role in [self.registry.data["master_director"], *self.registry.data["specialists"]]:
            aid = role["agent_id"]
            matrix[aid] = {
                "department": role["department"],
                "read_only": role["read_only"],
                "requires_fresh_context": role["requires_fresh_context"],
                "max_concurrent_instances": role["max_concurrent_instances"],
                "allowed_tools": role["allowed_tools"],
                "can_mutate_blender_post_approval": aid == "blender_specialist",
                "can_self_approve": False,
            }
        return matrix
