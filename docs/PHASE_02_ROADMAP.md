# Rencana Implementasi Phase 02A & 02B — XDX Autonomous Video Studio v3.4

Dengan selesainya seluruh penguatan keamanan, kecerdasan naskah/riset, storyboard hierarkis, generator aset semantik 12 kategori, konverter GLB/glTF nyata, dan kompilator shot Blender pada **Phase 01.5 (v3.4)**, berikut adalah tahapan **Phase 02**:

## Phase 02A — Headless WebGL, Remotion Bundler/Renderer & Audio/Caption Master Assembly
Lihat spesifikasi teknis mendalam di [`docs/PHASE_02A_DESIGN.md`](PHASE_02A_DESIGN.md):
1. **Playwright Headless Chromium WebGL Frame Exporter**:
   - Mengekspor sequence PNG `1080x1920` deterministik dari `engines/web/three_deterministic_scene.mjs` + aset `.glb` semantik dengan `AssetLoadBarrier` ketat (`fonts.ready` + `GLTFLoader` + `textureDecode`).
2. **Integrasi `@remotion/bundler@4.0.547`, `@remotion/renderer@4.0.547` & Opsional `@remotion/three@4.0.547` (`@react-three/fiber@9.8.2`)**:
   - Membangun `RemotionRoot` dan `<TransitionSeries>` yang merakit sequence shot, `<CaptionSafeOverlay>` berbahasa Indonesia, dan kurva sidechain ducking `PresetExecutorEngine` menjadi `final.mp4` (`H.264 yuv420p` + `AAC 48 kHz`).
3. **Verifikasi QC Tertutup (`FFmpeg` + `OpenCV`)**:
   - Menjalankan `VisualQualityControlEngine` secara otomatis terhadap hasil render MP4 aktual.

## Phase 02B — Live Vivo X200 Pro Relay Pairing, Indonesian TTS & Forced Alignment
1. **Live Remote Relay Connection**:
   - Menyambungkan `XDX_MCP_SERVER_URL` dan secret `MCP_AUTH_TOKEN` ke server Relay tempat **Vivo X200 Pro** aktif (`live_remote_relay_reachable: true`, `live_android_blender_connected: true`), lalu menguji `actual_visual_feedback_verified` melalui `look(mode="angles", shading="material")` pasca-approval.
2. **TTS Bahasa Indonesia, `whisper.cpp` / `faster-whisper` & `rhubarb` CLI**:
   - Menghasilkan WAV narasi/dialog aktual, menyelaraskan timestamp kata presisi untuk subtitle, dan mengekstrak viseme A–H+X untuk dialog karakter on-screen.
