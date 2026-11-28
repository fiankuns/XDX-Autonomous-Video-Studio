# Analisis Referensi Pra-Produksi Terintegrasi (`reference_database` v3.4)

- **Mode Pemilihan Referensi**: `explicit_multi_reference`
- **Genre Terkompilasi**: `explainer, edukasi`
- **Sidik Jari Analyzer REA (`SHA-256`)**: `123d73e7ca6078df4df3e8dbb8c1c53abd9cfe3e2883b1f6dcb8f45bf92d251c`
- **Status Otorisasi Produksi**: `False` *(Referensi tidak pernah menggantikan persetujuan eksplisit pengguna)*
- **Referensi Aktif Terverifikasi (`VERIFIED`)**: `REF-001, REF-002, REF-003` *(File asli tersedia di repositori lokal via Git LFS; sistem tidak meminta unggah ulang)*

## Bukti Sumber & Lapisan Analisis Terpadu
### `REF-001` (`satirical_3d_vignette_storytelling_v1`)
- **SHA-256 Terverifikasi**: `12f9e1d992fc6f71f56c4c1116a91def3f6ca70bf1c55aa2618281ae4a71879d` (`27,026,130` byte)
- **Spesifikasi Sinyal**: `720x1280` · `h264` · `30.00 fps` · `154.5s` · Audio `-14.8 LUFS`
- **Data Riset/Analisis Sebelumnya**: `prior_analysis.md` dipertahankan dan digabungkan sebagai konteks.
- **Pola Narasi & Hook**: `circular_bedroom_loop_second_person_social_satire` — Protagonist wakes up stretching on a purple bed in a cozy striped bedroom (00:00s) and opens the front door (00:03s) as second-person narration ('Kamu...') immediately places the viewer inside everyday public infrastructure.
- **Benchmark Pacing**: Rentang shot tipikal `2.0–4.5 detik` (`<= 10s` batas mutlak).
- **Mode Visual & Cutaway**: `SURROGATE_CITIZEN_ACTING, INSTITUTIONAL_VIGNETTE, DIEGETIC_3D_SCOREBOARD_OR_SCALE, CROWD_RATIO_DIORAMA, STAGE_SPOTLIGHT_METAPHOR, CIRCULAR_CALLBACK`

### `REF-002` (`hosted_3d_explainer_cutaway_v1`)
- **SHA-256 Terverifikasi**: `042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01` (`38,669,358` byte)
- **Spesifikasi Sinyal**: `720x1600` · `hevc` · `35.00 fps` · `105.543s` · Audio `-20.0 LUFS`
- **Data Riset/Analisis Sebelumnya**: `prior_analysis.json` dipertahankan dan digabungkan sebagai konteks.
- **Pola Narasi & Hook**: `need -> question -> physical_demo -> mechanism -> obstacle_loop -> historical_reveal -> callback` — Concrete sensory need in 0-6s: stepping out of a desert adobe house (00:00s), top-down pouring of sweet iced tea (00:02-00:04s), and sitting under blazing sun craving cold ice without electricity (00:06s).
- **Benchmark Pacing**: Rentang shot tipikal `2–4 detik` (`<= 10s` batas mutlak).
- **Mode Visual & Cutaway**: `HOST_ACTING, OBJECT_INSERT, PHYSICAL_DEMONSTRATION, TECHNICAL_CUTAWAY, CONTEXTUAL_CUTAWAY, HISTORICAL_REENACTMENT`

### `REF-003` (`cinematic_geo_documentary_v1`)
- **SHA-256 Terverifikasi**: `6763efe27a2f312acedd15cb4f1663413fff533a99a4fd77de3686838d4bec87` (`10,302,125` byte)
- **Spesifikasi Sinyal**: `1280x720` · `h264` · `30.00 fps` · `64.333s` · Audio `n/a (Phase 04) LUFS`
- **Data Riset/Analisis Sebelumnya**: `prior_analysis.json` dipertahankan dan digabungkan sebagai konteks.
- **Pola Narasi & Hook**: `dated_disaster_hook -> false_cause -> geographic_scope -> doubt -> reveal_true_cause -> time_jump_loss -> protected_remnant -> callback_map_with_human_responsibility` — OBSERVED: year title over an erupting volcano, ash shockwave and tsunami front within 6 s
- **Benchmark Pacing**: Rentang shot tipikal `4–10 detik` (`<= 10s` batas mutlak).
- **Mode Visual & Cutaway**: `HISTORICAL_RECONSTRUCTION, GEOGRAPHIC_MAP, MAP_CAMERA_NAVIGATION, BOUNDARY_HIGHLIGHT, POPULATION_DOTS, RADIAL_WAVE`

## Sintesis Profil Produksi & Batas Hak Cipta
- **Penggabungan Multi-Referensi**: `True` (`satirical_3d_vignette_storytelling_v1, hosted_3d_explainer_cutaway_v1, cinematic_geo_documentary_v1`)
- **Target Pemecahan Shot Storyboard**: `<= 4.5 detik` per shot (seluruh shot `<= 10,0 detik`).
- **Aturan Anti-Plagiarisme**: Hanya mengabstraksi tata bahasa sinematografi, struktur kausal/satir, pacing klausa, dan mekanisme cutaway 3D; **dilarang keras** menyalin karakter, dialog, merek/UI aplikasi perekam layar, musik, atau aset visual sumber.
