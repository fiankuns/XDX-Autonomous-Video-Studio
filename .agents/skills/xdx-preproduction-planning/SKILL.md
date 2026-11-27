---
name: xdx-preproduction-planning
description: Compiles verified Indonesian topic research, original scripts, Character Bibles, frame-exact hierarchical storyboards (<=10s per shot), 12-category semantic 3D asset manifests, and 13-item approval packages stopping at WAITING_APPROVAL. Use when building or revising pre-production video packages.
---
# XDX Pre-Production Planning Skill (v4.0)

1. Rujuk modul inti yang telah teruji:
   - `intelligence/creative_pipeline.py` & `schemas/creative_intelligence.schema.json`
   - `intelligence/procedural_geometry.py` & `intelligence/asset_style_converter.py`
   - `engines/blender_xdx_engine.py`, `engines/preset_executors.py`, `libraries/loader.py`
   - Skill runtime `threejs` dan `xdx-blender-vivo` bila menyusun spesifikasi adegan 3D hybrid.
2. Pastikan setiap klaim faktual memiliki sumber `https://` yang dapat diperiksa, naskah bebas dari label placeholder, dan setiap shot pada storyboard berdurasi integer frame `<= 10,0 detik` (umumnya `2–6 detik`).
3. Jalankan kompilasi dan verifikasi gerbang persetujuan:
   ```bash
   python3 scripts/xdx_studio.py plan --project-id <ID> --genres <GENRE...> --duration <DETIK> --out projects/<ID>
   python3 scripts/approval_gate.py projects/<ID> --strict-schema
   ```
4. Selalu berhenti pada `WAITING_APPROVAL`. Jangan memulai mutasi scene Blender, sintesis audio berbayar, atau render sebelum persetujuan sah diterima.
