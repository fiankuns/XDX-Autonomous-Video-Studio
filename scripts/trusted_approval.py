#!/usr/bin/env python3
"""Phase 01.6D Trusted Human Approval CLI.

Human side (run on YOUR device, never inside the agent workspace):
  keygen  --out ~/xdx-keys/me.key --key-id fian-phone-1     -> prints the public-key JSON entry to commit
  sign    --key ~/xdx-keys/me.key --key-id fian-phone-1 --package projects/<id> --scopes all_production
          [--ttl-hours 24]                                    -> prints 'XDX-SIGNED-APPROVAL ...' token

Anyone (read-only):
  status                                                      -> trusted channel status (AVAILABLE / UNAVAILABLE)
  digest  --package projects/<id>                             -> canonical manifest digest + file list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from governance.canonical_manifest import build_canonical_manifest, manifest_digest  # noqa: E402
from governance.trusted_approval import (  # noqa: E402
    MAX_TTL,
    default_guard,
    generate_approver_keypair,
    sign_approval_token,
)


def _inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(ROOT_DIR.resolve())
        return True
    except ValueError:
        return False


def _package_identity(pkg: Path) -> tuple[str, str]:
    cfg = json.loads((pkg / "production_config.json").read_text(encoding="utf-8"))
    return str(cfg["project_id"]), str(cfg.get("package_version", "v1"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out", type=Path, required=True)
    k.add_argument("--key-id", required=True)
    k.add_argument("--owner", default="project-owner")
    s = sub.add_parser("sign")
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--key-id", required=True)
    s.add_argument("--package", type=Path, required=True)
    s.add_argument("--scopes", default="all_production")
    s.add_argument("--ttl-hours", type=float, default=24.0)
    sub.add_parser("status")
    d = sub.add_parser("digest")
    d.add_argument("--package", type=Path, required=True)
    a = ap.parse_args()

    if a.cmd == "keygen":
        if _inside_repo(a.out):
            print(json.dumps({"status": "REFUSED", "error": "Private key must be stored OUTSIDE the repository."}))
            return 2
        if a.out.exists():
            print(json.dumps({"status": "REFUSED", "error": f"{a.out} already exists"}))
            return 2
        priv, pub = generate_approver_keypair()
        a.out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(a.out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(priv)
        entry = {
            "key_id": a.key_id,
            "algorithm": "ed25519",
            "public_key_b64url": pub,
            "owner": a.owner,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "revoked": False,
        }
        print(json.dumps({"status": "KEY_CREATED", "private_key_path": str(a.out), "registry_entry": entry}, indent=2))
        return 0

    if a.cmd == "sign":
        if _inside_repo(a.key):
            print(json.dumps({"status": "REFUSED", "error": "Refusing to use a private key stored inside the repository."}))
            return 2
        ttl = timedelta(hours=a.ttl_hours)
        if ttl <= timedelta(0) or ttl > MAX_TTL:
            print(json.dumps({"status": "REFUSED", "error": f"ttl must be in (0, {MAX_TTL}]"}))
            return 2
        man = build_canonical_manifest(a.package)
        project_id, version = _package_identity(a.package)
        token = sign_approval_token(
            private_key_raw=a.key.read_bytes(),
            key_id=a.key_id,
            project_id=project_id,
            package_version=version,
            manifest_digest=manifest_digest(man),
            scopes=[x.strip() for x in a.scopes.split(",") if x.strip()],
            ttl=ttl,
        )
        print(token)
        return 0

    if a.cmd == "status":
        st = default_guard().channel_status()
        print(json.dumps(st, indent=2))
        return 0 if st["status"] == "AVAILABLE" else 3

    man = build_canonical_manifest(a.package)
    print(json.dumps({"manifest_digest": manifest_digest(man), "files": man["files"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
