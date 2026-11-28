# Bima v2 — character blueprint (Pixar-like stylized 3D)

Source: owner-supplied `karakter_6_view_v2.glb` (six-view reconstruction, trimesh, 554,800 tris, vertex colours,
no rig/UV). SHA-256 `f7c99f4c77cecd75c98efd256424c27476e54343e201681962f5a5005bcce390`. The GLB itself is NOT committed (14 MB).

- `blueprint/{front,back,left,right,three_quarter,face}.png` — orthographic, transparent, rendered from the GLB
  (768 px; body views ortho half-height 0.86 m centred at 0.80 m; face ortho half-height 0.26 m at 1.36 m). glTF +Z front.
- `blueprint/measurements.json` — height, width/depth bands every 5 cm, rough colour regions.
- `reference_proxy_44k.npz` — vertex-clustered proxy (11 mm grid, 43.8k tris, vertex colours) for in-Blender
  silhouette reference only. Not a production asset (side/3-4 views contain reconstruction ghosting).
- Style: `styles/xdx_pixar_stylized_3d_v1.json`, preset `engines/blender_scripts/style_preset_pixar.py`.
- Known blueprint defects: doubled arms/torso streaks in side and three-quarter views (reconstruction), so those
  views are judged on silhouette only, never on interior detail.
