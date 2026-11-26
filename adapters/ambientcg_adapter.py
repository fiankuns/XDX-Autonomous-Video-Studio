"""ambientCG v2 Public API Adapter for On-Demand CC0 PBR Materials."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

AMBIENTCG_API_URL = "https://ambientcg.com/api/v2/full_json"
USER_AGENT = "XDX-Autonomous-Video-Studio/3.3 (CC0-Targeted-Discovery)"


class AmbientCGAdapter:
    """Searches ambientCG v2 JSON API for CC0 PBR materials with bounded result size."""

    def __init__(self, api_url: str = AMBIENTCG_API_URL, timeout_s: float = 10.0) -> None:
        self.api_url = api_url
        self.timeout_s = timeout_s

    def search_materials(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        clamped = max(1, min(int(limit), 15))
        qs = urllib.parse.urlencode({"q": query, "limit": clamped, "type": "Material"})
        req = urllib.request.Request(
            f"{self.api_url}?{qs}",
            headers={"User-Agent": USER_AGENT},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        found = payload.get("foundAssets", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        for item in found[:clamped]:
            if not isinstance(item, dict):
                continue
            aid = str(item.get("assetId", ""))
            if not aid:
                continue
            results.append(
                {
                    "provider": "ambientCG",
                    "external_id": aid,
                    "name": aid,
                    "type": item.get("dataType", "Material"),
                    "license_spdx": "CC0-1.0",
                    "source_url": f"https://ambientcg.com/view?id={aid}",
                    "tags": item.get("tags", []),
                }
            )
        return results
