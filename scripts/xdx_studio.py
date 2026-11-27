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
from intelligence.creative_pipeline import SUPPORTED_GENRE_INPUTS, PreProductionPackageBuilder
from intelligence.reference_database_bridge import ReferenceDatabaseBridge
from libraries.loader import PresetLibraryRegistry
from orchestration.agent_registry import AgentRegistry
from orchestration.capability_discovery import RuntimeCapabilityDiscovery
from orchestration.task_router import MasterDirectorTaskRouter
from memory.persistence_probe import (
    StoragePersistenceProbe,
    sync_reference_database_into_knowledge_memory,
)
from memory.persistent_memory import SixPartitionMemoryStore


def cmd_preflight() -> int:
    ffmpeg = FFmpegEngine()
    three = ThreeJSEngine()
    remotion = RemotionEngine()
    mcp_report = asyncio.run(XDXBlenderMCPAdapter(read_only=True).discover_capabilities_readonly())
    ref_bridge = ReferenceDatabaseBridge()
    refs_by_id, _, profiles_by_id = ref_bridge.load_registries()

    payload = {
        "studio_version": "4.0.0-alpha.2",
        "runtimes": {
            "python": sys.version.split()[0],
            "node": shutil.which("node"),
            "chromium": shutil.which("google-chrome") or shutil.which("chromium"),
            "ffmpeg": ffmpeg.version_info(),
            "threejs_ready": three.is_available(),
            "remotion_ready": remotion.is_available(),
            "local_blender_binary": shutil.which("blender"),
        },
        "reference_database": {
            "registered_ids": sorted(refs_by_id),
            "profiles": sorted(profiles_by_id),
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
    agent_schema = json.loads((schemas_dir / "agent_role_contract.schema.json").read_text(encoding="utf-8"))

    for fname in ("dependency_registry.json", "engine_registry.json", "license_registry.json", "repository_registry.json"):
        data = json.loads((reg_dir / fname).read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=dep_schema)

    asset_data = json.loads((reg_dir / "asset_registry.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=asset_data, schema=asset_schema)

    agent_reg_file = reg_dir / "agent_registry_v4.json"
    if agent_reg_file.is_file():
        jsonschema.validate(instance=json.loads(agent_reg_file.read_text(encoding="utf-8")), schema=agent_schema)

    libs = PresetLibraryRegistry()
    libs.load_all(validate=True)

    ref_bridge = ReferenceDatabaseBridge()
    refs_by_id, _, _ = ref_bridge.load_registries()
    verified_refs = [ref_bridge.verify_and_load_reference(rid).reference_id for rid in sorted(refs_by_id)]

    agent_reg = AgentRegistry()
    agent_cust = agent_reg.validate_workspace_customizations()

    from orchestration.defect_registry import MasterAuditDefectRegistry

    defect_summary = MasterAuditDefectRegistry().summary()

    print(
        json.dumps(
            {
                "status": "VALIDATED",
                "studio_version": "4.0.0-alpha.3-phase01.6c",
                "schemas_checked": len(list(schemas_dir.glob("*.schema.json"))),
                "registries_checked": 7 if agent_reg_file.is_file() else 6,
                "master_audit_defect_registry": defect_summary,
                "preset_libraries": libs.summary_stats(),
                "reference_database_verified": verified_refs,
                "multi_agent_foundation": agent_cust,
            },
            indent=2,
        )
    )
    return 0


def cmd_capabilities() -> int:
    print(json.dumps(RuntimeCapabilityDiscovery().discover(), indent=2))
    return 0


def cmd_memory_status() -> int:
    store = SixPartitionMemoryStore()
    sync_info = sync_reference_database_into_knowledge_memory(store)
    integ = store.verify_database_integrity()
    print(json.dumps({"memory_integrity": integ, "reference_index_sync": sync_info}, indent=2))
    return 0


def cmd_persistence_probe() -> int:
    print(json.dumps(StoragePersistenceProbe().generate_tier_report(), indent=2))
    return 0


def cmd_agents(args: argparse.Namespace) -> int:
    router = MasterDirectorTaskRouter()
    if args.mode:
        print(json.dumps(router.build_dispatch_plan(args.mode), indent=2))
        return 0
    reg = AgentRegistry()
    print(json.dumps(reg.data, indent=2))
    return 0


def cmd_references(args: argparse.Namespace) -> int:
    bridge = ReferenceDatabaseBridge()
    ctx = bridge.resolve_context(
        genres=args.genres or [],
        explicit_reference_ids=args.ref_ids,
        include_related=args.include_related_refs,
    )
    summary = {k: v for k, v in ctx.items() if k != "reference_analysis_markdown"}
    print(json.dumps(summary, indent=2))
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
        reference_ids=args.ref_ids,
        include_related_references=args.include_related_refs,
        return_status_on_missing_payload=True,
    )
    if res["status"] == "CREATIVE_PAYLOAD_REQUIRED":
        print(
            json.dumps(
                {
                    "status": "CREATIVE_PAYLOAD_REQUIRED",
                    "project_id": args.project_id,
                    "topic": args.topic,
                    "output_dir": str(args.out),
                    "note": "Authored creative payload required — sample showcase fallback has been removed in Phase 01.6C.",
                },
                indent=2,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": res["status"],
                "package_version": res["package_version"],
                "package_digest": res["package_digest"],
                "selected_reference_ids": res["reference_intelligence"]["selected_reference_ids"],
                "reference_selection_mode": res["reference_intelligence"]["selection_mode"],
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

    sub.add_parser("preflight", help="Inspect runtime availability, Reference Database, and 6-tier XDX MCP status.")
    sub.add_parser("validate-all", help="Validate all schemas, registries, 16 preset libraries, Reference DB, and .agents/ customizations.")
    sub.add_parser("capabilities", help="Inspect 7-tier native multi-agent, model routing, and workspace capabilities.")
    sub.add_parser("memory-status", help="Sync Reference DB KnowledgeMemory index and verify 6-partition SQLite WAL integrity.")
    sub.add_parser("persistence-probe", help="Run live 5-tier storage durability classification & cross-process SQLite proof.")

    p_agents = sub.add_parser("agents", help="Inspect Master Director + 20 specialist contracts or simulate command-mode dispatch.")
    p_agents.add_argument("--mode", default=None, help="Optional user command mode (e.g. BUAT_VIDEO, CARI_TOPIK, AUDIT_PROJECT).")

    p_refs = sub.add_parser("references", help="Resolve Reference Database profiles by genre or explicit reference IDs (read-only).")
    p_refs.add_argument("--genres", nargs="*", choices=SUPPORTED_GENRE_INPUTS, default=["explainer"])
    p_refs.add_argument("--ref-ids", nargs="+", default=None, help="Explicit Reference IDs (e.g. REF-001 REF-002).")
    p_refs.add_argument("--include-related-refs", action="store_true")

    p_plan = sub.add_parser("plan", help="Validate/compile a 13-item pre-production package and stop at WAITING_APPROVAL.")
    p_plan.add_argument("--project-id", required=True)
    p_plan.add_argument("--topic", default=None)
    p_plan.add_argument(
        "--genres",
        nargs="+",
        choices=SUPPORTED_GENRE_INPUTS,
        default=["explainer", "edukasi", "sejarah", "biografi", "komedi_absurd"],
    )
    p_plan.add_argument("--ref-ids", nargs="+", default=None, help="Explicit Reference IDs (e.g. REF-002 or REF-001 REF-002).")
    p_plan.add_argument("--include-related-refs", action="store_true", help="Include optional related reference candidates.")
    p_plan.add_argument("--duration", type=int, default=150)
    p_plan.add_argument("--payload-json", type=Path, default=None, help="Path to structured AI CreativeProductionPayload JSON.")
    p_plan.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "preflight":
        return cmd_preflight()
    if args.command == "validate-all":
        return cmd_validate_all()
    if args.command == "capabilities":
        return cmd_capabilities()
    if args.command == "memory-status":
        return cmd_memory_status()
    if args.command == "persistence-probe":
        return cmd_persistence_probe()
    if args.command == "agents":
        return cmd_agents(args)
    if args.command == "references":
        return cmd_references(args)
    if args.command == "plan":
        return cmd_plan(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
