// XDX core: directional flow particle system ("comets" with optional arrow heads). Topic-agnostic.
import * as THREE from "three";
import { clamp, lerp, glowTex, arrowTex } from "./kit.js";

export function createCometsClass({ camera, rnd, W, H }) {
class Comets {
  constructor(parent, n, trail, curveOf, colorOf, size, speed, opts = {}) {
    this.n = n; this.trail = trail; this.curveOf = curveOf; this.colorOf = colorOf;
    this.size = size; this.speed = speed; this.opts = opts;
    this.sprites = [];
    this.group = new THREE.Group(); parent.add(this.group);
    for (let i = 0; i < n; i++) {
      const row = [];
      for (let k = 0; k < trail; k++) {
        const s = new THREE.Sprite(new THREE.SpriteMaterial({
          map: opts.arrows && k === 0 ? arrowTex : glowTex, transparent: true, depthWrite: false, blending: opts.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
        }));
        this.group.add(s); row.push(s);
      }
      this.sprites.push({ row, phase: rnd(), curve: curveOf(i) });
    }
  }
  update(time, fade = 1, boost = 1) {
    const col = new THREE.Color();
    const pa = new THREE.Vector3(), pb = new THREE.Vector3();
    for (let i = 0; i < this.n; i++) {
      const p = this.sprites[i];
      const head = (time * this.speed + p.phase) % 1;
      for (let k = 0; k < this.trail; k++) {
        const t = head - k * (this.opts.gap || 0.018);
        const s = p.row[k];
        if (t < 0) { s.visible = false; continue; }
        s.visible = fade > 0.001;
        s.position.copy(p.curve.getPoint(t));
        const life = Math.min(1, t / 0.08, (1 - t) / 0.08);
        const kf = 1 - k / this.trail;
        let sz = this.size * (0.45 + 0.55 * kf) * (this.opts.grow ? lerp(0.6, 1.6, t) : 1) * boost;
        if (this.opts.arrows && k === 0) {
          sz *= 1.6;
          // orient the arrow head along the on-screen direction of travel
          this.group.localToWorld(pa.copy(p.curve.getPoint(Math.max(0, t - 0.02)))).project(camera);
          this.group.localToWorld(pb.copy(p.curve.getPoint(Math.min(1, t + 0.02)))).project(camera);
          s.material.rotation = Math.atan2((pb.y - pa.y), (pb.x - pa.x) * (W / H));
        }
        s.scale.set(sz, sz, sz);
        col.copy(this.colorOf(i, t));
        s.material.color.copy(col);
        s.material.opacity = clamp(life) * kf * fade * (this.opts.alpha || 0.9);
      }
    }
  }
}
  return Comets;
}
