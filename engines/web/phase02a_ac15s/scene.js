// XDX Phase 02A visual engine (VISUAL_ONLY_BENCHMARK) for bench_p02a_ac_15s — Three.js 0.187.0, SwiftShader-safe.
// Deterministic: every frame is a pure function of the frame index (seeded PRNG only, no wall clock).
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

await document.fonts.load("800 60px PJS");
await document.fonts.load("700 26px PJS");

const W = 1080, H = 1920, FPS = 30;
// Shot ranges and caption cues come from the signed package (storyboard.json + caption_audio_plan.json),
// injected by scripts/render_phase02a_visual.py as window.__XDX_PACKAGE. The choreography below is authored for
// bench_p02a_ac_15s, so the shot ranges must match exactly or the scene refuses to render.
const PKG = window.__XDX_PACKAGE;
const EXPECTED_SHOTS = [["S001", 0, 105], ["S002", 105, 210], ["S003", 210, 330], ["S004", 330, 450]];
if (!PKG || PKG.project_id !== "bench_p02a_ac_15s") throw new Error("XDX package data missing or not bench_p02a_ac_15s");
if (JSON.stringify(PKG.shots) !== JSON.stringify(EXPECTED_SHOTS)) throw new Error("Storyboard shot ranges differ from the authored choreography");
const CUES = PKG.cues; // [shot_id, start_s, end_s, text, highlighted_keyword]

// ------------------------------------------------------------------ helpers
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (f, a, b) => clamp((f - a) / (b - a));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(202611);
const v3 = (x, y, z) => new THREE.Vector3(x, y, z);

function canvasTex(w, h, draw, repeat) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}
function noiseFill(g, w, h, base, amp, n, seed) {
  const r = mulberry32(seed);
  g.fillStyle = base; g.fillRect(0, 0, w, h);
  for (let i = 0; i < n; i++) {
    const a = (r() - 0.5) * amp;
    g.fillStyle = a > 0 ? `rgba(255,255,255,${a})` : `rgba(0,0,0,${-a})`;
    g.fillRect(r() * w, r() * h, 1 + r() * 3, 1 + r() * 3);
  }
}
const std = (color, roughness = 0.6, metalness = 0, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
function mesh(geo, mat, pos, parent, opts = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.copy(pos);
  m.castShadow = opts.cast !== false;
  m.receiveShadow = opts.receive !== false;
  if (parent) parent.add(m);
  return m;
}
const rbox = (w, h, d, r = 0.02, s = 3) => new RoundedBoxGeometry(w, h, d, s, Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4));
const capsule = (r, len) => new THREE.CapsuleGeometry(r, len, 6, 16);

const glowTex = canvasTex(128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,1)");
  gr.addColorStop(0.35, "rgba(255,255,255,0.75)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});

// ------------------------------------------------------------------ renderer / scene / camera
const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, W / H, 0.05, 80);
// Taller virtual frustum, showing its lower 80%: the camera target sits ~38% from the top,
// keeping the subject above the caption safe area.
camera.setViewOffset(W, H * 1.25, 0, H * 0.25, W, H);

// ------------------------------------------------------------------ comet particle system (directional flow)
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
          map: glowTex, transparent: true, depthWrite: false, blending: opts.additive ? THREE.AdditiveBlending : THREE.NormalBlending,
        }));
        this.group.add(s); row.push(s);
      }
      this.sprites.push({ row, phase: rnd(), curve: curveOf(i) });
    }
  }
  update(time, fade = 1) {
    const col = new THREE.Color();
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
        const sz = this.size * (0.45 + 0.55 * kf) * (this.opts.grow ? lerp(0.6, 1.6, t) : 1);
        s.scale.set(sz, sz, sz);
        col.copy(this.colorOf(i, t));
        s.material.color.copy(col);
        s.material.opacity = clamp(life) * kf * fade * (this.opts.alpha || 0.9);
      }
    }
  }
}

// ------------------------------------------------------------------ character: Bima (rigged)
const SKIN = "#C68A5E", SHIRT = "#E0A11B", PANTS = "#E8DFCA", HAIR = "#2C3539", ACCENT = "#FF6B4A";
function makeBima() {
  const root = new THREE.Group();
  const skin = std(SKIN, 0.55, 0, { emissive: new THREE.Color("#3a1a0a"), emissiveIntensity: 0.12 });
  const shirtTex = canvasTex(256, 256, (g, w, h) => {
    noiseFill(g, w, h, SHIRT, 0.12, 3000, 7);
    g.strokeStyle = "rgba(0,0,0,0.05)";
    for (let y = 0; y < h; y += 4) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
  });
  const shirt = std("#ffffff", 0.85, 0, { map: shirtTex });
  const pants = std(PANTS, 0.9);
  const hair = std(HAIR, 0.7);
  const shoe = std("#3B4248", 0.5);
  const sole = std("#F2F2F2", 0.6);
  const dark = std("#1E2226", 0.4);

  // legs
  const legs = [];
  for (const s of [-1, 1]) {
    const hip = new THREE.Group(); hip.position.set(s * 0.095, 0.92, 0); root.add(hip);
    mesh(capsule(0.082, 0.3), pants, v3(0, -0.2, 0), hip);
    const knee = new THREE.Group(); knee.position.set(0, -0.43, 0); hip.add(knee);
    mesh(new THREE.SphereGeometry(0.077, 16, 12), pants, v3(0, 0, 0), knee);
    mesh(capsule(0.072, 0.3), pants, v3(0, -0.19, 0), knee);
    mesh(capsule(0.05, 0.06), skin, v3(0, -0.4, 0), knee);
    mesh(rbox(0.13, 0.085, 0.27, 0.035), shoe, v3(0, -0.445, 0.045), knee);
    mesh(rbox(0.135, 0.025, 0.275, 0.01), sole, v3(0, -0.485, 0.045), knee);
    legs.push({ hip, knee });
  }
  // torso (lathe)
  const prof = [[0.0, 0], [0.165, 0], [0.175, 0.08], [0.19, 0.24], [0.205, 0.4], [0.2, 0.48], [0.15, 0.545], [0.07, 0.57], [0, 0.575]]
    .map(([r, y]) => new THREE.Vector2(r, y));
  const torso = mesh(new THREE.LatheGeometry(prof, 40), shirt, v3(0, 0.86, 0), root);
  torso.scale.set(1, 1, 0.72);
  mesh(new THREE.CylinderGeometry(0.168, 0.17, 0.07, 32), std("#CFC5AE", 0.9), v3(0, 0.88, 0), root).scale.set(1, 1, 0.73);
  mesh(new THREE.TorusGeometry(0.065, 0.018, 10, 28), std("#C98E14", 0.8), v3(0, 1.43, 0.0), root).rotation.x = Math.PI / 2;
  mesh(new THREE.CylinderGeometry(0.052, 0.058, 0.12, 20), skin, v3(0, 1.47, 0), root);

  // head
  const head = new THREE.Group(); head.position.set(0, 1.64, 0.0); root.add(head);
  const skull = mesh(new THREE.SphereGeometry(0.165, 48, 36), skin, v3(0, 0, 0), head);
  skull.scale.set(1, 1.05, 0.97);
  mesh(new THREE.SphereGeometry(0.075, 24, 16), skin, v3(0, -0.07, 0.065), head).scale.set(1.25, 0.8, 1); // jaw/cheeks
  for (const s of [-1, 1]) {
    mesh(new THREE.SphereGeometry(0.034, 16, 12), skin, v3(s * 0.163, -0.005, 0.0), head).scale.set(0.6, 1, 1);
  }
  // curly hair: deterministic clumps on the upper skull, fringe above the brows
  const hr = mulberry32(99);
  for (let i = 0; i < 70; i++) {
    const u = hr(), w = hr();
    const theta = u * Math.PI * 2;
    const phi = Math.acos(lerp(1, 0.05, w));
    const p = v3(Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta));
    if (p.z > 0.55 && p.y < 0.62) continue; // keep forehead/face clear
    if (p.y < 0.15 && p.z > -0.2) continue;
    const r = 0.042 + hr() * 0.02;
    mesh(new THREE.SphereGeometry(r, 14, 10), hair, p.multiplyScalar(0.162).add(v3(0, 0.012, -0.004)), head);
  }
  // face
  const eyeW = std("#FAFAF7", 0.25), iris = std("#2A1C14", 0.3), hl = new THREE.MeshBasicMaterial({ color: "#ffffff" });
  const eyes = [];
  for (const s of [-1, 1]) {
    const e = new THREE.Group(); e.position.set(s * 0.058, 0.018, 0.143); head.add(e);
    mesh(new THREE.SphereGeometry(0.032, 24, 16), eyeW, v3(0, 0, 0), e, { cast: false }).scale.set(1, 1.15, 0.55);
    const pupil = mesh(new THREE.SphereGeometry(0.019, 20, 14), iris, v3(0, -0.002, 0.012), e, { cast: false });
    pupil.scale.set(1, 1.1, 0.6);
    mesh(new THREE.SphereGeometry(0.006, 10, 8), hl, v3(0.007, 0.01, 0.024), e, { cast: false });
    const lid = mesh(new THREE.SphereGeometry(0.035, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), skin, v3(0, 0, 0), e, { cast: false });
    lid.scale.set(1.04, 1.2, 0.62);
    const brow = mesh(capsule(0.009, 0.045), hair, v3(0, 0.058, 0.008), e, { cast: false });
    brow.rotation.z = Math.PI / 2;
    eyes.push({ e, lid, brow, s });
  }
  mesh(new THREE.SphereGeometry(0.022, 16, 12), skin, v3(0, -0.025, 0.163), head);
  const blush = new THREE.MeshBasicMaterial({ color: "#E8786A", transparent: true, opacity: 0.35, depthWrite: false });
  for (const s of [-1, 1]) mesh(new THREE.CircleGeometry(0.026, 20), blush, v3(s * 0.095, -0.045, 0.142), head, { cast: false }).rotation.y = s * 0.55;
  const mouthOpen = mesh(new THREE.SphereGeometry(0.026, 20, 14), std("#5A1E1E", 0.6), v3(0, -0.085, 0.142), head, { cast: false });
  mouthOpen.scale.set(1.1, 0.75, 0.35);
  const smile = mesh(new THREE.TorusGeometry(0.03, 0.0075, 8, 20, Math.PI), std("#5A1E1E", 0.6), v3(0, -0.07, 0.152), head, { cast: false });
  smile.rotation.z = Math.PI;
  // sweat drops
  const sweatMat = new THREE.MeshStandardMaterial({ color: "#9ADBFF", roughness: 0.05, metalness: 0, transparent: true, opacity: 0.85 });
  const sweat = [];
  for (const [x, y, z] of [[0.14, 0.07, 0.085], [-0.15, 0.03, 0.07]]) {
    const d = new THREE.Group(); d.position.set(x, y, z); head.add(d);
    mesh(new THREE.SphereGeometry(0.014, 14, 10), sweatMat, v3(0, 0, 0), d, { cast: false });
    const c = mesh(new THREE.ConeGeometry(0.0135, 0.026, 14), sweatMat, v3(0, 0.017, 0), d, { cast: false });
    sweat.push({ d, y0: y });
  }

  // arms
  const arms = [];
  for (const s of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(s * 0.215, 1.375, 0); root.add(sh);
    mesh(new THREE.CylinderGeometry(0.07, 0.064, 0.15, 20), shirt, v3(0, -0.055, 0), sh);
    mesh(new THREE.SphereGeometry(0.07, 20, 14), shirt, v3(0, 0.005, 0), sh);
    mesh(capsule(0.048, 0.2), skin, v3(0, -0.15, 0), sh);
    const el = new THREE.Group(); el.position.set(0, -0.29, 0); sh.add(el);
    mesh(new THREE.SphereGeometry(0.047, 16, 12), skin, v3(0, 0, 0), el);
    mesh(capsule(0.043, 0.19), skin, v3(0, -0.12, 0), el);
    const wr = new THREE.Group(); wr.position.set(0, -0.255, 0); el.add(wr);
    mesh(new THREE.SphereGeometry(0.04, 14, 10), skin, v3(0, 0.0, 0), wr);
    mesh(rbox(0.075, 0.085, 0.036, 0.016), skin, v3(0, -0.045, 0), wr);
    const fingers = new THREE.Group(); fingers.position.set(0, -0.085, 0); wr.add(fingers);
    for (let k = 0; k < 4; k++) mesh(capsule(0.0095, 0.04), skin, v3(-0.027 + k * 0.018, -0.026, 0), fingers);
    const thumb = new THREE.Group(); thumb.position.set(-s * 0.04, -0.035, 0.012); wr.add(thumb);
    const tm = mesh(capsule(0.012, 0.035), skin, v3(0, -0.022, 0), thumb);
    thumb.rotation.z = -s * 0.5;
    arms.push({ sh, el, wr, fingers, thumb, s });
  }
  return { root, head, eyes, mouthOpen, smile, sweat, arms, legs, torso };
}

// ------------------------------------------------------------------ AC indoor unit (articulated, cutaway-ready)
function makeIndoorAC({ coilParticles = true } = {}) {
  const g = new THREE.Group();
  const white = std("#F4F6F8", 0.32);
  const panelMat = std("#FBFCFD", 0.25, 0, { transparent: true });
  const dark = std("#2A3036", 0.6);
  const Wd = 1.15, Hd = 0.36, Dd = 0.27;
  // shell parts (open front so the interior can be revealed)
  mesh(rbox(Wd, 0.03, Dd, 0.012), white, v3(0, Hd / 2 - 0.015, 0), g);
  mesh(rbox(Wd, 0.03, Dd, 0.012), white, v3(0, -Hd / 2 + 0.015, 0), g);
  for (const s of [-1, 1]) mesh(rbox(0.035, Hd, Dd, 0.014), white, v3(s * (Wd / 2 - 0.0175), 0, 0), g);
  mesh(rbox(Wd, Hd, 0.02, 0.008), std("#D7DCE1", 0.6), v3(0, 0, -Dd / 2 + 0.01), g);
  // top intake grille slats
  for (let i = 0; i < 14; i++) mesh(rbox(0.035, 0.008, Dd * 0.7, 0.003), dark, v3(-0.45 + i * 0.07, Hd / 2 + 0.002, -0.02), g, { cast: false });
  // interior: copper coil (serpentine) + aluminium fins + cross-flow blower
  const pts = [];
  const rows = 5;
  for (let r = 0; r < rows; r++) {
    const y = 0.1 - r * 0.045;
    const dir = r % 2 === 0 ? 1 : -1;
    const xs = [-0.47, -0.2, 0.2, 0.47];
    const order = dir > 0 ? xs : [...xs].reverse();
    for (const x of order) pts.push(v3(x, y, 0.035));
    if (r < rows - 1) pts.push(v3(0.51 * dir, y - 0.0225, 0.035));
  }
  const coilCurve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.2);
  const copper = std("#C47A45", 0.32, 0.9);
  const coil = mesh(new THREE.TubeGeometry(coilCurve, 400, 0.011, 12, false), copper, null, g);
  const finGeo = new THREE.BoxGeometry(0.004, 0.24, 0.085);
  const fins = new THREE.InstancedMesh(finGeo, std("#C9D2DA", 0.35, 0.8), 44);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < 44; i++) { m4.makeTranslation(-0.5 + i * (1.0 / 43), 0.01, 0.0); fins.setMatrixAt(i, m4); }
  fins.castShadow = true; g.add(fins);
  const blower = new THREE.Group(); blower.position.set(0, -0.12, 0.02); g.add(blower);
  mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.0, 12), std("#5B636B", 0.4, 0.6), null, blower).rotation.z = Math.PI / 2;
  for (let i = 0; i < 14; i++) {
    const b = mesh(new THREE.BoxGeometry(1.0, 0.004, 0.035), std("#4A5259", 0.5), null, blower);
    const a = (i / 14) * Math.PI * 2;
    b.position.set(0, Math.cos(a) * 0.04, Math.sin(a) * 0.04);
    b.rotation.x = a + 0.6;
  }
  // front panel (removable)
  const front = new THREE.Group(); g.add(front);
  const fp = mesh(rbox(Wd - 0.02, Hd - 0.05, 0.03, 0.012), panelMat, v3(0, 0.02, Dd / 2 - 0.005), front);
  mesh(rbox(0.22, 0.012, 0.004, 0.003), std("#AEB6BE", 0.4), v3(-0.38, 0.11, Dd / 2 + 0.012), front, { cast: false });
  const dispCanvas = document.createElement("canvas"); dispCanvas.width = 256; dispCanvas.height = 96;
  const dispTex = new THREE.CanvasTexture(dispCanvas); dispTex.colorSpace = THREE.SRGBColorSpace;
  const disp = mesh(new THREE.PlaneGeometry(0.13, 0.05), new THREE.MeshBasicMaterial({ map: dispTex, transparent: true }), v3(0.38, 0.02, Dd / 2 + 0.012), front, { cast: false, receive: false });
  const setDisplay = (txt, on) => {
    const c = dispCanvas.getContext("2d");
    c.clearRect(0, 0, 256, 96);
    c.fillStyle = on ? "rgba(10,25,40,0.9)" : "rgba(30,34,38,0.55)";
    c.beginPath(); c.roundRect(0, 0, 256, 96, 22); c.fill();
    if (on) { c.fillStyle = "#6FD3FF"; c.font = "800 66px PJS, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(txt, 128, 52); }
    dispTex.needsUpdate = true;
  };
  setDisplay("", false);
  const sensor = mesh(new THREE.SphereGeometry(0.014, 14, 10), std("#1B2026", 0.2), v3(0.25, 0.0, Dd / 2 + 0.012), front, { cast: false });
  // outlet slot + louver
  mesh(rbox(1.0, 0.03, 0.08, 0.008), dark, v3(0, -Hd / 2 + 0.03, Dd / 2 - 0.06), g, { cast: false });
  const louverPivot = new THREE.Group(); louverPivot.position.set(0, -Hd / 2 + 0.005, Dd / 2 - 0.01); g.add(louverPivot);
  const louver = mesh(rbox(1.0, 0.11, 0.014, 0.006), white, v3(0, -0.0, 0.0), louverPivot);
  louver.geometry.translate(0, -0.055, 0);
  const louverStripe = mesh(rbox(0.98, 0.006, 0.004, 0.002), std("#9FD8F5", 0.4), v3(0, -0.09, 0.009), louverPivot, { cast: false });
  return { g, front, panelMat, louverPivot, coilCurve, setDisplay, sensor, blower, Wd, Hd, Dd };
}

// ------------------------------------------------------------------ ROOM SET (S001–S003)
const room = new THREE.Group(); scene.add(room);
{
  const floorTex = canvasTex(1024, 1024, (g, w, h) => {
    const r = mulberry32(5);
    const pw = h / 8;
    for (let i = 0; i < 8; i++) {
      const c = ["#B98552", "#B07B49", "#C08D5B", "#A9743F"][i % 4];
      g.fillStyle = c; g.fillRect(0, i * pw, w, pw);
      for (let k = 0; k < 40; k++) { g.strokeStyle = `rgba(80,45,20,${0.05 + r() * 0.08})`; g.beginPath(); const y = i * pw + r() * pw; g.moveTo(0, y); g.bezierCurveTo(w * 0.3, y + 6, w * 0.6, y - 6, w, y + r() * 4); g.stroke(); }
      const off = r() * w; g.fillStyle = "rgba(60,35,15,0.35)"; g.fillRect(off, i * pw, 3, pw); g.fillRect(0, i * pw, w, 2);
    }
  }, [3, 3]);
  mesh(new THREE.PlaneGeometry(12, 12), std("#ffffff", 0.55, 0, { map: floorTex }), v3(0, 0, 0), room, { cast: false }).rotation.x = -Math.PI / 2;
  const wallTex = canvasTex(512, 512, (g, w, h) => noiseFill(g, w, h, "#EAD9C1", 0.06, 9000, 11), [4, 2]);
  const wallMat = std("#ffffff", 0.92, 0, { map: wallTex });
  const back = mesh(new THREE.PlaneGeometry(9, 4.2), wallMat, v3(0.5, 2.1, -2.0), room, { cast: false });
  const left = mesh(new THREE.PlaneGeometry(8, 4.2), std("#ffffff", 0.92, 0, { map: wallTex, color: "#E9D3B8" }), v3(-2.4, 2.1, 1.0), room, { cast: false });
  left.rotation.y = Math.PI / 2;
  mesh(new THREE.PlaneGeometry(12, 12), std("#F4EEE6", 0.95, 0, { emissive: new THREE.Color("#E9DFD0"), emissiveIntensity: 0.55 }), v3(0.5, 3.4, 1.0), room, { cast: false }).rotation.x = Math.PI / 2;
  mesh(new THREE.BoxGeometry(9, 0.08, 0.06), std("#F2ECE2", 0.6), v3(0.5, 3.36, -1.97), room);
  mesh(new THREE.BoxGeometry(9, 0.12, 0.03), std("#F2ECE2", 0.6), v3(0.5, 0.06, -1.985), room);
  const sk = mesh(new THREE.BoxGeometry(8, 0.12, 0.03), std("#F2ECE2", 0.6), v3(-2.385, 0.06, 1.0), room); sk.rotation.y = Math.PI / 2;

  // window (closed, sunny outside)
  const win = new THREE.Group(); win.position.set(0.55, 1.65, -1.99); room.add(win);
  const skyTex = canvasTex(512, 512, (g, w, h) => {
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#7FC4F2"); gr.addColorStop(0.7, "#CDEBFA"); gr.addColorStop(1, "#F7E6B8");
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const sg = g.createRadialGradient(w * 0.78, h * 0.22, 0, w * 0.78, h * 0.22, w * 0.45); sg.addColorStop(0, "rgba(255,250,220,1)"); sg.addColorStop(1, "rgba(255,240,200,0)");
    g.fillStyle = sg; g.fillRect(0, 0, w, h);
    g.fillStyle = "#7DB36A"; g.beginPath(); g.moveTo(0, h * 0.82); for (let x = 0; x <= w; x += 32) g.lineTo(x, h * (0.78 + 0.04 * Math.sin(x * 0.03))); g.lineTo(w, h); g.lineTo(0, h); g.fill();
  });
  mesh(new THREE.PlaneGeometry(1.2, 1.4), new THREE.MeshBasicMaterial({ map: skyTex }), v3(0, 0, -0.02), win, { cast: false, receive: false });
  const frameMat = std("#F6F1E8", 0.5);
  for (const [w, h, x, y] of [[1.3, 0.08, 0, 0.71], [1.3, 0.1, 0, -0.71], [0.08, 1.5, -0.62, 0], [0.08, 1.5, 0.62, 0], [0.05, 1.4, 0, 0], [1.2, 0.05, 0, 0.1]])
    mesh(rbox(w, h, 0.1, 0.015), frameMat, v3(x, y, 0.03), win);
  mesh(new THREE.PlaneGeometry(1.2, 1.4), new THREE.MeshStandardMaterial({ color: "#CFEAF9", roughness: 0.05, metalness: 0.1, transparent: true, opacity: 0.18 }), v3(0, 0, 0.01), win, { cast: false });
  mesh(rbox(1.45, 0.05, 0.22, 0.015), frameMat, v3(0, -0.78, 0.09), win);
  mesh(rbox(0.04, 0.09, 0.03, 0.01), std("#8D949B", 0.3, 0.7), v3(0.04, -0.05, 0.085), win);
  const curtainMat = std("#D9785F", 0.95, 0, { side: THREE.DoubleSide });
  for (const s of [-1, 1]) {
    const geo = new THREE.PlaneGeometry(0.42, 1.95, 24, 1);
    const pa = geo.attributes.position;
    for (let i = 0; i < pa.count; i++) pa.setZ(i, Math.sin(pa.getX(i) * 38) * 0.035);
    geo.computeVertexNormals();
    mesh(geo, curtainMat, v3(s * 0.85, 0.05, 0.14), win);
  }
  mesh(new THREE.CylinderGeometry(0.018, 0.018, 2.2, 12), std("#6B5440", 0.5, 0.3), v3(0, 1.04, 0.16), win).rotation.z = Math.PI / 2;

  // desk + digital thermometer + plant + books (left-back)
  const desk = new THREE.Group(); desk.position.set(-1.25, 0, -1.6); room.add(desk);
  const wood = std("#8A5A36", 0.55);
  mesh(rbox(1.15, 0.06, 0.62, 0.02), wood, v3(0, 0.76, 0), desk);
  for (const [x, z] of [[-0.52, -0.25], [0.52, -0.25], [-0.52, 0.25], [0.52, 0.25]]) mesh(rbox(0.05, 0.74, 0.05, 0.012), wood, v3(x, 0.37, z), desk);
  const thermo = new THREE.Group(); thermo.position.set(0.18, 0.79, 0.08); thermo.rotation.y = 0.55; desk.add(thermo);
  mesh(rbox(0.26, 0.19, 0.07, 0.025), std("#F7F7F5", 0.35), v3(0, 0.11, 0), thermo);
  mesh(rbox(0.18, 0.03, 0.12, 0.01), std("#F7F7F5", 0.35), v3(0, 0.015, 0.0), thermo);
  const thermoTex = canvasTex(256, 160, (g) => {
    g.fillStyle = "#101418"; g.beginPath(); g.roundRect(0, 0, 256, 160, 18); g.fill();
    g.fillStyle = "#FF5A3C"; g.font = "800 92px PJS, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("32°C", 128, 88);
    g.fillStyle = "#8C98A4"; g.font = "700 26px PJS, sans-serif"; g.fillText("SUHU KAMAR", 128, 26);
  });
  mesh(new THREE.PlaneGeometry(0.21, 0.13), new THREE.MeshBasicMaterial({ map: thermoTex }), v3(0, 0.115, 0.0365), thermo, { cast: false });
  const pot = mesh(new THREE.CylinderGeometry(0.08, 0.06, 0.15, 24), std("#C9643F", 0.7), v3(-0.38, 0.865, -0.12), desk);
  const leafMat = std("#4E9A55", 0.6);
  const lr = mulberry32(3);
  for (let i = 0; i < 9; i++) {
    const l = mesh(new THREE.SphereGeometry(0.06, 14, 10), leafMat, v3(-0.38 + (lr() - 0.5) * 0.12, 1.0 + lr() * 0.16, -0.12 + (lr() - 0.5) * 0.12), desk);
    l.scale.set(0.5, 1.4, 0.25); l.rotation.set(lr() - 0.5, lr() * 3, (lr() - 0.5) * 1.2);
  }
  for (const [i, c] of ["#3E6FA8", "#E3B23C", "#5B8C6A"].entries()) mesh(rbox(0.28, 0.04, 0.2, 0.008), std(c, 0.7), v3(0.36, 0.81 + i * 0.042, -0.1), desk).rotation.y = i * 0.12;

  // bed (right)
  const bed = new THREE.Group(); bed.position.set(1.75, 0, -0.95); room.add(bed);
  mesh(rbox(1.3, 0.3, 2.0, 0.04), std("#7C5236", 0.6), v3(0, 0.2, 0), bed);
  mesh(rbox(1.24, 0.2, 1.94, 0.08), std("#F3EFE7", 0.9), v3(0, 0.44, 0), bed);
  const blanketTex = canvasTex(256, 256, (g, w, h) => { g.fillStyle = "#5C8DB8"; g.fillRect(0, 0, w, h); g.fillStyle = "#4C7CA6"; for (let i = 0; i < 8; i++) g.fillRect(0, i * 32, w, 14); }, [2, 2]);
  mesh(rbox(1.28, 0.06, 1.2, 0.03), std("#ffffff", 0.95, 0, { map: blanketTex }), v3(0, 0.56, 0.35), bed);
  mesh(rbox(0.6, 0.14, 0.38, 0.07), std("#FFFFFF", 0.9), v3(0, 0.6, -0.72), bed);
  mesh(rbox(1.36, 0.9, 0.08, 0.03), std("#7C5236", 0.6), v3(0, 0.55, -1.0), bed);
}

const AC = makeIndoorAC();
AC.g.position.set(-2.24, 2.55, -0.25);
AC.g.rotation.y = Math.PI / 2; // front faces +x (into the room)
room.add(AC.g);

const bima = makeBima();
bima.root.position.set(0.05, 0, -0.35);
room.add(bima.root);

// handheld paper fan (S001) and remote (S002) attached to the right wrist
const rightArm = bima.arms[1], leftArm = bima.arms[0];
for (const a of bima.arms) a.sh.rotation.order = "YXZ";
const fanTex = canvasTex(512, 256, (g, w, h) => {
  for (let i = 0; i < 12; i++) { g.fillStyle = i % 2 ? "#FDF3E1" : "#F06449"; g.fillRect((i * w) / 12, 0, w / 12 + 1, h); }
  g.fillStyle = "rgba(0,0,0,0.08)"; g.fillRect(0, h * 0.9, w, h * 0.1);
});
const fan = new THREE.Group(); rightArm.wr.add(fan);
{
  const fg = new THREE.CircleGeometry(0.2, 32, Math.PI / 2 - 0.95, 1.9);
  const fm = mesh(fg, new THREE.MeshStandardMaterial({ map: fanTex, side: THREE.DoubleSide, roughness: 0.9 }), v3(0, -0.02, 0), fan);
  fm.rotation.x = Math.PI / 2; fm.rotation.z = Math.PI;
  mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.1, 8), std("#6B4A2E", 0.6), v3(0, -0.05, 0), fan);
  fan.position.set(0, -0.08, 0.02);
}
const remote = new THREE.Group(); leftArm.wr.add(remote);
let remoteTip, remoteBtn;
{
  mesh(rbox(0.055, 0.17, 0.024, 0.01), std("#EEF1F4", 0.3), v3(0, -0.075, 0.026), remote);
  const scrT = canvasTex(128, 96, (g) => { g.fillStyle = "#14202B"; g.fillRect(0, 0, 128, 96); g.fillStyle = "#7FD8FF"; g.font = "800 56px PJS, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("24°", 64, 52); });
  mesh(new THREE.PlaneGeometry(0.04, 0.03), new THREE.MeshBasicMaterial({ map: scrT }), v3(0, -0.13, 0.0385), remote, { cast: false });
  remoteBtn = mesh(new THREE.CylinderGeometry(0.009, 0.009, 0.006, 16), std(ACCENT, 0.4, 0, { emissive: new THREE.Color(ACCENT), emissiveIntensity: 0 }), v3(0, -0.07, 0.039), remote, { cast: false });
  remoteBtn.rotation.x = Math.PI / 2;
  for (const [x, y] of [[-0.014, -0.035], [0.014, -0.035], [-0.014, -0.01], [0.014, -0.01]]) mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.005, 12), std("#B8C0C8", 0.5), v3(x, y, 0.039), remote, { cast: false }).rotation.x = Math.PI / 2;
  remoteTip = new THREE.Object3D(); remoteTip.position.set(0, -0.16, 0.026); remote.add(remoteTip);
  mesh(new THREE.SphereGeometry(0.006, 10, 8), std("#552222", 0.3), v3(0, -0.162, 0.026), remote, { cast: false });
  remote.position.set(0.0, -0.02, 0.0);
}

// lights (room)
const roomLights = new THREE.Group(); room.add(roomLights);
const hemi = new THREE.HemisphereLight("#FFF1DC", "#7A5A3E", 0.85); roomLights.add(hemi);
const key = new THREE.DirectionalLight("#FFD6A5", 2.4); key.position.set(2.6, 4.6, 3.2); key.target.position.set(-0.4, 0.8, -0.8);
key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.camera.left = -4; key.shadow.camera.right = 4; key.shadow.camera.top = 4; key.shadow.camera.bottom = -4;
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 4;
roomLights.add(key); roomLights.add(key.target);
const sun = new THREE.PointLight("#FFE2B0", 6, 6, 1.6); sun.position.set(0.55, 1.9, -1.6); roomLights.add(sun);
const coolLight = new THREE.PointLight("#7FCBFF", 0, 3.5, 1.8); coolLight.position.set(-1.9, 2.2, -0.25); roomLights.add(coolLight);
const acInner = new THREE.PointLight("#BFE6FF", 0, 1.2, 2); acInner.position.set(-2.05, 2.55, -0.25); roomLights.add(acInner);

// heat flow in the room (S001): warm comets rising from the room toward the AC intake
const heatCurves = [];
const hr2 = mulberry32(42);
for (let i = 0; i < 26; i++) {
  const start = v3(lerp(-1.2, 1.6, hr2()), lerp(0.4, 1.4, hr2()), lerp(-1.4, 0.9, hr2()));
  const mid = v3(lerp(-1.0, 0.2, hr2()), lerp(2.0, 2.6, hr2()), lerp(-0.6, 0.4, hr2()));
  const end = v3(-2.24 + lerp(-0.05, 0.08, hr2()), 2.77, -0.25 + lerp(-0.45, 0.45, hr2()));
  heatCurves.push(new THREE.CatmullRomCurve3([start, mid, end]));
}
const heatComets = new Comets(room, 26, 7, (i) => heatCurves[i], () => new THREE.Color("#FF6A2B"), 0.11, 0.32, { additive: false, alpha: 0.85, gap: 0.016 });

// big "heat route" arrow for the second caption of S001: room -> AC -> out through the wall
const routeCurve = new THREE.CatmullRomCurve3([v3(-0.3, 1.25, 0.15), v3(-0.75, 2.05, 0.3), v3(-1.45, 2.95, 0.05), v3(-2.02, 2.88, -0.25)]);
const routeGeo = new THREE.TubeGeometry(routeCurve, 160, 0.02, 12, false);
const routeMat = new THREE.MeshStandardMaterial({ color: "#FF5A2B", emissive: new THREE.Color("#FF4A1B"), emissiveIntensity: 0.6, roughness: 0.4, transparent: true, opacity: 0.95 });
const route = mesh(routeGeo, routeMat, null, room, { cast: false });
const routeHead = mesh(new THREE.ConeGeometry(0.055, 0.14, 20), routeMat, null, room, { cast: false });

// IR signal (S002)
const irGroup = new THREE.Group(); room.add(irGroup);
const irDots = [];
for (let i = 0; i < 9; i++) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: "#FF3D6E", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  irGroup.add(s); irDots.push(s);
}
const sensorFlash = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: "#FF6F91", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
room.add(sensorFlash);

// cool air from the louver (S002 end, S003)
const coolCurves = [];
const cr = mulberry32(77);
for (let i = 0; i < 24; i++) {
  const zx = -0.25 + lerp(-0.45, 0.45, cr());
  const a = v3(-2.06, 2.36, zx);
  const b = v3(-1.55 + cr() * 0.2, 2.0 - cr() * 0.25, zx * 1.1);
  const c = v3(-0.6 + cr() * 0.9, 1.35 + cr() * 0.4, zx * 1.4 + 0.2);
  coolCurves.push(new THREE.CatmullRomCurve3([a, b, c]));
}
const coolComets = new Comets(room, 24, 7, (i) => coolCurves[i], () => new THREE.Color("#5CC8FF"), 0.1, 0.45, { alpha: 0.85, gap: 0.02 });

// S003 airflow through the evaporator (local to the AC so it follows the unit)
const evapFlowCurves = [];
const er = mulberry32(9);
for (let i = 0; i < 22; i++) {
  const x = lerp(-0.48, 0.48, (i + er() * 0.6) / 22);
  // AC local: +z = front (room), +y = up. Warm room air -> over the top -> down through fins/coil -> out the louver.
  evapFlowCurves.push(new THREE.CatmullRomCurve3([
    v3(x, -0.55, 0.75), v3(x, 0.05, 0.55), v3(x, 0.32, 0.12), v3(x, 0.12, 0.0), v3(x, -0.06, 0.02), v3(x, -0.2, 0.16), v3(x, -0.5, 0.55),
  ]));
}
const warm = new THREE.Color("#FF6A2B"), cool = new THREE.Color("#4FC3FF");
const evapComets = new Comets(AC.g, 22, 8, (i) => evapFlowCurves[i], (i, t) => warm.clone().lerp(cool, clamp((t - 0.5) / 0.12)), 0.05, 0.42, { alpha: 0.95, gap: 0.012 });
// refrigerant inside the coil: cold liquid (deep blue, small) -> vapour (pale, larger bubbles)
const refComets = new Comets(AC.g, 18, 1, () => AC.coilCurve, (i, t) => new THREE.Color("#1E6BFF").lerp(new THREE.Color("#E6F7FF"), t), 0.026, 0.12, { alpha: 1, grow: true });

// ------------------------------------------------------------------ CROSS-SECTION SET (S004)
const xs = new THREE.Group(); xs.position.set(40, 0, 0); scene.add(xs);
const xsParts = {};
{
  // sky + ground outside (x>0), warm room inside (x<0)
  const skyTex2 = canvasTex(512, 1024, (g, w, h) => {
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#5FB0EA"); gr.addColorStop(0.65, "#BFE4F8"); gr.addColorStop(1, "#F2E5C4");
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const sg = g.createRadialGradient(w * 0.75, h * 0.12, 0, w * 0.75, h * 0.12, w * 0.6); sg.addColorStop(0, "rgba(255,248,215,1)"); sg.addColorStop(1, "rgba(255,240,200,0)");
    g.fillStyle = sg; g.fillRect(0, 0, w, h);
  });
  mesh(new THREE.PlaneGeometry(6, 7), new THREE.MeshBasicMaterial({ map: skyTex2 }), v3(3.1, 2.8, -1.6), xs, { cast: false, receive: false });
  mesh(new THREE.PlaneGeometry(6.4, 4), std("#8DBB6E", 0.95), v3(2.9, 0.0, 0.4), xs, { cast: false }).rotation.x = -Math.PI / 2;
  const inTex = canvasTex(512, 512, (g, w, h) => noiseFill(g, w, h, "#EAD9C1", 0.06, 6000, 12));
  mesh(new THREE.PlaneGeometry(4, 7), std("#ffffff", 0.9, 0, { map: inTex }), v3(-2.15, 2.8, -1.6), xs, { cast: false });
  mesh(new THREE.PlaneGeometry(4.4, 4), std("#B98552", 0.6), v3(-2.0, 0.0, 0.4), xs, { cast: false }).rotation.x = -Math.PI / 2;
  // wall slab with brick cross-section facing the camera
  const brickTex = canvasTex(256, 1024, (g, w, h) => {
    g.fillStyle = "#D9CFC2"; g.fillRect(0, 0, w, h);
    const bh = 36;
    for (let r = 0; r * bh < h; r++) for (let c = -1; c < 3; c++) {
      const x = c * 120 + (r % 2) * 60;
      g.fillStyle = ["#B8735A", "#AD6A52", "#BF7B61"][(r + c + 9) % 3];
      g.fillRect(x + 4, r * bh + 4, 112, bh - 8);
    }
  });
  const wallMats = [std("#E9D8C0", 0.9), std("#E9D8C0", 0.9), std("#E9D8C0", 0.9), std("#E9D8C0", 0.9), std("#ffffff", 0.85, 0, { map: brickTex }), std("#E9D8C0", 0.9)];
  const wall = new THREE.Mesh(new THREE.BoxGeometry(0.32, 6.0, 3.2), wallMats);
  wall.position.set(0, 3.0, -1.6 + 1.6 - 1.6); wall.castShadow = wall.receiveShadow = true; xs.add(wall);
  wall.position.z = -0.6; // cut face at z = +1.0, just behind the refrigerant lines
  // indoor unit on the inner face (profile), reuse articulated unit
  const ac2 = makeIndoorAC();
  ac2.g.position.set(-0.3, 2.55, 0.95); ac2.g.rotation.y = -Math.PI / 2; ac2.g.scale.setScalar(0.85);
  xs.add(ac2.g); ac2.louverPivot.rotation.x = -1.0; ac2.setDisplay("24°", true);
  xsParts.ac2 = ac2;
  // outdoor unit on brackets outside
  const od = new THREE.Group(); od.position.set(0.8, 1.25, 0.9); xs.add(od); xsParts.od = od;
  const caseMat = std("#E8ECEF", 0.4);
  mesh(rbox(0.9, 0.62, 0.36, 0.03), caseMat, v3(0, 0, -0.02), od).visible = false; // reference size only
  // casing built from panels so the right part can be a cutaway
  mesh(rbox(0.9, 0.03, 0.36, 0.012), caseMat, v3(0, 0.31, 0), od);
  mesh(rbox(0.9, 0.03, 0.36, 0.012), caseMat, v3(0, -0.31, 0), od);
  mesh(rbox(0.03, 0.62, 0.36, 0.012), caseMat, v3(-0.435, 0, 0), od);
  mesh(rbox(0.03, 0.62, 0.36, 0.012), caseMat, v3(0.435, 0, 0), od);
  mesh(rbox(0.9, 0.62, 0.02, 0.008), std("#C9D0D6", 0.6), v3(0, 0, -0.17), od);
  // front panel: left half solid with fan opening, right half removed (cutaway) with a rim
  const frontL = mesh(rbox(0.56, 0.6, 0.02, 0.008), caseMat, v3(-0.17, 0, 0.17), od);
  // fan guard & fan
  const guard = mesh(new THREE.TorusGeometry(0.22, 0.012, 10, 48), std("#3A4148", 0.4, 0.5), v3(-0.17, 0, 0.19), od);
  for (let i = 0; i < 5; i++) mesh(new THREE.TorusGeometry(0.04 + i * 0.045, 0.0035, 6, 40), std("#3A4148", 0.4, 0.5), v3(-0.17, 0, 0.195), od, { cast: false });
  const fanHub = new THREE.Group(); fanHub.position.set(-0.17, 0, 0.175); od.add(fanHub); xsParts.fanHub = fanHub;
  mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.03, 20), std("#2A3036", 0.4), null, fanHub).rotation.x = Math.PI / 2;
  for (let i = 0; i < 3; i++) {
    const bl = mesh(new THREE.SphereGeometry(0.1, 16, 10), std("#2F363C", 0.45), null, fanHub);
    bl.scale.set(0.45, 1.0, 0.1); bl.geometry.translate(0, 0.1, 0);
    bl.rotation.z = (i / 3) * Math.PI * 2; bl.rotation.y = 0.35;
  }
  // black fan opening disc behind blades
  mesh(new THREE.CircleGeometry(0.215, 40), std("#15191D", 0.9), v3(-0.17, 0, 0.181), od, { cast: false });
  // cutaway interior on the right: compressor + condenser coil
  const comp = new THREE.Group(); comp.position.set(0.25, -0.08, 0.0); od.add(comp); xsParts.comp = comp;
  mesh(new THREE.CapsuleGeometry(0.075, 0.16, 8, 24), std("#3F5E56", 0.35, 0.4), v3(0, 0, 0), comp);
  mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.03, 24), std("#2D2F33", 0.6), v3(0, -0.15, 0), comp);
  const condPts = [];
  for (let r = 0; r < 6; r++) {
    const y = 0.22 - r * 0.075;
    const xsA = r % 2 === 0 ? [-0.38, 0.38] : [0.38, -0.38];
    condPts.push(v3(xsA[0], y, -0.12), v3(xsA[1], y, -0.12));
    if (r < 5) condPts.push(v3(xsA[1] + (r % 2 === 0 ? 0.03 : -0.03), y - 0.0375, -0.12));
  }
  const condCurve = new THREE.CatmullRomCurve3(condPts, false, "catmullrom", 0.15); xsParts.condCurve = condCurve;
  mesh(new THREE.TubeGeometry(condCurve, 400, 0.011, 10, false), std("#C47A45", 0.32, 0.9), null, od);
  // brackets
  for (const s of [-1, 1]) {
    mesh(rbox(0.04, 0.04, 0.5, 0.008), std("#6E757B", 0.4, 0.7), v3(s * 0.3, -0.34, -0.05), od);
    const d = mesh(rbox(0.03, 0.4, 0.03, 0.006), std("#6E757B", 0.4, 0.7), v3(s * 0.3, -0.5, -0.27), od);
  }
  // refrigerant lines through the wall (copper + insulation)
  const odW = new THREE.Vector3();
  const pipeTop = new THREE.CatmullRomCurve3([v3(-0.32, 2.47, 1.0), v3(-0.05, 2.38, 1.06), v3(0.26, 2.08, 1.06), v3(0.36, 1.78, 1.06), v3(0.55, 1.66, 1.06), v3(0.98, 1.66, 1.0), v3(1.05, 1.42, 0.94), v3(1.05, 1.27, 0.9)]);
  const pipeBot = new THREE.CatmullRomCurve3([v3(0.45, 1.0, 0.9), v3(0.28, 1.3, 1.03), v3(0.2, 1.98, 1.03), v3(-0.05, 2.28, 1.03), v3(-0.32, 2.4, 0.98)]);
  xsParts.pipeTop = pipeTop; xsParts.pipeBot = pipeBot;
  mesh(new THREE.TubeGeometry(pipeTop, 200, 0.03, 14, false), std("#EDEDE8", 0.85, 0, { transparent: true, opacity: 0.4, depthWrite: false }), null, xs);
  mesh(new THREE.TubeGeometry(pipeTop, 200, 0.013, 10, false), std("#C47A45", 0.32, 0.9), null, xs);
  mesh(new THREE.TubeGeometry(pipeBot, 200, 0.012, 10, false), std("#C47A45", 0.32, 0.9), null, xs);
  // lights
  const xsHemi = new THREE.HemisphereLight("#DDF0FF", "#8a7a5a", 0.9); xs.add(xsHemi);
  const xsSun = new THREE.DirectionalLight("#FFF1D6", 2.6); xsSun.position.set(4, 6, 5); xsSun.target.position.set(0.5, 1.5, 0.5);
  xsSun.castShadow = true; xsSun.shadow.mapSize.set(2048, 2048); xsSun.shadow.camera.left = -3; xsSun.shadow.camera.right = 3; xsSun.shadow.camera.top = 3; xsSun.shadow.camera.bottom = -3; xsSun.shadow.bias = -0.0004; xsSun.shadow.normalBias = 0.02;
  xs.add(xsSun); xs.add(xsSun.target);
  const warmIn = new THREE.PointLight("#FFD3A0", 2.0, 4, 1.5); warmIn.position.set(-1.3, 2.4, 1.5); xs.add(warmIn);
  const hotGlow = new THREE.PointLight("#FF6A2B", 0, 1.2, 2); hotGlow.position.set(1.05, 1.2, 1.25); xs.add(hotGlow); xsParts.hotGlow = hotGlow;
}
const hot = new THREE.Color("#FF5A1F"), hotPale = new THREE.Color("#FFB070");
const suction = new Comets(xs, 14, 6, () => xsParts.pipeTop, () => hot, 0.095, 0.35, { alpha: 0.95, gap: 0.02 });
const liquid = new Comets(xs, 12, 5, () => xsParts.pipeBot, () => new THREE.Color("#3FA9FF"), 0.055, 0.3, { alpha: 0.9, gap: 0.022 });
const condFlow = new Comets(xsParts.od, 14, 1, () => xsParts.condCurve, (i, t) => hot.clone().lerp(new THREE.Color("#FFD9A8"), t), 0.032, 0.22, { alpha: 1 });
// heat released to the outside air by the condenser fan
const heatOutCurves = [];
const ho = mulberry32(31);
for (let i = 0; i < 26; i++) {
  const a = v3(0.63 + (ho() - 0.5) * 0.3, 1.25 + (ho() - 0.5) * 0.3, 1.12);
  const b = v3(0.9 + ho() * 0.5, 1.5 + ho() * 0.5, 1.55 + ho() * 0.2);
  const c = v3(1.3 + ho() * 0.7, 2.1 + ho() * 1.1, 1.3 + ho() * 0.5);
  heatOutCurves.push(new THREE.CatmullRomCurve3([a, b, c]));
}
const heatOut = new Comets(xs, 26, 7, (i) => heatOutCurves[i], (i, t) => hot.clone().lerp(hotPale, t), 0.12, 0.38, { alpha: 0.8, gap: 0.02, grow: true });
const coolIn = new Comets(xs, 12, 6, (i) => new THREE.CatmullRomCurve3([v3(-0.55, 2.33, 0.9 + (i - 6) * 0.03), v3(-0.9, 2.0, 1.0), v3(-1.5, 1.6, 1.1 + (i % 3) * 0.1)]), () => new THREE.Color("#5CC8FF"), 0.07, 0.4, { alpha: 0.8, gap: 0.022 });

// ------------------------------------------------------------------ labels (content callouts, not debug)
const labelsEl = document.getElementById("labels");
function makeLabel(text, kind) { const d = document.createElement("div"); d.className = "label " + kind; d.textContent = text; labelsEl.appendChild(d); return d; }
const L = {
  heat: makeLabel("Panas kamar", "warm"),
  evap: makeLabel("Evaporator", "cool"),
  in: makeLabel("Udara panas masuk", "warm"),
  out: makeLabel("Udara sejuk keluar", "cool"),
  comp: makeLabel("Kompresor", "warm"),
  cond: makeLabel("Kondensor", "warm"),
  release: makeLabel("Kalor dibuang ke luar", "warm"),
  vapor: makeLabel("Uap refrigeran panas", "warm"),
};
function placeLabel(el, worldPos, alpha) {
  const p = worldPos.clone().project(camera);
  el.style.left = `${((p.x + 1) / 2) * W}px`;
  el.style.top = `${((1 - p.y) / 2) * H}px`;
  el.style.opacity = String(alpha);
}

// ------------------------------------------------------------------ caption
const capbox = document.getElementById("capbox");
function setCaption(t) {
  const cue = CUES.find((c) => t >= c[1] && t < c[2]) || CUES[CUES.length - 1];
  const [, a, , text, kw] = cue;
  const k = text.indexOf(kw);
  capbox.innerHTML = k >= 0 ? `${text.slice(0, k)}<b>${kw}</b>${text.slice(k + kw.length)}` : text;
  const fi = clamp((t - a) / 0.2);
  capbox.style.setProperty("--o", String(lerp(0.0, 1, easeOut(fi))));
  capbox.style.setProperty("--ty", `${lerp(18, 0, easeOut(fi))}px`);
}

// ------------------------------------------------------------------ poses
function poseNeutral() {
  for (const a of bima.arms) { a.sh.rotation.set(0, 0, a.s * 0.12); a.el.rotation.set(-0.15, 0, 0); a.wr.rotation.set(0, 0, 0); a.fingers.rotation.set(0, 0, 0); a.thumb.rotation.set(0, 0, -a.s * 0.5); }
  for (const l of bima.legs) { l.hip.rotation.set(0, 0, 0); l.knee.rotation.set(0, 0, 0); }
  bima.head.rotation.set(0, 0, 0);
  bima.torso.rotation.set(0, 0, 0);
}
function face(hot01, relief01, blink01 = 0) {
  for (const e of bima.eyes) {
    const lidClose = lerp(0.35, 0.0, relief01) * hot01 + blink01;
    e.lid.rotation.x = lerp(-1.6, -0.2, clamp(lidClose));
    e.brow.rotation.z = Math.PI / 2 + e.s * lerp(0, -0.35, hot01 * (1 - relief01));
    e.brow.position.y = 0.058 + 0.008 * hot01 * (1 - relief01);
  }
  const open = hot01 * (1 - relief01);
  bima.mouthOpen.scale.set(1.1, 0.75 * open + 0.001, 0.35);
  bima.mouthOpen.visible = open > 0.05;
  bima.smile.visible = relief01 > 0.05;
  bima.smile.scale.setScalar(0.5 + 0.5 * relief01);
}

// ------------------------------------------------------------------ camera rigs per shot
function camRig(f) {
  if (f < 105) { // S001 establishing, slow push-in
    const t = ease(seg(f, 0, 105));
    camera.fov = 60;
    camera.position.set(lerp(2.45, 2.15, t), lerp(2.45, 2.25, t), lerp(4.6, 4.0, t));
    camera.lookAt(lerp(-1.0, -0.9, t), 1.6, lerp(-0.45, -0.45, t));
  } else if (f < 210) { // S002 medium three-quarter: Bima right, AC upper-left
    const t = ease(seg(f, 105, 210));
    camera.fov = 56;
    const pan = ease(seg(f, 140, 166));
    camera.position.set(lerp(-0.7, -0.95, t), lerp(1.5, 1.55, t), lerp(1.55, 1.25, t));
    const back = ease(seg(f, 184, 202));
    camera.lookAt(lerp(lerp(-0.25, -2.1, pan), -0.2, back), lerp(lerp(1.72, 2.3, pan), 1.78, back), lerp(lerp(-0.3, -0.25, pan), -0.35, back));
  } else if (f < 330) { // S003 oblique cutaway, dolly-in on the evaporator
    const t = ease(seg(f, 210, 330));
    camera.fov = lerp(62, 50, t);
    camera.position.set(lerp(-0.55, -1.1, t), lerp(2.05, 2.2, t), lerp(1.45, 0.95, t));
    camera.lookAt(-2.2, lerp(2.42, 2.48, t), lerp(-0.25, -0.3, t));
  } else { // S004 cross-section, slow track inside -> outside
    const t = ease(seg(f, 330, 450));
    camera.fov = 58;
    camera.position.set(40 + lerp(0.2, 0.45, t), lerp(2.25, 2.0, t), lerp(5.3, 5.0, t));
    camera.lookAt(40 + lerp(0.3, 0.4, t), lerp(2.15, 2.0, t), 0.9);
  }
  camera.updateProjectionMatrix();
}

// ------------------------------------------------------------------ frame evaluation
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();
function renderFrame(f) {
  const t = f / FPS;
  const shot = f < 105 ? 0 : f < 210 ? 1 : f < 330 ? 2 : 3;
  room.visible = shot <= 2;
  xs.visible = shot === 3;
  poseNeutral();
  for (const el of Object.values(L)) el.style.opacity = "0";

  // defaults
  AC.louverPivot.rotation.x = 0;
  AC.setDisplay("", false);
  AC.front.visible = true; AC.panelMat.opacity = 1; AC.front.position.set(0, 0, 0);
  fan.visible = false; remote.visible = false;
  route.visible = false; routeHead.visible = false;
  irGroup.visible = false; sensorFlash.visible = false;
  coolLight.intensity = 0; acInner.intensity = 0; key.intensity = 2.4; hemi.intensity = 0.85; sun.intensity = 6;
  heatComets.group.visible = false; coolComets.group.visible = false; evapComets.group.visible = false; refComets.group.visible = false;
  bima.root.visible = true;

  if (shot === 0) {
    // Bima overheated, fanning his face; heat drifts toward the AC; route arrow on 2nd caption
    bima.root.rotation.y = 0.35;
    const w = Math.sin(t * 2 * Math.PI * 2.4);
    const ra = rightArm;
    ra.sh.rotation.set(-1.15, 0.25, 0.35);
    ra.el.rotation.set(-1.55 + 0.12 * w, 0, 0);
    ra.wr.rotation.set(0.25, 0.55 * w, 0.2);
    fan.visible = true;
    leftArm.sh.rotation.set(0.05, 0, -0.18); leftArm.el.rotation.set(-0.35, 0, 0);
    bima.head.rotation.set(0.12 + 0.02 * w, -0.1, 0.05 * w);
    bima.torso.rotation.y = 0.04 * w;
    face(1, 0, f % 70 > 66 ? 0.9 : 0);
    bima.sweat.forEach((s, i) => { s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; s.d.visible = true; });
    heatComets.group.visible = true; heatComets.update(t, 1);
    const rt = ease(seg(f, 70, 100));
    if (rt > 0) {
      route.visible = routeHead.visible = true;
      routeGeo.setDrawRange(0, Math.floor(routeGeo.index.count * rt / 6) * 6);
      routeCurve.getPoint(rt, tmpA); routeCurve.getTangent(rt, tmpB);
      routeHead.position.copy(tmpA); routeHead.quaternion.setFromUnitVectors(v3(0, 1, 0), tmpB.normalize());
    }
    camRig(f);
    scene.updateMatrixWorld(true);
    L.heat.style.left = "740px"; L.heat.style.top = "520px"; L.heat.style.opacity = String(seg(f, 12, 22) * (1 - seg(f, 66, 72)));
  } else if (shot === 1) {
    // Bima turns to the AC, presses 24° on the remote -> IR -> display on -> louver opens -> cool air
    bima.root.rotation.y = -0.7;
    const raise = easeOut(seg(f, 105, 122)) * (1 - ease(seg(f, 176, 194)));
    const ra = leftArm;
    ra.sh.rotation.set(lerp(-0.2, -2.05, raise), lerp(0, -0.8, raise), lerp(-0.12, -0.05, raise));
    ra.el.rotation.set(lerp(-0.3, -0.15, raise), 0, 0);
    ra.wr.rotation.set(lerp(0, -0.25, raise), 0, 0);
    remote.visible = true;
    const press = Math.max(seg(f, 128, 134) * (1 - seg(f, 138, 144)), 0);
    ra.thumb.rotation.x = -0.5 * press;
    remoteBtn.material.emissiveIntensity = 2.5 * press;
    rightArm.sh.rotation.set(0.0, 0, 0.15); rightArm.el.rotation.set(-0.3, 0, 0);
    bima.head.rotation.set(-0.3 * raise, -0.35 * raise, 0);
    const acOn = f >= 146;
    const relief = ease(seg(f, 180, 198));
    face(1 - 0.6 * relief, relief, 0);
    bima.sweat.forEach((s, i) => { s.d.visible = relief < 0.5; s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; });
    if (acOn) AC.setDisplay("24°", true);
    const open = ease(seg(f, 150, 176));
    AC.louverPivot.rotation.x = -1.05 * open;
    coolLight.intensity = 2.2 * open;
    scene.updateMatrixWorld(true);
    // IR pulse train from the remote tip to the AC sensor (during the press)
    const irT = seg(f, 130, 150);
    if (irT > 0 && irT < 1) {
      irGroup.visible = true;
      remoteTip.getWorldPosition(tmpA); AC.sensor.getWorldPosition(tmpB);
      irDots.forEach((d, i) => {
        const u = (irT * 1.6 - i * 0.07);
        d.visible = u > 0 && u < 1;
        d.position.lerpVectors(tmpA, tmpB, clamp(u));
        d.scale.setScalar(0.05);
        d.material.opacity = 0.95;
      });
    }
    const flash = seg(f, 144, 147) * (1 - seg(f, 150, 158));
    if (flash > 0) { sensorFlash.visible = true; AC.sensor.getWorldPosition(sensorFlash.position); sensorFlash.scale.setScalar(0.25 * flash + 0.02); sensorFlash.material.opacity = flash; }
    if (open > 0.2) { coolComets.group.visible = true; coolComets.update(t, clamp((open - 0.2) * 2) * (1 - 0.6 * ease(seg(f, 184, 200)))); }
    camRig(f);
    scene.updateMatrixWorld(true);
  } else if (shot === 2) {
    // Cutaway: panel lifts off, warm room air enters, crosses the cold coil, leaves cool; refrigerant boils inside
    bima.root.visible = false;
    AC.setDisplay("24°", true);
    AC.louverPivot.rotation.x = -1.05;
    const lift = ease(seg(f, 214, 240));
    AC.front.position.set(0, 0.35 * lift, 0.55 * lift);
    AC.panelMat.opacity = 1 - lift;
    AC.front.visible = lift < 0.99;
    key.intensity = 1.2; hemi.intensity = 0.45; sun.intensity = 2.5;
    acInner.intensity = 1.6 * lift; coolLight.intensity = 1.5;
    AC.blower.rotation.x = -t * 14;
    evapComets.group.visible = true; evapComets.update(t, seg(f, 232, 246));
    refComets.group.visible = true; refComets.update(t, seg(f, 236, 250));
    camRig(f);
    scene.updateMatrixWorld(true);
    const a = (x, y, z) => AC.g.localToWorld(v3(x, y, z));
    L.in.style.left = "760px"; L.in.style.top = "190px"; L.in.style.opacity = String(seg(f, 248, 258) * (1 - seg(f, 300, 306)));
    placeLabel(L.evap, a(-0.25, 0.08, 0.32), seg(f, 262, 272));
    placeLabel(L.out, a(0.1, -0.42, 0.55), seg(f, 280, 290));
  } else {
    // Cross-section: hot vapour to the compressor, through the condenser, heat blown out by the fan
    xsParts.fanHub.rotation.z = -t * 18;
    const pulse = 1 + 0.03 * Math.sin(t * 2 * Math.PI * 4);
    xsParts.comp.scale.set(pulse, 1 / pulse, pulse);
    xsParts.ac2.blower.rotation.x = -t * 14;
    xsParts.hotGlow.intensity = 0.5 + 0.2 * Math.sin(t * 6);
    suction.update(t, 1); liquid.update(t, 1); condFlow.update(t, 1);
    heatOut.update(t, seg(f, 344, 362)); coolIn.update(t, 1);
    camRig(f);
    scene.updateMatrixWorld(true);
    const o = (x, y, z) => xsParts.od.localToWorld(v3(x, y, z));
    placeLabel(L.comp, o(0.05, 0.42, 0.25), seg(f, 360, 370));
    placeLabel(L.vapor, v3(40.05, 2.62, 1.1), seg(f, 342, 350) * (1 - seg(f, 384, 390)));
    placeLabel(L.cond, o(0.05, -0.36, 0.25).add(v3(0, -0.05, 0)), seg(f, 392, 402));
    placeLabel(L.release, v3(40.72, 2.4, 1.4), seg(f, 404, 414));
  }
  setCaption(t);
  renderer.render(scene, camera);
}

window.__ready = document.fonts.ready.then(() => { AC.setDisplay("", false); xsParts.ac2.setDisplay("24°", true); return true; });
window.renderFrame = (f) => { renderFrame(f); return true; };
window.TOTAL_FRAMES = PKG.total_frames;
