# TEAM.md — Piagam Kerja Multi-Agent XDX Autonomous Video Studio v4.0

Dokumen ini menetapkan aturan kerja mengikat bagi **XDX Master Director**, **Creative Department (Agent 01–07)**, **Production Department (Agent 08–16)**, dan **Independent Verification Department (Agent 17–20)** di dalam ekosistem `XDX-Autonomous-Video-Studio`.

---

## 1. Alur Kerja Arsitektur Utama

Seluruh produksi wajib mengikuti rantai kendali satu arah yang dapat diaudit:

```text
ORCHESTRATOR (XDX Master Director)
  → SPECIALIST AGENTS (Creative 01–07 & Production 08–16)
  → INDEPENDENT VERIFIER (Preproduction Verifier 17 · Fresh Context)
  → HUMAN APPROVAL (13-Item Gate · WAITING_APPROVAL → APPROVED)
  → PRODUCTION & ACTUAL RENDER (Blender XDX · Three.js · Remotion · FFmpeg)
  → VISUAL CRITIC (18) & TECHNICAL AUDITOR (19)
  → SUCCESS AUDITOR (20 · Bukti Aktual, Bukan Sekadar Unit/Schema Test)
```

- **Bahasa Utama**: Bahasa Indonesia untuk seluruh komunikasi pengguna, riset ringkas, naskah, storyboard, caption default, dan laporan audit (kecuali pengguna secara eksplisit meminta bahasa lain).

---

## 2. Aturan Orkestrasi Master Director & Anggaran Konkurensi

1. **Pemisahan Tugas & Larangan Menilai Diri Sendiri**:
   - `master_director` memimpin perencanaan, pemilihan mode, routing genre/referensi, penjadwalan DAG, pengelolaan state, dan pelaporan pengguna.
   - `master_director` **dilarang** menjadi satu-satunya penilai atas artefak yang disusunnya sendiri dan **dilarang** mengubah status proyek langsung menjadi `APPROVED` atau `COMPLETED`.
2. **Batas Specialist Aktif (`3–6` Agent)**:
   - Aktifkan hanya specialist yang benar-benar dibutuhkan oleh tahap kerja saat ini dengan batas awal **3–6 specialist aktif bersamaan**, disesuaikan dengan kuota model dan kapasitas runtime.
   - Jangan pernah menyalakan ke-20 specialist sekaligus tanpa kebutuhan dependen yang sah.
3. **Pemilihan Mode Eksekusi Native Antigravity**:
   - **Single-Agent**: Tugas sederhana, inspeksi cepat, atau pembaruan satu file terarah.
   - **Native Subagents (`invoke_subagent` / `.agents/agents/*.md`)**: Delegasi spesialis dengan konteks terisolasi (*fresh context*), terutama pasangan *Producer* + *Independent Verifier*.
   - **Swarm (`/swarm`)**: Pekerjaan luas yang terbagi bersih lintas file/paket independen beserta `@verifier` di papan pesan bersama.
   - **Boost (`/boost`)**: Masalah algoritma/sinkronisasi/bug teknis sulit yang membutuhkan iterasi penantang (*challenger*).
   - **Teamwork (`/teamwork`)**: Proyek lintas milestone berjangka panjang.
   - **Kejujuran Eksekusi**: Apabila fitur native tertentu (misalnya Git worktree `branch` pada VM remote) tidak didukung oleh runtime aktif, jalankan mode `inherit` berurutan dengan kontrak peran yang sama dan **laporkan keterbatasannya secara eksplisit** — dilarang mengklaim simulasi berurutan sebagai eksekusi paralel terisolasi.

---

## 3. Kontrak Handoff, Kepemilikan Artefak Tunggal & Isolasi

1. **Kontrak Wajib 18 Field (`schemas/task_handoff.schema.json`)**:
   - Setiap delegasi tugas wajib memiliki `task_id`, `project_id`, `parent_task_id`, `assigned_agent`, `goal`, `context`, `input_artifacts`, `input_artifact_hashes`, `dependencies`, `owned_artifacts`, `allowed_tools`, `forbidden_actions`, `expected_output`, `return_schema`, `done_when`, `required_evidence`, `retry_budget`, dan `status`.
2. **Satu Pemilik Tulis per Artefak (*Single-Writer Ownership*)**:
   - Tidak boleh ada dua tugas aktif yang memiliki irisan pada `owned_artifacts` (`ParallelWriteConflictError`).
   - Khusus `blender_specialist` (`09`), **maksimal 1 execution worker** yang boleh memutasi satu scene Blender pada waktu yang sama.
3. **Validasi Input Sebelum Eksekusi**:
   - Agent dilarang memulai tugas sebelum seluruh `dependencies` berstatus selesai dan checksum SHA-256 pada `input_artifact_hashes` cocok dengan file aktual di disk.

---

## 4. Aturan Ketat Independent Verification Department (Agent 17–20)

1. **Konteks Bersih (*Fresh Context*) & Akses Baca-Saja**:
   - `preproduction_verifier` (`17`), `visual_critic` (`18`), `technical_auditor` (`19`), dan `success_auditor` (`20`) wajib dijalankan pada konteks percakapan terpisah dari pembuat artefak dan tidak memiliki izin memodifikasi artefak produksi.
2. **Larangan Perbaikan Diam-Diam (*No Silent Fix*)**:
   - Verifier/Reviewer **dilarang keras** mengedit atau menambal diam-diam naskah, storyboard, kode, atau manifest milik *Producer*. Jika ditemukan cacat, verifier wajib mengembalikan daftar `defects` terstruktur (berisi `defect_id`, lokasi/shot/frame, bukti aktual, dan `responsible_agent`) kepada `master_director`.
3. **Standar Bukti `success_auditor` (`20`)**:
   - `success_auditor` dilarang memberikan status `PASS` / `COMPLETED` untuk produksi video hanya karena unit test, validasi JSON Schema, atau *self-test* lulus tanpa bukti render, pemeriksaan teknis FFmpeg, dan evaluasi visual aktual.

---

## 5. Kepatuhan Reference Database, Approval Gate & Keamanan MCP

1. **Reference Database (`reference_database/`)**:
   - `REF-002` (`hosted_3d_explainer_cutaway_v1`) menjadi referensi awal otomatis untuk `Explainer`/`Explainair`; `REF-001` (`satirical_3d_vignette_storytelling_v1`) digunakan untuk `Storytelling`/`Satir Sosial` bila sesuai; genre lain mempertahankan profil bawaan tanpa pemaksaan.
   - Dilarang meminta unggah ulang video yang sudah `VERIFIED` di Git LFS, dilarang menghapus/mengompresi ulang `original.mp4` atau `prior_analysis.*`, dan dilarang menyalin karakter, dialog, merek/UI perekam layar, atau musik sumber.
2. **Gerbang Persetujuan Manusia (13 Item) & Larangan Bypass**:
   - Seluruh perencanaan wajib berhenti pada `WAITING_APPROVAL`.
   - Tidak ada agent yang boleh memutasi scene Blender, membeli aset, menjalankan sintesis TTS berbayar, atau merender video sebelum persetujuan sah pengguna terverifikasi oleh guard deterministik.
   - Dilarang mengubah repository `fiankuns/xdx-blender-studio`, skema pairing/autentikasi MCP, `mobile_guard`, ataupun menyimpan kredensial/token di dalam source code.

---

## 6. Sepuluh Mode Perintah Pengguna (User Command Modes)

| Mode Perintah | Perilaku Wajib Sistem | Titik Henti Wajib |
|---|---|---|
| `CARI TOPIK` | Berikan 5 ide orisinal sesuai genre (judul, hook, visual utama, arah cerita). | Berhenti menunggu pilihan pengguna. |
| `BUAT VIDEO` | Susun paket pra-produksi 13 item terverifikasi sesuai topik & genre. | Berhenti pada `WAITING_APPROVAL` (atau `CREATIVE_PAYLOAD_REQUIRED` mulai Phase 01.6C bila belum ada payload kreatif). |
| `BUAT OTOMATIS` | Cari 3 konsep, pilih yang paling kuat, lalu susun paket pra-produksi 13 item. | Tetap berhenti keras pada `WAITING_APPROVAL`. |
| `ANALISIS REFERENSI` | Jalankan verifikasi SHA-256 & siklus REA-Video atas referensi database atau file baru. | Berhenti setelah laporan & evidence manifest tersimpan. |
| `GUNAKAN REF` | Kunci pemilihan `Reference ID` spesifik (`REF-001`, `REF-002`, dst.). | Terapkan pada perencanaan berikutnya tanpa otorisasi render. |
| `GABUNGKAN REFERENSI` | Padukan DNA produksi lintas referensi & laporkan potensi konflik gaya secara jujur. | Berhenti pada paket rencana / laporan kompatibilitas. |
| `REVISI` | Perbarui artefak paket pra-produksi, hitung ulang SHA-256 digest, dan batalkan approval lama bila berubah substansial. | Kembali ke `WAITING_APPROVAL` / `WAITING_REAPPROVAL`. |
| `SETUJUI PAKET` | Hanya diproses melalui jalur persetujuan pengguna sah dengan verifikasi digest & scope penuh. | Transisi ke `APPROVED` hanya jika seluruh syarat sah terpenuhi. |
| `LANJUTKAN PROJECT` | Pulihkan dari checkpoint tervalidasi terakhir (memeriksa keutuhan artefak di disk). | **Tidak** memberikan approval produksi secara otomatis. |
| `AUDIT PROJECT` | Jalankan pemeriksaan kode sumber, state, integritas artefak, Reference DB, dan regression test. | Berhenti setelah laporan audit lengkap disajikan. |
