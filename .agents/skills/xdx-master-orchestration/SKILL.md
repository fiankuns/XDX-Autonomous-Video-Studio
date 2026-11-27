---
name: xdx-master-orchestration
description: Orchestrates XDX Autonomous Multi-Agent Video Studio v4.0 workflows across Master Director, 20 specialist contracts, structured 18-field task handoffs, capability discovery, and fail-closed approval gates. Use when planning, routing, delegating, or auditing multi-agent tasks.
---
# XDX Master Orchestration Skill (v4.0)

1. Baca piagam kerja di `TEAM.md`, aturan peran di `AGENTS.md`, serta kontrak penuh di `orchestration/agent_registry.py` dan `orchestration/master_director_config.json`.
2. Jalankan pemeriksaan kemampuan runtime dan status keseluruhan sebelum mendelegasikan tugas:
   ```bash
   python3 scripts/xdx_studio.py preflight
   python3 scripts/xdx_studio.py capabilities
   python3 scripts/xdx_studio.py validate-all
   ```
3. Aktifkan maksimal **3–6 specialist** sesuai kebutuhan mode perintah pengguna (`CARI TOPIK`, `BUAT VIDEO`, `BUAT OTOMATIS`, `ANALISIS REFERENSI`, `GUNAKAN REF`, `GABUNGKAN REFERENSI`, `REVISI`, `SETUJUI PAKET`, `LANJUTKAN PROJECT`, `AUDIT PROJECT`).
4. Validasi setiap delegasi tugas melalui `orchestration/handoff_manager.py` terhadap `schemas/task_handoff.schema.json` (18 field wajib, DAG bebas siklus, checksum SHA-256 input, dan *single-writer artifact ownership*).
5. Wajib pasangkan output *Producer* dengan agen peninjau independen (`xdx-preproduction-verifier` / `xdx-visual-technical-success-auditor`) pada konteks bersih, lalu berhenti pada `WAITING_APPROVAL` sebelum tindakan produksi apa pun.
