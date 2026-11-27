"""Phase 01.6D canonical SHA-256 manifest of every production-input artifact in a package.

Rules (fail-closed):
1. Every regular file under the package directory is hashed - there is no allow-list of "important" files,
   so narration, captions, character/style bibles, camera, semantic storyboard, research and reference
   adaptation (and anything added later) are always covered.
2. Only runtime/state files that legitimately change after approval are excluded (``RUNTIME_EXCLUDED_*``).
   ``approval_package_manifest.json`` is excluded because it *presents* the digest (it would be circular).
3. ``REQUIRED_PRODUCTION_INPUTS`` must all exist, be non-empty, and (for .json) parse.
4. Symlinks, special files and paths escaping the package directory are rejected.
5. Canonical form: UTF-8 JSON, sorted keys, no whitespace, POSIX relative paths; digest = SHA-256 of it.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "xdx.canonical-package-manifest.v1"

REQUIRED_PRODUCTION_INPUTS: tuple[str, ...] = (
    # v3.4 core
    "blueprint.md",
    "script.md",
    "storyboard.json",
    "asset_manifest.json",
    "character_bible.md",
    "motion_plan.json",
    "execution_plan.md",
    "production_config.json",
    "engine_plan.json",
    "research.md",
    "reference_analysis.md",
    # Phase 01.6D: previously NOT covered by the approval digest
    "narration_dialogue.json",
    "caption_audio_plan.json",
    "character_bible.json",
    "style_bible.json",
    "camera_plan.json",
    "semantic_visual_plan.json",
    "research_report.json",
    "reference_adaptation.json",
)

RUNTIME_EXCLUDED_FILES: frozenset[str] = frozenset(
    {
        "project_state.json",
        "project_state_v4.json",
        "approval_record.json",
        "approval_package_manifest.json",
        "canonical_manifest.json",
        ".DS_Store",
    }
)
RUNTIME_EXCLUDED_SUFFIXES: tuple[str, ...] = (".lock", ".tmp", ".pyc")
# Any directory component starting with "." is runtime (.checkpoints, .revisions, .reviews, .approvals ...)


class CanonicalManifestError(ValueError):
    """Raised when a package cannot produce a trustworthy canonical manifest."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_runtime_excluded(rel_posix: str) -> bool:
    parts = rel_posix.split("/")
    if any(p.startswith(".") for p in parts[:-1]):
        return True
    name = parts[-1]
    if name in RUNTIME_EXCLUDED_FILES or name.endswith(RUNTIME_EXCLUDED_SUFFIXES):
        return True
    return "__pycache__" in parts


def build_canonical_manifest(package_dir: Path) -> dict[str, Any]:
    root = Path(package_dir)
    if not root.is_dir():
        raise CanonicalManifestError(f"Package directory not found: {root}")
    if root.is_symlink():
        raise CanonicalManifestError(f"Package directory must not be a symlink: {root}")
    real_root = Path(os.path.realpath(root))

    files: dict[str, dict[str, Any]] = {}
    for dirpath, dirnames, filenames in os.walk(real_root, followlinks=False):
        dpath = Path(dirpath)
        for dname in list(dirnames):
            if (dpath / dname).is_symlink():
                rel = (dpath / dname).relative_to(real_root).as_posix()
                if not is_runtime_excluded(rel + "/x"):
                    raise CanonicalManifestError(f"Symlinked directory not allowed in package: {rel}")
                dirnames.remove(dname)
        for fname in filenames:
            fpath = dpath / fname
            rel = fpath.relative_to(real_root).as_posix()
            if is_runtime_excluded(rel):
                continue
            st = os.lstat(fpath)
            if stat.S_ISLNK(st.st_mode):
                raise CanonicalManifestError(f"Symlink not allowed in package: {rel}")
            if not stat.S_ISREG(st.st_mode):
                raise CanonicalManifestError(f"Non-regular file not allowed in package: {rel}")
            files[rel] = {"sha256": _sha256_file(fpath), "bytes": st.st_size}

    missing = [n for n in REQUIRED_PRODUCTION_INPUTS if n not in files]
    if missing:
        raise CanonicalManifestError(f"Missing/empty: {', '.join(missing)}")
    for name in REQUIRED_PRODUCTION_INPUTS:
        data = (real_root / name).read_bytes()
        if not data.strip():
            raise CanonicalManifestError(f"Missing/empty: {name}")
        if name.endswith(".json"):
            try:
                json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CanonicalManifestError(f"Invalid JSON in production input {name}: {exc}") from exc

    return {
        "schema": MANIFEST_SCHEMA,
        "files": dict(sorted(files.items())),
        "required_inputs": list(REQUIRED_PRODUCTION_INPUTS),
    }


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def manifest_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def compute_canonical_package_digest(package_dir: Path) -> tuple[str, dict[str, str]]:
    """Return (digest, {relpath: sha256}) over every production-input artifact."""
    man = build_canonical_manifest(package_dir)
    return manifest_digest(man), {k: v["sha256"] for k, v in man["files"].items()}
