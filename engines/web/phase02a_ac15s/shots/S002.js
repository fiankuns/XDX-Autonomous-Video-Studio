// S002 choreography (one file per shot: editing it invalidates ONLY this shot's selective re-render).
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

export function renderS002(ctx, f, t) {
  const { AC, SYNC_LEAD, WORLD_UP, acCenterW, acSensorW, bima, camera, coolComets, coolLight, cue, face, grip, irBeam, irDots, irGroup, ledFlash, leftArm, look, placeSpec, pressRing, pressThumb, remote, remoteBtn, remoteFace, remoteTip, rightArm, scene, sensorFlash, setRemoteTemp, tmpA, tmpB } = ctx;
    const c0 = cue("S002", 0), c1 = cue("S002", 1);
    const L0 = c0.b - c0.a;
    const raiseA = c0.a, raiseB = c0.a + Math.round(L0 * 0.22);
    const turnA = c0.a + Math.round(L0 * 0.3), turnB = c0.a + Math.round(L0 * 0.42);
    const cutIn = c0.a + Math.round(L0 * 0.46);               // cutaway to the remote once Bima has turned to the AC
    const pressA = c0.a + Math.round(L0 * 0.54), pressB = c0.a + Math.round(L0 * 0.72);
    const irA = pressA + 2, irB = c1.a - SYNC_LEAD - 2;
    const openA = c1.a - SYNC_LEAD, openB = c1.a + 12;
    bima.root.rotation.y = -0.7;
    const raise = easeOut(seg(f, raiseA, raiseB));
    const turn = ease(seg(f, turnA, turnB));
    bima.torso.rotation.x = 0.04;
    scene.updateMatrixWorld(true);
    lookHead(bima.head, acSensorW, turn);                      // the head turns to the AC BEFORE the press
    scene.updateMatrixWorld(true);
    const headP = bima.head.getWorldPosition(new THREE.Vector3());
    const rq = bima.root.getWorldQuaternion(new THREE.Quaternion());
    const rFwd = v3(0, 0, 1).applyQuaternion(rq), rLeft = v3(-1, 0, 0).applyQuaternion(rq);
    const holdT = headP.clone().addScaledVector(rFwd, 0.3).addScaledVector(rLeft, 0.1).add(v3(0, -0.24, 0));
    const hangT = bima.root.localToWorld(v3(-0.25, 0.83, 0.03));
    const wristL = hangT.clone().lerp(holdT, raise);
    const shL = leftArm.sh.getWorldPosition(new THREE.Vector3());
    solveArm(leftArm, wristL, shL.clone().add(v3(-0.4, -0.9, -0.3)));
    scene.updateMatrixWorld(true);
    const toACdir = acSensorW.clone().sub(wristL).normalize();
    aimTwo(leftArm.wr, v3(0, -1, 0), v3(0, -1, 0).lerp(toACdir, raise).normalize(), v3(0, 0, 1), rFwd.clone().lerp(headP.clone().sub(wristL).normalize(), raise).normalize()); // IR tip at the AC, screen toward his face
    grip(leftArm, raise);
    remote.visible = true;
    leftArm.thumb.visible = false;
    const press = seg(f, pressA, pressA + 4) * (1 - seg(f, pressB, pressB + 4));
    // thumb hovers over the power/24° button, then presses it (moves onto the button face)
    pressThumb.quaternion.setFromUnitVectors(v3(0, -1, 0), v3(lerp(-0.02, 0, press), lerp(-0.085, -0.105, press), lerp(0.09, 0.054, press)).sub(pressThumb.position).normalize());
    remoteBtn.material.emissiveIntensity = 0.15 + 2.6 * press;
    const ripple = seg(f, pressA + 3, pressA + 14); pressRing.material.opacity = 0.9 * (1 - ripple) * (ripple > 0 ? 1 : 0); pressRing.scale.setScalar(1 + 1.8 * ripple); // visible "click" feedback
    setRemoteTemp(f >= pressA + 6 ? "24°" : "28°"); // the setting visibly changes when the button is pressed
    rightArm.sh.rotation.set(0.0, 0, 0.15); rightArm.el.rotation.set(-0.3, 0, 0);
    const relief = ease(seg(f, openB, c1.b));
    face((0.55 + 0.45 * seg(f, cutIn, c1.a)) * (1 - 0.5 * relief), relief, 0); // alert eyes while turning to the AC; discomfort returns until the AC opens
    bima.sweat.forEach((s, i) => { s.d.position.y = s.y0 - ((t * 0.08 + i * 0.37) % 1) * 0.07; });
    if (f >= irB) AC.setDisplay("24°", true);
    const open = ease(seg(f, openA, openB));
    AC.louverPivot.rotation.x = -1.05 * open;
    coolLight.intensity = 1.2 * open;
    scene.updateMatrixWorld(true);
    remoteTip.getWorldPosition(tmpA);
    remoteFace.getWorldPosition(tmpB);
    const faceN = v3(0, 0, 1).applyQuaternion(remoteFace.getWorldQuaternion(new THREE.Quaternion()));
    // camera: medium on Bima (raise + head turn) -> CUT to the remote (thumb presses) -> CUT to the AC as the IR fires. Level horizon always.
    const toAC = f >= pressB + 4 ? 1 : 0;
    const inInsert = f >= cutIn && !toAC;
    if (inInsert) { bima.head.visible = false; bima.torso.visible = false; } // macro cutaway: nothing between the lens and the remote
    const remoteC = tmpB.clone();
    const mediumPos = v3(-1.05, 1.62, 1.75).lerp(v3(-0.95, 1.66, 1.6), seg(f, c0.a, cutIn)), mediumTgt = v3(-0.5, 1.75, -0.25);
    const remoteMid = remote.localToWorld(v3(0, -0.085, 0.04));
    const remoteUp = remote.localToWorld(v3(0, -0.19, 0)).sub(remote.localToWorld(v3(0, 0, 0))).normalize(); // IR tip up on screen
    const insertPos = remoteMid.clone().addScaledVector(faceN, lerp(0.56, 0.47, seg(f, cutIn, pressB + 4)));
    const acPush = ease(seg(f, pressB + 4, c1.b));
    const acPos = v3(lerp(-0.45, -0.62, acPush), lerp(1.9, 1.98, acPush), lerp(1.55, 1.3, acPush)), acTgt = acCenterW.clone().add(v3(0.15, -0.2, 0.0));
    const camP = toAC ? acPos : inInsert ? insertPos : mediumPos;
    const camT = toAC ? acTgt : inInsert ? remoteMid : mediumTgt;
    look(toAC ? 54 : inInsert ? 42 : 56, camP.x, camP.y, camP.z, camT.x, camT.y, camT.z, inInsert ? remoteUp : WORLD_UP);
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
      placeSpec("S002", f);
    }
    const led = seg(f, pressA + 1, pressA + 3) * (1 - seg(f, irA + 10, irA + 16));
    if (led > 0) { ledFlash.visible = true; ledFlash.position.copy(tmpA); ledFlash.scale.setScalar(0.05 + 0.03 * Math.sin(f * 1.7) ** 2); ledFlash.material.opacity = led; }
    const flash = seg(f, irB - 2, irB) * (1 - seg(f, irB + 2, irB + 10));
    if (flash > 0) { sensorFlash.visible = true; sensorFlash.position.copy(acSensorW); sensorFlash.scale.setScalar(0.25 * flash + 0.02); sensorFlash.material.opacity = flash; }
    if (open > 0.15) { coolComets.group.visible = true; coolComets.update(t, clamp((open - 0.15) * 2)); }
    scene.updateMatrixWorld(true);
}
