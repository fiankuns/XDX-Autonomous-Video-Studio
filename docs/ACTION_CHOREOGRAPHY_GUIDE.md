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


## 6. Gerak berulang, prop yang mengikuti, dan durasi (ditambahkan setelah review v7)
**Gerak bukan pose.** "Mengipas", "mengusap", "mengaduk" adalah gerak berulang: tulis `travel_gt` (anchor benar-benar berpindah sejauh X selama jendela) dan, bila ada prop, `rigid` (prop tetap menempel pada anggota tubuh dengan jarak konstan, jadi ikut bergerak bersama pergelangan). Prop tidak boleh diam sementara tangan bergerak, atau sebaliknya.
**Tentukan penggerak.** Untuk setiap gerak tulis: sendi mana yang menggerakkan (mengipas = fleksi PERGELANGAN maju-mundur, bukan seluruh lengan; mengusap = lengan bawah menyapu dengan siku keluar), arah, amplitudo, frekuensi, dan sisi prop yang harus menghadap target di seluruh siklus (beri bias agar sisi datar tidak berbalik membelakangi wajah).
**Pose lengan dari sketsa.** Bila pengguna menggambar garis pada frame (garis merah = lintasan siku/lengan, garis biru = lintasan lengan lain), salin sebagai: posisi siku (pole vector IK), lintasan pergelangan, dan constraint jarak/`travel_gt`. Jangan menafsirkan ulang.
**Cutaway aksi kontak mengikuti rujukan yang sudah disetujui.** Close-up objek: objek tegak (ujung fungsional di atas), seluruh objek terlihat, jari menggenggam di satu sisi, jempol/jari penekan masuk diagonal dan menyentuh tombol; kamera memakai vektor atas objek (bukan miring acak); sembunyikan oklusi; ganti dengan cut, bukan gerak kamera.
**Durasi mengikuti isi, bukan angka target.** Tiap event boleh punya `min_seconds`; bila jendela terlalu pendek verifikasi gagal dengan ACTION_TOO_SHORT. Perbaikan: `python scripts/visual_workflow.py retime <paket> S001=5.5 S002=6` (atau `retime_package`), yang menulis ulang storyboard, kamera, motion, engine, narasi, dan cue caption secara konsisten. Rumus awal: persiapan 0.5-1 dtk + aksi (siklus x periode, minimal 3 siklus untuk gerak berulang) + tahan 0.5 dtk.

# Callout (label penunjuk) generik
Setiap label = pill + garis penunjuk + lingkaran kecil TEPAT di bagian yang disebut (`engines/web/xdx_core/callouts.js`).
- Cincin ada di bagian itu; pill digeser menjauh dari subjek sepanjang garis (offset piksel), tidak di atas bagian yang diberi nama.
- Pill tidak menutup caption, tidak menimpa pill lain, tetap di dalam frame, garis minimal 70 px.
- Animasi masuk: cincin, lalu garis tumbuh dari cincin, lalu pill.
- Menaruh cincin: `window.__xdxScreenToLocal(frame, ruang, x, y, z)` mengubah piksel (dari sketsa pengguna) menjadi koordinat objek; `window.__xdxPick(frame, x, y)` menemukan objek liar di bawah piksel.
- Dicek otomatis: `intelligence/callout_contract.py` (CALLOUT_OVER_CAPTION, CALLOUT_OVERLAP, CALLOUT_COVERS_PART, CALLOUT_LEADER_TOO_SHORT, CALLOUT_OFF_FRAME); render penuh menulis `<id>_callout_verification.json`; gate delivery memblokir bila hilang atau gagal.
- Label hanya tampil di shot tempat bagian itu terlihat (jangan di cutaway objek lain).

## 7. Shot spec: satu file penulisan per topik (Three.js only, tanpa Blender)

`projects/<id>/shot_spec.json` (schema `schemas/shot_spec.schema.json`) adalah SATU-SATUNYA tempat menulis, per shot: `events` (aksi yang diverifikasi geometri) dan `callouts` (teks label, jangkar `world|ac|od|named`, offset pill, jendela tampil relatif cue).

- `python3 scripts/visual_workflow.py apply-spec <package>` memvalidasi spec (shot/cue valid, tiap shot punya event, anchor benar), meng-compile `action_events.json`, dan menyarankan durasi shot dari `min_seconds` (umpan ke `retime`).
- `action_events.json` adalah hasil compile; jangan diedit tangan. Scene membaca callout dari spec (`PKG.callouts`), jadi teks/penempatan label tidak ada di kode scene.
- Koreografi dipecah per shot: `engines/web/<scene>/shots/S00N.js` (fungsi murni `renderS00N(ctx, f, t)`). Mengubah satu file shot atau satu entri spec hanya me-render ulang shot itu (`rerender-plan`); mengubah `scene.js`/kit tetap me-render semua.
- Topik baru: salin pola ini (spec + shots/), jangan menaruh label atau aksi langsung di scene.js.
