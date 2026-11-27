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

---

## Perintah Cepat & Pengujian

```bash
# 1. Pemeriksaan runtime & 6-tingkat verifikasi MCP XDX secara baca-saja
python3 scripts/xdx_studio.py preflight

# 2. Validasi seluruh 11 JSON Schema, 5 Registry, dan 16 Production Preset Libraries
python3 scripts/xdx_studio.py validate-all

# 3. Kompilasi paket pra-produksi 150 detik (otomatis berhenti pada WAITING_APPROVAL)
python3 scripts/xdx_studio.py plan \
  --project-id persepsi_waktu_150s \
  --duration 150 \
  --out /tmp/xdx_pkg_150s

# 4. Verifikasi fail-closed Approval Gate
python3 scripts/approval_gate.py /tmp/xdx_pkg_150s --strict-schema

# 5. Jalankan seluruh suite regression test Phase 01 & Phase 01.5
pytest -v
```

Dokumentasi Teknis:
- [`docs/EXTERNAL_REPO_AUDIT.md`](docs/EXTERNAL_REPO_AUDIT.md)
- [`docs/ARCHITECTURE_V3_3.md`](docs/ARCHITECTURE_V3_3.md)
- [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md)
- [`docs/PHASE_02A_DESIGN.md`](docs/PHASE_02A_DESIGN.md)
- [`docs/PHASE_02_ROADMAP.md`](docs/PHASE_02_ROADMAP.md)