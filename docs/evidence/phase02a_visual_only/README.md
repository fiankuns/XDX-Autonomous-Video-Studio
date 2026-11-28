# Phase 02A — VISUAL_ONLY_BENCHMARK evidence (scope revision 2026-11-28)

| File | Isi |
|---|---|
| `first_test_render_contact_sheet.jpg` | 12 frame wajib (3 per shot) dari render uji AC 15 dtk pertama, diekstrak dengan `scripts/visual_review.py frames` |
| `independent_visual_review_ac15s.json` | Review independen (reviewer ≠ producer, konteks bersih, terikat SHA-256 render) |
| `independent_visual_qc_result_ac15s.json` | Hasil `evaluate_visual_review`: **HARD_FAIL** |

Ringkasan hasil render uji pertama:
- Technical QC (visual-only): **WARN** — hanya `DEF_UNNECESSARY_SILENT_AUDIO_TRACK` (track senyap −91 dBFS tidak perlu disertakan). Audio kosong tidak lagi dianggap gagal.
- Independent Visual QC: **HARD_FAIL** — 12 aksi wajib tidak terlihat, 5 aset placeholder, overlay debug di 4 shot, 5 artefak render, rata-rata shot 1,36–1,79/5, vs REF-002 1,42/5.

Tes: core 125 passed; `XDX_TEST_PROFILE=full_integration` 125 passed (REF-001/REF-002 MP4 asli terhidrasi).

## Prototipe v2 (engine `engines/web/phase02a_ac15s`)

| File | Isi |
|---|---|
| `prototype_v2_contact_sheet.jpg` | 12 frame wajib dari render prototipe v2 |
| `prototype_v2_technical_qc.json` | QC teknis visual-only: **PASS** (450 frame, tanpa track audio, 0 frame kosong) |

Status: `NON_PRODUCTION_PROTOTYPE`; arah visual disetujui pemilik proyek di chat; review visual independen masih **PENDING**.
Tes: core 130 passed; `full_integration` 130 passed.

