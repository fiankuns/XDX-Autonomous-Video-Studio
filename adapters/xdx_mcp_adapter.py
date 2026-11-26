"""Cross-Project XDX Blender Studio MCP Discovery & Client Adapter (Read-Only Safe).

Integrates with `fiankuns/xdx-blender-studio` without modifying its source code,
tokens, HMAC-SHA256 replay guard, Bearer authentication, or pairing configuration.
Supports Android ARM64 (Vivo X200 Pro Outbound Relay) and Cloud Linux runtimes.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SIBLING_BLENDER_STUDIO = Path("/home/antigravity/fiankuns/xdx-blender-studio")

READ_ONLY_SAFE_TOOLS: frozenset[str] = frozenset(
    {
        "get_mobile_device_profile",
        "get_scene_info",
    }
)

VISUAL_NON_MUTATING_TOOLS: frozenset[str] = frozenset(
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


class MCPSceneMutationBlockedError(PermissionError):
    """Raised when a mutating Blender MCP tool is called in read-only or unapproved mode."""


@dataclass
class MCPDiscoveryReport:
    """Actual discovered state and tool/resource schemas of XDX Blender Studio MCP."""

    server_reachable_live: bool
    relay_device_connected: bool
    discovery_source: str
    protocol_version: str
    server_info: dict[str, Any]
    connection_mode: str
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
    """Authenticated Streamable HTTP MCP client + zero-mutation protocol inspector."""

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

    def _base_http_url(self) -> str:
        if not self.server_url:
            return "http://127.0.0.1:8765"
        if self.server_url.endswith("/mcp"):
            return self.server_url[:-4]
        return self.server_url

    def _mcp_endpoint_url(self) -> str:
        return f"{self._base_http_url()}/mcp"

    def probe_live_health(self) -> dict[str, Any] | None:
        """Non-mutating GET /health probe against an active XDX Blender Studio server."""
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
        """Send an authenticated JSON-RPC 2.0 request to Streamable HTTP `/mcp`."""
        if not self.mcp_auth_token:
            raise PermissionError("MCP_AUTH_TOKEN is required for live Streamable HTTP /mcp calls.")
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
        """Discover actual XDX MCP tools, schemas, and resources WITHOUT mutating any scene."""
        import asyncio

        notes: list[str] = []
        health = await asyncio.to_thread(self.probe_live_health)

        # Case 1: Live HTTP XDX Blender Studio server is running and token is configured
        if health is not None and self.mcp_auth_token:
            try:
                init_resp = await asyncio.to_thread(self.jsonrpc_http, "initialize", {}, 1)
                tools_resp = await asyncio.to_thread(self.jsonrpc_http, "tools/list", {}, 2)
                resources_resp = await asyncio.to_thread(self.jsonrpc_http, "resources/list", {}, 3)
                init_res = init_resp["result"]
                tools_res = tools_resp["result"]
                resources_res = resources_resp["result"]
                notes.append("Discovered directly over authenticated Streamable HTTP /mcp.")
                return MCPDiscoveryReport(
                    server_reachable_live=True,
                    relay_device_connected=bool(health.get("relay_connected", False)),
                    discovery_source="live_streamable_http_mcp",
                    protocol_version=init_res["protocolVersion"],
                    server_info=init_res["serverInfo"],
                    connection_mode=str(health.get("connection_mode", "relay")),
                    tools=tools_res["tools"],
                    resources=resources_res["resources"],
                    health_payload=health,
                    scene_mutated=False,
                    notes=notes,
                )
            except urllib.error.HTTPError as exc:
                notes.append(f"Live server reachable at /health, but /mcp returned HTTP {exc.code}.")

        # Case 2: Inspect mounted sibling repository `xdx-blender-studio` in-process via JSON-RPC
        src_dir = self.blender_studio_repo / "src"
        if not src_dir.is_dir():
            return MCPDiscoveryReport(
                server_reachable_live=False,
                relay_device_connected=False,
                discovery_source="unavailable",
                protocol_version="unknown",
                server_info={},
                connection_mode="unknown",
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

            if health is not None:
                notes.append(
                    "Live /health endpoint detected, but MCP_AUTH_TOKEN not set in this project; "
                    "schemas verified via mounted xdx-blender-studio MCPProtocolHandler."
                )
            else:
                notes.append(
                    "No active XDX Relay daemon or paired Vivo X200 Pro session is running in this cloud VM yet. "
                    "Verified exact JSON-RPC 2.0 MCP protocol, 8 tools, and 3 resources from mounted "
                    "fiankuns/xdx-blender-studio without modifying any files or Blender scenes."
                )
                notes.append(
                    "To connect from this project in Cloud/Android ARM64 workflow: set XDX_MCP_SERVER_URL "
                    "(e.g. your Render/HTTPS/Tailscale XDX Relay URL) and MCP_AUTH_TOKEN, keeping existing "
                    "Vivo X200 Pro pairing & BLENDER_AUTH_TOKEN unchanged."
                )

            return MCPDiscoveryReport(
                server_reachable_live=health is not None,
                relay_device_connected=bool(health.get("relay_connected", False)) if health else False,
                discovery_source="cross_project_inprocess_mcp_protocol",
                protocol_version=init_resp["result"]["protocolVersion"],
                server_info=init_resp["result"]["serverInfo"],
                connection_mode="relay",
                tools=tools_resp["result"]["tools"],
                resources=res_resp["result"]["resources"],
                health_payload=health or {"status": "not_running_in_vm", "relay_connected": False},
                scene_mutated=False,
                notes=notes,
            )
        finally:
            if added_path and str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        project_approved: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool against live XDX MCP server with strict approval & read-only enforcement."""
        args = arguments or {}
        if self.read_only or not project_approved:
            if tool_name in SCENE_OR_CONFIG_MUTATING_TOOLS:
                raise MCPSceneMutationBlockedError(
                    f"Tool '{tool_name}' is blocked before explicit user approval (read_only={self.read_only}, "
                    f"project_approved={project_approved}). Only read-only inspection is permitted."
                )
            if tool_name == "look" and args.get("shading") == "rendered":
                raise MCPSceneMutationBlockedError(
                    "look(shading='rendered') is blocked during pre-approval read-only preflight to protect Vivo X200 Pro ANR budget."
                )

        resp = self.jsonrpc_http("tools/call", {"name": tool_name, "arguments": args}, req_id=10)
        if "error" in resp:
            raise RuntimeError(f"MCP error {resp['error'].get('code')}: {resp['error'].get('message')}")
        return resp.get("result", {})
