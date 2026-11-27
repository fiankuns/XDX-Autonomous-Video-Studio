# Rencana Eksekusi Hybrid v3.4 — `bench_c_laut_hilang_hybrid_180s`

> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.

- **Total Durasi**: `180.0s` (`5400 frame @ 30 fps`)
- **Jumlah Hierarchy**: `5 Sequence` · `10 Scene` · `10 Beat` · `57 Shot`

## Tabel Routing Shot & Handle Transisi
| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |
|---|---|---|---:|---|---|---:|
| S001 | B01 | `[0, 75)` | 2.50s | `blender` | `trans_hard_cut_zero` | 75 |
| S002 | B01 | `[75, 150)` | 2.50s | `blender` | `trans_hard_cut_zero` | 75 |
| S003 | B01 | `[150, 240)` | 3.00s | `blender` | `trans_hard_cut_zero` | 90 |
| S004 | B01 | `[240, 330)` | 3.00s | `blender` | `trans_hard_cut_zero` | 90 |
| S005 | B01 | `[330, 405)` | 2.50s | `blender` | `trans_hard_cut_zero` | 75 |
| S006 | B01 | `[405, 480)` | 2.50s | `blender` | `trans_hard_cut_zero` | 81 |
| S007 | B02 | `[480, 581)` | 3.37s | `threejs` | `trans_whip_pan_cutaway_6f` | 107 |
| S008 | B02 | `[581, 682)` | 3.37s | `threejs` | `trans_hard_cut_zero` | 101 |
| S009 | B02 | `[682, 767)` | 2.83s | `blender` | `trans_hard_cut_zero` | 85 |
| S010 | B02 | `[767, 851)` | 2.80s | `blender` | `trans_hard_cut_zero` | 84 |
| S011 | B02 | `[851, 936)` | 2.83s | `remotion` | `trans_hard_cut_zero` | 85 |
| S012 | B02 | `[936, 1020)` | 2.80s | `remotion` | `trans_hard_cut_zero` | 90 |
| S013 | B03 | `[1020, 1132)` | 3.73s | `threejs` | `trans_whip_pan_cutaway_6f` | 118 |
| S014 | B03 | `[1132, 1243)` | 3.70s | `threejs` | `trans_hard_cut_zero` | 111 |
| S015 | B03 | `[1243, 1346)` | 3.43s | `blender` | `trans_hard_cut_zero` | 103 |
| S016 | B03 | `[1346, 1449)` | 3.43s | `blender` | `trans_hard_cut_zero` | 103 |
| S017 | B03 | `[1449, 1535)` | 2.87s | `threejs` | `trans_hard_cut_zero` | 86 |
| S018 | B03 | `[1535, 1620)` | 2.83s | `threejs` | `trans_hard_cut_zero` | 91 |
| S019 | B04 | `[1620, 1716)` | 3.20s | `remotion` | `trans_whip_pan_cutaway_6f` | 102 |
| S020 | B04 | `[1716, 1811)` | 3.17s | `remotion` | `trans_hard_cut_zero` | 107 |
| S021 | B04 | `[1811, 1906)` | 3.17s | `blender` | `trans_cross_dissolve_12f` | 107 |
| S022 | B04 | `[1906, 2001)` | 3.17s | `blender` | `trans_hard_cut_zero` | 95 |
| S023 | B04 | `[2001, 2081)` | 2.67s | `threejs` | `trans_hard_cut_zero` | 80 |
| S024 | B04 | `[2081, 2160)` | 2.63s | `threejs` | `trans_hard_cut_zero` | 85 |
| S025 | B05 | `[2160, 2275)` | 3.83s | `threejs` | `trans_whip_pan_cutaway_6f` | 121 |
| S026 | B05 | `[2275, 2389)` | 3.80s | `threejs` | `trans_hard_cut_zero` | 114 |
| S027 | B05 | `[2389, 2486)` | 3.23s | `blender` | `trans_hard_cut_zero` | 97 |
| S028 | B05 | `[2486, 2583)` | 3.23s | `blender` | `trans_hard_cut_zero` | 97 |
| S029 | B05 | `[2583, 2672)` | 2.97s | `blender` | `trans_hard_cut_zero` | 89 |
| S030 | B05 | `[2672, 2760)` | 2.93s | `blender` | `trans_hard_cut_zero` | 94 |
| S031 | B06 | `[2760, 2875)` | 3.83s | `threejs` | `trans_whip_pan_cutaway_6f` | 121 |
| S032 | B06 | `[2875, 2989)` | 3.80s | `threejs` | `trans_hard_cut_zero` | 126 |
| S033 | B06 | `[2989, 3086)` | 3.23s | `blender` | `trans_cross_dissolve_12f` | 109 |
| S034 | B06 | `[3086, 3183)` | 3.23s | `blender` | `trans_hard_cut_zero` | 97 |
| S035 | B06 | `[3183, 3272)` | 2.97s | `remotion` | `trans_hard_cut_zero` | 89 |
| S036 | B06 | `[3272, 3360)` | 2.93s | `remotion` | `trans_hard_cut_zero` | 94 |
| S037 | B07 | `[3360, 3458)` | 3.27s | `threejs` | `trans_whip_pan_cutaway_6f` | 104 |
| S038 | B07 | `[3458, 3556)` | 3.27s | `threejs` | `trans_hard_cut_zero` | 98 |
| S039 | B07 | `[3556, 3646)` | 3.00s | `blender` | `trans_hard_cut_zero` | 90 |
| S040 | B07 | `[3646, 3736)` | 3.00s | `blender` | `trans_hard_cut_zero` | 90 |
| S041 | B07 | `[3736, 3818)` | 2.73s | `remotion` | `trans_hard_cut_zero` | 82 |
| S042 | B07 | `[3818, 3900)` | 2.73s | `remotion` | `trans_hard_cut_zero` | 88 |
| S043 | B08 | `[3900, 4008)` | 3.60s | `remotion` | `trans_whip_pan_cutaway_6f` | 114 |
| S044 | B08 | `[4008, 4116)` | 3.60s | `remotion` | `trans_hard_cut_zero` | 108 |
| S045 | B08 | `[4116, 4201)` | 2.83s | `blender` | `trans_hard_cut_zero` | 85 |
| S046 | B08 | `[4201, 4286)` | 2.83s | `blender` | `trans_hard_cut_zero` | 97 |
| S047 | B08 | `[4286, 4363)` | 2.57s | `threejs` | `trans_cross_dissolve_12f` | 89 |
| S048 | B08 | `[4363, 4440)` | 2.57s | `threejs` | `trans_hard_cut_zero` | 77 |
| S049 | B09 | `[4440, 4528)` | 2.93s | `threejs` | `trans_hard_cut_zero` | 88 |
| S050 | B09 | `[4528, 4615)` | 2.90s | `threejs` | `trans_hard_cut_zero` | 87 |
| S051 | B09 | `[4615, 4702)` | 2.90s | `threejs` | `trans_hard_cut_zero` | 99 |
| S052 | B09 | `[4702, 4811)` | 3.63s | `blender` | `trans_cross_dissolve_12f` | 121 |
| S053 | B09 | `[4811, 4920)` | 3.63s | `blender` | `trans_hard_cut_zero` | 121 |
| S054 | B10 | `[4920, 5035)` | 3.83s | `blender` | `trans_cross_dissolve_12f` | 127 |
| S055 | B10 | `[5035, 5150)` | 3.83s | `blender` | `trans_hard_cut_zero` | 115 |
| S056 | B10 | `[5150, 5275)` | 4.17s | `blender` | `trans_hard_cut_zero` | 125 |
| S057 | B10 | `[5275, 5400)` | 4.17s | `blender` | `trans_hard_cut_zero` | 125 |

