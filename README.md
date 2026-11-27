# XDX Autonomous Video Studio v3.4

Fondasi produksi video otonom hybrid generasi **v3.4 (Phase 01.5 — Hardened & Production Intelligence)** yang menyempurnakan v3.1 dan v3.3. Mengorkestrasi **XDX Blender Studio MCP (Android ARM64 Vivo X200 Pro & Cloud Relay)**, **Three.js (`v0.187.0`)**, **Remotion (`v4.0.547`)**, **REA-Video Intelligence**, dan **FFmpeg (`v6.1+`)** dengan pemisahan tegas antara **penulisan kreatif/riset AI** dan **kompilasi/validasi fail-closed Python**.

---

## Pembaruan Utama v3.4 (Phase 01.5 Hardening)

1. **AI Creative & Verified Research Intelligence (`schemas/creative_intelligence.schema.json`)**:
   - Menolak otomatis naskah berlabel placeholder (`PlaceholderScriptError`) dan klaim faktual tanpa sumber `https://` primer/institusional (`UnverifiedResearchError`).
   - Menyertakan naskah contoh 150 detik berbahasa Indonesia alami yang siap dibacakan lengkap dengan dialog karakter, humor situasional, dan sitasi ilmiah/sejarah terverifikasi.
2. **Hierarchical Frame-Exact Storyboard Engine (`15s`, `30s`, `60s`, `150s`, `180s+`)**:
   - Memisahkan `Story Arc → Sequence → Scene → Narrative Beat → Shot → [Action, Camera, Audio, Caption, VFX Events]`.
   - Menjamin setiap shot berdurasi **maksimal 10,0 detik (`<= 300 frame`)** dengan target 2–6 detik, kontinuitas integer frame eksak tanpa celah, dan pencatatan handle transisi eksplisit.
3. **Fail-Closed Structured Approval Gate & Live MCP AuthZ**:
   - Mengganti pencocokan substring dengan format terstruktur `XDX-APPROVE project=... version=... digest=... scopes=...` yang menolak kalimat negasi (`"tidak setuju"`), syarat (`"jika"`/`"tapi"`), kutipan, self-approval AI, approval kedaluwarsa/dicabut, serta mutasi file pasca-approval.
   - Menghapus parameter boolean lemah pada adapter MCP dan mewajibkan objek `ExecutionAuthorizationContext` live + allowlist tool baca-saja + penolakan tool tak dikenal (`UnclassifiedMCPToolError`).
4. **12-Category Multi-Component Semantic Asset Generator & Real GLB/glTF Converter**:
   - Generator prosedural multi-komponen ber-normal dan ber-UV nyata untuk **Lampu, Meja, Kursi, Kasur, Pintu, Jendela, Lemari, Buku, Jam, Pohon, Bangunan Modular, dan Kendaraan Sederhana**.
   - Kotak primitif 12-segitiga dipisahkan tegas sebagai `PLACEHOLDER` dan diblokir pada QC produksi akhir.
   - Konversi nyata `GLB ↔ glTF 2.0`, normalisasi PBR/palet HSV langsung pada buffer, penskalaan vertex, rotasi sumbu `+Y`↔`+Z`, koreksi normal, serta pemisahan cache Cloud vs Android (`Vivo X200 Pro`).
5. **7-Tier Honest Preset Status, Executable Evaluators & Full Blender Shot Compiler**:
   - 16 pustaka preset (`53` preset) diaudit ke dalam 7 status jujur (`RUNTIME_TESTED`, `UNIT_TESTED`, `SPECIFICATION_ONLY`, dst.) dan didukung `PresetExecutorEngine` (10 domain) serta `BlenderXDXEngine` (scene, koleksi, aset, karakter/armature/IK, keyframe, kamera, lighting, material, render settings, dan skrip `bpy` terverifikasi AST).
6. **Integrated Git LFS Reference Database (`reference_database/` — `REF-001` & `REF-002`)**:
   - Verifikasi SHA-256 otomatis atas video referensi Git LFS (`REF-001` Satir Sosial/Storytelling & `REF-002` Yakhchal Explainer), analisis mendalam 10 dimensi REA-Video v3.4 (dengan mempertahankan `prior_analysis.*`), routing otomatis genre/alias (`explainer`/`explainair` → `REF-002`; `storytelling`/`satir_sosial` → `REF-001`), serta penggabungan multi-referensi (`--ref-ids REF-001 REF-002`) tanpa pernah meminta unggah ulang dan tetap berhenti pada `WAITING_APPROVAL`.
7. **Multi-Agent Foundation & Capability Discovery (`v4.0-alpha.1` — Phase 01.6A)**:
   - Piagam tim [`TEAM.md`](TEAM.md), kontrak `master_director` + **20 Specialist Agents** (`registry/agent_registry_v4.json`, `orchestration/agent_registry.py`), kustomisasi native Antigravity (`.agents/agents/`, `.agents/skills/`, `.agents/rules/`), validator handoff 18 field & DAG kepemilikan tunggal (`orchestration/handoff_manager.py`), matriks izin *default-deny* (`governance/permission_policy.py`), serta pemanggilan subagent native baca-saja (*Producer* + *Independent Verifier*).
8. **Persistent Agent Intelligence, DAG Execution & Checkpoint Recovery (`v4.0-alpha.2` — Phase 01.6B)**:
   - Kepemilikan artefak kanonik (resolusi path, validasi symlink/batas project, pola role, `ArtifactOwnershipLockManager` berbasis `fcntl` + pemulihan stale lock), batas output, dan `verify_independent_review_pass` yang diperketat (`schemas/review_report.schema.json`, hash artefak tidak berubah, receipt `invocation_id`).
   - Capability discovery 7 status berbasis bukti TTL (`schemas/capability_evidence.schema.json`), `orchestration/dependency_scheduler.py` (DAG + timeout + `done_when`), `orchestration/native_execution_adapter.py`, state machine bersama 26 state (`orchestration/shared_state.py`), memori SQLite 6 partisi (`memory/persistent_memory.py`), probe persistensi 5 tingkat (`memory/persistence_probe.py`), serta `orchestration/checkpoint_manager.py` & `orchestration/revision_manager.py`.
   - Perintah baru: `python3 scripts/xdx_studio.py memory-status` dan `python3 scripts/xdx_studio.py persistence-probe`. Bukti workflow live: `docs/evidence/phase01_6b_workflow/`. Rencana berikutnya (belum diimplementasikan): `docs/PHASE_01_6C_IMPLEMENTATION_PLAN.md`.

---

## Perintah Cepat & Pengujian

```bash
# 1. Verifikasi objek Git LFS Reference Database (REF-001 & REF-002 -> VERIFIED)
git lfs pull
python3 reference_database/scripts/reference_db.py verify

# 2. Pemeriksaan runtime, Reference Database, & 6-tingkat verifikasi MCP XDX secara baca-saja
python3 scripts/xdx_studio.py preflight

# 3. Validasi seluruh 11 JSON Schema, 5 Registry, 16 Preset Libraries, & Reference Database
python3 scripts/xdx_studio.py validate-all

# 4. Kompilasi paket pra-produksi (routing otomatis genre/alias atau multi-referensi -> WAITING_APPROVAL)
python3 scripts/xdx_studio.py plan \
  --project-id demo_explainair_ref002 \
  --genres explainair \
  --duration 60 \
  --out /tmp/xdx_pkg_ref002

# 5. Verifikasi fail-closed Approval Gate
python3 scripts/approval_gate.py /tmp/xdx_pkg_ref002 --strict-schema

# 6. Jalankan seluruh suite regression test (Phase 01 + Phase 01.5 + Reference Database)
pytest -v
```

Dokumentasi Teknis:
- [`reference_database/README.md`](reference_database/README.md)
- [`docs/EXTERNAL_REPO_AUDIT.md`](docs/EXTERNAL_REPO_AUDIT.md)
- [`docs/ARCHITECTURE_V3_3.md`](docs/ARCHITECTURE_V3_3.md)
- [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md)
- [`docs/PHASE_02A_DESIGN.md`](docs/PHASE_02A_DESIGN.md)
- [`docs/PHASE_02_ROADMAP.md`](docs/PHASE_02_ROADMAP.md)