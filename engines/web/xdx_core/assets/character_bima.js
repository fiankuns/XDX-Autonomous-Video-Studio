// XDX reusable asset: stylized young-adult character rig (jointed arms, fingers, face, sweat) — "Bima".
// Colours come from the character bible via the style binding (see xdx_core/style_binding.js); skin tone is an asset default.
import * as THREE from "three";
import { lerp, mulberry32, canvasTex, noiseFill, std, mesh, rbox, capsule, v3 } from "../kit.js";

export const ASSET_ID = "char_bima_stylized_v1";
export const SKIN_DEFAULT = "#C68A5E";

export function createBimaFactory({ SKIN = SKIN_DEFAULT, SHIRT, PANTS, HAIR }) {
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
  mesh(new THREE.TorusGeometry(0.163, 0.012, 10, 40), std("#C98E14", 0.85), v3(0, 0.865, 0), root).rotation.x = Math.PI / 2;
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
    for (let k = 0; k < 4; k++) {
      const fg = new THREE.Group(); fg.position.set(-0.0285 + k * 0.019, -0.004, 0); fingers.add(fg);
      mesh(capsule(0.0082, 0.022), skin, v3(0, -0.014, 0), fg);
      const tip = new THREE.Group(); tip.position.set(0, -0.03, 0); fg.add(tip);
      mesh(capsule(0.0078, 0.016), skin, v3(0, -0.01, 0), tip);
      fg.userData.tip = tip;
    }
    const thumb = new THREE.Group(); thumb.position.set(-s * 0.04, -0.035, 0.012); wr.add(thumb);
    const tm = mesh(capsule(0.012, 0.035), skin, v3(0, -0.022, 0), thumb);
    thumb.rotation.z = -s * 0.5;
    arms.push({ sh, el, wr, fingers, thumb, s });
  }
  return { root, head, eyes, mouthOpen, smile, sweat, arms, legs, torso };
}
  return makeBima;
}
