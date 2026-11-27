#!/usr/bin/env python3
"""Unified XDX Autonomous Video Studio v3.4 CLI (`preflight`, `validate-all`, `plan`)."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.xdx_mcp_adapter import XDXBlenderMCPAdapter
from engines.ffmpeg_engine import FFmpegEngine
from engines.web_engines import RemotionEngine, ThreeJSEngine
from intelligence.creative_pipeline import SUPPORTED_GENRES, PreProductionPackageBuilder
from libraries.loader import PresetLibraryRegistry


def cmd_preflight() -> int:
    ffmpeg = FFmpegEngine()
    three = ThreeJSEngine()
    remotion = RemotionEngine()
    mcp_report = asyncio.run(XDXBlenderMCPAdapter(read_only=True).discover_capabilities_readonly())

    payload = {
        "studio_version": "3.4.0",
        "runtimes": {
            "python": sys.version.split()[0],
            "node": shutil.which("node"),
            "chromium": shutil.which("google-chrome") or shutil.which("chromium"),
            "ffmpeg": ffmpeg.version_info(),
            "threejs_ready": three.is_available(),
            "remotion_ready": remotion.is_available(),
            "local_blender_binary": shutil.which("blender"),
        },
        "xdx_mcp": {
            "discovery_source": mcp_report.discovery_source,
            "server_reachable_live": mcp_report.server_reachable_live,
            "relay_device_connected": mcp_report.relay_device_connected,
            "verification_tiers": mcp_report.verification_tiers.to_dict(),
            "discovered_tools": [t["name"] for t in mcp_report.tools],
            "discovered_resources": [r["uri"] for r in mcp_report.resources],
            "scene_mutated": mcp_report.scene_mutated,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_validate_all() -> int:
    schemas_dir = ROOT_DIR / "schemas"
    reg_dir = ROOT_DIR / "registry"

    for sf in sorted(schemas_dir.glob("*.schema.json")):
        jsonschema.Draft202012Validator.check_schema(json.loads(sf.read_text(encoding="utf-8")))

    dep_schema = json.loads((schemas_dir / "dependency_registry.schema.json").read_text(encoding="utf-8"))
    asset_schema = json.loads((schemas_dir / "asset_registry.schema.json").read_text(encoding="utf-8"))

    for fname in ("dependency_registry.json", "engine_registry.json", "license_registry.json", "repository_registry.json"):
        data = json.loads((reg_dir / fname).read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=dep_schema)

    asset_data = json.loads((reg_dir / "asset_registry.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=asset_data, schema=asset_schema)

    libs = PresetLibraryRegistry()
    libs.load_all(validate=True)

    print(
        json.dumps(
            {
                "status": "VALIDATED",
                "studio_version": "3.4.0",
                "schemas_checked": len(list(schemas_dir.glob("*.schema.json"))),
                "registries_checked": 5,
                "preset_libraries": libs.summary_stats(),
            },
            indent=2,
        )
    )
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    authored = None
    if args.payload_json:
        authored = json.loads(args.payload_json.read_text(encoding="utf-8"))

    builder = PreProductionPackageBuilder()
    res = builder.build_waiting_approval_package(
        package_dir=args.out,
        project_id=args.project_id,
        topic=args.topic,
        genres=args.genres,
        target_duration_s=args.duration,
        authored_payload=authored,
    )
    print(
        json.dumps(
            {
                "status": res["status"],
                "package_version": res["package_version"],
                "package_digest": res["package_digest"],
                "approval_command_example": res["approval_command_example"],
                "output_dir": str(args.out),
                "note": "STOPPED AT WAITING_APPROVAL — Do not start rendering before explicit structured user approval.",
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="Inspect runtime availability and 6-tier XDX MCP status.")
    sub.add_parser("validate-all", help="Validate all 11 schemas, 5 registries, and 16 preset libraries.")

    p_plan = sub.add_parser("plan", help="Validate/compile a 13-item pre-production package and stop at WAITING_APPROVAL.")
    p_plan.add_argument("--project-id", required=True)
    p_plan.add_argument("--topic", default=None)
    p_plan.add_argument("--genres", nargs="+", choices=SUPPORTED_GENRES, default=["explainer", "edukasi", "sejarah", "biografi", "komedi_absurd"])
    p_plan.add_argument("--duration", type=int, default=150)
    p_plan.add_argument("--payload-json", type=Path, default=None, help="Path to structured AI CreativeProductionPayload JSON.")
    p_plan.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "preflight":
        return cmd_preflight()
    if args.command == "validate-all":
        return cmd_validate_all()
    if args.command == "plan":
        return cmd_plan(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
