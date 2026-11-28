"""Load the committed production-technique and error-lesson seeds into a SixPartitionMemoryStore.

The SQLite store itself is never committed (.xdx_memory/); these seeds are the portable, reviewable source of truth.
Only techniques with a verified test status enter ProductionMemory (see ProductionMemory.ALLOWED_VERIFIED_STATUSES).
"""
from __future__ import annotations

import json
from pathlib import Path

from memory.persistent_memory import SixPartitionMemoryStore

SEED_DIR = Path(__file__).resolve().parent / "seed_knowledge"


def load_production_seed(store: SixPartitionMemoryStore, seed_dir: Path = SEED_DIR) -> dict[str, int]:
    tech = json.loads((seed_dir / "production_techniques_v4.json").read_text(encoding="utf-8"))
    errs = json.loads((seed_dir / "error_lessons_v4.json").read_text(encoding="utf-8"))
    for t in tech["techniques"]:
        store.production.record_tested_technique(
            technique_id=t["technique_id"], version_tag=tech["version"], domain=t["domain"], test_status=t["test_status"], payload=t)
    for e in errs["errors"]:
        store.error.record_error(
            project_id=errs["project_id"], error_id=e["error_id"], task_id="PHASE02A", error_category=e["error_category"], payload=e)
    return {"techniques": len(tech["techniques"]), "errors": len(errs["errors"])}
