# Rencana Implementasi Phase 02A & 02B — XDX Autonomous Video Studio v3.4

Dengan selesainya seluruh penguatan keamanan, kecerdasan naskah/riset, storyboard hierarkis, generator aset semantik 12 kategori, konverter GLB/glTF nyata, dan kompilator shot Blender pada **Phase 01.5 (v3.4)**, berikut adalah tahapan **Phase 02**:

## Phase 02A — Headless WebGL, Remotion Bundler/Renderer & Caption Assembly (VISUAL_ONLY_BENCHMARK)

> Revisi scope 2026-11-28: tanpa audio. Fokus kualitas visual + Independent Visual QC vs REF-002 (lihat Bagian 4 desain).

Lihat spesifikasi teknis mendalam di [`docs/PHASE_02A_DESIGN.md`](PHASE_02A_DESIGN.md):
1. **Playwright Headless Chromium WebGL Frame Exporter**:
   - Mengekspor sequence PNG `1080x1920` deterministik dari `engines/web/three_deterministic_scene.mjs` + aset `.glb` semantik dengan `AssetLoadBarrier` ketat (`fonts.ready` + `GLTFLoader` + `textureDecode`).
2. **Integrasi `@remotion/bundler@4.0.547`, `@remotion/renderer@4.0.547` & Opsional `@remotion/three@4.0.547` (`@react-three/fiber@9.8.2`)**:
   - Membangun `RemotionRoot` dan `<TransitionSeries>` yang merakit sequence shot, `<CaptionSafeOverlay>` berbahasa Indonesia, menjadi `final.mp4` (`H.264 yuv420p`, **tanpa track audio**, `muted:true`).
3. **Verifikasi QC Tertutup (`FFmpeg` + `OpenCV`) + Independent Visual QC**:
   - Menjalankan `VisualQualityControlEngine` (`delivery_profile="VISUAL_ONLY_BENCHMARK"`) terhadap MP4 aktual.
   - Review semantik independen per shot (`scripts/visual_review.py`) dan perbandingan dengan REF-002; hanya `PASS` yang diterima.

## Phase 02B — Live Vivo X200 Pro Relay Pairing
1. **Live Remote Relay Connection**:
   - Menyambungkan `XDX_MCP_SERVER_URL` dan secret `MCP_AUTH_TOKEN` ke server Relay tempat **Vivo X200 Pro** aktif (`live_remote_relay_reachable: true`, `live_android_blender_connected: true`), lalu menguji `actual_visual_feedback_verified` melalui `look(mode="angles", shading="material")` pasca-approval.

## Phase 04 — Audio (ditunda dari Phase 02A/02B)
1. **TTS Bahasa Indonesia, `whisper.cpp` / `faster-whisper` & `rhubarb` CLI**:
   - Menghasilkan WAV narasi/dialog aktual, menyelaraskan timestamp kata presisi untuk subtitle, dan mengekstrak viseme A–H+X untuk dialog karakter on-screen.
2. **Musik, SFX, mixing & ducking** (`-15 LUFS`, true peak `<= -1 dBTP`) dengan profil `MASTER_WITH_AUDIO`: audio hilang atau senyap = HARD_FAIL.
