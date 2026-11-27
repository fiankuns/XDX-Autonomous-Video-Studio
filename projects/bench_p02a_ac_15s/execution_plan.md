# Rencana Eksekusi Hybrid v3.4 — `bench_p02a_ac_15s`

> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.

- **Total Durasi**: `15.0s` (`450 frame @ 30 fps`)
- **Jumlah Hierarchy**: `2 Sequence` · `3 Scene` · `4 Beat` · `4 Shot`

## Tabel Routing Shot & Handle Transisi
| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |
|---|---|---|---:|---|---|---:|
| S001 | B01 | `[0, 105)` | 3.50s | `threejs` | `trans_hard_cut_zero` | 105 |
| S002 | B02 | `[105, 210)` | 3.50s | `threejs` | `trans_hard_cut_zero` | 105 |
| S003 | B03 | `[210, 330)` | 4.00s | `threejs` | `trans_hard_cut_zero` | 120 |
| S004 | B04 | `[330, 450)` | 4.00s | `threejs` | `trans_hard_cut_zero` | 120 |

