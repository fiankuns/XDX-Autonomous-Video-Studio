# XDX Internal Reference Database — Verified & Integrated (v3.4)

## Status Verifikasi Aktual (Berdasarkan Pengujian Langsung)

- **Status Database**: `VERIFIED_AND_INTEGRATED_READ_ONLY` (`production_authorized = false`)
- **Pengujian Fresh Git LFS Checkout**: `LULUS` (kloning bersih dari `origin/main` + `git lfs pull` + `python3 reference_database/scripts/reference_db.py verify` mengembalikan `VERIFIED` untuk seluruh referensi).
- **Integrasi Creative Pipeline & Approval Gate**: `LULUS` (`42/42` pengujian `pytest -v` lulus, termasuk 36 regression test Phase 01/01.5 dan 6 pengujian integrasi database referensi; seluruh perencanaan berhenti pada `WAITING_APPROVAL`).
- **Mutasi Blender / Produksi Video**: `TIDAK DIJALANKAN` (0 perubahan pada `fiankuns/xdx-blender-studio`, pairing/token tidak disentuh, dan tidak ada render produksi tanpa persetujuan terstruktur pengguna).

| ID | Genre Bawaan & Alias | Path Objek Git LFS | Ukuran (Byte) | SHA-256 Terverifikasi | Profil Produksi | Analisis Tersimpan (Append-Only) | Status |
|---|---|---|---:|---|---|---|---|
| `REF-001` | `social_satire`, `satir_sosial`, `storytelling` | `references/social_satire/REF-001/original.mp4` | `27.026.130` | `12f9e1d992fc6f71f56c4c1116a91def3f6ca70bf1c55aa2618281ae4a71879d` | `satirical_3d_vignette_storytelling_v1` | [`prior_analysis.md`](references/social_satire/REF-001/prior_analysis.md) + [`rea_analysis_v3_4.json`](references/social_satire/REF-001/rea_analysis_v3_4.json) / [`.md`](references/social_satire/REF-001/rea_analysis_v3_4.md) | `VERIFIED` |
| `REF-002` | `explainer`, `explainair`, `explaner` | `references/explainer/REF-002-Yakhchal/original.mp4` | `38.669.358` | `042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01` | `hosted_3d_explainer_cutaway_v1` | [`prior_analysis.json`](references/explainer/REF-002-Yakhchal/prior_analysis.json) + [`rea_analysis_v3_4.json`](references/explainer/REF-002-Yakhchal/rea_analysis_v3_4.json) / [`.md`](references/explainer/REF-002-Yakhchal/rea_analysis_v3_4.md) | `VERIFIED` |
| `REF-003` | `dokumenter` (alias `documentary`; sejarah, geografi, fenomena alam) | `references/documentary/REF-003-Javan-Rhino-Krakatau/original.mp4` | `10.302.125` | `6763efe27a2f312acedd15cb4f1663413fff533a99a4fd77de3686838d4bec87` | `cinematic_geo_documentary_v1` | [`prior_analysis.json`](references/documentary/REF-003-Javan-Rhino-Krakatau/prior_analysis.json) + [`rea_analysis_v3_4.json`](references/documentary/REF-003-Javan-Rhino-Krakatau/rea_analysis_v3_4.json) / [`.md`](references/documentary/REF-003-Javan-Rhino-Krakatau/rea_analysis_v3_4.md) | `VERIFIED` (media) · teknik `REFERENCE_OBSERVED` |

## Aturan Operasional & Batasan Jujur

1. **Baca Kebijakan Agen**: Selalu patuhi [`integration/AGENT_REFERENCE_RULES.md`](integration/AGENT_REFERENCE_RULES.md), [`../MASTER_PROMPT.md`](../MASTER_PROMPT.md), [`../SKILL.md`](../SKILL.md), dan [`../AGENTS.md`](../AGENTS.md).
2. **Tanpa Unggah Ulang & Fail-Closed**: Ketika objek MP4 asli terverifikasi sesuai ukuran byte dan `SHA-256` di [`reference_registry.json`](reference_registry.json), sistem langsung menggunakannya tanpa meminta unggah ulang. Bila objek belum dihidrasi Git LFS atau tidak ada, sistem wajib gagal tertutup dengan `MEDIA_MISSING` / `INTEGRITY_FAILED` tanpa mengarang hasil analisis.
3. **Routing Otomatis & Multi-Referensi**:
   - `Explainer` / `Explainair` → otomatis memilih `REF-002` (`hosted_3d_explainer_cutaway_v1`).
   - `Storytelling` / `Satir Sosial` → otomatis memilih `REF-001` (`satirical_3d_vignette_storytelling_v1`).
   - `Dokumenter` / `Documentary` (sejarah, geografi, fenomena alam) → otomatis memilih `REF-003` (`cinematic_geo_documentary_v1`).
   - Per shot: `route_references_for_shots` memakai `genre_registry.json → shot_need_routing` (REF-001 storytelling/satir, REF-002 explainer/mekanisme, REF-003 dokumenter/geografi/fenomena alam; fusi dengan REF utama per kebutuhan shot).
   - Teknik REF-003 ada di `profiles/reference_technique_registry.json` (Animation Technique Profile, gaya-independen) dan berstatus `REFERENCE_OBSERVED`; dipromosikan ke `RENDER_TESTED` hanya setelah render XDX aktual + QC independen. Profil gaya visual REF-003 hanya pengamatan, tidak disalin.
   - Pemilihan eksplisit (`--ref-ids REF-001` atau `--ref-ids REF-001 REF-002`) dan kombinasi lintas genre didukung melalui `intelligence/reference_database_bridge.py` dan `scripts/xdx_studio.py`.
4. **Batasan Epistemik & Hak Cipta**:
   - Status hak cipta kedua file tetap tercatat jujur sebagai `USER_SUPPLIED_PRIVATE_REFERENCE_RIGHTS_NOT_VERIFIED` hanya untuk analisis internal repositori privat; dilarang mempublikasikan ulang file sumber atau menyalin karakter, naskah, nama kampanye, UI aplikasi perekam layar (`REF-002`), maupun musik latar.
   - Transkripsi ASR kata-demi-kata penuh, pemisahan stem musik, serta identitas engine/prompt pembuat asli tidak diklaim.
   - Database ini bersifat baca-saja dan **tidak pernah memberikan otorisasi render/produksi** sebelum perintah persetujuan eksplisit terstruktur dari manusia diterima.
