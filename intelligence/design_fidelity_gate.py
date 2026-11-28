"""Silhouette fidelity gate for Blender character/prop renders (original implementation).

Compares a reference image (usually RGBA, transparent background) with a render using an
ALPHA-AWARE foreground mask. Lesson from the design-os-3d-blender audit: flattening a transparent
render onto RGB turns the background black, so a naive mask covers the whole frame and a shifted
silhouette still scores ~100% IoU. Here the mask comes from alpha when present, else from distance
to the corner/background colour. Diagnostic only; a PASS also needs Independent Visual QC.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

DEFAULT_IOU_PASS = 0.85  # stylised chibi vs hand-drawn art; stricter for hard-surface props


def foreground_mask(im: Image.Image, bg_tolerance: int = 24) -> np.ndarray:
    rgba = im.convert("RGBA")
    a = np.asarray(rgba)[:, :, 3]
    if a.min() < 255:  # real transparency
        return a > 127
    rgb = np.asarray(rgba)[:, :, :3].astype(int)
    corners = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    bg = np.median(corners, axis=0)
    return (np.abs(rgb - bg).max(axis=2) > bg_tolerance)


def _crop_to_box(mask: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return mask, None
    return mask, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def silhouette_report(ref_path: str | Path, render_path: str | Path, *, iou_pass: float = DEFAULT_IOU_PASS,
                      align: str = "bbox") -> dict[str, Any]:
    """align='bbox' scales/translates the render's silhouette bbox onto the reference bbox (proportion
    check, independent of framing); align='none' requires identical framing (pixel check)."""
    with Image.open(ref_path) as r, Image.open(render_path) as q:
        ref, ren = r.copy(), q.copy()
    mr, mq = foreground_mask(ref), foreground_mask(ren)
    br, bq = _crop_to_box(mr)[1], _crop_to_box(mq)[1]
    if br is None or bq is None:
        return {"verdict": "FAIL", "reason": "empty foreground mask", "iou": 0.0}
    if align == "bbox":
        cr = Image.fromarray((mr[br[1]:br[3], br[0]:br[2]] * 255).astype("uint8"))
        cq = Image.fromarray((mq[bq[1]:bq[3], bq[0]:bq[2]] * 255).astype("uint8")).resize(cr.size, Image.NEAREST)
        a, b = np.asarray(cr) > 127, np.asarray(cq) > 127
        aspect_err = abs((bq[2] - bq[0]) / (bq[3] - bq[1]) - (br[2] - br[0]) / (br[3] - br[1]))
    else:
        if ref.size != ren.size:
            ren = ren.resize(ref.size, Image.LANCZOS)
            mq = foreground_mask(ren)
        a, b, aspect_err = mr, mq, 0.0
    inter, union = int(np.logical_and(a, b).sum()), int(np.logical_or(a, b).sum())
    iou = inter / union if union else 0.0
    return {
        "iou": round(iou, 4), "aspect_error": round(float(aspect_err), 4), "align": align,
        "threshold": iou_pass, "verdict": "PASS_GEOMETRY_ONLY" if iou >= iou_pass and aspect_err < 0.08 else "FAIL",
        "note": "Geometry-only diagnostic; production PASS needs Independent Visual QC on real renders.",
    }
