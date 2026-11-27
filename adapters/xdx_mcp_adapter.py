"""Cross-Project XDX Blender Studio MCP Adapter (v3.4 — Fail-Closed AuthZ & 6-Tier Preflight).

Hardening in v3.4:
- Replaces boolean `project_approved` with live `ExecutionAuthorizationContext` verification
  bound to project_id, package_version, live SHA-256, approved_scopes, TTL, and human_user role.
- Enforces strict Read-Only Allowlist (`get_mobile_device_profile`, `get_scene_info`).
- Rejects any unknown/unclassified MCP tool name fail-closed (`UnclassifiedMCPToolError`).
- Separates 6 distinct MCP verification tiers so `in_process` is never confused with a live
  Vivo X200 Pro Android connection.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.state_and_approval import (
    ApprovalAuthorizationError,
    ApprovalGate,
    ExecutionAuthorizationContext,
)

DEFAULT_SIBLING_BLENDER_STUDIO = Path("/home/antigravity/fiankuns/xdx-blender-studio")

READ_ONLY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "get_mobile_device_profile",
        "get_scene_info",
    }
)

VISUAL_NON_MUTATING_ALLOWLIST: frozenset[str] = frozenset(
    {
        "look",
    }
)

SCENE_OR_CONFIG_MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "execute_blender_code",
        "create_primitive",
        "modify_object",
        "set_material",
        "configure_mobile_guard",
    }
)

KNOWN_CLASSIFIED_TOOLS: frozenset[str] = (
    READ_ONLY_ALLOWLIST | VISUAL_NON_MUTATING_ALLOWLIST | SCENE_OR_CONFIG_MUTATING_TOOLS
)


class MCPSceneMutationBlockedError(PermissionError):
    """Raised when a mutating Blender MCP tool is called without valid live authorization."""


class UnclassifiedMCPToolError(PermissionError):
    """Raised fail-closed when calling an unknown MCP tool that has not been security-classified."""


@dataclass
class MCPVerificationTiers:
    """Explicit 6-tier MCP verification matrix preventing false device-connection claims."""

    source_code_discovery: bool = False
    in_process_protocol_test: bool = False
    local_http_integration_test: bool = False
    live_remote_relay_reachable: bool = False
    live_android_blender_connected: bool = False
    actual_visual_feedback_verified: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "source_code_discovery": self.source_code_discovery,
            "in_process_protocol_test": self.in_process_protocol_test,
            "local_http_integration_test": self.local_http_integration_test,
            "live_remote_relay_reachable": self.live_remote_relay_reachable,
            "live_android_blender_connected": self.live_android_blender_connected,
            "actual_visual_feedback_verified": self.actual_visual_feedback_verified,
        }


@dataclass
class MCPDiscoveryReport:
    """Actual discovered state, 6-tier verification matrix, and schemas of XDX Blender Studio MCP."""

    server_reachable_live: bool
    relay_device_connected: bool
    discovery_source: str
    protocol_version: str
    server_info: dict[str, Any]
    connection_mode: str
    verification_tiers: MCPVerificationTiers = field(default_factory=MCPVerificationTiers)
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    health_payload: dict[str, Any] = field(default_factory=dict)
    android_arm64_workflow_ready: bool = True
    cloud_relay_workflow_ready: bool = True
    scene_mutated: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_reachable_live": self.server_reachable_live,
            "relay_device_connected": self.relay_device_connected,
            "discovery_source": self.discovery_source,
            "protocol_version": self.protocol_version,
            "server_info": self.server_info,
            "connection_mode": self.connection_mode,
            "verification_tiers": self.verification_tiers.to_dict(),
            "tool_names": [t["name"] for t in self.tools],
            "tools": self.tools,
            "resource_uris": [r["uri"] for r in self.resources],
            "resources": self.resources,
            "health_payload": self.health_payload,
            "android_arm64_workflow_ready": self.android_arm64_workflow_ready,
            "cloud_relay_workflow_ready": self.cloud_relay_workflow_ready,
            "scene_mutated": self.scene_mutated,
            "notes": self.notes,
        }


class XDXBlenderMCPAdapter:
    """Authenticated Streamable HTTP MCP client + fail-closed authorization & 6-tier preflight."""

    def __init__(
        self,
        *,
        server_url: str | None = None,
        mcp_auth_token: str | None = None,
        blender_studio_repo: Path | None = None,
        read_only: bool = True,
        timeout_s: float = 10.0,
    ) -> None:
        raw_url = (server_url or os.environ.get("XDX_MCP_SERVER_URL", "")).strip()
        self.server_url = raw_url.rstrip("/") if raw_url else ""
        self.mcp_auth_token = (mcp_auth_token or os.environ.get("MCP_AUTH_TOKEN", "")).strip()
        self.blender_studio_repo = blender_studio_repo or Path(
            os.environ.get("XDX_BLENDER_STUDIO_REPO", str(DEFAULT_SIBLING_BLENDER_STUDIO))
        )
        self.read_only = read_only
        self.timeout_s = timeout_s
        self._session_id: str | None = None
        self._approval_gate = ApprovalGate()

    def _base_http_url(self) -> str:
        if not self.server_url:
            return "http://127.0.0.1:8765"
        if self.server_url.endswith("/mcp"):
            return self.server_url[:-4]
        return self.server_url

    def _is_remote_relay_url(self) -> bool:
        base = self._base_http_url().lower()
        return bool(self.server_url) and not (
            base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
        )

    def _mcp_endpoint_url(self) -> str:
        return f"{self._base_http_url()}/mcp"

    def probe_live_health(self) -> dict[str, Any] | None:
        url = f"{self._base_http_url()}/health"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=min(3.5, self.timeout_s)) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        return None

    def jsonrpc_http(self, method: str, params: dict[str, Any] | None = None, req_id: int = 1) -> dict[str, Any]:
        if not self.mcp_auth_token:
            raise PermissionError("MCP_AUTH_TOKEN environment secret is required for live Streamable HTTP /mcp calls.")
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.mcp_auth_token}",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        req = urllib.request.Request(self._mcp_endpoint_url(), data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self._session_id = sid
            return json.loads(resp.read().decode("utf-8"))

    async def discover_capabilities_readonly(self) -> MCPDiscoveryReport:
        """Discover actual XDX MCP tools, schemas, and 6-tier connectivity WITHOUT mutating any scene."""
        notes: list[str] = []
        src_dir = self.blender_studio_repo / "src"
        has_source = (src_dir / "xdx_blender_studio" / "mcp_protocol.py").is_file()
        tiers = MCPVerificationTiers(source_code_discovery=has_source)

        health = await asyncio.to_thread(self.probe_live_health)
        is_remote = self._is_remote_relay_url()

        if health is not None and self.mcp_auth_token:
            try:
                init_resp = await asyncio.to_thread(self.jsonrpc_http, "initialize", {}, 1)
                tools_resp = await asyncio.to_thread(self.jsonrpc_http, "tools/list", {}, 2)
                resources_resp = await asyncio.to_thread(self.jsonrpc_http, "resources/list", {}, 3)
                init_res = init_resp["result"]
                tools_res = tools_resp["result"]
                resources_res = resources_resp["result"]

                relay_conn = bool(health.get("relay_connected", False))
                tiers.local_http_integration_test = not is_remote
                tiers.live_remote_relay_reachable = is_remote
                tiers.live_android_blender_connected = relay_conn
                tiers.actual_visual_feedback_verified = False

                notes.append(
                    f"Discovered over authenticated Streamable HTTP ({'remote relay' if is_remote else 'local loopback'}). "
                    f"Android Blender session connected: {relay_conn}."
                )
                return MCPDiscoveryReport(
                    server_reachable_live=True,
                    relay_device_connected=relay_conn,
                    discovery_source="live_remote_relay_mcp" if is_remote else "local_http_mcp",
                    protocol_version=init_res["protocolVersion"],
                    server_info=init_res["serverInfo"],
                    connection_mode=str(health.get("connection_mode", "relay")),
                    verification_tiers=tiers,
                    tools=tools_res["tools"],
                    resources=resources_res["resources"],
                    health_payload=health,
                    scene_mutated=False,
                    notes=notes,
                )
            except urllib.error.HTTPError as exc:
                notes.append(f"Live /health reachable, but /mcp returned HTTP {exc.code}.")

        if not has_source:
            return MCPDiscoveryReport(
                server_reachable_live=False,
                relay_device_connected=False,
                discovery_source="unavailable",
                protocol_version="unknown",
                server_info={},
                connection_mode="unknown",
                verification_tiers=tiers,
                scene_mutated=False,
                notes=[f"Neither live server nor sibling repository at {self.blender_studio_repo} found."],
            )

        added_path = False
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
            added_path = True
        try:
            from xdx_blender_studio.mcp_protocol import MCPProtocolHandler  # type: ignore
            from xdx_blender_studio.relay_hub import OutboundRelayHub  # type: ignore

            hub = OutboundRelayHub(command_timeout_s=2.0, poll_timeout_s=1.0)
            handler = MCPProtocolHandler(hub, connection_mode="relay")
            init_resp = await handler.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            tools_resp = await handler.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            res_resp = await handler.handle_jsonrpc({"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}})
            assert init_resp and tools_resp and res_resp
            tiers.in_process_protocol_test = True

            notes.append(
                "HONEST PREFLIGHT STATUS: In-process MCP protocol & source discovery succeeded, "
                "but NO live remote relay URL/secret is configured in this environment and NO Vivo X200 Pro "
                "Android Blender session is actively connected (`live_android_blender_connected: false`)."
            )
            return MCPDiscoveryReport(
                server_reachable_live=health is not None,
                relay_device_connected=False,
                discovery_source="in_process_protocol_only_not_live_device",
                protocol_version=init_resp["result"]["protocolVersion"],
                server_info=init_resp["result"]["serverInfo"],
                connection_mode="relay",
                verification_tiers=tiers,
                tools=tools_resp["result"]["tools"],
                resources=res_resp["result"]["resources"],
                health_payload=health or {"status": "not_running_in_vm", "relay_connected": False},
                scene_mutated=False,
                notes=notes,
            )
        finally:
            if added_path and str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))

    def authorize_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        auth_context: ExecutionAuthorizationContext | None = None,
    ) -> None:
        """Fail-closed authorization gate before dispatching any MCP tool call."""
        args = arguments or {}

        # 1. Fail-closed rejection of unknown/unclassified tools
        if tool_name not in KNOWN_CLASSIFIED_TOOLS:
            raise UnclassifiedMCPToolError(
                f"MCP tool '{tool_name}' is not in KNOWN_CLASSIFIED_TOOLS allowlist; rejected fail-closed."
            )

        # 2. Pure read-only allowlist tools
        if tool_name in READ_ONLY_ALLOWLIST:
            return

        # 3. Visual viewport (`look`): non-rendered shading allowed in non-mutating preflight,
        #    `rendered` shading requires live authorization context & read_only=False
        if tool_name in VISUAL_NON_MUTATING_ALLOWLIST:
            shading = str(args.get("shading", "material")).lower()
            if shading in {"material", "solid", "wireframe"} and not self.read_only:
                if auth_context is None:
                    raise MCPSceneMutationBlockedError(
                        "Calling look() in active mode requires a valid ExecutionAuthorizationContext."
                    )
                self._verify_ctx(auth_context, required_scope="mcp_preflight")
                return
            if shading in {"material", "solid", "wireframe"} and self.read_only:
                return
            # shading == 'rendered' or unknown shading -> requires full authorization!
            if self.read_only or auth_context is None:
                raise MCPSceneMutationBlockedError(
                    "look(shading='rendered') is blocked in read_only mode or without ExecutionAuthorizationContext."
                )
            self._verify_ctx(auth_context, required_scope="style_frame")
            return

        # 4. Scene or configuration mutating tools
        if self.read_only:
            raise MCPSceneMutationBlockedError(
                f"Mutating tool '{tool_name}' blocked because adapter has read_only=True."
            )
        if auth_context is None:
            raise MCPSceneMutationBlockedError(
                f"Mutating tool '{tool_name}' requires a cryptographically verified ExecutionAuthorizationContext "
                "(boolean flags are not accepted)."
            )
        self._verify_ctx(auth_context, required_scope="blender_scene_mutation")

    def _verify_ctx(self, auth_context: ExecutionAuthorizationContext, *, required_scope: str) -> None:
        try:
            self._approval_gate.verify_live_execution_context(auth_context, required_scope=required_scope)
        except (ApprovalAuthorizationError, ValueError) as exc:
            raise MCPSceneMutationBlockedError(f"Live MCP authorization check failed: {exc}") from exc

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        auth_context: ExecutionAuthorizationContext | None = None,
    ) -> dict[str, Any]:
        """Execute an MCP tool ONLY after passing fail-closed classification & live authorization."""
        args = arguments or {}
        self.authorize_tool_call(tool_name, args, auth_context=auth_context)
        resp = self.jsonrpc_http("tools/call", {"name": tool_name, "arguments": args}, req_id=10)
        if "error" in resp:
            raise RuntimeError(f"MCP error {resp['error'].get('code')}: {resp['error'].get('message')}")
        return resp.get("result", {})
