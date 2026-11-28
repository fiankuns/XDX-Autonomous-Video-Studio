---
name: xdx-blender-production
description: Professional Blender modeling recipes for XDX characters, props and environments (proportions, topology, hair, materials, lighting, geometry QC, reference-guided silhouette gate, Android budgets). Use before modeling or correcting any Blender asset.
---
# XDX Blender Production Skill (v4.0-02B.3)

Ideas below were learned from the audit in `docs/audits/PHASE_02B3_EXTERNAL_BLENDER_REPO_AUDIT.md` and rewritten in our own words; no external code is copied. Status tags: `VERIFIED` (seen in a real Blender render on the device), `RESEARCHED` (documented upstream, not yet tested here).

## Workflow (do not skip a gate)
Reference → Design Blueprint → Asset Strategy → **Preview Approval** → Geometry → Material → Style Frame → Independent Review → Correction → Approved Asset.
Split the reference by purpose: *shape* (silhouette), *proportion* (head-units), *material*, *colour* (palette from Global Style Bible), *cinematography* (REF-001/002/003).

## Recipes
1. **Proportions before polish (RESEARCHED).** Peg every part to head height; chibi ≈ 2.5–3 head-units, head ≈ 35% of height (Ingpoh: head 296 of 844 px). Guessing torso/legs produces bobble-heads. Check total height within ±2% of the declared canon.
2. **Silhouette first (VERIFIED for measurement, `character_tools.front_view_extent_px`).** Match the front silhouette against the reference with `intelligence/design_fidelity_gate.py` (alpha-aware IoU; never flatten a transparent render to RGB — it turns the background black and hides a shifted silhouette).
3. **Hair = few large locks (VERIFIED failure of 12 thin locks).** 6–8 big tapered locks with end flare and 1–2 waves, plus a cap; hair curves via data API rather than particle operators in headless runs. Avoid a solid ellipsoid for the back of the head.
4. **Joints (RESEARCHED).** Three staggered edge loops at elbows/knees; no 3- or 5-valent poles on eyelids, lips or hinges; enable deformation volume preservation on armatures.
5. **Rig (VERIFIED partial).** 2-bone IK with pole targets; IK targets exactly at wrist/ankle at rest (deviation 0); bone parenting must preserve `matrix_world`.
6. **Materials (VERIFIED).** Toon-flat look = base colour + same emission (strength ~0.9) + inverted-hull outline (solidify, flipped normals, back-face culling). Prints/decals must be geometry joined into the garment; check from a side angle.
7. **Lighting (RESEARCHED).** Three-point (key/fill/rim); evaluate with the scene camera, not only the solid viewport.
8. **Geometry QC.** Non-manifold edges, loose verts, zero-area faces, duplicate verts, hidden placeholder primitives; polycount within budget.
9. **Environment.** Procedural/instanced modules from the registry; textures from verified CC0 sources only (license check via `LicenseValidator`).
10. **Complex characters.** Prefer a licensed base mesh (verified licence) and customise; primitives are only blockout.

## Android (Vivo X200 Pro, Blender 5.3, EEVEE)
Each MCP call < 3.5 s (split into batches); preview ≤ 640 px; temp files in `bpy.app.tempdir`; character ≤ 60k tris, prop ≤ 15k, environment ≤ 100k; no CUDA/heavy runtimes; no desktop add-ons assumed to run on ARM64. After a dropped MCP call (Bad Gateway) read the scene before repeating.

## Gates
No PASS from JSON/script success. PASS needs: gate report + real multi-angle renders + Independent Visual QC (reviewer ≠ producer). Placeholder primitives are rejected as final assets.
