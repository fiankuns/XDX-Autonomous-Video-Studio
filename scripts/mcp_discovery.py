#!/usr/bin/env python3
"""Read-Only XDX Blender Studio MCP Discovery CLI (Zero Scene Mutation Guaranteed)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.xdx_mcp_adapter import XDXBlenderMCPAdapter


async def _run(server_url: str | None) -> int:
    adapter = XDXBlenderMCPAdapter(server_url=server_url, read_only=True)
    report = await adapter.discover_capabilities_readonly()
    assert report.scene_mutated is False
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server-url", default=None, help="Optional XDX Streamable HTTP server URL")
    args = p.parse_args()
    return asyncio.run(_run(args.server_url))


if __name__ == "__main__":
    raise SystemExit(main())
