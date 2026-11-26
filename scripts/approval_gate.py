#!/usr/bin/env python3
"""v3.3 Approval Gate CLI (100% backward-compatible with v3.1 `scripts/approval_gate.py`).

Detects plan edits, validates JSON schemas & 13-item manifest, and checks approval_record.json.
NOT proof of identity, quality, or self-authorization.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from intelligence.state_and_approval import ApprovalGate, REQUIRED_PACKAGE_FILES, compute_package_digest

REQUIRED = REQUIRED_PACKAGE_FILES


def digest(p: Path) -> str:
    d, _ = compute_package_digest(p)
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--check", action="store_true", help="Verify approval_record.json against current SHA-256 digest.")
    parser.add_argument("--strict-schema", action="store_true", help="Also run full v3.3 JSON Schema validation.")
    args = parser.parse_args()

    try:
        if args.strict_schema:
            gate = ApprovalGate()
            res = gate.inspect_package(args.package, check_record=args.check)
            print(json.dumps(res))
            return 0 if res["status"] in {"WAITING_APPROVAL", "RECORD_MATCH_ONLY"} else 2

        d = digest(args.package)
        if not args.check:
            print(json.dumps({"digest": d, "status": "WAITING_APPROVAL", "note": "No authorization granted"}))
            return 0

        f = args.package / "approval_record.json"
        r = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        ok = (
            r.get("digest") == d
            and r.get("decision") == "approved"
            and all(isinstance(r.get(k), str) and r[k].strip() for k in ("user_message", "recorded_at", "package_version"))
        )
        print(
            json.dumps(
                {
                    "digest": d,
                    "status": "RECORD_MATCH_ONLY" if ok else "BLOCKED",
                    "note": "Agent must verify actual explicit user approval separately; this is not authorization.",
                }
            )
        )
        return 0 if ok else 2
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
