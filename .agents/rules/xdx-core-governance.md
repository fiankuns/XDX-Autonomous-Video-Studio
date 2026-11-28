---
trigger: always_on
description: "Aturan tata kelola inti XDX Studio v4.0: pemisahan tugas multi-agent, gerbang persetujuan 13 item fail-closed, larangan self-approval, dan pelestarian v3.4."
---
# XDX Studio v4.0 — Core Multi-Agent Governance Rule

1. Selalu patuhi rantai orkestrasi pada `TEAM.md` dan `AGENTS.md`: `ORCHESTRATOR → SPECIALIST AGENTS → INDEPENDENT VERIFIER → HUMAN APPROVAL → PRODUCTION → ACTUAL RENDER → VISUAL CRITIC → SUCCESS AUDITOR`.
2. `master_director` dilarang menjadi satu-satunya pemeriksa atas artefak buatannya sendiri dan dilarang mengubah status langsung ke `APPROVED` atau `COMPLETED`.
3. Pertahankan seluruh kemampuan Phase 01, Phase 01.5, dan Reference Database v3.4 secara aditif. Dilarang memodifikasi `fiankuns/xdx-blender-studio`, skema pairing/autentikasi MCP, objek MP4 Git LFS di `reference_database/`, maupun arsip `prior_analysis.*`.
4. Pada runtime remote devbox yang membatasi mode workspace subagent, selalu panggil `invoke_subagent` dengan `Workspace: "inherit"` dan jaga eksklusivitas kepemilikan file melalui `orchestration/handoff_manager.py`.

5. **Kebijakan Persetujuan Sederhana (Instruksi Pemilik):** Sistem tanda tangan Ed25519 (`XDX-SIGNED-APPROVAL` / `fian-termux-1`) telah dihapus. Cukup terima 1 kata konfirmasi manusia di chat (`Setuju`, `Lanjutkan`, `Ok`, `Gas`, `Approve`) untuk membuka status `APPROVED` — jangan lagi meminta kunci Ed25519 atau format digest panjang.
