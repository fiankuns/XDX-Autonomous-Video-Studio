# Rencana Eksekusi Hybrid v3.4 — `bench_p02b_char_10s`

> **GERBANG PERSETUJUAN WAJIB (`WAITING_APPROVAL`)**: Dilarang menjalankan mutasi scene Blender, sintesis TTS, atau render sebelum pengguna memberikan perintah persetujuan terstruktur yang sah.

- **Total Durasi**: `10.0s` (`300 frame @ 30 fps`)
- **Jumlah Hierarchy**: `2 Sequence` · `2 Scene` · `3 Beat` · `3 Shot`

## Tabel Routing Shot & Handle Transisi
| Shot | Beat | Frame `[start, end)` | Durasi | Engine Utama | Transisi Masuk | Render Frames (termasuk Handle) |
|---|---|---|---:|---|---|---:|
| S001 | B01 | `[0, 105)` | 3.50s | `blender` | `trans_hard_cut_zero` | 105 |
| S002 | B02 | `[105, 195)` | 3.00s | `blender` | `trans_hard_cut_zero` | 90 |
| S003 | B03 | `[195, 300)` | 3.50s | `blender` | `trans_hard_cut_zero` | 105 |

