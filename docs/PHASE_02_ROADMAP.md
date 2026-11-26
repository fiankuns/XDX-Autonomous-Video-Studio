# Rencana Implementasi Phase 02 — XDX Autonomous Video Studio v3.3

Setelah fondasi modular, skema, registri, 16 pustaka preset, sistem aset 9 tahap, dan gerbang persetujuan 13 item selesai pada **Phase 01**, tahapan **Phase 02** berfokus pada eksekusi produksi end-to-end setelah persetujuan pengguna:

## Target Teknis Phase 02
1. **Live End-to-End XDX Relay Pairing & Smoke Render**:
   - Menghubungkan sesi Cloud `XDX-Autonomous-Video-Studio` ke server Relay aktif tempat **Vivo X200 Pro** terhubung (`relay_connected: true`).
   - Menjalankan smoke test pasca-approval (`get_mobile_device_profile` → `get_scene_info` → turntable style frame `look(mode="angles", shading="material")`).
2. **Headless Three.js WebGL Frame Sequence Renderer**:
   - Mengintegrasikan Playwright + Chromium headless (`/usr/bin/google-chrome`) dengan `engines/web/three_deterministic_scene.mjs` untuk mengekspor sequence PNG RGBA 1080x1920 frame-demi-frame secara deterministik dengan load barrier penuh.
3. **Remotion Full React Project & Master MP4 Render**:
   - Membangun bundle komposisi React/Remotion (`@remotion/bundler` + `@remotion/renderer`) yang menggabungkan sequence shot Blender, sequence shot Three.js, overlay grafis D3/Anime.js, komponen subtitle aman 9:16, dan pencampuran multi-track WAV 48 kHz.
4. **Indonesian TTS, Whisper Forced Alignment & Rhubarb Lip-Sync**:
   - Mengintegrasikan penyedia TTS Bahasa Indonesia berlisensi + kompilasi `whisper.cpp` / `faster-whisper` untuk penyelarasan kata aktual pasca-WAV, serta biner `rhubarb` untuk adegan dialog on-screen.
5. **Automated Closed-Loop Visual Self-Correction**:
   - Menghubungkan `VisualQualityControlEngine` dan evaluasi frame multimodal untuk me-render ulang shot yang gagal QC secara otomatis hingga maksimal 3 iterasi sebelum pengemasan `final.mp4`.
