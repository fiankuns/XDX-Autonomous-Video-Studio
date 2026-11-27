---
trigger: model_decision
description: "Gunakan aturan ini setiap kali menjalankan Preproduction Verifier (17), Visual Critic (18), Technical Auditor (19), atau Success Auditor (20) untuk review independen."
---
# XDX Studio v4.0 — Independent Verification & No-Silent-Fix Rule

1. Seluruh agen di Independent Verification Department (`preproduction_verifier`, `visual_critic`, `technical_auditor`, `success_auditor`) wajib berjalan pada konteks percakapan bersih (*fresh context*) yang terpisah dari agen pembuat artefak.
2. **Larangan Perbaikan Diam-Diam**: Verifier dilarang memodifikasi, menambal, atau menulis ulang artefak milik *Producer*. Setiap temuan wajib dikembalikan sebagai daftar `defects` terstruktur (`defect_id`, `shot_id`/lokasi/frame, `severity`, `expected_result`, `observed_result`, `evidence`, `responsible_agent`).
3. `success_auditor` dilarang memberikan status `PASS` akhir untuk produksi video hanya berdasarkan kelulusan unit test, validasi JSON Schema, atau *self-test* tanpa bukti decode teknis dan evaluasi frame visual aktual.
