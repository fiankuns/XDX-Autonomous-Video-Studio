// S001 choreography (one file per shot: editing it invalidates ONLY this shot's selective re-render).
// Pure function of the frame index; shared scene objects arrive through ctx (built once in scene.js).
import * as THREE from "three";
import { clamp, lerp, seg, ease, easeOut, mulberry32, v3, canvasTex, noiseFill, std, mesh, rbox, capsule, glowTex, arrowTex } from "../../xdx_core/kit.js";
import { createCometsClass } from "../../xdx_core/comets.js";
import { buildTimeline } from "../../xdx_core/timeline.js";
import { createAssetLoadBarrier } from "../../xdx_core/barrier.js";
import { bindCharacterPalette } from "../../xdx_core/style_binding.js";
import { createCallouts } from "../../xdx_core/callouts.js";
import { solveArm, aimTwo, lookHead, anchor } from "../../xdx_core/rig_ik.js";
import { createBimaFactory } from "../../xdx_core/assets/character_bima.js";
import { createIndoorACFactory } from "../../xdx_core/assets/indoor_ac.js";

export function renderS001(ctx, f, t) {
  const { AC, SYNC_LEAD, bima, cue, face, fan, grip, heatComets, leftArm, look, placeSpec, rightArm, room, scene } = ctx;
    const c0 = cue("S001", 0), c1 = cue("S001", 1);
    const L0 = c0.b - c0.a;
    const tt = ease(seg(f, c0.a, c1.b));
    look(62, lerp(0.85, 0.65, tt), lerp(2.3, 2.15, tt), lerp(4.1, 3.6, tt), -1.15, 1.55, -0.6);
    bima.root.rotation.y = 0.5;
    const w = Math.sin(t * 2 * Math.PI * 2.6), w2 = Math.cos(t * 2 * Math.PI * 2.6); // fanning rhythm
    bima.torso.rotation.x = 0.1;                          // slumped, tired
    bima.head.rotation.set(0.2 + 0.03 * w, -0.1, 0.06);   // chin slightly down; no glance at the AC in this shot
    face(1, 0, f % 70 > 66 ? 0.9 : 0);
    scene.updateMatrixWorld(true);
    const headP = bima.head.getWorldPosition(new THREE.Vector3());
    const hq = bima.head.getWorldQuaternion(new THREE.Quaternion());
    const fwd = v3(0, 0, 1).applyQuaternion(hq), side = v3(1, 0, 0).applyQuaternion(hq), upv = v3(0, 1, 0).applyQuaternion(hq);
    const faceC = headP.clone().addScaledVector(fwd, 0.1).addScaledVector(upv, -0.03);
    // fan hand: the forearm holds the fist in front of the face; the WRIST rocks forward/back and the fan (child of the wrist) follows it.
    const fanC = faceC.clone().addScaledVector(fwd, 0.22).addScaledVector(side, 0.03).addScaledVector(upv, -0.05);
    const toFace = faceC.clone().sub(fanC).normalize();
    const bladeDir = upv.clone().multiplyScalar(0.8).addScaledVector(toFace, 0.5).normalize(); // blade extends up-and-in from the fist
    const wristR = fanC.clone().addScaledVector(bladeDir, -0.35).addScaledVector(fwd, 0.035 * w2).addScaledVector(upv, 0.012 * w); // small forearm drive
    const shR = rightArm.sh.getWorldPosition(new THREE.Vector3());
    solveArm(rightArm, wristR, shR.clone().add(v3(0.25, -0.9, 0.0)));
    scene.updateMatrixWorld(true);
    aimTwo(rightArm.wr, v3(0, -1, 0), bladeDir, v3(0, 0, 1), toFace);
    rightArm.wr.rotateX(0.4 + 0.4 * w);                 // wrist flexion: the blade sweeps toward the face and back, flat side always roughly toward him
        grip(rightArm, 0.8);
    fan.visible = true;
    // other hand wipes the forehead during the first part of caption 1, then drops
    const wipe = ease(seg(f, c0.a + 4, c0.a + 14)) * (1 - ease(seg(f, c1.a + Math.round((c1.b - c1.a) * 0.6), c1.a + Math.round((c1.b - c1.a) * 0.6) + 12)));
    const foreheadC = headP.clone().addScaledVector(upv, 0.09).addScaledVector(fwd, 0.17);
    const swipe = Math.sin(t * 2 * Math.PI * 1.7);
    const wipeT = foreheadC.clone().addScaledVector(side, -0.15 * swipe).addScaledVector(upv, 0.02 * Math.cos(t * 2 * Math.PI * 3.4));
    const hangT = bima.root.localToWorld(v3(-0.25, 0.83, 0.03));
    const wristL = hangT.clone().lerp(wipeT, wipe);
    const shL = leftArm.sh.getWorldPosition(new THREE.Vector3());
    solveArm(leftArm, wristL, shL.clone().add(side.clone().multiplyScalar(-0.9 * wipe)).add(v3(0, -0.9 * (1 - 0.75 * wipe), -0.1))); // elbow swings OUT to the side while wiping
    scene.updateMatrixWorld(true);
    const aL = v3(0, -1, 0).lerp(upv.clone().multiplyScalar(0.7).addScaledVector(side, -0.4), wipe).normalize();
    const bL = v3(0, 0, 1).lerp(foreheadC.clone().sub(wristL).normalize(), wipe).normalize();
    aimTwo(leftArm.wr, v3(0, -1, 0), aL, v3(0, 0, 1), bL);
    grip(leftArm, 0.5 * wipe);
    bima.sweat.forEach((s, i) => { s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; });
    heatComets.group.visible = true;
    // c1 "memindahkan panas": the room heat visibly streams into the AC intake (denser, larger arrows)
    const rt = ease(seg(f, c1.a - SYNC_LEAD, c1.a + 12));
    heatComets.update(t, 1, 1 + 0.45 * rt);
    scene.updateMatrixWorld(true);
    placeSpec("S001", f);
}
