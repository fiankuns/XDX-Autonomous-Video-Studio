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
7. **Reference Database Curator & Pattern Synthesizer (`intelligence/reference_database_bridge.py`, `reference_database/`)**
   - Memverifikasi byte & SHA-256 objek Git LFS (`REF-001`, `REF-002`), menjalankan routing otomatis (`explainer`/`explainair` → `REF-002`; `storytelling`/`satir_sosial` → `REF-001`) maupun fusi multi-referensi (`--ref-ids`), menggabungkan MP4 asli + analisis REA-Video v3.4 + profil produksi + `prior_analysis.*` secara *append-only*, serta menjaga `production_authorized == False` hingga persetujuan manusia diterima.

## 2. Larangan Mutlak Bagi Seluruh Agen
- **Dilarang** memulai modeling, mutasi scene Blender, animasi, atau render video sebelum status `APPROVED` terverifikasi melalui `ExecutionAuthorizationContext` yang sah.
- **Dilarang** mengandalkan pencarian substring sederhana atau boolean tunggal untuk otorisasi eksekusi.
- **Dilarang** menghasilkan naskah berlabel placeholder, riset berstatus `pending_external_verification` pada genre faktual, atau menyamarkan kotak 12-segitiga sebagai aset produksi.
- **Dilarang** menganggap *in-process MCP discovery* sebagai bukti koneksi live ke perangkat **Vivo X200 Pro**.
- **Dilarang** memodifikasi file apa pun di dalam repository `fiankuns/xdx-blender-studio` tanpa izin eksplisit pemilik proyek.
- **Dilarang** menulis ke path `/tmp` di dalam skrip `bpy` Blender Android (wajib gunakan `bpy.app.tempdir`).
- **Dilarang** menyalin kode `UNLICENSED` (`remotion-dev/animated-captions`), mencampur kode `AGPL-3.0`/`GPL-3.0` ke dalam paket inti MIT, meminta token di chat, atau menyimpan aset besar/cache/rahasia ke GitHub (selain objek referensi resmi yang telah diizinkan melalui Git LFS di `reference_database/`).
- **Dilarang** meminta pengguna mengunggah ulang video referensi yang sudah terverifikasi di `reference_database/`, menghapus `prior_analysis.*`, atau menyalin karakter, dialog, merek/UI perekam layar, maupun musik dari video referensi.
- **Dilarang** bagi `master_director` bertindak sebagai satu-satunya pemeriksa atas hasil kerjanya sendiri, mengaktifkan lebih dari batas specialist tanpa kebutuhan (`3–6` specialist awal), atau mengubah status langsung ke `APPROVED` / `COMPLETED`.
- **Dilarang** bagi agen Independent Verification (`preproduction_verifier`, `visual_critic`, `technical_auditor`, `success_auditor`) mengedit diam-diam artefak milik *Producer* atau meluluskan produksi video hanya dari unit/schema test tanpa bukti render aktual (lihat piagam lengkap pada `TEAM.md` dan kontrak 20 specialist pada `orchestration/agent_registry.py`).

## Phase 01.6B — Persistent Agent Intelligence, DAG Execution & Checkpoint Recovery (v4.0-alpha.2, aditif)
- Kepemilikan artefak wajib divalidasi secara kanonik (realpath, symlink, batas workspace/project, pola role) dan dikunci lintas proses melalui `ArtifactOwnershipLockManager`; perbandingan string path tidak boleh dipakai sebagai single-writer lock.
- `expected_output.output_artifacts` harus merupakan subset `owned_artifacts`; konflik input/output/ownership/role ditolak ulang saat eksekusi.
- Independent verifier hanya lulus bila laporan valid terhadap `schemas/review_report.schema.json`, reviewer ≠ producer, hash artefak producer tidak berubah, dan receipt memiliki `invocation_id`.
- Capability discovery memakai 7 status berbasis bukti ber-TTL (`schemas/capability_evidence.schema.json`); in-process discovery bukan bukti koneksi live Vivo X200 Pro.
- Eksekusi DAG lewat `orchestration/dependency_scheduler.py`; `blender_specialist` tetap diblokir sampai `ExecutionAuthorizationContext` APPROVED. Checkpoint/revisi via `orchestration/checkpoint_manager.py` & `orchestration/revision_manager.py`; memori SQLite 6 partisi (`.xdx_memory/`, tidak di-commit) dengan redaksi rahasia.
- `master_director` tetap dilarang menyetel `APPROVED`/`COMPLETED`.

## Phase 02A — Consolidation (v4.0, aditif; VISUAL_ONLY_BENCHMARK)
- **Mesin generik, bukan per topik:** kode bersama ada di `engines/web/xdx_core/` (`kit`, `comets`, `timeline`, `barrier`, `style_binding`, `assets/`); file scene hanya berisi koreografi topik. Aset yang digambar harus terdaftar di `registry/asset_registry.json` dan diikat per proyek lewat `asset_bindings.json`; status `PLACEHOLDER`/`PLANNED` memblokir QC final.
- **Alur wajib:** validasi input → timeline kanonik integer-frame (chapter = tampilan di timeline yang sama, tanpa timeline kedua) → kontrak visual semantik per beat → style frame satu per caption → animatic / preview gerak per shot dari mesin yang sama → render → shot evidence (frame aktual ber-hash) → Independent Semantic Visual QC → delivery validation. Perintah: `scripts/visual_workflow.py` (`validate-inputs|timeline|contract|rerender-plan|delivery`), `scripts/render_phase02a_visual.py --prototype --preview|--animatic|--shot`.
- **Re-render selektif** berdasarkan hash + dependensi (`render_dependencies.json`); render yang sudah diterima menjadi benchmark piksel (`docs/evidence/phase02a_visual_only/regression_benchmark_v5.json`) dan refactor wajib identik.
- **Teknik yang terbukti (Production Memory, `memory/seed_knowledge/production_techniques_v4.json`):** frame murni deterministik; beat terikat cue caption (lead ≤ 0,3 s); kamera datar tanpa roll dan cut pada aksi (bukan whip); aliran searah dengan panah; prop artikulatif siap cutaway; subjek di atas safe area caption; palet dari bible, gagal-tertutup bila hilang.
- **Pelajaran kegagalan (Error Memory, `error_lessons_v4.json`, defect `DEF-P02A-041…046`):** aset primitif, overlay debug, partikel tanpa arah, caption menutup subjek, beat frame hard-coded, roll/whip kamera, celah set, QC buta semantik, perubahan nilai tidak terlihat, kontinuitas antar-cut. Tidak ada yang spesifik AC.
- **Tetap berlaku:** Trusted Approval + Execution Guard untuk semua render (termasuk preview/animatic/per-shot); Remotion = master timeline, Three.js = visual engine, Blender = modeling/rigging/acting/cinematic (Phase 02B, butuh persetujuan); audio/TTS/musik/SFX/lip sync ditunda ke Phase 04; maks. 2 agen aktif; reviewer ≠ producer; tidak ada `APPROVED`/merge ke main oleh agen.

## Action Choreography Contract (generik, v4.0)
- Setiap aksi penting dalam naskah wajib punya *action event* (`projects/<id>/action_events.json`): aktor + bagian tubuh, objek, target, sisi/ujung yang menghadap, jendela waktu relatif cue, apa yang belum boleh terjadi, kamera, dan bukti. Panduan + templat perintah: `docs/ACTION_CHOREOGRAPHY_GUIDE.md`.
- Dilarang menebak sudut sendi untuk aksi kontak/arah: gunakan `solveArm` / `aimTwo` / `lookHead` (`engines/web/xdx_core/rig_ik.js`); objek genggam dibangun dengan gagang di dalam kepalan.
- Urutan sebab-akibat: gestur persiapan (menoleh ke target) tepat sebelum aksi, lalu cut ke macro aksi kontak (sembunyikan oklusi), lalu cut ke efek. Horizon datar. Nilai yang berubah harus terlihat sebelum dan sesudah.
- Bukti geometris sebelum review piksel: `scripts/visual_workflow.py verify-actions`; gate delivery memblokir laporan yang hilang atau gagal.
