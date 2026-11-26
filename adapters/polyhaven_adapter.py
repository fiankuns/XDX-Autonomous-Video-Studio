"""Poly Haven CC0 Public REST API Adapter (On-Demand Discovery Only, Never Bulk-Download)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

POLYHAVEN_API_BASE = "https://api.polyhaven.com"
USER_AGENT = "XDX-Autonomous-Video-Studio/3.3 (CC0-Targeted-Discovery)"


class PolyHavenAdapter:
    """Queries api.polyhaven.com for CC0 HDRIs, PBR textures, and 3D models on demand."""

    def __init__(self, base_url: str = POLYHAVEN_API_BASE, timeout_s: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _get_json(self, path: str) -> Any:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={"User-Agent": USER_AGENT},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search_assets(
        self,
        query: str,
        *,
        asset_type: str = "all",
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search Poly Haven catalog metadata and return normalized CC0 asset candidates."""
        if asset_type not in {"all", "hdris", "textures", "models"}:
            raise ValueError(f"Unsupported Poly Haven asset_type: {asset_type}")
        qs = urllib.parse.urlencode({"t": asset_type}) if asset_type != "all" else ""
        catalog = self._get_json(f"/assets?{qs}" if qs else "/assets")
        if not isinstance(catalog, dict):
            return []

        tokens = [t.lower() for t in query.split() if t.strip()]
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for asset_id, meta in catalog.items():
            if not isinstance(meta, dict):
                continue
            haystack = " ".join(
                [
                    asset_id.lower(),
                    str(meta.get("name", "")).lower(),
                    " ".join(str(c).lower() for c in meta.get("categories", [])),
                    " ".join(str(t).lower() for t in meta.get("tags", [])),
                ]
            )
            score = sum(2 if tok in asset_id.lower() else (1 if tok in haystack else 0) for tok in tokens)
            if score > 0 or not tokens:
                scored.append((score, asset_id, meta))

        scored.sort(key=lambda item: (-item[0], -int(item[2].get("download_count", 0))))
        results: list[dict[str, Any]] = []
        for _score, asset_id, meta in scored[: max(1, min(max_results, 20))]:
            results.append(
                {
                    "provider": "Poly Haven",
                    "external_id": asset_id,
                    "name": meta.get("name", asset_id),
                    "type": meta.get("type"),
                    "license_spdx": "CC0-1.0",
                    "source_url": f"https://polyhaven.com/a/{asset_id}",
                    "categories": meta.get("categories", []),
                    "tags": meta.get("tags", []),
                }
            )
        return results
