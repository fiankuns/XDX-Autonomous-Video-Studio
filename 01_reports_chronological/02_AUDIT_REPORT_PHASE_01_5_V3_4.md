# LAPORAN AUDIT TOTAL PHASE 01.5 — XDX AUTONOMOUS VIDEO STUDIO v3.4

- **Waktu Pembuatan (UTC)**: `2026-11-27T02:54:50Z`
- **Repository Utama**: `https://github.com/fiankuns/XDX-Autonomous-Video-Studio`
- **Baseline Commit (Phase 01)**: `ca85e5b51b900c6256009155538debf56ac08a71`
- **Commit SHA Terbaru (Phase 01.5 / v3.4)**: `f7bfe6e010eb3a1e1b344a9514513b7dfda16ec2`
- **Jumlah File Terlacak**: `91` file (`0` token/rahasia, `0` `node_modules`, `0` cache biner besar)
- **Status `fiankuns/xdx-blender-studio`**: `UNTOUCHED (0 perubahan)` (`17/17` unittest lulus)
- **Status Regression Suite (`pytest -v`)**: `Exit Code 0` (`36 passed`)

---

## 1. Daftar Kelemahan Audit Independen yang Telah Diperbaiki
- **FIX-01 — Critical Approval Gate Bypass**
  - *Sebelum*: is_explicit_approval_message('Saya tidak setuju paket v1, jangan render', 'v1') returned True via substring match.
  - *Sesudah (v3.4)*: Fail-closed structured grammar (XDX-APPROVE project=... version=... digest=... scopes=...) + lexical negation/conditional/quote/meta rejection + human_user check + TTL + revocation + live disk SHA-256 verification.
- **FIX-02 — MCP Boolean AuthZ & Unclassified Tools**
  - *Sebelum*: XDXBlenderMCPAdapter accepted boolean project_approved and did not fail-close on unknown tools or distinguish 6 connectivity tiers.
  - *Sesudah (v3.4)*: Requires live ExecutionAuthorizationContext, enforces READ_ONLY_ALLOWLIST, raises UnclassifiedMCPToolError on unknown tools, and reports 6 separate verification_tiers.
- **FIX-03 — 150s Storyboard Beat vs Shot Collapse**
  - *Sebelum*: At 150s, generated 6 beats of 18.75s..56.25s mapped 1:1 to shots, violating <=10s rule.
  - *Sesudah (v3.4)*: Full Hierarchical Storyboard (Story Arc -> Sequence -> Scene -> Beat -> Shot <=10s -> Action/Camera/Audio/Caption/VFX Events) tested at 15s, 30s, 60s, 150s (35 shots, max 5.0s), and 180s with explicit transition render handles.
- **FIX-04 — Template Placeholder Narration & Unverified Research**
  - *Sebelum*: Generated '[HOOK_ANOMALY] ...' template strings, fixed 4.6 score, and allowed pending_external_verification.
  - *Sesudah (v3.4)*: AI-authored CreativeProductionPayload schema + CreativePayloadValidator rejecting placeholders/off-topic scripts (PlaceholderScriptError) and unverified factual URLs (UnverifiedResearchError), backed by a genuine 150s Indonesian script with peer-reviewed/institutional citations.
- **FIX-05 — 12-Triangle Box Disguised as Production Lamp**
  - *Sebelum*: prop_custom_lamp_v1 produced a 12-triangle box and passed QC.
  - *Sesudah (v3.4)*: 12 multi-component semantic glTF 2.0 generators (lamp, table, chair, bed, door, window, wardrobe, book, clock, tree, modular_building, simple_vehicle) with unit normals & UVs; 12-tri boxes marked PLACEHOLDER and hard-blocked by AssetQualityControl.
- **FIX-06 — Asset Management & Real Buffer/Style Conversion**
  - *Sebelum*: Metadata-only style harmonizer, single cache tier, minimal URL/zip checks.
  - *Sesudah (v3.4)*: Real GLB<->glTF binary codec, glTF PBR/HSV buffer harmonizer, vertex scaling, +Y<->+Z axis rotation, normal renormalization, PNG remapping, Cloud vs Android caches, SSRF/HTML-on-200/Zip-Slip/Bomb guards, atomic writes, and AttributionLedger.
- **FIX-07 — Preset Status Overclaiming & Minimal Blender Compiler**
  - *Sebelum*: 48 presets marked generic 'tested'; Blender compiler only emitted basic timeline/camera.
  - *Sesudah (v3.4)*: 7-tier honest preset statuses (26 RUNTIME_TESTED, 19 UNIT_TESTED, 8 SPECIFICATION_ONLY, 0 false RENDER_TESTED), 10 PresetExecutorEngine domains, and full AST-verified BlenderXDXEngine Shot Compiler.

---

## 2. Ringkasan Perubahan Kode dari Baseline Phase 01 (`git diff --stat`)
```text
AGENTS.md                                          |   35 +-
 MASTER_PROMPT.md                                   |  128 +--
 README.md                                          |   84 +-
 SKILL.md                                           |   37 +-
 adapters/__init__.py                               |   16 +-
 adapters/xdx_mcp_adapter.py                        |  207 +++-
 docs/PHASE_02A_DESIGN.md                           |   48 +
 docs/PHASE_02_ROADMAP.md                           |   30 +-
 engines/__init__.py                                |    4 +-
 engines/blender_xdx_engine.py                      |  318 +++++-
 engines/preset_executors.py                        |  367 ++++++
 intelligence/__init__.py                           |   56 +-
 intelligence/asset_management.py                   |  823 +++++++++-----
 intelligence/asset_style_converter.py              |  369 ++++++
 intelligence/authored_showcase_150s.py             |  812 ++++++++++++++
 intelligence/creative_pipeline.py                  | 1182 +++++++++++++-------
 intelligence/procedural_geometry.py                |  905 +++++++++++++++
 intelligence/state_and_approval.py                 |  670 +++++++++--
 libraries/asset_3d_library.json                    |   13 +-
 libraries/audio_sfx_library.json                   |   15 +-
 libraries/camera_library.json                      |   18 +-
 libraries/caption_library.json                     |   17 +-
 libraries/character_animation_library.json         |   24 +-
 libraries/environment_library.json                 |   22 +-
 libraries/facial_expression_library.json           |   24 +-
 libraries/lighting_library.json                    |   15 +-
 libraries/lip_sync_library.json                    |   13 +-
 libraries/loader.py                                |   17 +-
 libraries/material_library.json                    |   13 +-
 libraries/motion_library.json                      |   24 +-
 libraries/particle_library.json                    |   17 +-
 libraries/transition_library.json                  |   17 +-
 libraries/typography_library.json                  |   17 +-
 libraries/vfx_library.json                         |   17 +-
 libraries/visual_explainer_library.json            |   19 +-
 package-lock.json                                  |   26 +-
 package.json                                       |   26 +-
 pyproject.toml                                     |    4 +-
 registry/asset_registry.json                       |  174 ++-
 registry/dependency_registry.json                  |   10 +-
 registry/engine_registry.json                      |   11 +-
 registry/license_registry.json                     |    2 +-
 registry/repository_registry.json                  |    2 +-
 schemas/approval_package.schema.json               |  110 +-
 schemas/asset_registry.schema.json                 |   26 +-
 schemas/blender_shot_manifest.schema.json          |  148 +++
 schemas/creative_intelligence.schema.json          |  207 ++++
 schemas/dependency_registry.schema.json            |   46 +-
 schemas/engine_plan.schema.json                    |  174 ++-
 schemas/preset_library.schema.json                 |   15 +-
 schemas/project_state.schema.json                  |   11 +-
 schemas/qc_report.schema.json                      |  214 +++-
 schemas/semantic_asset_spec.schema.json            |  134 +++
 schemas/storyboard.schema.json                     |  236 +++-
 scripts/approval_gate.py                           |   42 +-
 scripts/xdx_studio.py                              |   31 +-
 tests/test_approval_state_rea_and_qc.py            |   13 +-
 tests/test_asset_management.py                     |    7 +-
 tests/test_mcp_discovery_readonly.py               |    9 +-
 .../test_phase01_5_assets_compiler_and_presets.py  |  267 +++++
 tests/test_phase01_5_security_and_state.py         |  176 +++
 tests/test_phase01_5_storyboard_and_creative.py    |  139 +++
 62 files changed, 7223 insertions(+), 1430 deletions(-)
```

## 3. Bukti Eksekusi Regression Test Aktual (`36 passed`)
```text
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0 -- /opt/pyenv/versions/3.12.16/bin/python3
cachedir: .pytest_cache
rootdir: /home/antigravity/fiankuns/XDX-Autonomous-Video-Studio
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 36 items

tests/test_approval_state_rea_and_qc.py::test_13_item_approval_gate_and_state_machine_across_hybrid_genres PASSED [  2%]
tests/test_approval_state_rea_and_qc.py::test_rea_video_reference_analysis_and_visual_qc_on_synthetic_mp4 PASSED [  5%]
tests/test_asset_management.py::test_license_validator_accepts_permissive_and_blocks_unlicensed_or_copyleft PASSED [  8%]
tests/test_asset_management.py::test_cache_manager_sha256_integrity_and_lru_quota PASSED [ 11%]
tests/test_asset_management.py::test_9_step_asset_procurement_procedural_and_external_and_retargeting PASSED [ 13%]
tests/test_mcp_discovery_readonly.py::CrossProjectMCPDiscoveryTests::test_inprocess_readonly_discovery_and_mutation_guard PASSED [ 16%]
tests/test_mcp_discovery_readonly.py::CrossProjectMCPDiscoveryTests::test_live_streamable_http_cross_project_discovery_without_touching_repo PASSED [ 19%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[lamp] PASSED [ 22%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[table] PASSED [ 25%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[chair] PASSED [ 27%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[bed] PASSED [ 30%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[door] PASSED [ 33%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[window] PASSED [ 36%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[wardrobe] PASSED [ 38%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[book] PASSED [ 41%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[clock] PASSED [ 44%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[tree] PASSED [ 47%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[modular_building] PASSED [ 50%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_12_semantic_procedural_asset_categories_and_real_geometry[simple_vehicle] PASSED [ 52%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_primitive_placeholder_blocked_in_production_and_attribution_preserved PASSED [ 55%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_cache_hardening_safe_paths_ssrf_html_spoof_and_zip_slip PASSED [ 58%]
tests/test_phase01_5_assets_compiler_and_presets.py::test_blender_shot_compiler_preset_executors_and_cross_engine_compatibility PASSED [ 61%]
tests/test_phase01_5_security_and_state.py::test_critical_audit_regression_negative_conditional_quoted_and_ambiguous_approvals PASSED [ 63%]
tests/test_phase01_5_security_and_state.py::test_invalid_state_transitions_ai_self_approval_expiry_and_revocation PASSED [ 66%]
tests/test_phase01_5_security_and_state.py::test_mcp_tool_allowlist_unknown_tool_rejection_and_live_tamper_blocking PASSED [ 69%]
tests/test_phase01_5_storyboard_and_creative.py::test_hierarchical_storyboard_across_durations_and_genres[15-genres0] PASSED [ 72%]
tests/test_phase01_5_storyboard_and_creative.py::test_hierarchical_storyboard_across_durations_and_genres[30-genres1] PASSED [ 75%]
tests/test_phase01_5_storyboard_and_creative.py::test_hierarchical_storyboard_across_durations_and_genres[60-genres2] PASSED [ 77%]
tests/test_phase01_5_storyboard_and_creative.py::test_hierarchical_storyboard_across_durations_and_genres[150-genres3] PASSED [ 80%]
tests/test_phase01_5_storyboard_and_creative.py::test_hierarchical_storyboard_across_durations_and_genres[180-genres4] PASSED [ 83%]
tests/test_phase01_5_storyboard_and_creative.py::test_placeholder_narration_and_offtopic_script_rejected PASSED [ 86%]
tests/test_phase01_5_storyboard_and_creative.py::test_unverified_factual_research_rejected PASSED [ 88%]
tests/test_structure_schemas_and_runtimes.py::test_modular_repository_structure_and_gitignore PASSED [ 91%]
tests/test_structure_schemas_and_runtimes.py::test_all_schemas_and_five_registries_valid PASSED [ 94%]
tests/test_structure_schemas_and_runtimes.py::test_all_16_production_preset_libraries PASSED [ 97%]
tests/test_structure_schemas_and_runtimes.py::test_lockfiles_and_actual_runtime_availability PASSED [100%]

============================= 36 passed in 14.88s ==============================
```

## 4. Status Preflight, 6-Tier MCP Honesty & Validasi 11 Schema / 16 Library
```json
{
  "studio_version": "3.4.0",
  "runtimes": {
    "python": "3.12.16",
    "node": "/opt/nvm/current/bin/node",
    "chromium": "/usr/bin/google-chrome",
    "ffmpeg": {
      "available": true,
      "ffmpeg": "/usr/bin/ffmpeg",
      "ffprobe": "/usr/bin/ffprobe",
      "banner": "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers"
    },
    "threejs_ready": true,
    "remotion_ready": true,
    "local_blender_binary": null
  },
  "xdx_mcp": {
    "discovery_source": "in_process_protocol_only_not_live_device",
    "server_reachable_live": false,
    "relay_device_connected": false,
    "verification_tiers": {
      "source_code_discovery": true,
      "in_process_protocol_test": true,
      "local_http_integration_test": false,
      "live_remote_relay_reachable": false,
      "live_android_blender_connected": false,
      "actual_visual_feedback_verified": false
    },
    "discovered_tools": [
      "get_mobile_device_profile",
      "get_scene_info",
      "look",
      "execute_blender_code",
      "create_primitive",
      "modify_object",
      "set_material",
      "configure_mobile_guard"
    ],
    "discovered_resources": [
      "ui://mcp-for-blender/viewport-v2",
      "xdx://device/profile",
      "xdx://scene/summary"
    ],
    "scene_mutated": false
  }
}
```
```json
{
  "status": "VALIDATED",
  "studio_version": "3.4.0",
  "schemas_checked": 11,
  "registries_checked": 5,
  "preset_libraries": {
    "library_count": 16,
    "total_presets": 53,
    "by_test_status": {
      "RUNTIME_TESTED": 26,
      "SPECIFICATION_ONLY": 8,
      "UNIT_TESTED": 19
    }
  }
}
```

## 5. Keterbatasan yang Masih Tersisa (Honest Disclosure)
- No live remote XDX Relay URL/token is injected in this cloud VM yet (`live_remote_relay_reachable: false`, `live_android_blender_connected: false`).
- Blender scene compilation & AST validation are tested offline; live scene execution on Vivo X200 Pro awaits Phase 02B pairing & user approval.
- Skeletal animation curve transfer & live Blender IK constraint evaluation are honestly marked SPECIFICATION_ONLY until executed inside Blender bpy.
- Full Chromium WebGL PNG sequence export & Remotion MP4 rendering are designed in docs/PHASE_02A_DESIGN.md for Phase 02A execution.
- External TTS, whisper.cpp/faster-whisper ASR models, and Rhubarb CLI binaries are deferred to Phase 02B.

---

# Desain Arsitektur Phase 02A — Headless Three.js WebGL & Remotion Master Render (v3.4)

Dokumen ini merinci hasil audit kompatibilitas `package-lock.json` aktual serta cetak biru teknis **Phase 02A** untuk eksekusi render WebGL & Remotion secara deterministik di Cloud Runtime.

---

## 1. Hasil Audit Lockfile & Kompatibilitas Peer Dependency Aktual

| Paket | Versi Terkunci (`package-lock.json`) | Lisensi | Kompatibilitas Phase 02A |
|---|---|---|---|
| `three` | `0.187.0` | `MIT` | Inti scene 3D, `SRGBColorSpace`, `ACESFilmicToneMapping` |
| `remotion` | `4.0.547` | `Remotion License` | Wajib dikunci persis `4.0.547` tanpa `^` agar selaras antar sub-paket `@remotion/*` |
| `@remotion/captions` | `4.0.547` | `MIT` | Paginasi subtitle kata-demi-kata deterministik |
| `@remotion/transitions` | `4.0.547` | `Remotion License` | Transisi frame-overlap deterministik |
| `react` / `react-dom` | `19.3.1` | `MIT` | Kompatibel penuh dengan `@remotion/renderer@4.0.547` (`react >=16.8.0`) |
| `@react-three/fiber` *(Target 02A)* | `9.8.2` | `MIT` | Terverifikasi npm mendukung `react >=19 <19.4` dan `three >=0.156` (cocok dengan `19.3.1` & `0.187.0`) |
| `@remotion/three` *(Target 02A)* | `4.0.547` | `Remotion License` | Menyediakan `<ThreeCanvas>` sinkron `useCurrentFrame()` (`@react-three/fiber >=8.0.0`, `remotion == 4.0.547`) |
| `@remotion/bundler` & `@remotion/renderer` *(Target 02A)* | `4.0.547` | `Remotion License` | Webpack bundling & kontrol Chromium headless per frame |
| `heygen-com/hyperframes` | *Tidak dipasang di core* | `Apache-2.0` | **Tidak menggantikan Remotion**. Hanya dijadikan referensi pola sinkronisasi `<video>`/`canvas` HTML apabila dibutuhkan |

---

## 2. Arsitektur Headless Chromium WebGL & Deterministic PNG Sequence

1. **Runtime Eksekusi**: Playwright (`1.65.2`) + `/usr/bin/google-chrome` dengan flag deterministik:
   - `--use-gl=angle --use-angle=swiftshader` (atau GPU hardware pada instance ber-GPU) agar hasil piksel WebGL konsisten lintas mesin.
   - `--enable-webgl --ignore-gpu-blocklist --force-color-profile=srgb`.
2. **Load Barrier Ketat (`AssetLoadBarrier`)**:
   - Sebelum frame `0` dirender, halaman wajib menyelesaikan `Promise.all([document.fonts.ready, gltfLoaderBarrier, textureDecodeBarrier])`.
   - Jika memakai Remotion, bungkus dengan `delayRender("three-assets")` dan hanya panggil `continueRender(handle)` setelah seluruh mesh `.glb`/tekstur siap di memori GPU.
3. **Evaluasi Frame Murni (`window.__renderFrame(frameIndex, fps)`)**:
   - `requestAnimationFrame` otomatis dinonaktifkan; halaman mengekspos fungsi sinkron/awaitable `renderExactFrame(f)` yang mengevaluasi kamera, transformasi `animejs.seek((f / fps) * 1000)`, dan partikel PRNG `Mulberry32(seed)` pada waktu eksak `t = f / fps`, memanggil `renderer.render(scene, camera)`, lalu mengekspor PNG `1080x1920` RGBA/RGB terindeks `S00X_0000.png .. S00X_NNNN.png`.

---

## 3. Arsitektur Remotion Master Composition, Audio Mixing & MP4 Encoding

1. **Root Composition (`RemotionRoot.tsx`)**:
   - Satu `<Composition id="XDXMaster" fps={30} width={1080} height={1920} durationInFrames={totalFrames} />`.
   - Menggunakan `<TransitionSeries>` dari `@remotion/transitions` untuk mengelola `overlap_frames_in` / `overlap_frames_out` persis sesuai `transition_spec` pada `storyboard.json` sehingga durasi akhir tetap eksak `total_frames`.
2. **Dua Jalur Integrasi Three.js**:
   - **Jalur A (Pre-Rendered PNG Sequence — Utama & Paling Stabil)**: Shot `threejs` dan `blender` diimpor sebagai sequence PNG terverifikasi ke dalam `<Img src={staticFile(...)} />` berdasarkan `useCurrentFrame()`.
   - **Jalur B (`<ThreeCanvas>` Inline — Opsional Teruji)**: Untuk overlay 3D ringan langsung di dalam Remotion menggunakan `@remotion/three@4.0.547` + `@react-three/fiber@9.8.2`.
3. **Caption & Audio Layer**:
   - Layer `<CaptionSafeOverlay>` merender `caption_events` pada zona aman bawah `9:16` (`safe_bottom_pct: 0.18`), maksimal 2 baris, menggunakan font `Plus Jakarta Sans` OFL-1.1.
   - Kurva sidechain ducking dari `PresetExecutorEngine.evaluate_audio_ducking_envelope` diterapkan sebagai fungsi `volume={(f) => dbToLinear(duckCurve[f])}` pada komponen `<Audio>` musik latar, sementara track VO dan dialog dijaga pada `-15 LUFS` / true peak `<= -1.0 dBTP`.
4. **Bundling, Rendering & Validasi Akhir**:
   - `@remotion/bundler` (`bundle()`) → `@remotion/renderer` (`renderMedia({ codec: "h264", pixelFormat: "yuv420p", audioCodec: "aac" })`) → diverifikasi wajib oleh `FFmpegEngine.verify_full_decode()` dan `VisualQualityControlEngine`.


---

## 6. Checksum SHA-256 Seluruh File Repository v3.4
```text
56021185676c67dc10274c8d4f5e14c5add47f1768af6f726251e401b06789c3  .env.example  (258 B)
95f178226cc08b402cf6619451ad7ec6eadcd5b77ff7115cc9677532cf1f83c4  .gitignore  (752 B)
2145ceef919f2e339b6fdf2573131350849dc89438542f65e1b17ed0616a559d  AGENTS.md  (4036 B)
7ec282a96e66b0677985ac9039da84804c56dad2f35f4a75c41c4c84277293d8  MASTER_PROMPT.md  (8477 B)
d8e026f199404569c24c3daafefcf17fe57732066e83af7ca335f1baa052b50c  README.md  (3958 B)
0de43a889131e7740c2ecaea3289ea2f1895cf48eaba6c227ef9091a6b6de26e  SKILL.md  (2373 B)
b8dab2abe997767200e6303f90a11bffa1ca886049412f916cc004b4b29c70e4  adapters/__init__.py  (807 B)
c292dbfc47eb28f719b938db065b118d25864c2ff292e3141f9d0322445f169b  adapters/ambientcg_adapter.py  (1889 B)
1adb06dc1532e1db8e0aeaf86a44f581ee0c7d3b74c2d21d0acebd9818475ddc  adapters/caption_lipsync_adapter.py  (5275 B)
f7bee79226972f57fe8e27af32888af82f1befccf420438475abdfdd29cff2ef  adapters/polyhaven_adapter.py  (3097 B)
954734db02beb7d5b302720e576a54d130761b8a86e6cad8d869bfe02bae044e  adapters/xdx_mcp_adapter.py  (16323 B)
1b65aa11475fbe342d1dc06c5323d5fcadecae29e95a0d34209135b1573128bc  docs/ARCHITECTURE_V3_3.md  (1969 B)
71f1d060520c4f9ef7f041a9f268b546462a54ed1c2d8493bd4874d7c9c7b310  docs/EXTERNAL_REPO_AUDIT.md  (12424 B)
1dab0607ddc2c0fb395c66b985dbbbbec7b65cc6ea5b925a5699fd20552f7d18  docs/MCP_INTEGRATION.md  (3266 B)
f5b079a6761756a27b4f6088649ddaf4f9d3f1880e0b990347f15d6dc7b2cc09  docs/PHASE_02A_DESIGN.md  (4571 B)
9828b6da1628668681135f83fe19fde15f34482eb0ad2dca0d19c781597eaf69  docs/PHASE_02_ROADMAP.md  (1966 B)
e669298da38df33e3899d032ae0235b880f204855006128b02714c701f516712  docs/v3_1_foundation/HYBRID_EXECUTION.md  (1063 B)
f2fa68198e2c0d3512b1a6dfeba942a1906511a48d5348583cfe74288ad35f46  docs/v3_1_foundation/MCP_EXECUTION.md  (989 B)
b63d1c84a7fdf3d4117453a584e5778a4dd0027a1bd816bf4d0313f7cfbf100c  docs/v3_1_foundation/rea_video_upstream.md  (1501 B)
e28961780b7544c36f0d9782093c5bd88c049df4edf032a9420498110d2d9f11  docs/v3_1_foundation/reference_analysis.md  (3573 B)
326087871ec68dd4087089b1f2125f20d57881a9dd00e6fb895319536b284857  engines/__init__.py  (404 B)
b1285b96e02aeb431dba9f7b228acde252b77e5000463da260fd15a5a7a24a95  engines/blender_xdx_engine.py  (13454 B)
e662168270ae0108cd909fdbfc8e9f617ef70cb870edecfb69f97af66926e30f  engines/ffmpeg_engine.py  (3748 B)
4811c08d3d115518a605ca386e6dd29556e8b1e690eadd84d2c602a87a6ad4a1  engines/preset_executors.py  (14702 B)
db14afe7bba972ebc8652354e8092145b9a2036665134992a6ca58cb52e47e38  engines/web/remotion_timeline_spec.mjs  (2032 B)
5d513fecb05157528a72fc58a77b8e0e1212ae8125e91dd95258f1a388c602b2  engines/web/three_deterministic_scene.mjs  (3187 B)
53ad3a72afa96f80b3c80f5e0f20a1d3f39497c3ccabdb120f5815491f6a11e6  engines/web_engines.py  (3184 B)
5b9ed8a927edc77cd7454ac272fffd0243913a7a3e68186224adf0562dd6dfec  intelligence/__init__.py  (3966 B)
b39d2b84142a5461ce6f71d2228ef77895689812f34bd21fe36232b18684114f  intelligence/asset_management.py  (44136 B)
91647084ad9474edf2e579096ceb2465c58f5e98487f10e16c77071de9af555e  intelligence/asset_style_converter.py  (16580 B)
0f771a462b00b7fdef3e96d4fbfd709c50afe8f3f72014da5538582479b7108b  intelligence/authored_showcase_150s.py  (46667 B)
a61a2e7f5179f21ca891896d50b856a3769a95ec4fa9927edc06d74646e4b575  intelligence/creative_pipeline.py  (57043 B)
08a7c7e8a6bad9e727bbfbbaa79c628050bb3c3dc48ef48682863b9e9eede496  intelligence/procedural_geometry.py  (47678 B)
030d1c5e57205ddac084f5a1f8508d5b3a15c2f72f85a22156983fd8afd20991  intelligence/rea_reference_intelligence.py  (12981 B)
444ba993c63f89ae949ae01bb4b859e5380aec5fbb3360f56cc2f672db3fb99a  intelligence/state_and_approval.py  (33498 B)
25ca0d5f580f270e1b7a7e9988efc96b4edeae8b4d9fd8ee1dd450cb44711fca  intelligence/visual_qc_engine.py  (8798 B)
17cac08294398f2ced3dc393034d41b79d875397abb1c9830bb98eb49003d179  libraries/__init__.py  (179 B)
2c8db871074f807d17e9e4e3a8b6d545ec0daed8e57162a0adb201012e9d6209  libraries/asset_3d_library.json  (2175 B)
2d65373ef5743d9ffe6ee562bcf5b0713c6d8361caab58496c604a755d19dd43  libraries/audio_sfx_library.json  (2173 B)
dda1a9f8b22497bc3e8b9a6f640b5c5dce99bf84ac4c256b6a426a0b2aec5edd  libraries/camera_library.json  (2924 B)
e971888df08032506d0615aa6ee7655a513e1aeb6dceb1b14dece8818dd77899  libraries/caption_library.json  (2627 B)
06d3cd7b750727323839ca0c6e1ba0077fee522a36f76b9e16e4729c2737ca32  libraries/character_animation_library.json  (2987 B)
095040e8cf03d02b38fba3a7d98165eca24f5bff43c8e43294f92c4d9d18fd62  libraries/environment_library.json  (3404 B)
313669b38e6e71cf48f10d4a0ddfe15516d9a976f968cc3049baf505346d60c5  libraries/facial_expression_library.json  (2767 B)
7bc9cc703f3aa51e0a0d2a504fb8859444ccbcd6e299d7a328173f48c2f650c8  libraries/lighting_library.json  (2136 B)
4cc989d85f23fb4a7bdf555951252df11b325526801feba5a41c11ecdcff0226  libraries/lip_sync_library.json  (2264 B)
4c0ad10afe097013c213ed23b0978b7fbef7c9518ac8722c903bdc7cb3f669db  libraries/loader.py  (4293 B)
7e14abc330341a6e0c612e0467f11fcca9bdc241a15e7d66b9404efa34e224c6  libraries/material_library.json  (1953 B)
94b5f0e2dde76a43edbc4ab0e75820d5612c1616bdfccef1af9d1ee6e676410d  libraries/motion_library.json  (3098 B)
adb4bbd11bcc709c266b7a0c1dded6144d110b8766b058069d124e6e391179b5  libraries/particle_library.json  (2367 B)
4c450290745d24cff4887f9f5a0eeaea67298468132f957a238895f2d6aed710  libraries/transition_library.json  (2111 B)
996c68b0ebe0ab4ca1a55fa3171902f312d9ad37f5bb67200089c7d0293891bc  libraries/typography_library.json  (2320 B)
0b35acf6e7ac703e3a8a2dceb21b3df9d486f13896ae548f61bf9403e8dd2d47  libraries/vfx_library.json  (2315 B)
d39134e7c03d617a0c76f9a65be9d96adbbdfea35ea9b08f129843e4d1ec854e  libraries/visual_explainer_library.json  (2341 B)
89eb42a0ce5f061a26bf948d21b1970576cd1be468ec99b079f0ef5295080398  package-lock.json  (9452 B)
e43688fdd0786a9d3d98a959c5d55efb67bb6e1b6516ffd0339a00016f233d61  package.json  (799 B)
24397bb6f4e8dfce03abadeaaea750030c1c2cd90f392f6b32ed83a3f15151c2  pyproject.toml  (980 B)
67627c9c7803864ff4a7d594f1e93db3847db2aa21ecac55a32f204683e6d5c5  registry/asset_registry.json  (8747 B)
41ebbe24aa3e1ccc2315be94a3bf47f9d71b2bb214278098daed97db6ddb08e4  registry/dependency_registry.json  (7717 B)
af0a981c44b9500bea36be49466ffd43bbefd572cd876861b776cb525655f21c  registry/engine_registry.json  (4332 B)
67aa5be8066214f1665ba32b7400159558d167da8d06786fb7203f89bed93ad3  registry/license_registry.json  (5199 B)
19be906538c9a20b5f7eccd76ce9dc2c911ae3a78439269b349b0e0c4bc02e24  registry/repository_registry.json  (24007 B)
f289a5b862ef3355909bce0c5f68c4a3e55a3aa379346d5dc2a4e4e0845eb667  requirements.lock  (378 B)
b5fa99efc6b7faba34deea0ff801f47a6a24de0119892ecdf71e61738b0cefbd  schemas/approval_package.schema.json  (3413 B)
fc9a7b576a33a2b26a1e5c965161b42ae8b00a1d47f3bd7195f6815b4a100876  schemas/asset_registry.schema.json  (3726 B)
1557b1e3deaa97920a466e0c60221e3ebf89409a9ab6679c9edb63994d22a475  schemas/blender_shot_manifest.schema.json  (6012 B)
9735de2b62b8b827ff5a22399185609495ce648601c16abaa5828093670e007e  schemas/creative_intelligence.schema.json  (7973 B)
c47e657c8063894f744428004af05dbf352f36616f69e76ab17d53e2be9f68cd  schemas/dependency_registry.schema.json  (1370 B)
41f31a92c6948fabf835b135b28fd26e1813068fc6d7a95a7047f93f47172be8  schemas/engine_plan.schema.json  (4803 B)
616dbdcaa9168d041c139474b079204dd5881d606dbaa0913d8db6f69a85a46f  schemas/preset_library.schema.json  (2415 B)
d2f48dcd7c662ef22421bbf3b01b8405f4253d291e07e73b6ff76c27cbee55ae  schemas/project_state.schema.json  (3660 B)
eb6c746dff382f61e477b19ac4ca85ab2d32bfa890dacc36bcc9fd0d68dea10b  schemas/qc_report.schema.json  (4728 B)
bff1b72ccc38ef4876e7b0e59e2cb10c312fe149da86e8355b83a39ed9363b0a  schemas/semantic_asset_spec.schema.json  (4627 B)
83a3be98746986fdc6b18389f188efa1e439526d4aa7a81bb9787e16c8d5de01  schemas/storyboard.schema.json  (12403 B)
e1fd501cd6c2d8492d720e3146c9d52daa7250eab371ec6c8ae3373958dc38bf  scripts/adaptive_detect.py  (1097 B)
323a082a3e51f683345e52ca6e3b56a624b2e326895f72415e9039892f394b2b  scripts/approval_gate.py  (1509 B)
718a7528024e1f96ad2edae5067f57360c15a692e992845d476888d91865c489  scripts/mcp_discovery.py  (996 B)
77d451cd5ddc560b6e0652f4a29d2f4ed3868d5ff798f087be1cb2a82a933e97  scripts/rea_analyze.py  (1174 B)
4a996bd480ca53f5878aa722e2c8fbd550a091f231477f7d601967a0d4c92dc6  scripts/xdx_studio.py  (5549 B)
25b6ea746d7d57d22dd9649464e9a13a23e88e9a8352327789cf734baa05027a  tests/fixtures/synthetic.mp4  (74732 B)
f037baba445ed06f9cb2c6b49d086e48fc24ac1b9e0ad61ac52956c77f38e99a  tests/fixtures/v3_1_regression/approval_gate_test.json  (926 B)
74855f668dc904fed189d38470e0af163d70189e84ca99f2c56acc1434cd1979  tests/fixtures/v3_1_regression/hybrid_approval_gate_test.json  (225 B)
3dcb1d8c14e799894c8442cdc345c421cbbcf9ec0940983da996005d945f9f53  tests/fixtures/v3_1_regression/real_candidates.json  (14877 B)
717ac81739ed2177582a75e516206eb4baed8cdc671f43aa2abe5324a968681b  tests/fixtures/v3_1_regression/synthetic_qc.json  (251 B)
23fe32a7f0b004ae2acd5e6c3ee06549ea87c9ea98ce2faab3bcce3b72a91c98  tests/test_approval_state_rea_and_qc.py  (5311 B)
b45ecda4deaadf3dcbab620205751c5a1e8cf5654adb95b307367cd74522b8d1  tests/test_asset_management.py  (5494 B)
bc8f85d3f3a814abebe393b7b9afea939a73c6d7f4ebd25c74228875a7a843b9  tests/test_mcp_discovery_readonly.py  (4391 B)
6208b5fe910f510dd48191c9d04585581cc8145ac82bb833bd80d0b7d8356563  tests/test_phase01_5_assets_compiler_and_presets.py  (12525 B)
f024d72f88d1e078b4d39fe2a1ac0aac8672b1e220b915c669847fd6a5683380  tests/test_phase01_5_security_and_state.py  (8442 B)
d204a15fb7936cb08003c2cfc96a414696861238e925b526b752b9d985430f24  tests/test_phase01_5_storyboard_and_creative.py  (5985 B)
4ba70e755e5a6444c2161cddd338902a245ce7a1d40c4edd08b1bfeaebe11016  tests/test_structure_schemas_and_runtimes.py  (4604 B)
```
