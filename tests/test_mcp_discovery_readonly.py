"""Tests for Cross-Project XDX Blender Studio MCP Discovery & Zero-Mutation Guarantee."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import unittest
from pathlib import Path

import uvicorn

from adapters.xdx_mcp_adapter import (
    MCPSceneMutationBlockedError,
    SCENE_OR_CONFIG_MUTATING_TOOLS,
    XDXBlenderMCPAdapter,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
BLENDER_STUDIO_REPO = Path(
    os.environ.get("XDX_BLENDER_STUDIO_REPO", str(ROOT_DIR.parent / "xdx-blender-studio"))
)
EXPECTED_8_TOOLS = {
    "get_mobile_device_profile",
    "get_scene_info",
    "look",
    "execute_blender_code",
    "create_primitive",
    "modify_object",
    "set_material",
    "configure_mobile_guard",
}
EXPECTED_3_RESOURCES = {
    "ui://mcp-for-blender/viewport-v2",
    "xdx://device/profile",
    "xdx://scene/summary",
}


class CrossProjectMCPDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_inprocess_readonly_discovery_and_mutation_guard(self) -> None:
        adapter = XDXBlenderMCPAdapter(blender_studio_repo=BLENDER_STUDIO_REPO, read_only=True)
        report = await adapter.discover_capabilities_readonly()

        self.assertFalse(report.scene_mutated)
        if (BLENDER_STUDIO_REPO / "src" / "xdx_blender_studio" / "mcp_protocol.py").is_file():
            self.assertEqual({t["name"] for t in report.tools}, EXPECTED_8_TOOLS)
            self.assertEqual({r["uri"] for r in report.resources}, EXPECTED_3_RESOURCES)
        else:
            self.assertEqual(report.discovery_source, "unavailable")

        for tool_name in SCENE_OR_CONFIG_MUTATING_TOOLS:
            with self.assertRaises(MCPSceneMutationBlockedError):
                adapter.call_tool(tool_name, {}, auth_context=None)

        with self.assertRaises(MCPSceneMutationBlockedError):
            adapter.call_tool("look", {"shading": "rendered"}, auth_context=None)

    async def test_live_streamable_http_cross_project_discovery_without_touching_repo(self) -> None:
        src_dir = BLENDER_STUDIO_REPO / "src"
        if not (src_dir / "xdx_blender_studio" / "server.py").is_file():
            adapter = XDXBlenderMCPAdapter(blender_studio_repo=BLENDER_STUDIO_REPO, read_only=True)
            report = await adapter.discover_capabilities_readonly()
            self.assertFalse(report.server_reachable_live)
            self.assertFalse(report.scene_mutated)
            return
        added = False
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
            added = True

        try:
            from xdx_blender_studio.config import StudioConfig  # type: ignore
            from xdx_blender_studio.security import generate_strong_token  # type: ignore
            from xdx_blender_studio.server import create_app  # type: ignore

            mcp_tok = generate_strong_token(24)
            blender_tok = generate_strong_token(24)
            port = 18875
            cfg = StudioConfig(
                transport="streamable-http",
                http_host="127.0.0.1",
                http_port=port,
                connection_mode="relay",
                mcp_auth_token=mcp_tok,
                blender_auth_token=blender_tok,
            )
            app = create_app(cfg)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
            task = asyncio.create_task(server.serve())
            for _ in range(40):
                if server.started:
                    break
                await asyncio.sleep(0.05)

            try:
                adapter = XDXBlenderMCPAdapter(
                    server_url=f"http://127.0.0.1:{port}",
                    mcp_auth_token=mcp_tok,
                    read_only=True,
                )
                report = await adapter.discover_capabilities_readonly()
                self.assertTrue(report.server_reachable_live)
                self.assertFalse(report.relay_device_connected)
                self.assertEqual(report.discovery_source, "local_http_mcp")
                self.assertTrue(report.verification_tiers.local_http_integration_test)
                self.assertFalse(report.verification_tiers.live_remote_relay_reachable)
                self.assertFalse(report.verification_tiers.live_android_blender_connected)
                self.assertEqual({t["name"] for t in report.tools}, EXPECTED_8_TOOLS)
                self.assertFalse(report.scene_mutated)
            finally:
                server.should_exit = True
                await task
        finally:
            if added and str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))

        # Prove zero files were modified or untracked in fiankuns/xdx-blender-studio
        git_check = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(BLENDER_STUDIO_REPO),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(git_check.stdout.strip(), "")
