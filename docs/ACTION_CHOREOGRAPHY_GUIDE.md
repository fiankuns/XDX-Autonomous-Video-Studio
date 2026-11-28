# Action Choreography Guide (berlaku untuk topik apa pun)

Masalah yang diselesaikan: aksi penting ("mengipasi wajah", "menekan tombol", "menuang air", "memutar kunci") sering salah arah atau salah waktu jika sudut sendi ditebak. Aturan: **aksi didefinisikan sebagai kontrak, digerakkan oleh IK/aim, lalu dibuktikan secara geometris sebelum review piksel.**

## 1. Kontrak aksi (tulis SEBELUM membuat animasi)
Untuk setiap aksi penting di naskah, isi satu *action event* di `projects/<id>/action_events.json` (skema `schemas/action_events.schema.json`):

| Field | Pertanyaan yang harus dijawab | Contoh (AC) | Contoh (topik lain) |
|---|---|---|---|
| actor + bagian tubuh | siapa, anggota mana | Bima, tangan kanan | Pelayan, tangan kiri |
| objek | memegang/menyentuh apa | kipas kertas | teko |
| target | diarahkan ke mana | wajahnya sendiri | gelas |
| arah | sisi/ujung objek yang menghadap target | sisi datar kipas → wajah | corong teko → bibir gelas |
| kontak | kapan menyentuh | jempol di tombol | — |
| waktu | jendela relatif terhadap cue caption | cue 1, 15%–100% | cue 3, 40%–80% |
| urutan | apa yang TIDAK boleh terjadi sebelum | kepala belum menoleh ke AC | tangan belum meraih teko |
| kamera | cut ke mana dan kapan | medium → cut close-up remot → cut ke AC | — |
| bukti | constraint yang dicek | `facing`, `distance_lt`, `not_facing` | sama |

Tipe constraint: `distance_lt`, `distance_gt`, `facing` (vektor arah objek menunjuk target), `not_facing`. Anchor diambil dari `window.__xdxProbe` (kepala, wajah, dahi, pergelangan, ujung remot, dll.); tambahkan anchor baru di scene untuk objek topik baru.

## 2. Cara menggerakkan (jangan menebak sudut)
Gunakan primitive `engines/web/xdx_core/rig_ik.js`:
- `solveArm(arm, targetWorld, poleWorld)` — IK dua tulang: pergelangan diletakkan tepat di target.
- `aimTwo(obj, axisA, dirA, axisB, dirB)` — sumbu A objek menunjuk arah A, sumbu B sedekat mungkin ke arah B (mis. gagang ke atas, sisi datar ke wajah).
- `lookHead(head, target, amount)` — menoleh dengan batas yaw/pitch.
- `anchor(obj, localPos, localDir)` — probe geometris.
Objek genggam harus dibangun dengan gagang **di dalam kepalan** dan bagian fungsional menjauh dari kepalan (kipas: gagang sepanjang sumbu tangan, bilah terbuka di ujung).

## 3. Urutan sebab-akibat dan kamera
- Gestur persiapan mendahului aksi: **kepala menoleh ke target tepat sebelum menekan**, bukan di shot sebelumnya.
- Close-up objek (macro) memakai **cut**, bukan gerak kamera cepat; sembunyikan oklusi (kepala/badan) saat macro agar lensa bebas.
- Horizon kamera selalu datar.
- Nilai yang berubah ("32 → 24") harus terlihat sebelum dan sesudah.

## 4. Verifikasi (otomatis)
`python scripts/visual_workflow.py verify-actions projects/<id>` memuat scene yang sama dan mengevaluasi semua event tanpa piksel. Render penuh menulis `<id>_action_verification.json`; `validate_delivery` memblokir bila paket punya `action_events.json` tetapi laporan hilang atau tidak OK. `validate_inputs` memberi peringatan bila paket tidak punya `action_events.json`.

## 5. Templat perintah untuk agen (salin ke brief shot)
> Aksi: [actor] menggunakan [bagian tubuh] untuk [kata kerja] [objek] ke arah [target]. Sisi/ujung [objek] yang menghadap [target] adalah [bagian]. Mulai pada cue [n] di [x%], selesai [y%]. Sebelum itu [hal yang belum boleh terjadi]. Kamera: [cut/gerak] ke [subjek]. Bukti: [constraint]. Jangan menebak sudut sendi; pakai solveArm/aimTwo/lookHead dan tulis event di action_events.json.
