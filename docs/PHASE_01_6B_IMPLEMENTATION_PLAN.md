# Rencana Implementasi Phase 01.6B — Structured Handoff Execution, Task Scheduler, Shared Memory & Checkpoint

> **Status Saat Ini**: **BELUM DIJALANKAN** (Menunggu review dan instruksi pengguna setelah Phase 01.6A selesai sesuai PART 26 & PART 28).

---

## 1. Ruang Lingkup Teknis Phase 01.6B

1. **`orchestration/dependency_scheduler.py`**:
   - Mesin eksekusi DAG bertahap di atas `TaskHandoffManager` dengan *ready queue*, batas konkurensi dinamis (`3–6` specialist aktif, `1` worker Blender), *timeout* per task, dan pengelolaan *retry budget* otomatis.
2. **`orchestration/shared_state.py` & State Machine v4.0**:
   - Memperluas state machine eksplisit ke 16 state utama (`IDLE` → `REQUEST_RECEIVED` → `RESEARCHING` → `REFERENCE_ANALYSIS` → `CREATIVE_DEVELOPMENT` → `STORYBOARDING` → `PREPRODUCTION_QC` → `WAITING_APPROVAL` → `APPROVED` → `ASSET_PRODUCTION` → `ANIMATING` → `RENDERING` → `POST_PRODUCTION` → `TECHNICAL_QC` → `VISUAL_QC` → `COMPLETED`) ditambah 10 state pengecualian (`CREATIVE_PAYLOAD_REQUIRED`, `REFERENCE_UNAVAILABLE`, `WAITING_RESOURCE`, `WAITING_CONNECTION`, `WAITING_REAPPROVAL`, `REVISION_REQUIRED`, `PAUSED`, `FAILED`, `CANCELLED`, `BLOCKED`) dengan kompatibilitas penuh terhadap `ProjectStateManager` v3.4.
3. **`memory/` — Enam Partisi Penyimpanan Terstruktur**:
   - Implementasi `KnowledgeMemory`, `ProductionMemory`, `ProjectMemory`, `ExecutionMemory`, `ErrorMemory`, dan `QualityMemory` menggunakan *atomic writes*, `fcntl` *file locking*, *versioning*, dan verifikasi SHA-256 artefak aktual di disk (menolak klaim "selesai" apabila file artefak hilang).
4. **`orchestration/checkpoint_manager.py` & `orchestration/revision_manager.py`**:
   - Pemulihan proyek pasca-interupsi (`LANJUTKAN PROJECT`) dari checkpoint tervalidasi terakhir tanpa memberikan otorisasi produksi otomatis, serta pembatalan approval otomatis ke `WAITING_REAPPROVAL` ketika revisi mengubah artefak input.

---

## 2. Acceptance Criteria Phase 01.6B

- Seluruh 42 pengujian v3.4 + seluruh pengujian Phase 01.6A tetap lulus (`0` regresi).
- Pengujian baru untuk: *task timeout*, *resume after interruption*, *checkpoint artifact-missing detection*, *parallel file lock contention*, *revision digest invalidation*, dan *v4.0 illegal state transition rejection*.
- Berhenti penuh setelah commit Phase 01.6B untuk review pengguna sebelum memasuki Phase 01.6C.
