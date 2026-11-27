#!/usr/bin/env python3
"""Build the complete Phase 01.6C Independent Audit ZIP Bundle (Section 22).

Includes:
- Baseline commit SHA (632970226c5377e668f560bf106ce27e11eb4e81) & final HEAD commit SHA
- Full source snapshot (excluding .git/, node_modules/, .xdx_memory/, .xdx_cache/, __pycache__/, and large LFS reference_database/**/original.mp4 files, while explicitly INCLUDING tests/fixtures/synthetic.mp4!)
- Complete SHA-256 checksum manifest (SHA256SUMS.json & SHA256SUMS.txt)
- Full git diff 632970226c5377e668f560bf106ce27e11eb4e81..HEAD
- registry/master_audit_defect_registry.json & defect correction evidence
- Full regression test logs separated by tier (unit, integration, mock_test, replay_test, live_evidence)
- Runtime capability, native agent invocation, scheduler, reference cache, memory persistence, and checkpoint recovery reports
- All 4 complete benchmark packages (bench_a, bench_b, bench_c, bench_d) + independent verifier reports
- Remaining limitations & Phase 01.6D implementation plan
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BASELINE_SHA = "632970226c5377e668f560bf106ce27e11eb4e81"
OUT_ZIP = Path("/home/antigravity/XDX_Phase_01_6C_Audit_Bundle.zip")

EXCLUDE_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".xdx_memory",
    ".xdx_cache",
    ".venv",
    "venv",
}


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _should_exclude(rel: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    rel_posix = rel.as_posix()
    # Exclude the two large Git LFS reference MP4 files while keeping tests/fixtures/synthetic.mp4
    if rel_posix.startswith("reference_database/") and rel_posix.endswith("original.mp4"):
        return True
    if rel_posix.endswith((".pyc", ".pyo", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm")):
        return True
    return False


def main() -> int:
    head_sha = _git(["rev-parse", "HEAD"]).strip()
    branch_name = _git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    git_diff_text = _git(["diff", f"{BASELINE_SHA}..HEAD"])
    git_stat_text = _git(["diff", "--stat", f"{BASELINE_SHA}..HEAD"])
    git_log_text = _git(["log", "--oneline", f"{BASELINE_SHA}..HEAD"])

    files_to_pack: list[tuple[Path, str]] = []
    for p in sorted(ROOT_DIR.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT_DIR)
        if _should_exclude(rel):
            continue
        files_to_pack.append((p, f"repo_snapshot/{rel.as_posix()}"))

    checksums: dict[str, dict[str, object]] = {}

    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src_path, arcname in files_to_pack:
            data = src_path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            checksums[arcname] = {"sha256": sha, "bytes": len(data)}
            zf.writestr(arcname, data)

        # Write audit metadata & git diff artifacts at top level of ZIP
        meta_files: dict[str, bytes] = {
            "audit_meta/git_diff_from_baseline.patch": git_diff_text.encode("utf-8"),
            "audit_meta/git_diff_stat.txt": git_stat_text.encode("utf-8"),
            "audit_meta/git_commits_since_baseline.txt": git_log_text.encode("utf-8"),
            "audit_meta/AUDIT_BUNDLE_METADATA.json": (
                json.dumps(
                    {
                        "schema_version": "4.0.0-phase01.6c",
                        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                        "repository": "https://github.com/fiankuns/XDX-Autonomous-Video-Studio",
                        "branch": branch_name,
                        "baseline_commit_sha": BASELINE_SHA,
                        "final_commit_sha": head_sha,
                        "excluded_large_lfs_mp4s": [
                            "reference_database/references/social_satire/REF-001/original.mp4",
                            "reference_database/references/explainer/REF-002-Yakhchal/original.mp4",
                        ],
                        "included_synthetic_fixture_mp4": "repo_snapshot/tests/fixtures/synthetic.mp4",
                        "total_packaged_files_before_checksums": len(checksums) + 3,
                    },
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
        }
        for arcname, data in meta_files.items():
            sha = hashlib.sha256(data).hexdigest()
            checksums[arcname] = {"sha256": sha, "bytes": len(data)}
            zf.writestr(arcname, data)

        # Write deterministic checksum manifests
        sums_txt_lines = [f"{info['sha256']}  {name}" for name, info in sorted(checksums.items())]
        zf.writestr("SHA256SUMS.txt", ("\n".join(sums_txt_lines) + "\n").encode("utf-8"))
        zf.writestr(
            "SHA256SUMS.json",
            (
                json.dumps(
                    {
                        "schema_version": "4.0.0-phase01.6c",
                        "baseline_commit_sha": BASELINE_SHA,
                        "final_commit_sha": head_sha,
                        "total_files": len(checksums),
                        "files": dict(sorted(checksums.items())),
                    },
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
        )

    zip_sha = hashlib.sha256(OUT_ZIP.read_bytes()).hexdigest()
    print(f"BUILT: {OUT_ZIP}")
    print(f"ZIP_BYTES: {OUT_ZIP.stat().st_size}")
    print(f"ZIP_SHA256: {zip_sha}")
    print(f"PACKAGED_FILES: {len(checksums)} (+ SHA256SUMS.txt, SHA256SUMS.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
