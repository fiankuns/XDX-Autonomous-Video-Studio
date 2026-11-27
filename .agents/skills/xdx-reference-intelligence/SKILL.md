---
name: xdx-reference-intelligence
description: Verifies Git LFS reference videos (REF-001, REF-002), runs REA-Video forensic analysis, resolves automatic genre or multi-reference profiles, and extracts structured production DNA without copying source content. Use when analyzing reference videos or selecting production profiles.
---
# XDX Reference Intelligence Skill (v4.0)

1. Gunakan modul yang sudah terverifikasi tanpa meminta pengguna mengunggah ulang video yang tersedia di `reference_database/`:
   - `reference_database/scripts/reference_db.py`
   - `intelligence/reference_database_bridge.py`
   - `intelligence/rea_reference_intelligence.py`
   - Skill runtime `rea-video` untuk inspeksi frame visual & taksonomi shot.
2. Perintah standar baca-saja:
   ```bash
   python3 reference_database/scripts/reference_db.py verify
   python3 scripts/xdx_studio.py references --genres explainair
   python3 scripts/xdx_studio.py references --genres satir_sosial storytelling
   python3 scripts/xdx_studio.py references --ref-ids REF-001 REF-002
   ```
3. Pertahankan `prior_analysis.md` dan `prior_analysis.json` secara *append-only*. Pisahkan secara tegas antara `measurement`, kandidat heuristik, observasi visual frame aktual, inferensi metode produksi, dan hal yang belum diketahui (`unknown`).
4. Jangan pernah menyalin karakter, naskah, nama kampanye, merek/UI perekam layar ponsel, atau musik dari video referensi.
