# Analisis Mendalam REA-Video v3.4 — `REF-001` (Satir Sosial & Storytelling Diorama)

- **File Asli**: `1001952045.mp4` (`27.026.130` byte · Git LFS `VERIFIED`)
- **SHA-256**: `12f9e1d992fc6f71f56c4c1116a91def3f6ca70bf1c55aa2618281ae4a71879d`
- **Arsip Sebelumnya Dipertahankan**: [`prior_analysis.md`](prior_analysis.md)
- **Status Otorisasi Produksi**: `false` (Referensi baca-saja; tidak memberikan izin render)

## 1. Pengukuran Sinyal Terverifikasi (`ffprobe`, `ffmpeg`, `OpenCV`)
- **Video**: `720×1280` (`9:16` bersih tanpa UI perekaman layar), `H.264`, `30,0 fps`, `4.635` frame, durasi stream `154,500 s` (kontainer `154,619 s`).
- **Audio**: `HE-AAC` stereo `44.100 Hz`, loudness terintegrasi **`-14,8 LUFS`**, rentang dinamika **`4,2 LU`**, true peak **`-0,2 dBFS`**, hanya `9` jeda hening `>250 ms` (`3,601 s` total) yang menandakan narasi rapat di atas musik latar kontinu.
- **Deteksi Kandidat Cut & Transisi**:
  - `FFmpeg scene > 0.30`: `2` segmen; `FFmpeg scene > 0.08`: `16` segmen.
  - `OpenCV Adaptive MAD`: `78` kandidat perubahan mendadak + `51` kandidat perubahan bertahap (*sustained change*).
  - **Temuan Forensik Visual**: Banyaknya *cross-dissolve* `10–15 frame` antar-lokasi (terlihat jelas pada `00:06,0s`, `00:21,0s`, `00:36,0s`, dan `02:15,0s`) membuat detektor *hard-cut* tunggal tidak cukup tanpa peninjauan contact sheet 52 frame.

## 2. Dekonstruksi 10 Dimensi Produksi
1. **Struktur Narasi & Hook (`0–5s`)**: Menggunakan sudut pandang orang kedua (*"Kamu..."*) dengan pola **Circular Bedroom Loop** — dibuka tokoh utama bangun tidur di kasur ungu (`00:00s`) dan membuka pintu rumah (`00:03s`), lalu ditutup bangun kembali di kasur yang sama (`02:30s`) dan melangkah keluar rumah (`02:33s`).
2. **Shot, Timestamp & Pacing**: Sekitar `48` shot visual berdurasi rata-rata `2,0–4,5 detik` yang dikelompokkan dalam 8 sekuens tematik (`12–22 detik` per sekuens: jalan raya/kementerian, kemacetan/Bappenas, sekolah/Puskesmas, pangan/bansos, indeks korupsi/integritas sejarah, kontras kampanye pemilu, hingga bilik suara).
3. **Karakter & Acting**: Satu protagonis konsisten berbaju hijau toska sebagai wakil penonton, dikelilingi ansambel modular yang langsung dikenali lewat siluet properti (helm proyek kuning, jas dokter, caping petani, toga hakim, podium kandidat).
4. **Gerak Tubuh, Ekspresi & Objek**: Kepala bulat (`~0,35` tinggi badan) dan anggota tubuh silinder ramping; ekspresi wajah 2D kontras tinggi (mata membelalak, keringat panik di bilik suara `02:27s`, kilau kacamata `01:18s`) dengan interaksi objek konkret (penggaris aspal, motor merah, timbangan `10 kg`, papan catur, surat suara).
5. **Kamera & Sinematografi**: Kombinasi *eye-level medium*, *wide diorama establishing*, *high-angle crowd shot* (`00:48s` rasio `1 DOKTER` di tengah ratusan warga), *over-the-shoulder* podium, dan panggung sorot lampu tunggal (`01:48s`).
6. **Environment, Aset, Material & Lighting**: Diorama fasilitas publik & rumah Indonesia bermaterial *matte/semi-matte* bersih; pencahayaan hangat lampu meja untuk interior kamar/arsip dan *daylight* cerah untuk jalan raya/kampanye.
7. **Technical Cutaway & Demonstrasi Diegetik**: Statistik tidak ditampilkan sebagai slide 2D datar, melainkan **properti 3D di dalam dunia cerita** (`RAPOR DUNIA 34/100`, `DETIK MERAH 30`, baliho `KERUGIAN MACET 65 TRILIUN`, kerumunan figur `1 DOKTER`).
8. **Caption & Typography**: Caption dinamis *word-by-word* (`1–2 kata` per cue) putih tebal ber-stroke hitam di sepertiga bawah tengah, dipadukan papan nama 3D huruf kapital yang terbaca jelas di layar ponsel.
9. **Narasi, Audio & SFX**: VO Bahasa Indonesia lugas berirama satir tenang dengan kompresi rapi (`-14,8 LUFS`). Transkrip penuh ASR dan pemisahan stem musik tidak diklaim ataupun disalin.
10. **Editing, Transition & VFX**: *Hard cut* cepat di dalam adegan yang sama, *cross-dissolve* lembut saat berpindah topik/instansi, kerucut cahaya panggung volumetrik, dan *rack focus* buram latar depan (`01:45s`).
