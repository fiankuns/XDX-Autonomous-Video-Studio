---
name: xdx-autonomous-video-studio
version: 3.4.0
replaces: xdx-autonomous-video-studio (v3.3), xdx-reference-to-hybrid-video (v3.1)
description: Hardened universal multi-genre autonomous video production studio (v3.4). Combines AI-authored verified research & natural Indonesian scriptwriting with fail-closed structured approval gates, hierarchical frame-exact storyboards (15s-180s+, all shots <=10s), 12-category multi-component glTF/GLB semantic asset generation, real buffer/style conversion, Blender shot compilation, Three.js v0.187, Remotion v4.0.547, REA-Video forensics, and Visual QC.
---
# XDX Autonomous Video Studio Skill v3.4

1. **Baca Protokol Utama**: Selalu baca `MASTER_PROMPT.md` dan `AGENTS.md` terlebih dahulu. Komunikasi menggunakan Bahasa Indonesia.
2. **Preflight 6-Tingkat & Validasi Skema**:
   ```bash
   python3 scripts/xdx_studio.py preflight
   python3 scripts/xdx_studio.py validate-all
   ```
   Bedakan dengan jujur antara *in-process protocol test* dan koneksi live ke **Vivo X200 Pro** (`live_android_blender_connected`). Jangan pernah meminta token di chat atau menyimpan kredensial di Git.
3. **AI sebagai Penulis & Peneliti Aktual (`CreativeProductionPayload`)**:
   - Tulis riset bersumber primer/institusional terverifikasi (`https://...`), blueprint 3 babak, karakter orisinal, dialog hidup, dan naskah Bahasa Indonesia alami tanpa tag placeholder ke dalam format `schemas/creative_intelligence.schema.json`.
   - Kompilasi paket 13 item ke status `WAITING_APPROVAL`:
     ```bash
     python3 scripts/xdx_studio.py plan --project-id <ID> --duration 150 --payload-json <payload.json> --out projects/<ID>
     ```
4. **Fail-Closed Approval Gate**:
   - Verifikasi paket melalui `python3 scripts/approval_gate.py projects/<ID> --strict-schema`.
   - Berhenti penuh pada `WAITING_APPROVAL`. Eksekusi mutasi scene/produksi hanya diizinkan setelah pengguna memberikan perintah persetujuan terstruktur (`XDX-APPROVE project=... version=... digest=... scopes=...`) yang lolos `ExecutionAuthorizationContext` live.
5. **Pengadaan Aset Semantik & Kompilasi Hybrid**:
   - Gunakan `IntelligentAssetPipeline` (menolak kotak `PLACEHOLDER` untuk produksi akhir) dan `BlenderXDXEngine` / `ThreeJSEngine` / `RemotionEngine` / `PresetExecutorEngine` sesuai `engine_plan.json`, diakhiri validasi `FFmpegEngine` & `VisualQualityControlEngine`.
6. **Automatic Reference Database Intelligence (`reference_database/`)**:
   - Verifikasi objek Git LFS referensi (`REF-001` & `REF-002`) tanpa meminta pengguna mengunggah ulang:
     ```bash
     python3 reference_database/scripts/reference_db.py verify
     python3 scripts/xdx_studio.py references --genres explainair
     ```
   - Routing otomatis pada `xdx_studio.py plan`: `explainer`/`explainair` → `REF-002` (`hosted_3d_explainer_cutaway_v1`); `storytelling`/`satir_sosial` → `REF-001` (`satirical_3d_vignette_storytelling_v1`); dukung pemilihan spesifik & multi-referensi melalui `--ref-ids REF-001 REF-002`. Pertahankan seluruh `prior_analysis.*` secara *append-only* dan selalu berhenti pada `WAITING_APPROVAL`.
