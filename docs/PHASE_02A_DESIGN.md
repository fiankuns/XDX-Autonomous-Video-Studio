# Desain Arsitektur Phase 02A — Headless Three.js WebGL & Remotion Master Render (v3.4)

> **Revisi scope 2026-11-28 — VISUAL ONLY.** Phase 02A sekarang menghasilkan `VISUAL_ONLY_BENCHMARK`. Seluruh audio
> (TTS, voice-over, musik, SFX, lip sync, mixing, forced alignment) ditunda ke **Phase 04**. Bagian 3.3 dan `audioCodec`
> pada 3.4 di bawah hanya berlaku untuk profil `MASTER_WITH_AUDIO` di Phase 04. Lihat **Bagian 4**.

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

---

## 4. Revisi Scope Phase 02A — `VISUAL_ONLY_BENCHMARK` (2026-11-28)

**Ditunda ke Phase 04:** TTS, voice-over, musik, sound effect, lip sync, audio mixing/ducking, forced alignment.
Tidak ada kuota agent untuk audio di Phase 02A; guard hook menolak tool/perintah audio dengan `PhaseScopeDeferredError`
(`governance/phase_scope.py`).

**Aturan render & QC**
- Render tanpa audio sah sebagai `VISUAL_ONLY_BENCHMARK`. Ekspor **tanpa track audio**: `renderMedia({codec:"h264", pixelFormat:"yuv420p", muted:true})`
  (`RemotionEngine.compile_master_composition` default: `audioSpec: null`).
- `VisualQualityControlEngine.evaluate_video(..., delivery_profile="VISUAL_ONLY_BENCHMARK")`: audio hilang **bukan** defect;
  track senyap yang ikut terekspor = `DEF_UNNECESSARY_SILENT_AUDIO_TRACK` (low, WARN).
- Caption tetap menjadi representasi narasi dan tolok ukur kecocokan visual dengan cerita.
- Field audio pada paket (`audio_events`, `sfx_cues`, `target_lufs`, `music_direction`, …) tetap tersimpan sebagai rencana
  Phase 04 dan diabaikan di 02A (`projects/<id>/delivery_scope.json`).

**Fokus sumber daya:** kualitas karakter & aset · semantic visual storytelling · animasi & interaksi objek · visualisasi
mekanisme · kamera & sinematografi · lighting, shadow, material & tekstur · komposisi & transisi · Independent Visual QC ·
perbandingan render aktual dengan REF-002.

**Independent Visual QC** (`intelligence/visual_semantic_qc.py`, `scripts/visual_review.py`)
1. `checklist` — dari storyboard + semantic visual plan + caption yang ditandatangani: per shot caption, aksi wajib,
   aset wajib, kamera, dan 3 frame yang wajib diperiksa.
2. `frames` — ekstrak frame wajib + contact sheet dari MP4 aktual (analisis, bukan render).
3. `evaluate` — review reviewer independen (`reviewer_context: "fresh"`, reviewer ≠ producer, terikat SHA-256 render):
   - HARD_FAIL: aksi wajib tidak terlihat, aset placeholder/primitif, overlay debug, artefak render, skor dimensi < 3.0,
     rata-rata shot < 3.5, rata-rata vs REF-002 < 3.0.
   - WARN: caption menutupi subjek, subjek terpotong tepi frame.
   - INCOMPLETE: shot/aksi/frame/dimensi tidak tercakup.
   - Hanya `PASS` yang boleh disebut lulus visual.

**Bukti awal:** render uji AC 15 dtk pertama → `HARD_FAIL` (12 ketidaksesuaian semantik, 5 aset placeholder, overlay debug
di 4 shot, skor vs REF-002 1,42/5) — `docs/evidence/phase02a_visual_only/`.

**Keamanan tidak berubah:** trusted approval Ed25519, canonical manifest, pin dependensi produksi, dan batas eksekusi
Phase 02 tetap berlaku untuk setiap render (render muted pun tetap butuh approval terverifikasi).

---

## 5. Engine Visual Phase 02A — `engines/web/phase02a_ac15s` (2026-11-28)

- Scene Three.js `0.187.0` deterministik (frame = fungsi murni dari indeks frame, PRNG ber-seed), dirender oleh Chrome headless
  + SwiftShader lewat `scripts/render_phase02a_visual.py`, lalu di-encode H.264 `yuv420p` **tanpa audio** (`-an`).
- Caption dan rentang shot dibaca dari paket bertanda tangan (`caption_audio_plan.json`, `storyboard.json`). Scene menolak
  render jika rentang shot berbeda dari koreografi yang dibuat untuk `bench_p02a_ac_15s`.
- Isi visual: karakter Bima stylized ber-rig (tangan, jari, mata, alis, mulut, keringat, ekspresi), AC dengan kisi berputar dan
  display, cutaway evaporator (kumparan tembaga, sirip, blower, perubahan fase refrigeran), potongan dinding dengan kompresor,
  kondensor dan kipas, aliran panas/sejuk berarah, soft shadow, material bertekstur, gerak kamera per shot, label konten.
- **Produksi**: `python scripts/render_phase02a_visual.py projects/bench_p02a_ac_15s` → wajib lolos `assert_render_authorized`
  (batas Phase 02, token Ed25519, canonical manifest, ledger, dependensi ter-pin). Saat ini diblokir batas fase.
- **Prototipe** (iterasi visual oleh manusia): `--prototype --out <dir di luar repo>`; berlabel `NON_PRODUCTION_PROTOTYPE`,
  tidak pernah menjadi deliverable. Guard hook memperlakukan skrip ini sebagai render produksi untuk agent.
- Scene, `index.html`, renderer, `package.json` dan `package-lock.json` (termasuk font OFL `@fontsource/plus-jakarta-sans@5.3.0`)
  di-pin di `production_dependencies.json` paket benchmark.
- Bukti prototipe v2: `docs/evidence/phase02a_visual_only/prototype_v2_*`. Review visual independen masih wajib sebelum PASS.

### 5.1 Timing map, sinkron caption & gerbang pratinjau (v3)
- **Timing map**: semua beat scene diturunkan dari cue caption paket (`CUEF`), dengan lead visual maksimal 0,3 dtk (`SYNC_LEAD`).
  Jika caption digeser, koreografi ikut bergeser; tidak ada nomor frame bebas untuk aksi.
- **Sinkron caption ↔ visual** (checklist v2): tiap cue punya `frame_window` = [awal − 0,3 dtk, akhir). Reviewer wajib memberi
  `caption_sync_evidence`; isi caption tidak tampak = critical, tampak di luar jendela = high.
- **Storyboard-first**: `render_phase02a_visual.py --prototype --preview --out <dir>` merender satu frame kunci per caption +
  contact sheet + `style_frames_manifest.json` (terikat digest paket & hash scene) untuk disetujui pemilik sebelum render penuh.

