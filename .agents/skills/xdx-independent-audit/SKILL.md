---
name: xdx-independent-audit
description: Performs fresh-context read-only verification of pre-production packages, task handoffs, SHA-256 digests, Reference Database integrity, and regression suites without silently modifying producer artifacts. Use when running Preproduction Verifier, Technical Auditor, Visual Critic, or Success Auditor checks.
---
# XDX Independent Audit & Verification Skill (v4.0)

1. Jalankan seluruh pemeriksaan dalam mode **baca-saja** pada konteks independen tanpa mengubah file milik *Producer*.
2. Periksa keutuhan skema, referensi Git LFS, kontrak handoff, dan regression suite:
   ```bash
   python3 scripts/xdx_studio.py validate-all
   python3 reference_database/scripts/reference_db.py verify
   pytest -v
   ```
3. Untuk paket pra-produksi pada `projects/<ID>`, verifikasi ke-13 komponen wajib, koherensi klausa-ke-visual, kecocokan SHA-256 melalui `python3 scripts/approval_gate.py projects/<ID> --strict-schema`, serta ketiadaan aset `PLACEHOLDER`.
4. Kembalikan laporan audit terstruktur berisi daftar `defects` (bila ada) kepada `master_director`; jangan memberikan status `COMPLETED` produksi tanpa bukti render dan QC visual aktual.
