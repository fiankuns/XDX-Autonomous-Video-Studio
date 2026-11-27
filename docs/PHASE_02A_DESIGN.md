# Desain Arsitektur Phase 02A — Headless Three.js WebGL & Remotion Master Render (v3.4)

Dokumen ini merinci hasil audit kompatibilitas `package-lock.json` aktual serta cetak biru teknis **Phase 02A** untuk eksekusi render WebGL & Remotion secara deterministik di Cloud Runtime.

---

## 1. Hasil Audit Lockfile & Kompatibilitas Peer Dependency Aktual

| Paket | Versi Terkunci (`package-lock.json`) | Lisensi | Kompatibilitas Phase 02A |
|---|---|---|---|
| `three` | `0.187.0` | `MIT` | Inti scene 3D, `SRGBColorSpace`, `ACESFilmicToneMapping` |
| `remotion` | `4.0.547` | `Remotion License` | Wajib dikunci persis `4.0.547` tanpa `^` agar selaras antar sub-paket `@remotion/*` |
| `@remotion/captions` | `4.0.547` | `MIT` | Paginasi subtitle kata-demi-kata deterministik |
| `@remotion/transitions` | `4.0.547` | `Remotion License` | Transisi frame-overlap deterministik |
| `react` / `react-dom` | `19.3.1` | `MIT` | Kompatibel penuh dengan `@remotion/renderer@4.0.547` (`react >=16.8.0`) |
| `@react-three/fiber` *(Target 02A)* | `9.8.2` | `MIT` | Terverifikasi npm mendukung `react >=19 <19.4` dan `three >=0.156` (cocok dengan `19.3.1` & `0.187.0`) |
| `@remotion/three` *(Target 02A)* | `4.0.547` | `Remotion License` | Menyediakan `<ThreeCanvas>` sinkron `useCurrentFrame()` (`@react-three/fiber >=8.0.0`, `remotion == 4.0.547`) |
| `@remotion/bundler` & `@remotion/renderer` *(Target 02A)* | `4.0.547` | `Remotion License` | Webpack bundling & kontrol Chromium headless per frame |
| `heygen-com/hyperframes` | *Tidak dipasang di core* | `Apache-2.0` | **Tidak menggantikan Remotion**. Hanya dijadikan referensi pola sinkronisasi `<video>`/`canvas` HTML apabila dibutuhkan |

---

## 2. Arsitektur Headless Chromium WebGL & Deterministic PNG Sequence

1. **Runtime Eksekusi**: Playwright (`1.65.2`) + `/usr/bin/google-chrome` dengan flag deterministik:
   - `--use-gl=angle --use-angle=swiftshader` (atau GPU hardware pada instance ber-GPU) agar hasil piksel WebGL konsisten lintas mesin.
   - `--enable-webgl --ignore-gpu-blocklist --force-color-profile=srgb`.
2. **Load Barrier Ketat (`AssetLoadBarrier`)**:
   - Sebelum frame `0` dirender, halaman wajib menyelesaikan `Promise.all([document.fonts.ready, gltfLoaderBarrier, textureDecodeBarrier])`.
   - Jika memakai Remotion, bungkus dengan `delayRender("three-assets")` dan hanya panggil `continueRender(handle)` setelah seluruh mesh `.glb`/tekstur siap di memori GPU.
3. **Evaluasi Frame Murni (`window.__renderFrame(frameIndex, fps)`)**:
   - `requestAnimationFrame` otomatis dinonaktifkan; halaman mengekspos fungsi sinkron/awaitable `renderExactFrame(f)` yang mengevaluasi kamera, transformasi `animejs.seek((f / fps) * 1000)`, dan partikel PRNG `Mulberry32(seed)` pada waktu eksak `t = f / fps`, memanggil `renderer.render(scene, camera)`, lalu mengekspor PNG `1080x1920` RGBA/RGB terindeks `S00X_0000.png .. S00X_NNNN.png`.

---

## 3. Arsitektur Remotion Master Composition, Audio Mixing & MP4 Encoding

1. **Root Composition (`RemotionRoot.tsx`)**:
   - Satu `<Composition id="XDXMaster" fps={30} width={1080} height={1920} durationInFrames={totalFrames} />`.
   - Menggunakan `<TransitionSeries>` dari `@remotion/transitions` untuk mengelola `overlap_frames_in` / `overlap_frames_out` persis sesuai `transition_spec` pada `storyboard.json` sehingga durasi akhir tetap eksak `total_frames`.
2. **Dua Jalur Integrasi Three.js**:
   - **Jalur A (Pre-Rendered PNG Sequence — Utama & Paling Stabil)**: Shot `threejs` dan `blender` diimpor sebagai sequence PNG terverifikasi ke dalam `<Img src={staticFile(...)} />` berdasarkan `useCurrentFrame()`.
   - **Jalur B (`<ThreeCanvas>` Inline — Opsional Teruji)**: Untuk overlay 3D ringan langsung di dalam Remotion menggunakan `@remotion/three@4.0.547` + `@react-three/fiber@9.8.2`.
3. **Caption & Audio Layer**:
   - Layer `<CaptionSafeOverlay>` merender `caption_events` pada zona aman bawah `9:16` (`safe_bottom_pct: 0.18`), maksimal 2 baris, menggunakan font `Plus Jakarta Sans` OFL-1.1.
   - Kurva sidechain ducking dari `PresetExecutorEngine.evaluate_audio_ducking_envelope` diterapkan sebagai fungsi `volume={(f) => dbToLinear(duckCurve[f])}` pada komponen `<Audio>` musik latar, sementara track VO dan dialog dijaga pada `-15 LUFS` / true peak `<= -1.0 dBTP`.
4. **Bundling, Rendering & Validasi Akhir**:
   - `@remotion/bundler` (`bundle()`) → `@remotion/renderer` (`renderMedia({ codec: "h264", pixelFormat: "yuv420p", audioCodec: "aac" })`) → diverifikasi wajib oleh `FFmpegEngine.verify_full_decode()` dan `VisualQualityControlEngine`.
