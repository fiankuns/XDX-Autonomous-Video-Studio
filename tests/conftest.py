"""Shared pytest configuration for XDX Studio.

Phase 01.6C portability fix (DEF-P016B-017): the reference MP4s are Git LFS objects. A clone made with
``GIT_LFS_SKIP_SMUDGE=1`` (or an audit bundle that excludes them) only has pointer files or nothing.
Tests that genuinely need the real bytes carry ``@pytest.mark.requires_lfs`` and are skipped - not
failed - in that environment. Everything else must pass without the MP4s.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_ROOT = ROOT_DIR / "reference_database"
_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def reference_media_hydrated() -> bool:
    """True only if every registered reference MP4 exists as real bytes of the registered size."""
    reg = json.loads((DB_ROOT / "reference_registry.json").read_text(encoding="utf-8"))
    for entry in reg["references"]:
        p = DB_ROOT / entry["path"]
        if not p.is_file() or p.stat().st_size != int(entry["bytes"]):
            return False
        with p.open("rb") as fh:
            if fh.read(len(_LFS_PREFIX)).startswith(_LFS_PREFIX):
                return False
    return True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if reference_media_hydrated():
        return
    skip = pytest.mark.skip(
        reason="requires_lfs: reference MP4s not hydrated (run `git lfs pull` to enable this test)"
    )
    for item in items:
        if "requires_lfs" in item.keywords:
            item.add_marker(skip)
