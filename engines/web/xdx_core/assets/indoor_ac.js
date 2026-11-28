// XDX reusable asset: articulated indoor split air-conditioner (louver pivot, display, IR sensor, coil, fins, blower, removable panel).
import * as THREE from "three";
import { mesh, rbox, std, v3 } from "../kit.js";

export const ASSET_ID = "prop_indoor_ac_articulated_v1";

export function createIndoorACFactory() {
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
  const coil = mesh(new THREE.TubeGeometry(coilCurve, 400, 0.011, 12, false), copper, null, g, { receive: false });
  const finGeo = new THREE.BoxGeometry(0.004, 0.24, 0.085);
  const fins = new THREE.InstancedMesh(finGeo, std("#C9D2DA", 0.35, 0.8), 44);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < 44; i++) { m4.makeTranslation(-0.5 + i * (1.0 / 43), 0.01, 0.0); fins.setMatrixAt(i, m4); }
  fins.castShadow = false; fins.receiveShadow = false; g.add(fins);
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
  panelMat.depthWrite = true;
  return { g, front, panelMat, louverPivot, coilCurve, setDisplay, sensor, blower, Wd, Hd, Dd, copper };
}
  return makeIndoorAC;
}
