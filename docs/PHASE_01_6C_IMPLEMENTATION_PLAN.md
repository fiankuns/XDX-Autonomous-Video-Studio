# Rencana Implementasi Phase 01.6C — Creative Specialist Agents, End-to-End Multi-Agent Pre-Production & Approval Readiness (v4.0)

> **Status**: **DOKUMEN RENCANA SAJA (BELUM DIEKSEKUSI PADA PHASE 01.6B)**
> Seluruh pekerjaan di bawah ini dijadwalkan setelah audit independen atas branch `feat/phase-01.6b-persistent-agent-intelligence` selesai dan disetujui pemilik proyek.

---

## 1. Tujuan Utama Phase 01.6C

Mengintegrasikan fondasi orkestrasi DAG (`orchestration/dependency_scheduler.py`), penyimpanan memori 6 partisi (`memory/persistent_memory.py`), checkpoint recovery (`orchestration/checkpoint_manager.py`), dan revision invalidation (`orchestration/revision_manager.py`) dengan eksekusi nyata **Creative Department Agents (01–07)** + **Audio/Caption Planning Agents (15–16)** + **Asset Planning Agent (08)** + **Preproduction Verifier (17)** hingga menghasilkan paket pra-produksi 13 item utuh yang berhenti secara *fail-closed* pada status `WAITING_APPROVAL`.

---

## 2. Ruang Lingkup Teknis Phase 01.6C

### A. Orkestrasi Multi-Agen Paket Pra-Produksi 13 Item
1. **Tahap Paralel 1 (`RESEARCHING` & `REFERENCE_ANALYSIS`)**:
   - `topic_research_agent` (`xdx-topic-researcher`): menghasilkan klaim riset faktual bersumber primer/institusional (`https://...`), pemetaan miskonsepsi, dan `projects/<id>/research.md` + `research_report.json`.
   - `rea_video_reference_analyst` (`xdx-rea-reference-analyst`): memilih/menggabungkan profil `REF-001` / `REF-002` dari `KnowledgeMemory` dan `ReferenceDatabaseBridge` ke `projects/<id>/reference_analysis.md`.
2. **Tahap Sekuensial 2 (`CREATIVE_DEVELOPMENT`)**:
   - `creative_director` & `scriptwriter_agent` (`xdx-creative-scriptwriter`): menyusun `blueprint.md`, naskah Bahasa Indonesia siap baca (`script.md`), dialog karakter (`narration_dialogue.json`), serta strategi humor situasional lintas genre tanpa label placeholder.
   - `character_design_agent` & `art_director` (`xdx-character-art-director`): menyusun `character_bible.json` (kontinuitas identitas lintas shot) dan `style_bible.json`.
3. **Tahap Paralel 3 (`STORYBOARDING`)**:
   - `storyboard_director`, `motion_director`, & `cinematographer` (`xdx-storyboard-cinematographer`): mengompilasi `storyboard.json` berbasis frame integer eksak (`<= 10s` per shot, target `2–6s`), rig kamera 36mm, dan kontak IK.
   - `audio_director` & `caption_specialist` (`xdx-audio-caption-specialist`): menyusun pacing narasi 130–160 WPM awal, target `-14` s.d. `-16 LUFS`, dan `caption_audio_plan.json`.
   - `asset_specialist` (`xdx-hybrid-production-engineer` dalam mode perencanaan pra-persetujuan): menyusun `asset_manifest.json` 12 kategori semantik tanpa kotak `PLACEHOLDER`.
4. **Tahap Gate Independen 4 (`PREPRODUCTION_QC` → `WAITING_APPROVAL`)**:
   - `preproduction_verifier` (`xdx-preproduction-verifier`) berjalan dalam *fresh context* baca-saja penuh, menerbitkan laporan yang divalidasi terhadap `schemas/review_report.schema.json`.
   - Bila terdapat defect, `RevisionManager` mengarsipkan revisi ke `.revisions/` dan memicu validasi ulang hilir sebelum menyegel paket `WAITING_APPROVAL`.

---

## 3. Batasan Ketat Phase 01.6C

- **Tetap Dilarang** mengeksekusi mutasi scene Blender, render Three.js, atau render Remotion sebelum masuk ke Phase 02 dengan persetujuan manusia terverifikasi (`ExecutionAuthorizationContext`).
- **Tetap Dilarang** memodifikasi repository `fiankuns/xdx-blender-studio` atau menghapus objek MP4 Git LFS dan `prior_analysis.*` di `reference_database/`.
