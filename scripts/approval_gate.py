#!/usr/bin/env python3
"""v3.4 Fail-Closed Approval Gate CLI (compatible with v3.1/v3.3 CLI flags).

Enforces structured explicit approval verification, actor_role=='human_user', TTL,
revocation checks, and live SHA-256 package digest validation.
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
    parser.add_argument("--check", action="store_true", help="Verify approval_record.json fail-closed against live SHA-256.")
    parser.add_argument("--strict-schema", action="store_true", help="Validate all JSON schemas (enabled by default in v3.4).")
    args = parser.parse_args()

    try:
        gate = ApprovalGate()
        res = gate.inspect_package(args.package, check_record=args.check)
        print(json.dumps(res))
        return 0 if res["status"] in {"WAITING_APPROVAL", "RECORD_MATCH_ONLY"} else 2
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
