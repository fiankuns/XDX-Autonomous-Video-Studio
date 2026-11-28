// XDX Phase 02A visual engine (VISUAL_ONLY_BENCHMARK) for bench_p02a_ac_15s — Three.js 0.187.0, SwiftShader-safe.
// Deterministic: every frame is a pure function of the frame index (seeded PRNG only, no wall clock).
// Generic machinery lives in ../xdx_core (kit, comets, timeline, barrier, style binding, assets); this file is only
// the topic choreography (room set, cross-section set, shot beats).
import * as THREE from "three";
import { clamp, lerp, seg, ease, easeOut, mulberry32, v3, canvasTex, noiseFill, std, mesh, rbox, capsule, glowTex, arrowTex } from "../xdx_core/kit.js";
import { createCometsClass } from "../xdx_core/comets.js";
import { buildTimeline } from "../xdx_core/timeline.js";
import { createAssetLoadBarrier } from "../xdx_core/barrier.js";
import { bindCharacterPalette } from "../xdx_core/style_binding.js";
import { createBimaFactory } from "../xdx_core/assets/character_bima.js";
import { createIndoorACFactory } from "../xdx_core/assets/indoor_ac.js";

const barrier = createAssetLoadBarrier();
barrier.require("font:PJS-800", document.fonts.load("800 60px PJS"));
barrier.require("font:PJS-700", document.fonts.load("700 26px PJS"));
await barrier.settle();
if (barrier.failed()) throw new Error("Asset load barrier failed: " + JSON.stringify(barrier.report()));

const W = 1080, H = 1920, FPS = 30;
// Shot ranges and caption cues come from the signed package (storyboard.json + caption_audio_plan.json),
// injected by scripts/render_phase02a_visual.py as window.__XDX_PACKAGE. The choreography below is authored for
// bench_p02a_ac_15s, so the shot ranges must match exactly or the scene refuses to render.
const PKG = window.__XDX_PACKAGE;
const EXPECTED_SHOTS = [["S001", 0, 105], ["S002", 105, 210], ["S003", 210, 330], ["S004", 330, 450]];
if (!PKG || PKG.project_id !== "bench_p02a_ac_15s") throw new Error("XDX package data missing or not bench_p02a_ac_15s");
if (JSON.stringify(PKG.shots) !== JSON.stringify(EXPECTED_SHOTS)) throw new Error("Storyboard shot ranges differ from the authored choreography");
// Timing map: every beat below is anchored to a caption cue window (frames), never to a hard-coded frame number.
const { CUEF, SYNC_LEAD, cue } = buildTimeline(PKG);
const CUES = PKG.cues; // [shot_id, start_s, end_s, text, highlighted_keyword]
const { SHIRT, PANTS, HAIR, ACCENT } = bindCharacterPalette(PKG);
const SKIN = "#C68A5E";
const rnd = mulberry32(202611);


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

const Comets = createCometsClass({ camera, rnd, W, H });

const makeBima = createBimaFactory({ SKIN, SHIRT, PANTS, HAIR });
const makeIndoorAC = createIndoorACFactory();

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
  const win = new THREE.Group(); win.position.set(0.3, 1.65, -1.99); room.add(win);
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

// large wall thermometer (readable in S001/S002) + set dressing (rug, frame, clock)
const wallThermo = new THREE.Group(); wallThermo.position.set(-1.05, 1.9, -1.975); room.add(wallThermo);
{
  mesh(rbox(0.42, 0.27, 0.04, 0.03), std("#F7F7F5", 0.35), v3(0, 0, 0.02), wallThermo);
  const tt = canvasTex(512, 320, (g) => {
    g.fillStyle = "#101418"; g.beginPath(); g.roundRect(0, 0, 512, 320, 28); g.fill();
    g.fillStyle = "#8C98A4"; g.font = "700 44px PJS, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("SUHU KAMAR", 256, 52);
    g.fillStyle = "#FF5A3C"; g.font = "800 176px PJS, sans-serif"; g.fillText("32°C", 256, 190);
  });
  mesh(new THREE.PlaneGeometry(0.36, 0.225), new THREE.MeshBasicMaterial({ map: tt }), v3(0, 0, 0.042), wallThermo, { cast: false });
  const rugTex = canvasTex(512, 512, (g, w, h) => {
    g.fillStyle = "#C9B79A"; g.fillRect(0, 0, w, h);
    g.strokeStyle = "#A3876A"; g.lineWidth = 18; g.strokeRect(30, 30, w - 60, h - 60);
    g.strokeStyle = "#D98C6A"; g.lineWidth = 8; g.strokeRect(70, 70, w - 140, h - 140);
  });
  mesh(new THREE.PlaneGeometry(1.9, 1.3), std("#ffffff", 0.95, 0, { map: rugTex }), v3(0.0, 0.004, 0.35), room, { cast: false }).rotation.x = -Math.PI / 2;
  const art = canvasTex(256, 320, (g) => {
    g.fillStyle = "#F2E9DA"; g.fillRect(0, 0, 256, 320);
    g.fillStyle = "#7FB3D5"; g.fillRect(28, 28, 200, 160);
    g.fillStyle = "#F2C14E"; g.beginPath(); g.arc(170, 80, 26, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#5E8C61"; g.beginPath(); g.moveTo(28, 188); g.lineTo(100, 110); g.lineTo(160, 188); g.fill();
  });
  const frame = new THREE.Group(); frame.position.set(-2.385, 1.55, 0.75); frame.rotation.y = Math.PI / 2; room.add(frame);
  mesh(rbox(0.5, 0.62, 0.03, 0.01), std("#6B4A2E", 0.6), v3(0, 0, 0), frame);
  mesh(new THREE.PlaneGeometry(0.44, 0.55), new THREE.MeshStandardMaterial({ map: art, roughness: 0.8 }), v3(0, 0, 0.017), frame, { cast: false });
}
const AC = makeIndoorAC();
AC.g.position.set(-2.24, 2.55, -0.25);
AC.g.rotation.y = Math.PI / 2; // front faces +x (into the room)
room.add(AC.g);

const bima = makeBima();
bima.root.position.set(-0.45, 0, -0.2);
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
  const fg = new THREE.CircleGeometry(0.25, 40, Math.PI / 2 - 0.95, 1.9);
  const fm = mesh(fg, new THREE.MeshStandardMaterial({ map: fanTex, side: THREE.DoubleSide, roughness: 0.9 }), v3(0, -0.02, 0), fan);
  fm.rotation.x = Math.PI / 2; fm.rotation.z = Math.PI;
  mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.1, 8), std("#6B4A2E", 0.6), v3(0, -0.05, 0), fan);
  fan.position.set(0, -0.08, 0.02);
}
const remote = new THREE.Group(); leftArm.wr.add(remote);
let remoteTip, remoteBtn, remoteFace, pressThumb;
{
  mesh(rbox(0.07, 0.2, 0.028, 0.013), std("#EEF1F4", 0.3), v3(0, -0.09, 0.03), remote);
  const scrT = canvasTex(256, 160, (g) => {
    g.fillStyle = "#14202B"; g.beginPath(); g.roundRect(0, 0, 256, 160, 20); g.fill();
    g.fillStyle = "#7FD8FF"; g.font = "800 104px PJS, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("24°", 128, 86);
    g.fillStyle = "#5C7A90"; g.font = "700 26px PJS, sans-serif"; g.fillText("COOL", 128, 22);
  });
  mesh(new THREE.PlaneGeometry(0.056, 0.035), new THREE.MeshBasicMaterial({ map: scrT }), v3(0, -0.155, 0.0445), remote, { cast: false }).rotation.z = Math.PI; // text reads with the IR tip up
  remoteBtn = mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.007, 20), std(ACCENT, 0.4, 0, { emissive: new THREE.Color(ACCENT), emissiveIntensity: 0.15 }), v3(0, -0.105, 0.0445), remote, { cast: false });
  remoteBtn.rotation.x = Math.PI / 2;
  const glyph = canvasTex(64, 64, (g) => { g.strokeStyle = "#fff"; g.lineWidth = 7; g.lineCap = "round"; g.beginPath(); g.arc(32, 34, 17, -1.1, 4.25); g.stroke(); g.beginPath(); g.moveTo(32, 10); g.lineTo(32, 32); g.stroke(); });
  mesh(new THREE.PlaneGeometry(0.016, 0.016), new THREE.MeshBasicMaterial({ map: glyph, transparent: true }), v3(0, -0.105, 0.0485), remote, { cast: false, receive: false }).rotation.z = Math.PI;
  const pm = (txt) => canvasTex(64, 64, (g) => { g.fillStyle = "#3A4650"; g.font = "800 50px PJS, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(txt, 32, 34); });
  for (const [x, y, t] of [[-0.018, -0.07, "+"], [0.018, -0.07, "−"], [-0.018, -0.045, "▲"], [0.018, -0.045, "▼"]]) {
    mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.006, 16), std("#D2D8DE", 0.5), v3(x, y, 0.0445), remote, { cast: false }).rotation.x = Math.PI / 2;
    mesh(new THREE.PlaneGeometry(0.012, 0.012), new THREE.MeshBasicMaterial({ map: pm(t), transparent: true }), v3(x, y, 0.0482), remote, { cast: false, receive: false }).rotation.z = Math.PI;
  }
  remoteTip = new THREE.Object3D(); remoteTip.position.set(0, -0.19, 0.03); remote.add(remoteTip);
  remoteFace = new THREE.Object3D(); remoteFace.position.set(0, -0.12, 0.045); remote.add(remoteFace);
  pressThumb = new THREE.Group(); pressThumb.position.set(-0.045, -0.06, 0.05); remote.add(pressThumb);
  const thumbSkin = std(SKIN, 0.55, 0, { emissive: new THREE.Color("#3a1a0a"), emissiveIntensity: 0.12 });
  const tb = mesh(capsule(0.0115, 0.05), thumbSkin, v3(0, -0.03, 0), pressThumb);
  mesh(new THREE.SphereGeometry(0.022, 16, 12), thumbSkin, v3(0.004, 0.006, -0.012), pressThumb).scale.set(1, 1.3, 0.8); // thenar base joins the palm
  const nail = mesh(new THREE.SphereGeometry(0.009, 12, 8), std("#E8C3A8", 0.3), v3(0, -0.058, 0.007), pressThumb, { cast: false });
  nail.scale.set(1, 1.3, 0.4);
  pressThumb.rotation.z = 0.75;
  for (let k = 0; k < 4; k++) {
    const tip = mesh(capsule(0.0105, 0.026), thumbSkin, v3(0.04, -0.07 - k * 0.026, 0.03), remote);
    tip.rotation.z = Math.PI / 2 - 0.15; tip.scale.set(1, 1, 0.9);
  }
  mesh(new THREE.SphereGeometry(0.05, 20, 14), thumbSkin, v3(0.005, 0.0, 0.0), remote).scale.set(1.1, 0.7, 0.75); // palm heel at the bottom end
  mesh(new THREE.SphereGeometry(0.008, 12, 8), std("#7A1F2B", 0.2, 0, { emissive: new THREE.Color("#FF2D55"), emissiveIntensity: 0.3 }), v3(0, -0.191, 0.03), remote, { cast: false });
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
const coolLight = new THREE.PointLight("#7FCBFF", 0, 3.0, 1.8); coolLight.position.set(-1.3, 1.4, -0.25); roomLights.add(coolLight);
const acInner = new THREE.PointLight("#BFE6FF", 0, 1.2, 2); acInner.position.set(-2.05, 2.55, -0.25); roomLights.add(acInner);

// heat flow in the room (S001): warm comets rising from the room toward the AC intake
const heatCurves = [];
const hr2 = mulberry32(42);
for (let i = 0; i < 26; i++) {
  const start = v3(lerp(-1.2, 1.6, hr2()), lerp(0.4, 1.4, hr2()), lerp(-1.4, 0.9, hr2()));
  if (Math.abs(start.x + 0.45) < 0.5 && Math.abs(start.z + 0.2) < 0.6) start.x += 1.1; // keep heat paths clear of Bima's body
  const mid = v3(lerp(-1.0, 0.2, hr2()), lerp(2.0, 2.6, hr2()), lerp(-0.6, 0.4, hr2()));
  const end = v3(-2.24 + lerp(-0.05, 0.08, hr2()), 2.77, -0.25 + lerp(-0.45, 0.45, hr2()));
  heatCurves.push(new THREE.CatmullRomCurve3([start, mid, end]));
}
const heatComets = new Comets(room, 26, 7, (i) => heatCurves[i], () => new THREE.Color("#F0461E"), 0.11, 0.32, { additive: false, alpha: 0.85, gap: 0.016, arrows: true });

// big "heat route" arrow for the second caption of S001: room -> AC -> out through the wall
const routeCurve = new THREE.CatmullRomCurve3([v3(-0.75, 1.3, 0.35), v3(-1.15, 2.15, 0.45), v3(-1.7, 2.95, 0.1), v3(-2.05, 2.86, -0.2)]);
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
const ledFlash = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: "#FF3D6E", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
const sensorFlash = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: "#FF6F91", transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
room.add(sensorFlash); room.add(ledFlash);

// cool air from the louver (S002 end, S003)
// IR beam (S002): a glowing ray that grows from the remote to the AC receiver
const irBeam = mesh(new THREE.CylinderGeometry(0.006, 0.006, 1, 10, 1, true), new THREE.MeshBasicMaterial({ color: "#FF3D6E", transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false }), null, room, { cast: false, receive: false });
irBeam.geometry.translate(0, 0.5, 0);
const coolCurves = [];
const cr = mulberry32(77);
for (let i = 0; i < 24; i++) {
  const zx = -0.25 + lerp(-0.45, 0.45, cr());
  const a = v3(-2.06, 2.36, zx);
  const b = v3(-1.55 + cr() * 0.2, 2.0 - cr() * 0.25, zx * 1.1);
  const c = v3(-1.1 + cr() * 0.8, 1.35 + cr() * 0.4, zx * 1.4 + 0.25);
  coolCurves.push(new THREE.CatmullRomCurve3([a, b, c]));
}
const coolComets = new Comets(room, 24, 7, (i) => coolCurves[i], () => new THREE.Color("#5CC8FF"), 0.1, 0.45, { alpha: 0.85, gap: 0.02, arrows: true });

// S003 airflow through the evaporator (local to the AC so it follows the unit)
const evapFlowCurves = [];
const er = mulberry32(9);
for (let i = 0; i < 22; i++) {
  const x = lerp(-0.48, 0.48, (i + er() * 0.6) / 22);
  // AC local: +z = front (room), +y = up. Warm room air -> over the top -> down through fins/coil -> out the louver.
  evapFlowCurves.push(new THREE.CatmullRomCurve3([
    v3(x, 0.62, 0.62), v3(x, 0.45, 0.3), v3(x, 0.24, 0.06), v3(x, 0.06, 0.0), v3(x, -0.1, 0.03), v3(x, -0.24, 0.2), v3(x, -0.55, 0.6),
  ]));
}
const warm = new THREE.Color("#FF6A2B"), cool = new THREE.Color("#4FC3FF");
const evapComets = new Comets(AC.g, 22, 8, (i) => evapFlowCurves[i], (i, t) => warm.clone().lerp(cool, clamp((t - 0.5) / 0.12)), 0.05, 0.42, { alpha: 0.95, gap: 0.012, arrows: true });
// refrigerant inside the coil: cold liquid (deep blue, small) -> vapour (pale, larger bubbles)
const refComets = new Comets(AC.g, 40, 1, () => AC.coilCurve, (i, t) => new THREE.Color("#1E5BFF").lerp(new THREE.Color("#FFFFFF"), clamp(t * 1.3)), 0.045, 0.1, { alpha: 1, grow: true });

// ------------------------------------------------------------------ CROSS-SECTION SET (S004)
const xs = new THREE.Group(); xs.position.set(40, 0, 0); scene.add(xs);
const xsParts = {};
{
  const skyTex2 = canvasTex(512, 1024, (g, w, h) => {
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#5FB0EA"); gr.addColorStop(0.65, "#BFE4F8"); gr.addColorStop(1, "#F2E5C4");
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const sg = g.createRadialGradient(w * 0.75, h * 0.12, 0, w * 0.75, h * 0.12, w * 0.6); sg.addColorStop(0, "rgba(255,248,215,1)"); sg.addColorStop(1, "rgba(255,240,200,0)");
    g.fillStyle = sg; g.fillRect(0, 0, w, h);
  });
  mesh(new THREE.PlaneGeometry(6, 7), new THREE.MeshBasicMaterial({ map: skyTex2 }), v3(3.1, 2.8, -1.6), xs, { cast: false, receive: false });
  mesh(new THREE.PlaneGeometry(6.36, 14), std("#8DBB6E", 0.95), v3(3.18, 0.0, 4.0), xs, { cast: false }).rotation.x = -Math.PI / 2;
  const inTex = canvasTex(512, 512, (g, w, h) => noiseFill(g, w, h, "#EAD9C1", 0.06, 6000, 12));
  mesh(new THREE.PlaneGeometry(4, 7), std("#ffffff", 0.9, 0, { map: inTex }), v3(-2.15, 2.8, -1.6), xs, { cast: false, receive: false });
  mesh(new THREE.PlaneGeometry(4.36, 14), std("#B98552", 0.65), v3(-2.18, 0.0, 4.0), xs, { cast: false, receive: false }).rotation.x = -Math.PI / 2;
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
  wall.position.set(0, 3.0, -0.6); wall.castShadow = wall.receiveShadow = true; xs.add(wall); // cut face at z = +1.0
  // sleeve hole through the wall where the refrigerant lines pass
  mesh(rbox(0.34, 0.2, 0.01, 0.006), std("#2B1E19", 0.9), v3(0, 2.405, 1.0), xs, { cast: false });
  mesh(rbox(0.34, 0.012, 0.012, 0.004), std("#8E8A84", 0.6), v3(0, 2.51, 1.004), xs, { cast: false });
  mesh(rbox(0.34, 0.012, 0.012, 0.004), std("#8E8A84", 0.6), v3(0, 2.3, 1.004), xs, { cast: false });

  // indoor unit as a technical section (cut at the same plane as the wall)
  const ac2 = makeIndoorAC();
  ac2.g.position.set(-0.64, 2.55, 0.7); ac2.g.scale.setScalar(0.6); xs.add(ac2.g);
  ac2.louverPivot.rotation.x = -1.05; ac2.setDisplay("24°", true);
  xsParts.ac2 = ac2;
  mesh(new THREE.PlaneGeometry(2.3, 4.2), std("#ffffff", 0.9, 0, { map: inTex, color: "#E9D3B8" }), v3(-1.31, 2.1, 0.5), xs, { cast: false }); // interior wall behind the unit
  mesh(rbox(0.5, 0.32, 3.4, 0.02), std("#9A9690", 0.9), v3(0, -0.12, -0.6), xs); // foundation under the wall
  const shadowTex = canvasTex(256, 128, (g) => { const gr = g.createRadialGradient(128, 64, 4, 128, 64, 120); gr.addColorStop(0, "rgba(0,0,0,0.45)"); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(0, 0, 256, 128); });
  mesh(new THREE.PlaneGeometry(1.4, 0.7), new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false }), v3(0.8, 0.004, 0.8), xs, { cast: false, receive: false }).rotation.x = -Math.PI / 2;

  // outdoor unit
  const od = new THREE.Group(); od.position.set(0.8, 1.25, 0.9); xs.add(od); xsParts.od = od;
  const caseMat = std("#E8ECEF", 0.4);
  mesh(rbox(0.9, 0.03, 0.36, 0.012), caseMat, v3(0, 0.31, 0), od);
  mesh(rbox(0.9, 0.03, 0.36, 0.012), caseMat, v3(0, -0.31, 0), od);
  mesh(rbox(0.03, 0.62, 0.36, 0.012), caseMat, v3(-0.435, 0, 0), od);
  mesh(rbox(0.03, 0.62, 0.36, 0.012), caseMat, v3(0.435, 0, 0), od);
  mesh(rbox(0.9, 0.62, 0.02, 0.008), std("#C9D0D6", 0.6), v3(0, 0, -0.17), od);
  mesh(rbox(0.56, 0.6, 0.02, 0.008), caseMat, v3(-0.17, 0, 0.17), od);
  mesh(new THREE.TorusGeometry(0.22, 0.012, 10, 48), std("#3A4148", 0.4, 0.5), v3(-0.17, 0, 0.19), od);
  for (let i = 0; i < 5; i++) mesh(new THREE.TorusGeometry(0.04 + i * 0.045, 0.0035, 6, 40), std("#3A4148", 0.4, 0.5), v3(-0.17, 0, 0.195), od, { cast: false });
  for (const a of [0, Math.PI / 2]) { const sp = mesh(new THREE.BoxGeometry(0.44, 0.006, 0.004), std("#3A4148", 0.4, 0.5), v3(-0.17, 0, 0.196), od, { cast: false }); sp.rotation.z = a; }
  mesh(new THREE.CircleGeometry(0.215, 40), std("#15191D", 0.9), v3(-0.17, 0, 0.165), od, { cast: false });
  const fanHub = new THREE.Group(); fanHub.position.set(-0.17, 0, 0.175); od.add(fanHub); xsParts.fanHub = fanHub;
  mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.03, 20), std("#2A3036", 0.4), null, fanHub).rotation.x = Math.PI / 2;
  const blade = new THREE.Shape();
  blade.moveTo(0.02, -0.02); blade.quadraticCurveTo(0.12, -0.07, 0.19, -0.03); blade.quadraticCurveTo(0.2, 0.04, 0.14, 0.06); blade.quadraticCurveTo(0.07, 0.05, 0.02, 0.02); blade.closePath();
  const bladeGeo = new THREE.ExtrudeGeometry(blade, { depth: 0.006, bevelEnabled: true, bevelThickness: 0.002, bevelSize: 0.002, bevelSegments: 2 });
  for (let i = 0; i < 3; i++) { const b = mesh(bladeGeo, std("#39424A", 0.45, 0.2), null, fanHub); b.rotation.z = (i / 3) * Math.PI * 2; }
  const comp = new THREE.Group(); comp.position.set(0.25, -0.08, 0.0); od.add(comp); xsParts.comp = comp;
  mesh(new THREE.CapsuleGeometry(0.075, 0.16, 8, 24), std("#3F5E56", 0.35, 0.4), v3(0, 0, 0), comp);
  mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.03, 24), std("#2D2F33", 0.6), v3(0, -0.15, 0), comp);
  const condPts = [];
  for (let r = 0; r < 6; r++) {
    const y = 0.22 - r * 0.075;
    const xa = r % 2 === 0 ? [-0.38, 0.38] : [0.38, -0.38];
    condPts.push(v3(xa[0], y, -0.12), v3(xa[1], y, -0.12));
    if (r < 5) condPts.push(v3(xa[1] + (r % 2 === 0 ? 0.03 : -0.03), y - 0.0375, -0.12));
  }
  const condCurve = new THREE.CatmullRomCurve3(condPts, false, "catmullrom", 0.15); xsParts.condCurve = condCurve;
  mesh(new THREE.TubeGeometry(condCurve, 400, 0.011, 10, false), std("#C47A45", 0.32, 0.9), null, od);
  for (const s2 of [-1, 1]) {
    mesh(rbox(0.04, 0.04, 0.5, 0.008), std("#6E757B", 0.4, 0.7), v3(s2 * 0.3, -0.34, -0.05), od);
    mesh(rbox(0.03, 0.4, 0.03, 0.006), std("#6E757B", 0.4, 0.7), v3(s2 * 0.3, -0.5, -0.27), od);
  }
  // refrigerant lines: out of the indoor section, through the wall sleeve, down to the outdoor unit
  const pipeTop = new THREE.CatmullRomCurve3([v3(-0.32, 2.5, 0.68), v3(-0.2, 2.47, 0.88), v3(-0.12, 2.45, 1.03), v3(0.12, 2.45, 1.03), v3(0.27, 2.38, 1.03), v3(0.34, 2.0, 1.03), v3(0.38, 1.72, 1.03), v3(0.55, 1.64, 1.02), v3(0.98, 1.64, 0.98), v3(1.05, 1.42, 0.94), v3(1.05, 1.27, 0.9)]);
  const pipeBot = new THREE.CatmullRomCurve3([v3(0.45, 1.0, 0.9), v3(0.3, 1.25, 1.03), v3(0.24, 2.0, 1.03), v3(0.2, 2.33, 1.03), v3(0.12, 2.36, 1.03), v3(-0.12, 2.38, 1.03), v3(-0.2, 2.4, 0.88), v3(-0.32, 2.44, 0.68)]);
  xsParts.pipeTop = pipeTop; xsParts.pipeBot = pipeBot;
  mesh(new THREE.TubeGeometry(pipeTop, 240, 0.028, 14, false), std("#EDEDE8", 0.85, 0, { transparent: true, opacity: 0.38, depthWrite: false }), null, xs, { cast: false });
  mesh(new THREE.TubeGeometry(pipeTop, 240, 0.013, 10, false), std("#C47A45", 0.32, 0.9), null, xs);
  mesh(new THREE.TubeGeometry(pipeBot, 240, 0.012, 10, false), std("#C47A45", 0.32, 0.9), null, xs);
  const xsHemi = new THREE.HemisphereLight("#DDF0FF", "#8a7a5a", 0.95); xs.add(xsHemi);
  const xsSun = new THREE.DirectionalLight("#FFF1D6", 2.4); xsSun.position.set(4, 6, 5); xsSun.target.position.set(0.5, 1.5, 0.5);
  xsSun.castShadow = true; xsSun.shadow.mapSize.set(2048, 2048); xsSun.shadow.camera.left = -3; xsSun.shadow.camera.right = 3; xsSun.shadow.camera.top = 3; xsSun.shadow.camera.bottom = -3; xsSun.shadow.bias = -0.0004; xsSun.shadow.normalBias = 0.02;
  xs.add(xsSun); xs.add(xsSun.target);
  const warmIn = new THREE.PointLight("#FFD3A0", 1.6, 4, 1.5); warmIn.position.set(-1.3, 2.4, 1.6); xs.add(warmIn);
}
const hot = new THREE.Color("#F0461E"), hotPale = new THREE.Color("#FF9A55");
const suction = new Comets(xs, 14, 6, () => xsParts.pipeTop, () => hot, 0.09, 0.35, { alpha: 0.95, gap: 0.02, arrows: true });
const liquid = new Comets(xs, 12, 5, () => xsParts.pipeBot, () => new THREE.Color("#2F8FFF"), 0.06, 0.3, { alpha: 0.9, gap: 0.022, arrows: true });
const condFlow = new Comets(xsParts.od, 14, 1, () => xsParts.condCurve, (i, t) => hot.clone().lerp(new THREE.Color("#FFD9A8"), t), 0.032, 0.22, { alpha: 1 });
const heatOutCurves = [];
const ho = mulberry32(31);
for (let i = 0; i < 24; i++) {
  const a = v3(0.63 + (ho() - 0.5) * 0.3, 1.25 + (ho() - 0.5) * 0.3, 1.12);
  const b = v3(0.85 + ho() * 0.4, 1.5 + ho() * 0.4, 1.5 + ho() * 0.2);
  const c = v3(1.1 + ho() * 0.6, 2.0 + ho() * 0.9, 1.4 + ho() * 0.4);
  heatOutCurves.push(new THREE.CatmullRomCurve3([a, b, c]));
}
const heatOut = new Comets(xs, 24, 7, (i) => heatOutCurves[i], (i, t) => hot.clone().lerp(hotPale, t), 0.09, 0.38, { alpha: 0.9, gap: 0.02, grow: true, arrows: true });
const coolIn = new Comets(xs, 12, 6, (i) => new THREE.CatmullRomCurve3([v3(-0.92 + i * 0.05, 2.42, 0.82), v3(-1.0 + i * 0.04, 2.05, 1.05), v3(-1.3 + i * 0.03, 1.6, 1.2)]), () => new THREE.Color("#5CC8FF"), 0.07, 0.4, { alpha: 0.85, gap: 0.022, arrows: true });

// ------------------------------------------------------------------ labels (content callouts grounded in the script, not debug)
const labelsEl = document.getElementById("labels");
function makeLabel(text, kind) { const d = document.createElement("div"); d.className = "label " + kind; d.textContent = text; labelsEl.appendChild(d); return d; }
const L = {
  heat: makeLabel("Panas kamar", "warm"),
  ir: makeLabel("Sinyal inframerah", "warm"),
  evap: makeLabel("Evaporator", "cool"),
  refr: makeLabel("Refrigeran cair → menguap", "cool"),
  heat3: makeLabel("Panas kamar", "warm"),
  vapor: makeLabel("Uap panas", "warm"),
  comp: makeLabel("Kompresor", "warm"),
  cond: makeLabel("Kondensor luar", "warm"),
  release: makeLabel("Kalor ke udara luar", "warm"),
};
function placeLabel(el, worldPos, alpha) {
  const p = worldPos.clone().project(camera);
  const hw = (el.offsetWidth || 400) / 2 + 30;
  const x = clamp(((p.x + 1) / 2) * W, hw, W - hw), y = clamp(((1 - p.y) / 2) * H, 120, H - 600);
  el.style.left = `${x}px`; el.style.top = `${y}px`; el.style.opacity = String(alpha);
}
function placeScreen(el, x, y, alpha) { el.style.left = `${x}px`; el.style.top = `${y}px`; el.style.opacity = String(alpha); }

// ------------------------------------------------------------------ caption (contiguous cues switch without a fade gap)
const capbox = document.getElementById("capbox");
function setCaption(t) {
  const idx = Math.max(0, CUES.findIndex((c) => t >= c[1] && t < c[2]));
  const [, a, , text, kw] = CUES[idx];
  const k = kw ? text.indexOf(kw) : -1;
  capbox.innerHTML = k >= 0 ? `${text.slice(0, k)}<b>${kw}</b>${text.slice(k + kw.length)}` : text;
  const prevEnd = idx > 0 ? CUES[idx - 1][2] : -1;
  const contiguous = a - prevEnd < 0.1;
  const fi = contiguous ? 1 : clamp((t - a) / 0.2);
  capbox.style.setProperty("--o", String(easeOut(fi)));
  capbox.style.setProperty("--ty", `${lerp(18, 0, easeOut(fi))}px`);
}

// ------------------------------------------------------------------ poses
function poseNeutral() {
  for (const a of bima.arms) {
    a.sh.rotation.set(0, 0, a.s * 0.12); a.el.rotation.set(-0.15, 0, 0); a.wr.rotation.set(0, 0, 0); a.fingers.rotation.set(0, 0, 0); a.thumb.rotation.set(0, 0, -a.s * 0.5);
    for (const fg of a.fingers.children) { fg.rotation.set(0, 0, 0); fg.userData.tip.rotation.set(0, 0, 0); }
  }
  for (const l of bima.legs) { l.hip.rotation.set(0, 0, 0); l.knee.rotation.set(0, 0, 0); }
  bima.head.rotation.set(0, 0, 0);
  bima.torso.rotation.set(0, 0, 0);
}
function grip(arm, amount) { for (const fg of arm.fingers.children) { fg.rotation.x = 1.1 * amount; fg.userData.tip.rotation.x = 1.2 * amount; } }
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

// ------------------------------------------------------------------ frame evaluation (all beats anchored to caption cues)
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3(), camPos = new THREE.Vector3(), camTgt = new THREE.Vector3();
const acSensorW = new THREE.Vector3(), acCenterW = new THREE.Vector3();
const WORLD_UP = v3(0, 1, 0);
function look(fov, px, py, pz, tx, ty, tz, up = WORLD_UP) { camera.up.copy(up); camera.fov = fov; camera.position.set(px, py, pz); camera.lookAt(tx, ty, tz); camera.updateProjectionMatrix(); camera.updateMatrixWorld(true); }

function renderFrame(f) {
  const t = f / FPS;
  const shot = f < CUEF.S002[0].a ? 0 : f < CUEF.S003[0].a ? 1 : f < CUEF.S004[0].a ? 2 : 3;
  room.visible = shot <= 2;
  xs.visible = shot === 3;
  poseNeutral();
  for (const el of Object.values(L)) el.style.opacity = "0";
  AC.louverPivot.rotation.x = 0;
  AC.setDisplay("", false);
  AC.front.visible = true; AC.panelMat.opacity = 1; AC.panelMat.transparent = false; AC.front.position.set(0, 0, 0);
  AC.copper.transparent = false; AC.copper.opacity = 1;
  fan.visible = false; remote.visible = false;
  route.visible = false; routeHead.visible = false;
  irGroup.visible = false; sensorFlash.visible = false; irBeam.visible = false; ledFlash.visible = false;
  coolLight.intensity = 0; acInner.intensity = 0; key.intensity = 2.4; hemi.intensity = 0.85; sun.intensity = 6;
  heatComets.group.visible = false; coolComets.group.visible = false; evapComets.group.visible = false; refComets.group.visible = false;
  bima.root.visible = true;
  bima.sweat.forEach((s) => (s.d.visible = true));
  for (const a of bima.arms) a.thumb.visible = true;
  scene.updateMatrixWorld(true);
  AC.sensor.getWorldPosition(acSensorW); AC.g.getWorldPosition(acCenterW);

  if (shot === 0) {
    const c0 = cue("S001", 0), c1 = cue("S001", 1);
    const tt = ease(seg(f, c0.a, c1.b));
    look(62, lerp(1.55, 1.3, tt), lerp(2.25, 2.1, tt), lerp(4.1, 3.6, tt), -0.95, 1.2, -0.6);
    bima.root.rotation.y = 0.5;
    // c0: overheated, fanning; c1 (lead 0.3 s): glances up at the AC while the heat route draws to it
    const glance = ease(seg(f, c1.a - SYNC_LEAD, c1.a + 10));
    const w = Math.sin(t * 2 * Math.PI * 2.4) * (1 - 0.6 * glance);
    const ra = rightArm;
    ra.sh.rotation.set(-0.75, 0.55, 0.15);
    ra.el.rotation.set(-2.15 + 0.18 * w, 0, 0);
    ra.wr.rotation.set(0.1, 0.0, 0.9 * w);
    grip(ra, 0.8);
    fan.visible = true;
    leftArm.sh.rotation.set(0.05, 0, -0.18); leftArm.el.rotation.set(-0.35, 0, 0);
    bima.head.rotation.set(lerp(0.12 + 0.02 * w, -0.42, glance), lerp(-0.1, -1.0, glance), 0.05 * w * (1 - glance));
    for (const e of bima.eyes) e.e.children[1].position.x = lerp(0, -0.008, glance);
    bima.torso.rotation.y = 0.04 * w;
    face(1, 0, f % 70 > 66 ? 0.9 : 0);
    bima.sweat.forEach((s, i) => { s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; });
    heatComets.group.visible = true;
    // c1 "memindahkan panas": the room heat visibly streams into the AC intake (denser, larger arrows)
    const rt = ease(seg(f, c1.a - SYNC_LEAD, c1.a + 12));
    heatComets.update(t, 1, 1 + 0.45 * rt);
    scene.updateMatrixWorld(true);
    placeScreen(L.heat, 760, 700, seg(f, c0.a + 10, c0.a + 20) * (1 - seg(f, c1.a - 8, c1.a)));
  } else if (shot === 1) {
    const c0 = cue("S002", 0), c1 = cue("S002", 1);
    const L0 = c0.b - c0.a;
    const raiseEnd = c0.a + Math.round(L0 * 0.14);
    const insA = c0.a + Math.round(L0 * 0.12), insB = c0.a + Math.round(L0 * 0.5); // ~0.9 s ease into the insert (was 0.5 s)
    const pressA = c0.a + Math.round(L0 * 0.54), pressB = c0.a + Math.round(L0 * 0.62);
    const irA = pressA + 2, irB = c1.a - SYNC_LEAD - 2;
    const openA = c1.a - SYNC_LEAD, openB = c1.a + 12;
    bima.root.rotation.y = -0.7;
    const raise = easeOut(seg(f, c0.a, raiseEnd));
    const ra = leftArm;
    ra.sh.rotation.set(lerp(-0.2, -2.05, raise), lerp(0, -0.8, raise), lerp(-0.12, -0.05, raise));
    ra.el.rotation.set(lerp(-0.3, -0.15, raise), 0, 0);
    ra.wr.rotation.set(lerp(0, -0.25, raise), 0, 0);
    grip(ra, raise);
    remote.visible = true;
    const press = seg(f, pressA, pressA + 4) * (1 - seg(f, pressB, pressB + 4));
    ra.thumb.visible = false;
    // thumb hovers over the power/24° button, then presses it (moves onto the button face)
    pressThumb.position.set(lerp(-0.045, -0.025, press), lerp(-0.06, -0.072, press), lerp(0.072, 0.052, press));
    remoteBtn.material.emissiveIntensity = 0.15 + 2.6 * press;
    rightArm.sh.rotation.set(0.0, 0, 0.15); rightArm.el.rotation.set(-0.3, 0, 0);
    bima.head.rotation.set(-0.3 * raise, -0.35 * raise, 0);
    const relief = ease(seg(f, openB, c1.b));
    face(1 - 0.5 * relief, relief, 0);
    bima.sweat.forEach((s, i) => { s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; });
    if (f >= irB) AC.setDisplay("24°", true);
    const open = ease(seg(f, openA, openB));
    AC.louverPivot.rotation.x = -1.05 * open;
    coolLight.intensity = 1.2 * open;
    scene.updateMatrixWorld(true);
    remoteTip.getWorldPosition(tmpA);
    remoteFace.getWorldPosition(tmpB);
    const faceN = v3(0, 0, 1).applyQuaternion(remoteFace.getWorldQuaternion(new THREE.Quaternion()));
    // camera: medium on Bima -> close insert on the thumb/remote -> follow the IR ray to the AC -> hold on the louver
    const ins = ease(seg(f, insA, insB));
    const toAC = f >= pressB + 4 ? 1 : 0; // clean cut from the remote insert to the AC as the IR fires
    const mediumPos = v3(-1.05, 1.62, 1.75), mediumTgt = v3(-0.5, 1.75, -0.25);
    const remoteC = tmpB.clone();
    const insertPos = remoteC.clone().addScaledVector(faceN, 0.42).add(v3(0, -0.05, 0));
    const acPush = ease(seg(f, pressB + 4, c1.b));
    const acPos = v3(lerp(-0.45, -0.62, acPush), lerp(1.9, 1.98, acPush), lerp(1.55, 1.3, acPush)), acTgt = acCenterW.clone().add(v3(0.15, -0.2, 0.0));
    const beamHead = tmpA.clone().lerp(acSensorW, seg(f, irA, irB));
    // orbit around the remote while closing in (no straight line through the set dressing)
    const dirMed = mediumPos.clone().sub(remoteC); const dMed = dirMed.length(); dirMed.normalize();
    const orbitDir = dirMed.clone().lerp(faceN, ins).normalize();
    const orbitPos = remoteC.clone().addScaledVector(orbitDir, lerp(dMed, 0.42, ins)).add(v3(0, -0.05 * ins, 0));
    camPos.copy(orbitPos).lerp(acPos, toAC);
    camTgt.copy(mediumTgt).lerp(remoteC, ins).lerp(acTgt, toAC);
    // during the insert the camera's up follows the remote's long axis (tip at the top of the frame)
    const tipUp = tmpA.clone().sub(remoteC).normalize();
    const camUp = WORLD_UP; // keep the horizon level (no roll); tipUp kept for reference only
    look(lerp(56, 42, ins) * (1 - toAC) + 54 * toAC, camPos.x, camPos.y, camPos.z, camTgt.x, camTgt.y, camTgt.z, camUp);
    // IR ray grows from the remote tip to the receiver
    const ir = seg(f, irA, irB);
    if (ir > 0 && f < c1.a + 6) {
      irBeam.visible = toAC > 0.5; // inside the macro insert the IR is shown by the LED flash, not a cylinder
      const dir = acSensorW.clone().sub(tmpA); const len = dir.length();
      irBeam.position.copy(tmpA); irBeam.quaternion.setFromUnitVectors(v3(0, 1, 0), dir.normalize());
      irBeam.scale.set(1, len * ir, 1);
      irBeam.material.opacity = 0.85 * (1 - seg(f, c1.a - 4, c1.a + 6));
      irGroup.visible = true;
      irDots.forEach((d, i) => { const u = ((f - irA) / 14 - i * 0.12) % 1; d.visible = u > 0 && u < ir; d.position.lerpVectors(tmpA, acSensorW, clamp(u)); d.scale.setScalar(0.045); d.material.opacity = 0.95; });
      placeLabel(L.ir, tmpA.clone().lerp(acSensorW, 0.55).add(v3(0, 0.12, 0)), seg(f, irA + 6, irA + 12) * (1 - seg(f, c1.a - 6, c1.a)));
    }
    const led = seg(f, pressA + 1, pressA + 3) * (1 - seg(f, irA + 10, irA + 16));
    if (led > 0) { ledFlash.visible = true; ledFlash.position.copy(tmpA); ledFlash.scale.setScalar(0.05 + 0.03 * Math.sin(f * 1.7) ** 2); ledFlash.material.opacity = led; }
    const flash = seg(f, irB - 2, irB) * (1 - seg(f, irB + 2, irB + 10));
    if (flash > 0) { sensorFlash.visible = true; sensorFlash.position.copy(acSensorW); sensorFlash.scale.setScalar(0.25 * flash + 0.02); sensorFlash.material.opacity = flash; }
    if (open > 0.15) { coolComets.group.visible = true; coolComets.update(t, clamp((open - 0.15) * 2)); }
    scene.updateMatrixWorld(true);
  } else if (shot === 2) {
    const c0 = cue("S003", 0), c1 = cue("S003", 1);
    const tt = ease(seg(f, c0.a, c1.b));
    look(lerp(60, 56, tt), lerp(-0.55, -0.72, tt), lerp(2.15, 2.2, tt), lerp(1.3, 1.12, tt), -2.2, 2.4, -0.25);
    bima.root.visible = false;
    AC.setDisplay("24°", true);
    AC.louverPivot.rotation.x = -1.05;
    const lift = ease(seg(f, c0.a + 2, c0.a + 16));
    AC.front.position.set(0, 0.35 * lift, 0.55 * lift);
    AC.panelMat.transparent = true; AC.panelMat.opacity = 1 - lift;
    AC.front.visible = lift < 0.98;
    // x-ray copper so the refrigerant inside the coil (liquid -> vapour) is visible
    const xr = seg(f, c0.a + 14, c0.a + 26);
    AC.copper.transparent = xr > 0; AC.copper.opacity = lerp(1, 0.3, xr); AC.copper.depthWrite = xr < 0.5;
    key.intensity = 1.2; hemi.intensity = 0.45; sun.intensity = 2.5;
    acInner.intensity = 1.6 * lift; coolLight.intensity = 1.5;
    AC.blower.rotation.x = -t * 14;
    const heatBoost = 1 + 0.6 * ease(seg(f, c1.a - SYNC_LEAD, c1.a + 8));
    evapComets.group.visible = true; evapComets.update(t, seg(f, c0.a + 14, c0.a + 26), heatBoost);
    refComets.group.visible = true; refComets.update(t, seg(f, c0.a + 18, c0.a + 30));
    scene.updateMatrixWorld(true);
    const a = (x, y, z) => AC.g.localToWorld(v3(x, y, z));
    placeLabel(L.evap, a(-0.3, 0.27, 0.3), seg(f, c0.a + 20, c0.a + 30));
    placeLabel(L.refr, a(0.2, -0.36, 0.45), seg(f, c0.a + 34, c0.a + 44));
    placeLabel(L.heat3, a(0.3, 0.45, 0.7), seg(f, c1.a - SYNC_LEAD, c1.a + 2));
  } else {
    const c0 = cue("S004", 0), c1 = cue("S004", 1);
    const tt = ease(seg(f, c0.a, c1.b));
    look(64, 40 + lerp(0.0, 0.35, tt), lerp(2.15, 1.95, tt), lerp(5.4, 5.1, tt), 40 + lerp(0.1, 0.42, tt), lerp(2.0, 1.8, tt), 0.9);
    xsParts.fanHub.rotation.z = -t * 18;
    const pulse = 1 + 0.08 * Math.sin(t * 2 * Math.PI * 4);
    xsParts.comp.scale.set(pulse, 1 / pulse, pulse);
    suction.update(t, 1); liquid.update(t, 1); condFlow.update(t, 1);
    heatOut.update(t, ease(seg(f, c1.a - SYNC_LEAD, c1.a + 10)) * 0.9 + 0.1, 1 + 0.3 * seg(f, c1.a, c1.b));
    coolIn.update(t, 1);
    scene.updateMatrixWorld(true);
    const o = (x, y, z) => xsParts.od.localToWorld(v3(x, y, z));
    placeLabel(L.vapor, v3(40.05, 2.62, 1.1), seg(f, c0.a + 4, c0.a + 12) * (1 - seg(f, c0.a + 46, c0.a + 52)));
    placeLabel(L.comp, o(0.62, -0.08, 0.2), seg(f, c0.a + 30, c0.a + 40));
    placeLabel(L.cond, o(-0.2, -0.5, 0.3), seg(f, c1.a - SYNC_LEAD, c1.a + 2));
    placeLabel(L.release, v3(41.25, 2.55, 1.4), seg(f, c1.a, c1.a + 8));
  }
  setCaption(t);
  renderer.render(scene, camera);
}

window.__ready = document.fonts.ready.then(() => { AC.setDisplay("", false); return true; });
window.renderFrame = (f) => { renderFrame(f); return true; };
window.TOTAL_FRAMES = PKG.total_frames;
