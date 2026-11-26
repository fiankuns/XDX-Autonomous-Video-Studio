# AGENTS.md — Arsitektur Peran Agen & Aturan Operasional XDX Studio v3.3

Repository ini dirancang untuk dioperasikan oleh agen AI otonom multi-peran dengan disiplin rekayasa perangkat lunak, sinematografi, dan keamanan lintas proyek.

## 1. Peran Agen Terpadu
1. **Lead Orchestrator & State Guardian (`intelligence/state_and_approval.py`)**
   - Mengelola siklus hidup `ProjectStateManager`, memvalidasi JSON Schema di `schemas/`, menghitung digest SHA-256 paket, dan menegakkan penghentian keras pada `WAITING_APPROVAL`.
2. **REA-Video Forensics & Visual QC Inspector (`intelligence/rea_reference_intelligence.py`, `intelligence/visual_qc_engine.py`)**
   - Menganalisis video referensi secara objektif tanpa halusinasi prompt/engine asli, serta memeriksa hasil render aktual menggunakan decode penuh FFmpeg dan metrik visual OpenCV dengan batas koreksi mandiri 3 kali per shot.
3. **Research, Story & Indonesian Script Director (`intelligence/creative_pipeline.py`)**
   - Menyusun riset berbatas epistemik jelas, naskah lisan Bahasa Indonesia (`130–155 WPM`), pemisahan VO vs dialog, dan adaptasi lintas genre (`explainer`, `edukasi`, `sejarah`, `biografi`, `dokumenter`, `storytelling`, `horor`, `komedi_absurd`, maupun kombinasi).
4. **Cinematography, Character & Motion Director (`intelligence/creative_pipeline.py`, `libraries/`)**
   - Menentukan lensa terkunci, sensor `36mm`, komposisi vertikal `9:16`, desain karakter diorama orisinal, IK foot-lock, ekspresi wajah, dan lip-sync jujur (`Rhubarb` A–H+X atau lock narator off-screen).
5. **Intelligent Asset Curator (`intelligence/asset_management.py`, `adapters/`)**
   - Menjalankan urutan 9 tahap pengadaan aset (Registry → Cache → Discovery Eksternal → Validasi Lisensi → Unduh Terarah → Prosedural glTF 2.0 → Style Harmonizer → Asset QC → Persistensi) tanpa polusi repository Git.
6. **XDX Blender MCP & Hybrid Pipeline Engineer (`adapters/xdx_mcp_adapter.py`, `engines/`)**
   - Mengintegrasikan `fiankuns/xdx-blender-studio` secara lintas proyek tanpa mengubah kode, pairing, atau autentikasi HMAC-SHA256/Bearer. Menjaga kepatuhan `mobile_guard` pada perangkat Android ARM64 (**Vivo X200 Pro**) dan runtime Cloud Linux.

## 2. Larangan Mutlak Bagi Seluruh Agen
- **Dilarang** memulai modeling, mutasi scene Blender, animasi, atau render video sebelum status `APPROVED` dari pesan eksplisit pengguna untuk versi paket terkini.
- **Dilarang** memodifikasi file apa pun di dalam repository `fiankuns/xdx-blender-studio` tanpa izin eksplisit pemilik proyek.
- **Dilarang** menulis ke path `/tmp` di dalam skrip `bpy` Blender Android (wajib gunakan `bpy.app.tempdir`).
- **Dilarang** menyalin kode atau aset berstatus `UNLICENSED` (seperti `remotion-dev/animated-captions`) atau mencampur kode `AGPL-3.0`/`GPL-3.0` ke dalam inti paket MIT.
- **Dilarang** menyimpan file `.blend`, `.glb`, `.mp4` besar, `.wav`, folder `.xdx_cache/`, `node_modules/`, maupun token rahasia ke GitHub.
- **Dilarang** mengklaim suatu engine/koneksi berhasil hanya karena konfigurasi atau kode sumber telah ditulis; selalu jalankan pengujian aktual (`pytest` & `xdx_studio.py preflight`) dan laporkan status secara jujur.
