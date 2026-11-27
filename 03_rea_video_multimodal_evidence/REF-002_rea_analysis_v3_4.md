# Analisis Mendalam REA-Video v3.4 — `REF-002` (Yakhchal — Hosted 3D Explainer & Technical Cutaway)

- **File Asli**: `1001952305.mp4` (`38.669.358` byte · Git LFS `VERIFIED`)
- **SHA-256**: `042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01`
- **Arsip Sebelumnya Dipertahankan**: [`prior_analysis.json`](prior_analysis.json)
- **Profil Produksi Terkait**: `hosted_3d_explainer_cutaway_v1`
- **Status Otorisasi Produksi**: `false` (Referensi baca-saja; tidak memberikan izin render)

## 1. Pengukuran Sinyal Terverifikasi (`ffprobe`, `ffmpeg`, `OpenCV`)
- **Video**: `720×1600` (`HEVC`, rekaman layar ponsel vertikal `9:20`), `35,00 fps` rata-rata (`3.694` frame), durasi `105,543 s`. *(Catatan: UI aplikasi sosial, status bar Android, dan notifikasi jaringan pada sumber rekaman layar diabaikan sepenuhnya dan dilarang ditiru).*
- **Audio**: `AAC-LC` stereo `48.000 Hz`, loudness rekaman **`-20,0 LUFS`** (produksi XDX dinormalisasi ke `-15,0 LUFS`), rentang dinamika **`2,9 LU`**, true peak **`-9,4 dBFS`**, dengan **`33` jeda napas terukur `>250 ms`** (`10,710 s` total) yang selaras dengan pergantian klausa penjelasan.
- **Deteksi Kandidat Cut**: `FFmpeg scene > 0.18` mendeteksi **`46` segmen** (median **`2,257 s`**, rata-rata **`2,294 s`**, rentang **`0,600 s – 6,028 s`**), konsisten kuat dengan `OpenCV Adaptive MAD` (**`47` kandidat abrupt**, hanya `4` *sustained change*). Tidak ada satu pun shot melebihi `6,03 detik`.

## 2. Dekonstruksi 10 Dimensi Produksi
1. **Struktur Narasi & Hook (`0–6s`)**: Pola **Kebutuhan Konkret → Pertanyaan Inti → Demonstrasi Fisik → Mekanisme Fisika → Rintangan Berantai & Solusi → Pengungkapan Sejarah → Callback**. Dibuka kebutuhan langsung meracik es teh manis di tengah panas terik (`00:00–00:06s`), bukan definisi kamus.
2. **Shot, Timestamp & Pacing**: Ritme *hard-cut* presisi `2–4 detik` per klausa, diselingi *micro-shot* `0,6–1,5 detik` pada aksi menuang teh, jarum termometer, dan kemunculan panah aliran udara.
3. **Karakter & Acting**: Satu karakter *host* konsisten yang mempraktikkan langsung setiap tahap rekayasa (menggali kolam dangkal, melapisi tanah liat, mengaduk adukan, memanen balok es) sekaligus mewakili rasa penasaran penonton (*"kan di gurun?"*, `00:18s`).
4. **Gerak Tubuh, Ekspresi & Objek**: Gerakan berbasis kata kerja fisik yang terbaca jelas: menuang teko (`00:04s`), berlutut memeriksa es (`00:16s`), mengipasi wajah (`00:40s`), mengaduk pasir-abu-bulu kambing bersama figur kambing 3D (`01:00–01:02s`), hingga mengangkat gelas dingin (`01:42s`).
5. **Kamera & Sinematografi**: Pergantian disiplin antara 4 sudut utama: (a) **Top-Down 90° Insert** (`00:02s`, `00:10s`, `00:36s`, `00:58s`), (b) **Orthographic Cross-Section Cutaway** belahan tanah & kubah (`00:24s`, `00:48s`, `01:12s`, `01:20s`), (c) **Eye-Level Host Medium**, dan (d) **Low-Angle Architectural Reveal** (`01:06s`, `01:28s`).
6. **Environment, Aset, Material & Lighting**: Lingkungan berkembang secara kausal mengikuti tahap pembangunan struktur; pencahayaan matahari fungsional menghasilkan bayangan geometris nyata yang membuktikan fungsi tembok peneduh (`00:36–00:38s`), dikontraskan dengan pencahayaan malam biru dingin (`00:22–00:28s`).
7. **Technical Cutaway & Demonstrasi**: Belahan melintang tanah berlapis dengan **panah 3D berkode warna** (biru: udara dingin berat turun ke kolam; merah: rambatan panas tanah; oranye: udara hangat naik ke lubang puncak kubah; sian: sirkulasi menara penangkap angin *badgir*), termometer analog (`40°C` ke `-2°C`), serta selipan humor anakronisme singkat (`TOKO MATERIAL: BUKA 2000 TAHUN LAGI`, `01:08s`).
8. **Caption & Typography**: Frasa pendek `2–3 kata` sinkron klausa di area aman bawah-tengah, ditambah papan penanda diegetik ringkas (`YAKHCHAL — YAZD - IRAN`, `01:32s`).
9. **Narasi, Audio & SFX**: Bahasa Indonesia sehari-hari yang memecah fisika termodinamika menjadi sebab-akibat konkret (`"udara dingin itu berat -> ngumpul di bawah"`).
10. **Editing, Transition & VFX**: Hampir 100% *hard cut* bersih pada akhir klausa, VFX pita aliran udara 3D deterministik, dan callback visual penutup kembali ke meja pembuka (`01:42–01:45s`).
