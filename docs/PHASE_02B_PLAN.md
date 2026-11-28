# Phase 02B — Rencana (BELUM DIJALANKAN; butuh persetujuan pengguna)

Tidak ada produksi Blender sebelum persetujuan eksplisit. Blender MCP tidak diubah. Audio tetap Phase 04.

## Prasyarat (gate masuk)
1. Pengguna menyetujui rencana ini dan menentukan scope (karakter, prop, shot).
2. Keputusan atas v5: review independen PASS, atau penerimaan tertulis pengguna sebagai benchmark visual.
3. Paket dalam status `APPROVED` lewat Trusted Approval (Ed25519, `fian-termux-1`); `PHASE02_EXECUTION_ENABLED` diubah hanya oleh manusia.

## Peran engine (tetap)
Remotion = master timeline · Three.js = visual engine · Blender = modeling, rigging, acting, cinematic rendering.

## Pekerjaan
1. **Aset (Blender → glTF 2.0):** Bima (rig IK/FK, tangan, viseme dikunci untuk Phase 04), AC indoor dan outdoor, remot; export ke `xdx_core/assets/` sebagai pengganti prosedural; kontrak: palet dari bible, budget poligon di registry.
2. **Material dan cahaya:** PBR ber-tekstur, bevel, AO/kontak shadow, kurva cahaya; target menutup celah lawan REF-002 (aset, kamera, cahaya, komposisi ≈ 2,5).
3. **Acting dan kamera:** pose kipas "kepanasan", perubahan 32 → 24 yang terlihat, pompa kompresor, plume panas lewat kipas, kumparan dingin (embun/biru).
4. **Pipeline:** pecah koreografi `scene.js` per shot (`shots/S00N.js`) agar rerender selektif per shot nyata; ekstrak aset inline; gate otomatis roll kamera dan tepi frame (menutup DEF-P02A-043/044).
5. **Evidence dan QC:** style frame → animatic → render per shot → review independen (fresh context, reviewer ≠ producer) → delivery validation; benchmark piksel di-baseline ulang dengan bukti.

## Acceptance
Semua dimensi ≥ 3,0; rata-rata shot ≥ 3,5; REF-002 ≥ 3,0; 0 placeholder, 0 overlay debug, aksi wajib terlihat dalam jendela caption, caption di safe area, delivery gate OK.

## Batas
Maks. 2 agen aktif; tanpa Swarm/Boost/Teamwork; tanpa audio/TTS/musik/SFX/lip sync; output prototipe di luar repo; tanpa commit checkpoint runtime, force-push, atau merge ke main.


> Update: pemisahan `scene.js` per shot (`shots/S00N.js`) dan `shot_spec.json` sudah dikerjakan di Phase 02A (Three.js only). Sisa item 4: ekstraksi aset inline dan gate camera-roll/frame-edge (DEF-P02A-043/044). Blender tetap tidak dieksekusi.
