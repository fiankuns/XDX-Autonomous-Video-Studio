#!/usr/bin/env python3
"""Phase 01.6D host-agnostic pre-tool Execution Guard hook.

Reads one JSON tool-call event on stdin and exits 0 (allow) or 2 (block, reason on stdout as JSON).

    {"tool_name": "create_primitive", "arguments": {...}, "package_dir": "projects/<id>"}

* Unknown / unclassified MCP tools -> BLOCK.
* Read-only MCP tools -> ALLOW.
* Mutating MCP tools -> ALLOW only if the package has a live trusted approval that passes the central guard
  (signature, canonical manifest, TTL, ledger, revocation, scope) AND the Phase 02 boundary permits it.
  In Phase 01.6D the boundary is closed, so every mutation is blocked.
* Render / scene-write shell commands (blender -b, remotion render, ffmpeg into renders/) -> same rule.

Host wiring (e.g. Antigravity ``.agents/hooks.json``) is intentionally not generated here: the host hook schema
has not been verified in this environment (tracked as DEF-P016D-029).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.xdx_mcp_adapter import XDXBlenderMCPAdapter  # noqa: E402
from intelligence.state_and_approval import ProjectStateManager  # noqa: E402

_RENDER_CMD = re.compile(
    r"("
    r"\bblender\b.*(\s-b\b|--background\b|--python\b)"
    r"|\b(npx\s+)?remotion\s+(render|still|benchmark)\b"
    r"|\bnode\b.*(remotion|three_deterministic|render_threejs|phase02a_render)"
    r"|\b(puppeteer|playwright|chromium|google-chrome)\b.*\b(render|screenshot|mp4|png)\b"
    r"|\bffmpeg\b.*\.(mp4|mov|mkv|webm|png)\b"
    r"|\bffmpeg\b.*projects/[^ ]+/renders/"
    r"|\b(bash|sh|zsh|python3?)\b.*(-c|--command).*(blender|remotion|threejs|ffmpeg|render_production|trusted_approvers)"
    r")",
    re.IGNORECASE,
)
_TRUST_TAMPER_CMD = re.compile(
    r"(registry/trusted_approvers\.json|governance/trusted_approval\.py|scripts/execution_guard_hook\.py)",
    re.IGNORECASE,
)


def decide(event: dict) -> tuple[bool, str]:
    tool = str(event.get("tool_name", ""))
    pkg = event.get("package_dir")
    args = event.get("arguments") or {}
    if tool in {"bash", "shell", "run_command"}:
        cmd = str(args.get("CommandLine") or args.get("command") or "")
        if _TRUST_TAMPER_CMD.search(cmd) and any(
            tok in cmd for tok in (">", "sed ", "tee ", "rm ", "mv ", "cp ", "git add", "git commit", "python", "node")
        ):
            return False, "TrustRegistryTamperBlocked: modifying trust registry or execution guard via shell requires independent human action"
        if not _RENDER_CMD.search(cmd):
            return True, "non-production shell command"
        tool = "execute_blender_code"  # treat render/scene-write commands as guarded production execution
    adapter = XDXBlenderMCPAdapter(read_only=False)
    try:
        try:
            adapter.authorize_tool_call(tool, args, auth_context=None)
            return True, "read-only tool"
        except Exception as first:  # noqa: BLE001 - decide below with a context if possible
            if not pkg:
                return False, f"{type(first).__name__}: {first}"
        pdir = (ROOT_DIR / str(pkg)).resolve() if not Path(str(pkg)).is_absolute() else Path(str(pkg))
        ctx = ProjectStateManager(pdir / "project_state.json").build_authorization_context(pdir)
        adapter.authorize_tool_call(tool, args, auth_context=ctx)
        return True, "trusted approval verified"
    except Exception as exc:  # noqa: BLE001 - fail closed on anything
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"decision": "block", "reason": f"invalid hook event: {exc}"}))
        return 2
    ok, reason = decide(event if isinstance(event, dict) else {})
    print(json.dumps({"decision": "allow" if ok else "block", "reason": reason}))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
