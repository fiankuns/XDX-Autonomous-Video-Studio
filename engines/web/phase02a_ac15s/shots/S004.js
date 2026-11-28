// S004 choreography (one file per shot: editing it invalidates ONLY this shot's selective re-render).
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

export function renderS004(ctx, f, t) {
  const { SYNC_LEAD, compBase, condFlow, coolIn, cue, heatOut, liquid, look, placeSpec, scene, suction, xsParts } = ctx;
    const c0 = cue("S004", 0), c1 = cue("S004", 1);
    const tt = ease(seg(f, c0.a, c1.b));
    look(67, 39.9 + lerp(0.0, 0.15, tt), lerp(2.15, 1.95, tt), lerp(5.5, 5.2, tt), 39.95 + lerp(0.1, 0.25, tt), lerp(2.0, 1.8, tt), 0.9);
    xsParts.fanHub.rotation.z = -t * 18;
    const beat = Math.sin(t * 2 * Math.PI * 4);
    const pulse = 1 + 0.15 * beat;
    xsParts.comp.scale.set(pulse, 1 / pulse, pulse);
    xsParts.comp.position.set(compBase.x + 0.006 * Math.sin(t * 2 * Math.PI * 8), compBase.y + 0.01 * beat, compBase.z); // pumping stroke + vibration
    suction.update(t, 1); liquid.update(t, 1); condFlow.update(t, 1);
    heatOut.update(t, ease(seg(f, c1.a - SYNC_LEAD, c1.a + 10)) * 0.9 + 0.1, 1 + 0.3 * seg(f, c1.a, c1.b));
    coolIn.update(t, 1);
    scene.updateMatrixWorld(true);
    const o = (x, y, z) => xsParts.od.localToWorld(v3(x, y, z));
    placeSpec("S004", f);
}
