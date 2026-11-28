# Shared Persistent Memory (`memory/`) — Peta Jalan Phase 01.6B

Sesuai prinsip kejujuran arsitektur **PART 25 & PART 28**, direktori `memory/` diinisialisasi pada **Phase 01.6A** tanpa konfigurasi atau implementasi palsu.

Implementasi penuh keenam partisi penyimpanan terstruktur berbasis *atomic write*, *file locking*, *content hashing*, dan *checkpoint recovery* dijadwalkan pada **Phase 01.6B**:
1. `knowledge_memory` — Referensi video, profil genre, DNA teknik produksi terverifikasi, dan sumber riset.
2. `production_memory` — Teknik modeling, rigging, motion, kamera, material, dan caption yang telah lulus pengujian.
3. `project_memory` — Topik, keputusan pengguna, naskah, storyboard, Character Bible, Style Bible, dan catatan approval.
4. `execution_memory` — Status DAG task, checkpoint, percobaan (*attempt*), dan manifest artefak.
5. `error_memory` — Riwayat *defect*, log kegagalan, akar masalah, solusi, dan regression test terkait.
6. `quality_memory` — Bukti frame, hasil render, contact sheet, dan evaluasi yang telah ditinjau independen.

## Seed produksi (Phase 02A)
`memory/seed_knowledge/production_techniques_v4.json` (teknik teruji, `RENDER_TESTED`) dan `error_lessons_v4.json` (kegagalan → akar masalah → perbaikan → pencegahan) adalah sumber kebenaran yang di-commit; `memory/seed_loader.py::load_production_seed(store)` memuatnya ke `ProductionMemory` / `ErrorMemory` (`project_id="xdx_global"`). Database SQLite tetap tidak di-commit.
