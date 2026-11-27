"""Master Director Mode & Specialist Roster Router (Phase 01.6A).

Maps the 10 user command modes from PART 24 to minimal 3-6 specialist rosters,
enforces separation of duties, and pairs every workflow with an independent verifier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestration.agent_registry import AgentRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


class MasterDirectorTaskRouter:
    """Routes user command modes to bounded specialist rosters and independent verifiers."""

    MODE_ALIASES: dict[str, str] = {
        "cari topik": "CARI_TOPIK",
        "cari_topik": "CARI_TOPIK",
        "buat video": "BUAT_VIDEO",
        "buat_video": "BUAT_VIDEO",
        "topik": "BUAT_VIDEO",
        "buat otomatis": "BUAT_OTOMATIS",
        "buat_otomatis": "BUAT_OTOMATIS",
        "analisis referensi": "ANALISIS_REFERENSI",
        "analisis_referensi": "ANALISIS_REFERENSI",
        "gunakan ref": "GUNAKAN_REF",
        "gunakan_ref": "GUNAKAN_REF",
        "gabungkan referensi": "GABUNGKAN_REFERENSI",
        "gabungkan_referensi": "GABUNGKAN_REFERENSI",
        "revisi": "REVISI",
        "setujui paket": "SETUJUI_PAKET",
        "setujui_paket": "SETUJUI_PAKET",
        "lanjutkan project": "LANJUTKAN_PROJECT",
        "lanjutkan_project": "LANJUTKAN_PROJECT",
        "lanjutkan": "LANJUTKAN_PROJECT",
        "audit project": "AUDIT_PROJECT",
        "audit_project": "AUDIT_PROJECT",
    }

    def __init__(self, root_dir: Path | None = None, registry: AgentRegistry | None = None) -> None:
        self.root_dir = (root_dir or ROOT_DIR).resolve()
        self.registry = registry or AgentRegistry(root_dir=self.root_dir)
        self.config = json.loads(
            (self.root_dir / "orchestration" / "master_director_config.json").read_text(encoding="utf-8")
        )

    def normalize_mode(self, raw_mode: str) -> str:
        cleaned = (raw_mode or "").strip()
        upper = cleaned.upper().replace(" ", "_")
        if upper in self.config["user_command_modes"]:
            return upper
        low = cleaned.lower()
        if low in self.MODE_ALIASES:
            return self.MODE_ALIASES[low]
        raise ValueError(
            f"Unsupported command mode '{raw_mode}'. Supported: {sorted(self.config['user_command_modes'])}"
        )

    def build_dispatch_plan(self, command_mode: str) -> dict[str, Any]:
        mode = self.normalize_mode(command_mode)
        spec = self.config["user_command_modes"][mode]
        specialists = list(spec["active_specialists"])
        verifier_id = str(spec["independent_verifier"])

        roster_check = self.registry.validate_active_roster(specialists)
        verifier_role = self.registry.get_role(verifier_id)
        if verifier_role["department"] != "independent_verification_department" or not verifier_role["read_only"]:
            raise ValueError(f"Configured verifier '{verifier_id}' must belong to Independent Verification Department")

        return {
            "command_mode": mode,
            "orchestrator": "master_director",
            "active_specialists": roster_check["active_specialists"],
            "active_specialist_count": roster_check["active_count"],
            "independent_verifier": verifier_id,
            "verifier_requires_fresh_context": verifier_role["requires_fresh_context"],
            "halt_point": spec["halt_point"],
            "auto_authorizes_production": False,
        }
