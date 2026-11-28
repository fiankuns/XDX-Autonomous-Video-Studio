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


# ---------------------------------------------------------------- multi-criteria design gate (02B.3)
def row_width_profile(mask: np.ndarray, bands: int = 12) -> list[float]:
    """Silhouette width per horizontal band, normalised by bbox width (shape/volume independent of framing)."""
    box = _crop_to_box(mask)[1]
    if box is None:
        return [0.0] * bands
    x0, y0, x1, y1 = box
    sub = mask[y0:y1, x0:x1]
    w = max(1, x1 - x0)
    edges = np.linspace(0, sub.shape[0], bands + 1).astype(int)
    out = []
    for i in range(bands):
        band = sub[edges[i]:max(edges[i + 1], edges[i] + 1)]
        cols = band.any(axis=0)
        out.append(round(float(cols.sum()) / w, 4))
    return out


def profile_error(ref_profile: list[float], ren_profile: list[float]) -> float:
    return float(np.mean(np.abs(np.array(ref_profile) - np.array(ren_profile))))


def framing_report(mask: np.ndarray, *, min_margin: float = 0.03, fill: tuple[float, float] = (0.35, 0.92)) -> dict[str, Any]:
    box = _crop_to_box(mask)[1]
    if box is None:
        return {"ok": False, "reason": "empty"}
    h, w = mask.shape
    x0, y0, x1, y1 = box
    margins = {"left": x0 / w, "right": (w - x1) / w, "top": y0 / h, "bottom": (h - y1) / h}
    fill_ratio = max((x1 - x0) / w, (y1 - y0) / h)
    cx_off = abs(((x0 + x1) / 2) / w - 0.5)
    ok = min(margins.values()) >= min_margin and fill[0] <= fill_ratio <= fill[1] and cx_off < 0.2
    return {"ok": bool(ok), "min_margin": round(min(margins.values()), 3), "fill_ratio": round(fill_ratio, 3), "center_offset": round(cx_off, 3)}


def _hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def palette_consistency(im: Image.Image, palette: list[str], mask: np.ndarray, *, tol: float = 70.0) -> dict[str, Any]:
    """Share of foreground pixels within `tol` (RGB distance) of any palette colour + which colours are used."""
    rgb = np.asarray(im.convert("RGB")).astype(float)[mask]
    if rgb.size == 0:
        return {"match_share": 0.0, "used": []}
    pal = np.stack([_hex_rgb(p) for p in palette])
    d = np.linalg.norm(rgb[:, None, :] - pal[None, :, :], axis=2)
    near = d.min(axis=1) <= tol
    used = [palette[i] for i in range(len(palette)) if (d.argmin(axis=1)[near] == i).mean() > 0.01]
    return {"match_share": round(float(near.mean()), 4), "used": used}


def landmark_error(measured: dict[str, tuple[float, float]], ref: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Landmarks must be given in head-frame coordinates (0..1 across head bbox). Mean Euclidean error."""
    keys = [k for k in ref if k in measured]
    if not keys:
        return {"mean_error": None, "missing": list(ref)}
    errs = {k: round(float(np.hypot(measured[k][0] - ref[k][0], measured[k][1] - ref[k][1])), 4) for k in keys}
    return {"mean_error": round(float(np.mean(list(errs.values()))), 4), "per_landmark": errs, "missing": [k for k in ref if k not in measured]}


def hair_region_report(mr: np.ndarray, mq: np.ndarray, *, top_frac: float = 0.22, tol: float = 0.10) -> dict[str, Any]:
    """Hair is judged on its own (top band of the silhouette), never folded into the body outline."""
    def band(m):
        sub, box = _crop_to_box(m)
        if box is None:
            return None
        h = max(1, int(sub.shape[0] * top_frac))
        top = sub[:h]
        return {"w": top.any(axis=0).sum() / max(1, sub.shape[1]), "area": top.sum() / max(1, h * sub.shape[1])}
    a, b = band(mr), band(mq)
    if a is None or b is None:
        return {"ok": None, "reason": "empty mask"}
    err = max(abs(a["w"] - b["w"]), abs(a["area"] - b["area"]))
    return {"ok": bool(err <= tol), "error": round(float(err), 4), "tolerance": tol}


def evaluate_design(ref_path, front_render, *, palette, other_views: dict[str, str] | None = None,
                    ref_views: dict[str, str] | None = None,
                    part_ratios: dict[str, float] | None = None, ref_part_ratios: dict[str, float] | None = None,
                    landmarks: dict | None = None, ref_landmarks: dict | None = None,
                    geometry: dict | None = None, thresholds: dict | None = None) -> dict[str, Any]:
    """Multi-criteria verdict: PASS_AUTOMATED_CHECKS | FAIL | INSUFFICIENT_EVIDENCE.
    - Any failed criterion -> FAIL.
    - Mandatory evidence missing/empty (proportions, landmarks, geometry, each non-front view
      vs a real reference view) -> never PASS; INSUFFICIENT_EVIDENCE.
    - Framing is a technical check only and is NOT similarity evidence.
    - Hair is checked separately from the body silhouette."""
    th = {"iou": 0.80, "profile_err": 0.12, "part_ratio_err": 0.06, "landmark_err": 0.08,
          "palette_share": 0.80, "hair_tol": 0.10, **(thresholds or {})}
    with Image.open(ref_path) as r, Image.open(front_render) as q:
        ref, ren = r.copy(), q.copy()
    mr, mq = foreground_mask(ref), foreground_mask(ren)
    sil = silhouette_report(ref_path, front_render, iou_pass=th["iou"])
    prof = profile_error(row_width_profile(mr), row_width_profile(mq))
    res: dict[str, Any] = {"silhouette": sil, "body_volume_profile_error": round(prof, 4),
                           "framing": framing_report(mq), "material": palette_consistency(ren, palette, mq),
                           "hair": hair_region_report(mr, mq, tol=th["hair_tol"])}
    hard = {"silhouette": sil["verdict"] == "PASS_GEOMETRY_ONLY", "body_volume_profile": prof <= th["profile_err"],
            "technical_framing": res["framing"]["ok"], "palette": res["material"]["match_share"] >= th["palette_share"]}
    missing: list[str] = []
    if res["hair"]["ok"] is None:
        missing.append("hair_region")
    else:
        hard["hair"] = res["hair"]["ok"]
    if part_ratios and ref_part_ratios:
        errs = {k: round(abs(part_ratios[k] - v), 4) for k, v in ref_part_ratios.items() if k in part_ratios}
        res["proportions"] = {"errors": errs}
        if errs:
            hard["proportions"] = max(errs.values()) <= th["part_ratio_err"]
        else:
            missing.append("proportions")
    else:
        missing.append("proportions")
    if landmarks and ref_landmarks:
        res["landmarks"] = landmark_error(landmarks, ref_landmarks)
        if res["landmarks"]["mean_error"] is None or res["landmarks"]["missing"]:
            missing.append("landmarks")
        else:
            hard["landmarks"] = res["landmarks"]["mean_error"] <= th["landmark_err"]
    else:
        missing.append("landmarks")
    views = {}
    for name, path in (other_views or {}).items():
        refp = (ref_views or {}).get(name)
        with Image.open(path) as v:
            m = foreground_mask(v.copy())
        entry: dict[str, Any] = {"framing": framing_report(m)}
        if refp:
            with Image.open(refp) as rv:
                rm = foreground_mask(rv.copy())
            iou = silhouette_report(refp, path, iou_pass=th["iou"])
            entry["silhouette"] = iou
            hard[f"view_{name}_silhouette"] = iou["verdict"] == "PASS_GEOMETRY_ONLY"
        else:
            missing.append(f"view_{name}_reference")
        views[name] = entry
    res["other_views"] = views
    if geometry and geometry.get("objects") != 0 and ("within_budget" in geometry):
        res["geometry"] = {"within_budget": geometry.get("within_budget"), "needs_attention": geometry.get("needs_attention")}
        hard["geometry_integrity"] = bool(geometry["within_budget"]) and not geometry.get("needs_attention")
    else:
        missing.append("geometry")
    res["criteria"] = hard
    res["missing_evidence"] = sorted(set(missing))
    if not all(hard.values()):
        res["verdict"] = "FAIL"
    elif missing:
        res["verdict"] = "INSUFFICIENT_EVIDENCE"
    else:
        res["verdict"] = "PASS_AUTOMATED_CHECKS"
    res["note"] = "Automated checks only. Acceptance also requires Independent Visual Critic on real renders and user approval."
    return res
