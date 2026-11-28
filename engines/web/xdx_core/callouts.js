// Generic callout system (topic-agnostic): a label pill + a thin leader line ending in a small ring ON the part it names.
// Rules (checked by intelligence/callout_contract.py): the ring sits on the named part, the pill sits AWAY from the subject
// (offset along the leader), never over the caption or another label, and animates in as ring -> line -> pill.
import { clamp, easeOut } from "./kit.js";

const COLORS = { warm: "#FF7A45", cool: "#5CC8FF" };
const SVG_NS = "http://www.w3.org/2000/svg";

export function createCallouts({ labelsEl, svgEl, camera, W, H, safe = { top: 150, bottom: 1340, side: 30 } }) {
  const items = [];
  let placed = [];
  function make(text, kind) {
    const el = document.createElement("div");
    el.className = "label " + kind;
    el.textContent = text;
    labelsEl.appendChild(el);
    const g = document.createElementNS(SVG_NS, "g");
    const under = document.createElementNS(SVG_NS, "line");
    const line = document.createElementNS(SVG_NS, "line");
    const ringU = document.createElementNS(SVG_NS, "circle");
    const ring = document.createElementNS(SVG_NS, "circle");
    for (const l of [under, line]) { l.setAttribute("stroke-linecap", "round"); }
    under.setAttribute("stroke", "rgba(14,20,30,0.55)"); under.setAttribute("stroke-width", "10");
    line.setAttribute("stroke", COLORS[kind] || "#fff"); line.setAttribute("stroke-width", "4.5");
    ringU.setAttribute("fill", "none"); ringU.setAttribute("stroke", "rgba(14,20,30,0.55)"); ringU.setAttribute("stroke-width", "10");
    ring.setAttribute("fill", "rgba(255,255,255,0.15)"); ring.setAttribute("stroke", COLORS[kind] || "#fff"); ring.setAttribute("stroke-width", "4.5");
    g.append(under, ringU, line, ring); g.style.opacity = "0"; svgEl.appendChild(g);
    const it = { text, el, g, under, line, ring, ringU };
    items.push(it);
    return it;
  }
  function reset() {
    placed = [];
    for (const it of items) { it.el.style.opacity = "0"; it.g.style.opacity = "0"; }
  }
  // anchor: THREE.Vector3 (world) or {x,y} (screen px). offset: {dx,dy} px from the anchor to the pill centre (pill goes AWAY from the subject).
  function place(it, anchor, offset, alpha) {
    if (alpha <= 0.001) return;
    let ax, ay;
    if (anchor.isVector3) { const p = anchor.clone().project(camera); ax = ((p.x + 1) / 2) * W; ay = ((1 - p.y) / 2) * H; } else { ax = anchor.x; ay = anchor.y; }
    const hw = (it.el.offsetWidth || 300) / 2, hh = (it.el.offsetHeight || 64) / 2;
    const lx = clamp(ax + offset.dx, hw + safe.side, W - hw - safe.side);
    const ly = clamp(ay + offset.dy, safe.top + hh, safe.bottom - hh);
    const a = clamp(alpha), ringP = easeOut(clamp(a * 3)), lineP = easeOut(clamp((a - 0.2) * 2.2)), pillP = clamp((a - 0.5) * 2.4);
    // line from the ring edge to the pill border (ray from the pill centre toward the anchor, clipped to the pill rect)
    const dx = ax - lx, dy = ay - ly, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
    const tRect = Math.min(hw / Math.max(Math.abs(ux), 1e-6), hh / Math.max(Math.abs(uy), 1e-6));
    const sx = lx + ux * tRect, sy = ly + uy * tRect;           // start on the pill border
    const R = 13, ex = ax - ux * R, ey = ay - uy * R;            // end at the ring edge
    const k = lineP;                                               // draws from the ring toward the pill
    const x1 = ex, y1 = ey, x2 = ex + (sx - ex) * k, y2 = ey + (sy - ey) * k;
    for (const l of [it.line, it.under]) { l.setAttribute("x1", x1); l.setAttribute("y1", y1); l.setAttribute("x2", x2); l.setAttribute("y2", y2); }
    for (const c of [it.ring, it.ringU]) { c.setAttribute("cx", ax); c.setAttribute("cy", ay); c.setAttribute("r", R * (0.4 + 0.6 * ringP)); }
    it.g.style.opacity = String(ringP);
    it.el.style.left = `${lx}px`; it.el.style.top = `${ly}px`; it.el.style.opacity = String(pillP);
    placed.push({ text: it.text, alpha: a, anchor: [ax, ay], rect: [lx - hw, ly - hh, lx + hw, ly + hh] });
  }
  return { make, place, reset, report: () => placed.slice() };
}
