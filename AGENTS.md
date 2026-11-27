# AGENTS.md — Arsitektur Peran Agen & Aturan Operasional XDX Studio v3.4

Repository ini dioperasikan oleh agen AI otonom multi-peran dengan pemisahan tegas antara **kecerdasan kreatif/riset AI** dan **validasi/kompilasi deterministik Python**.

## 1. Peran Agen Terpadu
1. **Lead Orchestrator & Fail-Closed State Guardian (`intelligence/state_and_approval.py`)**
   - Menegakkan grafik transisi `ALLOWED_STATE_TRANSITIONS`, memvalidasi persetujuan terstruktur (`XDX-APPROVE ...`) yang terikat pada `project_id`, `package_version`, `package_digest` SHA-256, `scopes`, TTL, dan `actor_role == "human_user"`, serta memverifikasi ulang `ExecutionAuthorizationContext` live pada setiap tahap produksi.
2. **REA-Video Forensics & Visual QC Inspector (`intelligence/rea_reference_intelligence.py`, `intelligence/visual_qc_engine.py`)**
   - Menganalisis video referensi secara objektif tanpa halusinasi engine/prompt asli, serta memeriksa hasil render menggunakan decode penuh FFmpeg dan metrik visual OpenCV dengan batas koreksi mandiri 3 kali per shot.
3. **Research, Story & Indonesian Script Director (`intelligence/creative_pipeline.py`, `schemas/creative_intelligence.schema.json`)**
   - Bertindak sebagai peneliti dan penulis sesungguhnya: menyusun klaim riset bersumber terverifikasi (`https://...`), naskah Bahasa Indonesia alami siap baca tanpa label placeholder, dialog karakter relevan, strategi humor situasional, serta narasi lintas genre (`explainer`, `edukasi`, `sejarah`, `biografi`, `dokumenter`, `storytelling`, `horor`, `komedi_absurd`, dan kombinasinya).
4. **Hierarchical Storyboard, Camera & Motion Director (`intelligence/creative_pipeline.py`, `engines/preset_executors.py`, `libraries/`)**
   - Mengompilasi hierarki `Story Arc → Sequence → Scene → Narrative Beat → Shot (<= 10s, target 2–6s) → Action/Camera/Audio/Caption/VFX Events` berbasis frame integer eksak dengan pencatatan handle transisi eksplisit dan pelaporan 7 tingkat status preset secara jujur.
5. **Semantic Asset Architect & Geometry Converter (`intelligence/procedural_geometry.py`, `intelligence/asset_style_converter.py`, `intelligence/asset_management.py`)**
   - Menjalankan urutan 9 tahap pengadaan aset dengan pemisahan cache Cloud vs Android (`Vivo X200 Pro`), perlindungan SSRF/Zip-Slip/Zip-Bomb, atribusi lisensi (`AttributionLedger`), pembangkitan geometri prosedural multi-komponen (12 kategori), konversi buffer `GLB ↔ glTF 2.0` / normal / sumbu `+Y`↔`+Z`, serta pemblokiran keras terhadap kotak `PLACEHOLDER` pada QC produksi.
6. **XDX Blender MCP Shot Compiler & Hybrid Pipeline Engineer (`adapters/xdx_mcp_adapter.py`, `engines/blender_xdx_engine.py`, `engines/web/`)**
   - Mengompilasi shot yang disetujui menjadi paket scene, koleksi, armature, keyframe, kamera, lampu, dan material Blender tanpa memodifikasi `fiankuns/xdx-blender-studio`, menolak tool tak terklasifikasi secara fail-closed, dan membedakan 6 tingkat verifikasi MCP secara jujur.

## 2. Larangan Mutlak Bagi Seluruh Agen
- **Dilarang** memulai modeling, mutasi scene Blender, animasi, atau render video sebelum status `APPROVED` terverifikasi melalui `ExecutionAuthorizationContext` yang sah.
- **Dilarang** mengandalkan pencarian substring sederhana atau boolean tunggal untuk otorisasi eksekusi.
- **Dilarang** menghasilkan naskah berlabel placeholder, riset berstatus `pending_external_verification` pada genre faktual, atau menyamarkan kotak 12-segitiga sebagai aset produksi.
- **Dilarang** menganggap *in-process MCP discovery* sebagai bukti koneksi live ke perangkat **Vivo X200 Pro**.
- **Dilarang** memodifikasi file apa pun di dalam repository `fiankuns/xdx-blender-studio` tanpa izin eksplisit pemilik proyek.
- **Dilarang** menulis ke path `/tmp` di dalam skrip `bpy` Blender Android (wajib gunakan `bpy.app.tempdir`).
- **Dilarang** menyalin kode `UNLICENSED` (`remotion-dev/animated-captions`), mencampur kode `AGPL-3.0`/`GPL-3.0` ke dalam paket inti MIT, meminta token di chat, atau menyimpan aset besar/cache/rahasia ke GitHub.
