"""Master Audit Defect Registry Validator & Append-Only Guard (Phase 01.6C — Section 3).

Enforces:
1. Schema compliance against ``schemas/defect_registry.schema.json`` (all 13 mandatory fields).
2. Unique ``defect_id`` values and append-only preservation (no historical defect removal).
3. ``VERIFIED`` status is STRICTLY rejected unless ``regression_test`` points to an existing test
   file (and existing test function name when ``::`` is specified) inside ``tests/`` and ``evidence``
   is substantive.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent

VALID_DEFECT_STATUSES: frozenset[str] = frozenset(
    {"OPEN", "SCHEDULED", "IN_PROGRESS", "FIXED", "VERIFIED", "BLOCKED"}
)


class DefectRegistryValidationError(ValueError):
    """Raised when master_audit_defect_registry.json violates schema, append-only, or VERIFIED test rules."""


class MasterAuditDefectRegistry:
    """Loads, validates, and summarizes ``registry/master_audit_defect_registry.json``."""

    def __init__(self, root_dir: Path | None = None, registry_path: Path | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self.registry_path = registry_path or (self.root_dir / "registry" / "master_audit_defect_registry.json")
        self._schema = json.loads(
            (self.root_dir / "schemas" / "defect_registry.schema.json").read_text(encoding="utf-8")
        )

    def load_and_validate(self, *, previous_defect_ids: set[str] | None = None) -> dict[str, Any]:
        if not self.registry_path.is_file():
            raise FileNotFoundError(f"Master Audit Defect Registry missing: {self.registry_path}")
        doc = json.loads(self.registry_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=doc, schema=self._schema)
        except jsonschema.ValidationError as exc:
            raise DefectRegistryValidationError(f"Defect registry schema violation: {exc.message}") from exc

        seen_ids: set[str] = set()
        for item in doc["defects"]:
            did = item["defect_id"]
            if did in seen_ids:
                raise DefectRegistryValidationError(f"Duplicate defect_id '{did}' in defect registry")
            seen_ids.add(did)

            status = item["current_status"]
            if status not in VALID_DEFECT_STATUSES:
                raise DefectRegistryValidationError(f"Invalid current_status '{status}' on '{did}'")

            if status == "VERIFIED":
                reg_test = item.get("regression_test")
                if not reg_test or not str(reg_test).strip():
                    raise DefectRegistryValidationError(
                        f"Defect '{did}' cannot be marked VERIFIED without a relevant regression_test!"
                    )
                parts = str(reg_test).strip().split("::")
                test_file = self.root_dir / parts[0]
                if not test_file.is_file():
                    raise DefectRegistryValidationError(
                        f"Defect '{did}' is marked VERIFIED, but regression_test file '{parts[0]}' does not exist!"
                    )
                if len(parts) > 1:
                    src = test_file.read_text(encoding="utf-8")
                    fn_name = parts[-1]
                    if f"def {fn_name}" not in src:
                        raise DefectRegistryValidationError(
                            f"Defect '{did}' is marked VERIFIED, but test function '{fn_name}' was not found in '{parts[0]}'!"
                        )

        if previous_defect_ids:
            deleted = sorted(previous_defect_ids - seen_ids)
            if deleted:
                raise DefectRegistryValidationError(
                    f"Append-only violation: historical defect(s) were deleted from registry: {deleted}"
                )

        return doc

    def summary(self) -> dict[str, Any]:
        doc = self.load_and_validate()
        by_status: dict[str, list[str]] = {st: [] for st in sorted(VALID_DEFECT_STATUSES)}
        for d in doc["defects"]:
            by_status[d["current_status"]].append(d["defect_id"])
        return {
            "total_defects": len(doc["defects"]),
            "counts_by_status": {k: len(v) for k, v in by_status.items()},
            "ids_by_status": by_status,
        }
