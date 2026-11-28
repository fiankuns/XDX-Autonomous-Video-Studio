# Bima v2 — production model from owner blueprint (Phase 02B.3)
Status: **NOT APPROVED — independent critic verdict REJECT** (see independent_review.md). Automated gate: PASS_AUTOMATED_CHECKS
with full evidence (6 reference views, proportions, eye landmarks, geometry, palette); the gate checks geometry/colour only.

- Old Bima (v1) objects deleted from the Blender scene (33 objects). Three.js Bima asset in the repo is untouched.
- Model: one skin-modifier body (torso/arms/hands/fingers/legs) + Pixar head parts + metaball curl hair + sneakers + raised
  "kalian / tau gak?" print; rig 21 bones; distance+geodesic weights; 32 objects, ~50.2k tris (budget 60k).
- Gate IoU: front 0.848, back 0.847, left 0.809, right 0.809, three-quarter 0.872, face 0.915; palette share 0.91.
- Build is reproducible: engines/blender_scripts/bima_v2_build.py (stages) + style_preset_pixar.py.
- Critic top defects: fingers too small / mitten-like, stick arms without elbow/wrist form, bald nape, facial features
  protrude in profile + flat blush discs, shoes ~50 % too small and joggers instead of slim jeans; collar reads as turtleneck.
- Gate consistency note (critic): non-front views have framing margin 0.035 but framing is only enforced on the front render.
