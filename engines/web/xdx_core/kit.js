// XDX core kit: deterministic math/material helpers shared by every procedural scene (topic-agnostic).
// Every function is pure or only touches the objects passed in; randomness comes only from mulberry32(seed).
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const seg = (f, a, b) => clamp((f - a) / (b - a));
export const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t) => 1 - Math.pow(1 - t, 3);
export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const v3 = (x, y, z) => new THREE.Vector3(x, y, z);

export function canvasTex(w, h, draw, repeat) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}
export function noiseFill(g, w, h, base, amp, n, seed) {
  const r = mulberry32(seed);
  g.fillStyle = base; g.fillRect(0, 0, w, h);
  for (let i = 0; i < n; i++) {
    const a = (r() - 0.5) * amp;
    g.fillStyle = a > 0 ? `rgba(255,255,255,${a})` : `rgba(0,0,0,${-a})`;
    g.fillRect(r() * w, r() * h, 1 + r() * 3, 1 + r() * 3);
  }
}
export const std = (color, roughness = 0.6, metalness = 0, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
export function mesh(geo, mat, pos, parent, opts = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.copy(pos);
  m.castShadow = opts.cast !== false;
  m.receiveShadow = opts.receive !== false;
  if (parent) parent.add(m);
  return m;
}
export const rbox = (w, h, d, r = 0.02, s = 3) => new RoundedBoxGeometry(w, h, d, s, Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4));
export const capsule = (r, len) => new THREE.CapsuleGeometry(r, len, 6, 16);

export const glowTex = canvasTex(128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,1)");
  gr.addColorStop(0.35, "rgba(255,255,255,0.75)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});

export const arrowTex = canvasTex(128, 128, (g) => {
  g.translate(64, 64);
  g.shadowColor = "rgba(255,255,255,0.9)"; g.shadowBlur = 10;
  g.fillStyle = "#ffffff";
  g.beginPath(); g.moveTo(46, 0); g.lineTo(-10, -34); g.lineTo(-2, -12); g.lineTo(-40, -12); g.lineTo(-40, 12); g.lineTo(-2, 12); g.lineTo(-10, 34); g.closePath(); g.fill();
});
