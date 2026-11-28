# Phase 02B.3 — Blender Design Intelligence (paket desain + rencana preview)

Status: **PAKET DESAIN, BELUM ADA RENDER RESMI.** Render 5 tampilan menunggu persetujuan chat pengguna. Tidak mengubah autentikasi/Blender MCP, tidak ada infrastruktur agen baru, audio tetap Phase 04.

## 1. Audit modul yang sudah ada (diperluas, bukan diganti)
| Kemampuan | Modul | Kondisi | Peningkatan |
|---|---|---|---|
| Design Planner | `intelligence/shot_spec.py`, `universal_preproduction.py` | Merencanakan shot, belum merencanakan desain aset | Tambah **Visual Blueprint** per aset (di bawah) |
| Geometry Intelligence | `procedural_geometry.py` (12 kategori, glTF multi-node) | Primitif; QC memblokir `PLACEHOLDER` | Primitif hanya basis sculpt; `engines/blender_scripts/character_tools.py` (curve, bevel, sculpt grab/inflate, smooth, symmetrize, outline) |
| Asset Retrieval | `asset_management.py` (`AssetRegistryManager`, `LicenseValidator`, `AttributionLedger`, cache Android) | 10 aset terdaftar; belum ada model chibi | Strategi: cari Quaternius/Poly Haven/ambientCG dulu, lisensi CC0/MIT saja |
| Environment | registry `env_*` modular | Ada set kamar/arsip/koridor | Pakai `env_kamar_indonesia_modular_v1` sebagai dasar |
| Material/Texture | `asset_style_converter.py` | Konversi glTF/normal | Material toon-flat + outline inverted-hull; decal hanya untuk detail kecil |
| Rigging | `CharacterRetargetingEngine`, rig 28 tulang Ingpoh | Rig ada, belum teruji animasi | Skin weights diuji pada 3 pose sebelum approval |
| Cinematic | `engines/blender_xdx_engine.py` | Kamera/lampu dasar | Rig kamera 5 tampilan + lampu 3 titik (key/fill/rim) |
| Visual Self-Correction | `visual_qc_engine.py`, `visual_semantic_qc.py` | Metrik piksel + semantik | Rubrik desain karakter (di bawah), reviewer ≠ producer |

## 2. Visual Blueprint — Sebatas Ingpoh (chibi, narator)
- Referensi: `assets/characters/sebatas_ingpoh/front_reference_636x844.png`; skala 725 px = 1 m; kaki di y=835.
- Proporsi: kepala ≈ 36% tinggi (rx 130, ry 148 px); badan kecil; lengan dan kaki pendek.
- Rambut: lavender `#CDAEF0` + highlight `#E4D3F8` + bayangan `#B48DE0`; **6–8 helai besar** melebar di ujung, ahoge melengkung, poni; lebar total ≤ 636 px.
- Wajah: mata ungu besar (outline gelap, iris, pupil, 2 highlight), pipi merah muda, mulut kecil; kulit hangat `#FBE3D0`.
- Pakaian: kaus salmon `#F29A84` + cetak "Sebatas Ingpohh" putih dan garis merah `#E04545` **satu aset** dengan baju; celana pendek dengan motif bulan krem.
- Gaya: sesuai Global Style Bible (tidak diubah), outline tebal tipis seragam, material flat/toon.

## 3. Strategi aset (urutan prioritas)
1. Registry/Cache XDX → 2. Model berlisensi (Quaternius CC0 sebagai basis tubuh chibi, bila cocok) → 3. Base mesh + sculpt (`character_tools`) → 4. Procedural/parametrik untuk rambut dan prop → 5. Primitif hanya sebagai blok awal.
Prop: remot AC (atau prop dari benchmark) dari registry. Environment: set kamar modular dari registry, dilengkapi material ambientCG / HDRI Poly Haven jika lisensi lolos `LicenseValidator`. Semua unduhan melalui `AutomaticAssetDownloader` (SSRF/Zip-Slip guard) dan dicatat di `AttributionLedger`.

## 4. Workflow dan gerbang
Reference Analysis → Visual Blueprint → Asset Strategy → **Preview Approval (gerbang pengguna)** → Modeling → Material → Lighting → Multi-Angle Render → Independent Visual QC → Correction → Approved Asset. Animasi 02B.3 dilarang sebelum Approved Asset.

## 5. Rencana preview (menunggu "Setuju")
Render EEVEE, 640 px (batas Mobile Guard), per call < 3.5 s:
1. Karakter tampak depan · 2. samping · 3. belakang · 4. perspektif · 5. style frame karakter + environment.
Tiap render disimpan di luar repo (`bpy.app.tempdir`) lalu dikirim ke pengguna; hash dicatat di evidence.

## 6. Rubrik Visual Critic (skor 1–5, lulus ≥ 3,5 dan tanpa kritis)
Silhouette cocok referensi (±5% tinggi/lebar) · proporsi · kualitas rambut (helai besar, tidak berbonggol) · wajah · material dan outline · detail cetak/motif · pencahayaan · komposisi style frame · konsistensi gaya antar karakter/prop/environment. Kegagalan diperbaiki **hanya pada bagian yang gagal**, maksimal 3 putaran.

## 7. Budget Android (Vivo X200 Pro, Blender 5.3 EEVEE)
Karakter ≤ 60k tris, prop ≤ 15k, environment ≤ 100k; tekstur ≤ 1024 px, instancing untuk elemen berulang; preview 640 px; Mobile Guard tidak dimatikan.

## 8. Status kemampuan (jujur)
| Kemampuan | Status |
|---|---|
| `character_tools` modul | TESTED (load + ukur ekstent di Blender; sculpt/outline belum diuji visual) |
| Karakter Ingpoh 3D (v-dev) | DITOLAK pengguna; rambut dan wajah belum memenuhi standar |
| Render 5 tampilan, Visual Critic aktual | BELUM DIJALANKAN |
| Aset Quaternius/Poly Haven/ambientCG | BELUM DIUNDUH/DIVERIFIKASI |
