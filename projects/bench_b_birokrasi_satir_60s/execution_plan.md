# Rencana Eksekusi Hybrid v3.4 — `bench_b_birokrasi_satir_60s`

> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.

- **Total Durasi**: `60.0s` (`1800 frame @ 30 fps`)
- **Jumlah Hierarchy**: `3 Sequence` · `5 Scene` · `5 Beat` · `20 Shot`

## Tabel Routing Shot & Handle Transisi
| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |
|---|---|---|---:|---|---|---:|
| S001 | B01 | `[0, 72)` | 2.40s | `blender` | `trans_hard_cut_zero` | 72 |
| S002 | B01 | `[72, 143)` | 2.37s | `blender` | `trans_hard_cut_zero` | 71 |
| S003 | B01 | `[143, 222)` | 2.63s | `blender` | `trans_hard_cut_zero` | 79 |
| S004 | B01 | `[222, 300)` | 2.60s | `blender` | `trans_hard_cut_zero` | 78 |
| S005 | B02 | `[300, 402)` | 3.40s | `blender` | `trans_hard_cut_zero` | 102 |
| S006 | B02 | `[402, 504)` | 3.40s | `blender` | `trans_hard_cut_zero` | 102 |
| S007 | B02 | `[504, 597)` | 3.10s | `blender` | `trans_hard_cut_zero` | 93 |
| S008 | B02 | `[597, 690)` | 3.10s | `blender` | `trans_hard_cut_zero` | 99 |
| S009 | B03 | `[690, 786)` | 3.20s | `blender` | `trans_whip_pan_cutaway_6f` | 102 |
| S010 | B03 | `[786, 881)` | 3.17s | `blender` | `trans_hard_cut_zero` | 95 |
| S011 | B03 | `[881, 996)` | 3.83s | `blender` | `trans_hard_cut_zero` | 115 |
| S012 | B03 | `[996, 1110)` | 3.80s | `blender` | `trans_hard_cut_zero` | 120 |
| S013 | B04 | `[1110, 1212)` | 3.40s | `blender` | `trans_whip_pan_cutaway_6f` | 108 |
| S014 | B04 | `[1212, 1314)` | 3.40s | `blender` | `trans_hard_cut_zero` | 102 |
| S015 | B04 | `[1314, 1407)` | 3.10s | `blender` | `trans_hard_cut_zero` | 93 |
| S016 | B04 | `[1407, 1500)` | 3.10s | `blender` | `trans_hard_cut_zero` | 105 |
| S017 | B05 | `[1500, 1572)` | 2.40s | `blender` | `trans_cross_dissolve_12f` | 84 |
| S018 | B05 | `[1572, 1643)` | 2.37s | `blender` | `trans_hard_cut_zero` | 71 |
| S019 | B05 | `[1643, 1722)` | 2.63s | `blender` | `trans_hard_cut_zero` | 79 |
| S020 | B05 | `[1722, 1800)` | 2.60s | `blender` | `trans_hard_cut_zero` | 78 |

