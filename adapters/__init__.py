"""External Provider & Cross-Project MCP Adapters for XDX Studio v3.3."""

from .ambientcg_adapter import AmbientCGAdapter
from .caption_lipsync_adapter import RhubarbLipSyncAdapter, WhisperCaptionAdapter
from .polyhaven_adapter import PolyHavenAdapter
from .xdx_mcp_adapter import MCPDiscoveryReport, MCPSceneMutationBlockedError, XDXBlenderMCPAdapter

__all__ = [
    "AmbientCGAdapter",
    "MCPDiscoveryReport",
    "MCPSceneMutationBlockedError",
    "PolyHavenAdapter",
    "RhubarbLipSyncAdapter",
    "WhisperCaptionAdapter",
    "XDXBlenderMCPAdapter",
]
