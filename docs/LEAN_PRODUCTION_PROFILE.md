# Profil Produksi Hemat Token (model apa pun, termasuk Gemini)

Tujuan: video jadi dengan sedikit putaran, tanpa mengurangi urutan kerja. Prinsip: **angka sebelum piksel, satu render penuh, satu review.** Semua langkah memakai file JSON dan perintah CLI yang sama untuk model apa pun.

## Muat seperlunya (jangan baca seluruh repo)
Muat hanya: file ini, paket proyek (`projects/<id>/`), `docs/ACTION_CHOREOGRAPHY_GUIDE.md` bila ada aksi. Registry, memori, MASTER_PROMPT penuh dan bukti lama dibuka hanya bila tugas menyebutnya.

## Urutan kerja (setiap langkah punya syarat lanjut)
| # | Langkah | Perintah / keluaran | Lanjut bila |
|---|---|---|---|
| 1 | Validasi input | `visual_workflow.py validate-inputs <paket>` | tanpa isu kritis |
| 2 | Kontrak per beat | tulis `action_events.json` (aktor, anggota, objek, target, sisi yang menghadap, jendela cue, urutan, `min_seconds`) + daftar label (bagian yang disebut) | tiap aksi di naskah punya event |
| 3 | Durasi dari isi | `visual_workflow.py retime <paket> S001=.. S002=..` | jendela aksi >= `min_seconds` |
| 4 | Gerak dari primitive | `solveArm`, `aimTwo`, `lookHead`, `callouts.place`; sketsa pengguna disalin menjadi pole/lintasan/constraint | - |
| 5 | Bukti angka | `visual_workflow.py verify-actions <paket>` (tanpa render) | status OK (aksi + label) |
| 6 | Satu lembar kontak | `--preview` 1 frame per shot, atau `--frames` beberapa frame; gabung jadi SATU gambar (maks 12 petak, lebar <= 360 px) | tampak benar sekali lihat |
| 7 | Animatic / per shot | `--animatic`, `--shot S00N` hanya shot yang berubah (`rerender-plan`) | gerak dan urutan benar |
| 8 | Render penuh SEKALI | `render_phase02a_visual.py <paket> --prototype --out <luar repo>` | QC teknis PASS, verifikasi aksi/label OK |
| 9 | Gerbang kirim | `visual_workflow.py delivery <paket> --render-dir <dir>` | hanya review independen yang belum ada |
| 10 | Satu review independen | agen berkonteks baru memeriksa frame dari checklist saja | tidak ada cacat kritis |

## Aturan hemat (wajib)
- **Gambar mahal, angka murah.** Cek arah/jarak/gerak lewat probe dan constraint; lihat gambar hanya untuk komposisi. Satu lembar kontak per pengecekan, crop bagian yang dipertanyakan, jangan baca frame penuh berulang.
- **Jangan polling.** Satu kali tunggu untuk render; jangan membaca log berulang.
- **Batasi putaran.** Satu batch umpan balik pengguna = satu perbaikan + satu render penuh. Kumpulkan semua catatan (termasuk sketsa) dulu, jangan merender per catatan.
- **Shot yang sudah disetujui adalah referensi.** Ubah hanya bila diminta; bandingkan sebelum/sesudah pada frame yang sama; hash-cache menentukan shot yang perlu dirender ulang.
- **Jangan ulangi pekerjaan yang valid.** Pakai cache dan hasil tes yang masih berlaku; jalankan hanya tes yang menyentuh file yang berubah, suite penuh sekali sebelum commit.
- **Satu agen kerja + satu reviewer.** Reviewer tidak membaca seluruh repo: beri path checklist, video, dan format hasil.
- **Pertanyaan ke pengguna hanya bila keputusan tak bisa diputuskan dari data**; jangan menanyakan hal yang bisa dicek.

## Templat perintah ke agen (model mana pun)
> Kerjakan topik [X] dengan urutan Profil Produksi Hemat (langkah 1-10). Tulis action_events.json untuk setiap aksi dan daftar label dengan bagian yang disebut. Jangan menebak sudut sendi; pakai primitive. Jalankan verify-actions sampai OK sebelum melihat gambar apa pun. Maksimal satu render penuh per batch umpan balik. Laporkan hanya: status tiap langkah, cacat tersisa dengan nomor frame, dan file keluaran.

## Estimasi biaya per putaran (urutan besar, bukan angka tetap)
Probe dan verifikasi: detik, tanpa gambar. Lembar kontak: 1 gambar. Render per shot: menit. Render penuh: 7-10 menit. Review independen: satu agen, beberapa gambar. Pola lama (render penuh + baca banyak gambar per catatan) berkali-kali adalah penyebab utama boros.

## Lapisan penulisan shot (hemat revisi)

Tulis aksi dan label HANYA di `shot_spec.json`, jalankan `apply-spec`, lalu `verify-actions` (angka, tanpa piksel). Koreografi tiap shot ada di `shots/S00N.js`: revisi satu shot hanya me-render ulang shot itu (`rerender-plan`), sehingga satu putaran revisi tidak lagi mengongkos seluruh video. Lihat `docs/ACTION_CHOREOGRAPHY_GUIDE.md` bagian 7.
