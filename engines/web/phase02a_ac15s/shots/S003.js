// S003 choreography (one file per shot: editing it invalidates ONLY this shot's selective re-render).
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

export function renderS003(ctx, f, t) {
  const { AC, SYNC_LEAD, acInner, bima, coolLight, cue, evapComets, hemi, icyCoil, key, liquid, look, placeSpec, refComets, room, scene, sun } = ctx;
    const c0 = cue("S003", 0), c1 = cue("S003", 1);
    const tt = ease(seg(f, c0.a, c1.b));
    look(lerp(54, 50, tt), lerp(-0.62, -0.78, tt), lerp(2.3, 2.3, tt), lerp(1.25, 1.1, tt), -2.2, 2.75, -0.25);
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
    const chill = ease(seg(f, c0.a + 20, c0.a + 70)); // the coil turns icy as the refrigerant absorbs the room heat
    AC.copper.color.lerp(icyCoil, chill); AC.copper.emissive.set("#3AA0FF"); AC.copper.emissiveIntensity = 0.55 * chill;
    key.intensity = 1.2; hemi.intensity = 0.45; sun.intensity = 2.5;
    acInner.intensity = 1.6 * lift; coolLight.intensity = 1.5;
    AC.blower.rotation.x = -t * 14;
    const heatBoost = 1 + 0.6 * ease(seg(f, c1.a - SYNC_LEAD, c1.a + 8));
    evapComets.group.visible = true; evapComets.update(t, seg(f, c0.a + 14, c0.a + 26), heatBoost);
    refComets.group.visible = true; refComets.update(t, seg(f, c0.a + 18, c0.a + 30));
    scene.updateMatrixWorld(true);
    const a = (x, y, z) => AC.g.localToWorld(v3(x, y, z));
    placeSpec("S003", f);
}
