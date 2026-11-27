# Rencana Eksekusi Hybrid v3.4 — `bench_a_ac_explainer_60s`

> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.

- **Total Durasi**: `60.0s` (`1800 frame @ 30 fps`)
- **Jumlah Hierarchy**: `3 Sequence` · `5 Scene` · `5 Beat` · `20 Shot`

## Tabel Routing Shot & Handle Transisi
| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |
|---|---|---|---:|---|---|---:|
| S001 | B01 | `[0, 72)` | 2.40s | `blender` | `trans_hard_cut_zero` | 72 |
| S002 | B01 | `[72, 143)` | 2.37s | `blender` | `trans_hard_cut_zero` | 71 |
| S003 | B01 | `[143, 222)` | 2.63s | `blender` | `trans_hard_cut_zero` | 79 |
| S004 | B01 | `[222, 300)` | 2.60s | `blender` | `trans_hard_cut_zero` | 84 |
| S005 | B02 | `[300, 393)` | 3.10s | `blender` | `trans_whip_pan_cutaway_6f` | 99 |
| S006 | B02 | `[393, 486)` | 3.10s | `blender` | `trans_hard_cut_zero` | 93 |
| S007 | B02 | `[486, 588)` | 3.40s | `threejs` | `trans_hard_cut_zero` | 102 |
| S008 | B02 | `[588, 690)` | 3.40s | `threejs` | `trans_hard_cut_zero` | 108 |
| S009 | B03 | `[690, 800)` | 3.67s | `blender` | `trans_whip_pan_cutaway_6f` | 116 |
| S010 | B03 | `[800, 910)` | 3.67s | `blender` | `trans_hard_cut_zero` | 110 |
| S011 | B03 | `[910, 1010)` | 3.33s | `blender` | `trans_hard_cut_zero` | 100 |
| S012 | B03 | `[1010, 1110)` | 3.33s | `blender` | `trans_hard_cut_zero` | 100 |
| S013 | B04 | `[1110, 1212)` | 3.40s | `threejs` | `trans_hard_cut_zero` | 102 |
| S014 | B04 | `[1212, 1314)` | 3.40s | `threejs` | `trans_hard_cut_zero` | 102 |
| S015 | B04 | `[1314, 1407)` | 3.10s | `blender` | `trans_hard_cut_zero` | 93 |
| S016 | B04 | `[1407, 1500)` | 3.10s | `blender` | `trans_hard_cut_zero` | 105 |
| S017 | B05 | `[1500, 1572)` | 2.40s | `blender` | `trans_cross_dissolve_12f` | 84 |
| S018 | B05 | `[1572, 1643)` | 2.37s | `blender` | `trans_hard_cut_zero` | 71 |
| S019 | B05 | `[1643, 1722)` | 2.63s | `blender` | `trans_hard_cut_zero` | 79 |
| S020 | B05 | `[1722, 1800)` | 2.60s | `blender` | `trans_hard_cut_zero` | 78 |

