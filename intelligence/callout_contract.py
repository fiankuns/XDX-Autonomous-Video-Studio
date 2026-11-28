"""Callout contract (topic-agnostic): every label is a pill + leader line + small ring ON the part it names.

Checked per sampled frame from scene probes (no pixels): the pill must not cover the caption, another pill, or the part it
names; the leader must be long enough to be visible; everything must stay inside the frame. See engines/web/xdx_core/callouts.js.
"""

from __future__ import annotations

import math
from typing import Any

W, H = 1080, 1920
MIN_LEADER_PX = 70
ANCHOR_MARGIN_PX = 24


def _overlap(a: list[float], b: list[float], pad: float = 0.0) -> bool:
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _gap_to_rect(p: list[float], r: list[float]) -> float:
    dx = max(r[0] - p[0], 0, p[0] - r[2])
    dy = max(r[1] - p[1], 0, p[1] - r[3])
    return math.hypot(dx, dy)


def evaluate_callouts(probes: dict[int, dict[str, Any]], min_alpha: float = 0.85) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    checked = 0

    def add(code: str, label: str, frame: int, msg: str) -> None:
        if (code, label) not in seen:  # one entry per label and defect keeps the report readable
            seen.add((code, label))
            issues.append({"code": code, "severity": "critical", "label": label, "first_frame": frame, "message": f"{label}: {msg} (frame {frame})"})

    for f in sorted(probes):
        pr = probes[f]
        cap = pr.get("caption_rect")
        items = [c for c in pr.get("callouts", []) if c["alpha"] >= min_alpha]
        for i, c in enumerate(items):
            checked += 1
            r, a = c["rect"], c["anchor"]
            if r[0] < 0 or r[2] > W or r[1] < 0 or r[3] > H or not (0 <= a[0] <= W and 0 <= a[1] <= H):
                add("CALLOUT_OFF_FRAME", c["text"], f, "pill or ring outside the frame")
            if cap and _overlap(r, cap, 6):
                add("CALLOUT_OVER_CAPTION", c["text"], f, "pill overlaps the caption box")
            if _gap_to_rect(a, r) < ANCHOR_MARGIN_PX:
                add("CALLOUT_COVERS_PART", c["text"], f, f"pill sits on the part it names (ring {_gap_to_rect(a, r):.0f}px from the pill)")
            elif _gap_to_rect(a, r) < MIN_LEADER_PX:
                add("CALLOUT_LEADER_TOO_SHORT", c["text"], f, f"leader line only {_gap_to_rect(a, r):.0f}px long")
            for d in items[i + 1:]:
                if _overlap(r, d["rect"], 8):
                    add("CALLOUT_OVERLAP", c["text"] + "|" + d["text"], f, "two pills overlap")
    return {"schema": "xdx.callout-verification.v1", "status": "BLOCKED" if issues else "OK", "checked_label_frames": checked, "issues": issues}
