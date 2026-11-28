---
name: xdx-autonomous-video-studio
version: 3.4.0
replaces: xdx-autonomous-video-studio (v3.3), xdx-reference-to-hybrid-video (v3.1)
description: Hardened universal multi-genre autonomous video production studio (v3.4). Combines AI-authored verified research & natural Indonesian scriptwriting with fail-closed structured approval gates, hierarchical frame-exact storyboards (15s-180s+, all shots <=10s), 12-category multi-component glTF/GLB semantic asset generation, real buffer/style conversion, Blender shot compilation, Three.js v0.187, Remotion v4.0.547, REA-Video forensics, and Visual QC.
---
# XDX Autonomous Video Studio Skill v3.4

1. **Baca Protokol Utama**: Selalu baca `MASTER_PROMPT.md` dan `AGENTS.md` terlebih dahulu. Komunikasi menggunakan Bahasa Indonesia.
2. **Preflight 6-Tingkat & Validasi Skema**:
   ```bash
   python3 scripts/xdx_studio.py preflight
   python3 scripts/xdx_studio.py validate-all
   ```
   Bedakan dengan jujur antara *in-process protocol test* dan koneksi live ke **Vivo X200 Pro** (`live_android_blender_connected`). Jangan pernah meminta token di chat atau menyimpan kredensial di Git.
3. **AI sebagai Penulis & Peneliti Aktual (`CreativeProductionPayload`)**:
   - Tulis riset bersumber primer/institusional terverifikasi (`https://...`), blueprint 3 babak, karakter orisinal, dialog hidup, dan naskah Bahasa Indonesia alami tanpa tag placeholder ke dalam format `schemas/creative_intelligence.schema.json`.
   - Kompilasi paket 13 item ke status `WAITING_APPROVAL`:
     ```bash
     python3 scripts/xdx_studio.py plan --project-id <ID> --duration 150 --payload-json <payload.json> --out projects/<ID>
     ```
4. **Fail-Closed Approval Gate**:
   - Verifikasi paket melalui `python3 scripts/approval_gate.py projects/<ID> --strict-schema`.
   - Berhenti penuh pada `WAITING_APPROVAL`. Eksekusi mutasi scene/produksi hanya diizinkan setelah pengguna memberikan perintah persetujuan terstruktur (`XDX-APPROVE project=... version=... digest=... scopes=...`) yang lolos `ExecutionAuthorizationContext` live.
5. **Pengadaan Aset Semantik & Kompilasi Hybrid**:
   - Gunakan `IntelligentAssetPipeline` (menolak kotak `PLACEHOLDER` untuk produksi akhir) dan `BlenderXDXEngine` / `ThreeJSEngine` / `RemotionEngine` / `PresetExecutorEngine` sesuai `engine_plan.json`, diakhiri validasi `FFmpegEngine` & `VisualQualityControlEngine`.
6. **Automatic Reference Database Intelligence (`reference_database/`)**:
   - Verifikasi objek Git LFS referensi (`REF-001` & `REF-002`) tanpa meminta pengguna mengunggah ulang:
     ```bash
     python3 reference_database/scripts/reference_db.py verify
     python3 scripts/xdx_studio.py references --genres explainair
     ```
   - Routing otomatis pada `xdx_studio.py plan`: `explainer`/`explainair` → `REF-002` (`hosted_3d_explainer_cutaway_v1`); `storytelling`/`satir_sosial` → `REF-001` (`satirical_3d_vignette_storytelling_v1`); dukung pemilihan spesifik & multi-referensi melalui `--ref-ids REF-001 REF-002`. Pertahankan seluruh `prior_analysis.*` secara *append-only* dan selalu berhenti pada `WAITING_APPROVAL`.
7. **v4.0 Multi-Agent Foundation & Skill Routing (`TEAM.md`, `.agents/`, `orchestration/`)**:
   - Gunakan skill terfokus di `.agents/skills/` (`xdx-master-orchestration`, `xdx-reference-intelligence`, `xdx-preproduction-planning`, `xdx-independent-audit`) serta custom subagents di `.agents/agents/`.
   - Periksa kapabilitas runtime dan rencana dispatch 20 specialist:
     ```bash
     python3 scripts/xdx_studio.py capabilities
     python3 scripts/xdx_studio.py agents --mode BUAT_VIDEO
     ```

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

## Motion, Callout dan Durasi (generik, v4.0 lanjutan)
- Gerak berulang (mengipas, mengusap) = `travel_gt` + `rigid` pada action event; penggerak = sendi yang benar (pergelangan untuk mengipas, lengan bawah+siku keluar untuk mengusap); sisi prop menghadap target sepanjang siklus. Sketsa pengguna pada frame disalin menjadi pole vector/lintasan/constraint, tidak ditafsirkan ulang.
- Close-up aksi kontak meniru cutaway yang disetujui: objek tegak dan utuh, jari menggenggam di sisi, jempol diagonal menyentuh tombol, kamera memakai vektor atas objek, oklusi disembunyikan, hard cut.
- Label = pill + garis penunjuk + cincin kecil pada bagian yang disebut (`xdx_core/callouts.js`); pill digeser menjauh, tidak menutup caption/pill lain/bagian bernama; dicek `callout_contract.py`.
- Durasi mengikuti isi: `min_seconds` per event; `retime_package`/`visual_workflow.py retime` menjaga satu timeline konsisten; target 15 dtk hanyalah default.
- Latar tampang potong (section): lantai/dinding dipotong pada bidang yang sama, tanah di depan potongan menerus; jangan ada bentuk liar (pondasi menonjol, bayangan miring); cek dengan `__xdxPick`.
