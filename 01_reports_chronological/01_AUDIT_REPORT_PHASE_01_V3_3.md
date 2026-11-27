# LAPORAN AUDIT TOTAL PHASE 01 — XDX AUTONOMOUS VIDEO STUDIO v3.3

- **Waktu Pembuatan Paket Audit (UTC)**: `2026-11-26T15:16:48Z`
- **Repository Utama**: `https://github.com/fiankuns/XDX-Autonomous-Video-Studio`
- **Commit SHA (`main`)**: `ca85e5b51b900c6256009155538debf56ac08a71`
- **Jumlah File Terlacak (Tracked Files)**: `80` file (`0` rahasia/token, `0` `node_modules`, `0` cache besar)
- **Status Repository `fiankuns/xdx-blender-studio`**: `UNTouched / 0 Modifications` (`17/17` unittest lulus)
- **Status Suite Pengujian `pytest -v`**: `Exit Code 0` (`11/11` pengujian lulus)

---

## 1. Isi Paket ZIP Audit Ini
1. `AUDIT_REPORT_TOTAL_PHASE_01.md` — Dokumen laporan audit menyeluruh ini.
2. `AUDIT_REPORT_TOTAL_PHASE_01.json` — Data audit terstruktur lengkap beserta SHA-256 setiap file.
3. `01_evidence_logs/` — Bukti log eksekusi aktual (`pytest`, `unittest` Blender Studio, `preflight`, `validate-all`, `mcp_discovery`, `threejs_selftest`, `remotion_selftest`, `approval_gate`, `repository_files_sha256.txt`).
4. `02_sample_waiting_approval_package/` — Contoh nyata paket pra-produksi 13 item yang berhenti pada status `WAITING_APPROVAL`.
5. `03_repository_snapshot/` — Salinan utuh seluruh 80 file yang di-commit pada `XDX-Autonomous-Video-Studio` v3.3 untuk diaudit secara offline.

---

## 2. Output Aktual Pengujian `pytest -v`
```text
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0 -- /opt/pyenv/versions/3.12.16/bin/python3
cachedir: .pytest_cache
rootdir: /home/antigravity/fiankuns/XDX-Autonomous-Video-Studio
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 11 items

tests/test_approval_state_rea_and_qc.py::test_13_item_approval_gate_and_state_machine_across_hybrid_genres PASSED [  9%]
tests/test_approval_state_rea_and_qc.py::test_rea_video_reference_analysis_and_visual_qc_on_synthetic_mp4 PASSED [ 18%]
tests/test_asset_management.py::test_license_validator_accepts_permissive_and_blocks_unlicensed_or_copyleft PASSED [ 27%]
tests/test_asset_management.py::test_cache_manager_sha256_integrity_and_lru_quota PASSED [ 36%]
tests/test_asset_management.py::test_9_step_asset_procurement_procedural_and_external_and_retargeting PASSED [ 45%]
tests/test_mcp_discovery_readonly.py::CrossProjectMCPDiscoveryTests::test_inprocess_readonly_discovery_and_mutation_guard PASSED [ 54%]
tests/test_mcp_discovery_readonly.py::CrossProjectMCPDiscoveryTests::test_live_streamable_http_cross_project_discovery_without_touching_repo PASSED [ 63%]
tests/test_structure_schemas_and_runtimes.py::test_modular_repository_structure_and_gitignore PASSED [ 72%]
tests/test_structure_schemas_and_runtimes.py::test_all_schemas_and_five_registries_valid PASSED [ 81%]
tests/test_structure_schemas_and_runtimes.py::test_all_16_production_preset_libraries PASSED [ 90%]
tests/test_structure_schemas_and_runtimes.py::test_lockfiles_and_actual_runtime_availability PASSED [100%]

============================== 11 passed in 5.46s ==============================
```

## 3. Output Aktual Pengujian `xdx-blender-studio` (Tanpa Modifikasi)
```text
test_dist_zip_contains_expected_modules (test_addon_package.AddonPackageTests.test_dist_zip_contains_expected_modules) ... ok
test_apply_cycles_guard_caps_threads_and_samples (test_mobile_guard.MobileGuardTests.test_apply_cycles_guard_caps_threads_and_samples) ... ok
test_device_profile_and_configure_guard_command (test_mobile_guard.MobileGuardTests.test_device_profile_and_configure_guard_command) ... ok
test_resolution_clamping_for_rendered_vs_material (test_mobile_guard.MobileGuardTests.test_resolution_clamping_for_rendered_vs_material) ... ok
test_resolve_safe_tempdir_prefers_bpy_tempdir (test_mobile_guard.MobileGuardTests.test_resolve_safe_tempdir_prefers_bpy_tempdir) ... ok
test_auth_enforced_on_mcp_and_relay (test_relay_and_mcp.RelayAndMCPIntegrationTests.test_auth_enforced_on_mcp_and_relay) ... ok
test_outbound_relay_look_and_mcp_app_end_to_end (test_relay_and_mcp.RelayAndMCPIntegrationTests.test_outbound_relay_look_and_mcp_app_end_to_end) ... ok
test_bearer_token_verification (test_security.SecurityTests.test_bearer_token_verification) ... ok
test_fail_closed_config_validation (test_security.SecurityTests.test_fail_closed_config_validation) ... ok
test_generate_strong_token_entropy (test_security.SecurityTests.test_generate_strong_token_entropy) ... ok
test_hmac_rejects_tampered_body_and_expired_timestamp (test_security.SecurityTests.test_hmac_rejects_tampered_body_and_expired_timestamp) ... ok
test_hmac_sign_verify_and_replay_rejection (test_security.SecurityTests.test_hmac_sign_verify_and_replay_rejection) ... ok
test_render_resolution_table (test_settings_and_render.SettingsAndRenderPresetTests.test_render_resolution_table) ... ok
test_save_and_load_settings_roundtrip (test_settings_and_render.SettingsAndRenderPresetTests.test_save_and_load_settings_roundtrip) ... ok
test_sensor_fit_recommendations (test_settings_and_render.SettingsAndRenderPresetTests.test_sensor_fit_recommendations) ... ok
test_refuses_0_0_0_0_bind (test_socket_bridge.SocketBridgeTests.test_refuses_0_0_0_0_bind) ... ok
test_usb_adb_localhost_hmac_roundtrip (test_socket_bridge.SocketBridgeTests.test_usb_adb_localhost_hmac_roundtrip) ... ok

----------------------------------------------------------------------
Ran 17 tests in 0.686s

OK
```

## 4. Output Aktual `preflight` & `validate-all`
```json
{
  "studio_version": "3.3.0",
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
    "discovery_source": "cross_project_inprocess_mcp_protocol",
    "server_reachable_live": false,
    "relay_device_connected": false,
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
  "registries_checked": 5,
  "preset_libraries": {
    "library_count": 16,
    "total_presets": 53,
    "by_test_status": {
      "tested": 48,
      "specification_only": 5
    }
  }
}
```

## 5. Output Aktual Self-Test Deterministik Three.js (`v0.187.0`) & Remotion (`v4.0`)
```json
{"status":"ok","identical":true,"sample":{"shotId":"S002","threeVersion":"187","frame":45,"fps":30,"timeSeconds":1.5,"cameraPosition":[0,1.4,4.05],"pedestalScaleY":0.6,"seededParticleSample":[-0.089185,0.743397,0.322315],"colorSpace":"srgb","deterministic":true}}
```
```json
{"status":"ok","totalFrames":300,"durationSeconds":10,"hookSpringSample":1.074591,"fadeAlphaSample":0.666667,"captionPagesGenerated":1}
```

---

## 6. Matriks Kejujuran Status Modul Phase 01
| Modul | Status | Bukti |
|---|---|---|
| `MASTER_PROMPT.md`, `SKILL.md`, `AGENTS.md`, `README.md` v3.3 | `TESTED` | Tervalidasi struktural & kompatibel penuh dengan aturan v3.1 |
| 8 JSON Schemas (`schemas/*.schema.json`) | `TESTED` | Draft 2020-12 tervalidasi via `jsonschema 4.26.0` |
| 5 Registries (`dependency`, `asset`, `license`, `engine`, `repository`) | `TESTED` | 40 sumber eksternal + dependensi terkunci tervalidasi skema |
| 16 Production Preset Libraries (`libraries/*.json` — 53 Preset) | `48 TESTED / 5 SPECIFICATION_ONLY` | 5 preset animasi body-acting penuh ditandai jujur `specification_only` hingga rig Blender aktif |
| REA-Video Intelligence (`rea_reference_intelligence.py`) | `TESTED` | Diuji aktual pada `synthetic.mp4` (FFprobe + FFmpeg + OpenCV HSV/Laplacian MAD + contact sheet) |
| Creative Pipeline (Topic, Research, Script, VO/Dialog, Camera, Storyboard, Character, Motion, Hybrid Orchestrator) | `TESTED` | Menghasilkan 13 item pra-produksi lintas genre tanpa gap/overlap frame |
| Intelligent Asset Management (11 Komponen & Urutan 9 Tahap) | `TESTED` | Registry, SHA-256 LRU Cache, LicenseValidator, glTF 2.0 Procedural, Style Harmonizer, Converter, Retargeting, Asset QC lulus pytest |
| Approval Gate (13 Item) & `ProjectStateManager` | `TESTED` | Berhenti keras pada `WAITING_APPROVAL`, menolak kata ambigu (`lanjutkan`/`ok`), membatalkan approval bila file berubah 1 byte pun |
| Visual QC & Bounded Self-Correction (`visual_qc_engine.py`) | `TESTED` | Decode penuh FFmpeg + metrik luma/kontras/ketajaman OpenCV + batas 3x retry |
| Cross-Project XDX MCP Discovery (`xdx_mcp_adapter.py`) | `TESTED` | Menemukan 8 tool & 3 resource nyata secara in-process & live Streamable HTTP tanpa mengubah scene (`scene_mutated: false`) |
| Live Render Perangkat Vivo X200 Pro & TTS/Whisper/Rhubarb Binary | `NOT_TESTED (Phase 02)` | Menunggu pairing URL Relay aktif + persetujuan eksplisit paket pengguna |

---

# Audit Lengkap Repository & Penyedia Aset Eksternal — XDX Autonomous Video Studio v3.3

Dokumen ini mencatat hasil **audit aktual berbasis GitHub REST API (`gh api`) dan pemeriksaan HTTP langsung** pada 26 November 2026 terhadap **33 repository GitHub eksternal** dan **5 portal penyedia aset** sebelum pemilihan dependensi dilakukan.

## Prinsip Seleksi Arsitektur
1. **Tanpa Instalasi Membabi Buta**: Hanya paket yang benar-benar dibutuhkan, stabil, kompatibel dengan Python 3.12 / Node 22, serta aman untuk workflow **Cloud Runtime + Android ARM64 (Vivo X200 Pro)** yang dipasang.
2. **Kepatuhan Lisensi Ketat**: Kode `UNLICENSED` (`remotion-dev/animated-captions`) diblokir keras; paket `AGPL-3.0` (`freemocap`) dan `GPL-3.0` (`BlendArMocap`, `asu37/Rigger`) diisolasi dan tidak digabung ke inti studio berlisensi MIT; ketentuan `Remotion License` dicatat eksplisit.
3. **Stabilitas Pemeliharaan**: Repository yang sudah diarsipkan (`jianfch/stable-ts`, `archived=True`) ditolak dan digantikan oleh `whisper.cpp` / `faster-whisper`.

## Tabel Hasil Audit 33 Repository GitHub & 5 Penyedia Aset

| Kategori | Sumber / Repository | Bahasa | Lisensi Aktual | Archived | ARM64 | Cloud | Keputusan Status | Alasan Teknis & Produksi |
|---|---|---|---|---|---|---|---|---|
| Reference Intelligence | [JuneYaooo/rea-video](https://github.com/JuneYaooo/rea-video) | Python | `Apache-2.0` | Tidak | Ya | Ya | `selected_adapter_and_skill` | Adopted as primary Reference Intelligence & Remake Forensics taxonomy; offline FFprobe+OpenCV baseline active by default without unapproved external model downloads. |
| Video Production | [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | TypeScript | `Remotion-License` | Tidak | Tidak | Ya | `selected_core` | Selected as deterministic frame-based Master Timeline & Compositor (v4.0). Runs in Cloud VM Chromium; entity size license rule recorded in license_registry.json. |
| Video Production | [remotion-dev/skills](https://github.com/remotion-dev/skills) | TypeScript | `Remotion-License` | Tidak | Ya | Ya | `selected_reference_skill` | Used as reference best-practice patterns for deterministic Remotion Sequence/spring/caption authoring (not a runtime dependency). |
| Video Production | [mrdoob/three.js](https://github.com/mrdoob/three.js) | JavaScript | `MIT` | Tidak | Ya | Ya | `selected_core` | Selected as deterministic procedural 3D, simulation, glTF 2.0, and technical cutaway engine (v0.187.0). |
| Video Production | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | TypeScript | `Apache-2.0` | Tidak | Tidak | Ya | `optional_alternative_evaluated` | Evaluated (Bun monorepo HTML-to-MP4 editor); not installed in core to avoid duplicating Remotion master timeline and Bun runtime overhead. |
| Motion Graphics | [greensock/GSAP](https://github.com/greensock/GSAP) | JavaScript | `GSAP-Standard-No-Charge` | Tidak | Ya | Ya | `optional_custom_license` | Audited v3.15.1; custom non-OSI license and wall-clock defaults. Kept optional; MIT animejs + Remotion spring/interpolate chosen for core. |
| Motion Graphics | [juliangarnier/anime](https://github.com/juliangarnier/anime) | JavaScript | `MIT` | Tidak | Ya | Ya | `selected_core` | Selected (animejs v4.5.0, MIT) for deterministic seek()-driven motion graphics & kinetic typography. |
| Motion Graphics | [airbnb/lottie-web](https://github.com/airbnb/lottie-web) | JavaScript | `MIT` | Tidak | Ya | Ya | `selected_core` | Selected (v5.13.0, MIT) for deterministic frame-stepped vector animations via goToAndStop(frame, true). |
| Motion Graphics | [d3/d3](https://github.com/d3/d3) | Shell | `ISC` | Tidak | Ya | Ya | `selected_modular_subset` | Selected modular subset (d3-scale, d3-shape, d3-interpolate, ISC) for deterministic explainer charts without DOM bloat. |
| Motion Graphics | [motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) | TypeScript | `MIT` | Tidak | Tidak | Ya | `optional_alternative_evaluated` | Audited TypeScript canvas animation editor; omitted from core install to maintain a single Remotion deterministic master timeline. |
| Motion Graphics | [ManimCommunity/manim](https://github.com/ManimCommunity/manim) | Python | `MIT` | Tidak | Ya | Ya | `optional_external_specialist` | Audited v0.22.1 Python math engine; heavy Cairo/Pango/LaTeX native dependencies—deferred as optional specialist math renderer in Phase 02+. |
| Motion Graphics | [iconify/iconify](https://github.com/iconify/iconify) | TypeScript | `MIT` | Tidak | Ya | Ya | `selected_on_demand_svg_spec` | Audited MIT universal icon ecosystem; icon SVG data fetched/cached on-demand with per-set license check rather than bundling 300k icons. |
| Three.js & VFX | [pmndrs/react-three-fiber](https://github.com/pmndrs/react-three-fiber) | TypeScript | `MIT` | Tidak | Tidak | Ya | `optional_phase02_bridge` | Audited MIT React reconciler for Three.js; compatible for Phase 02 @remotion/three inline canvas integration. |
| Three.js & VFX | [pmndrs/drei](https://github.com/pmndrs/drei) | JavaScript | `MIT` | Tidak | Tidak | Ya | `optional_phase02_bridge` | Audited MIT R3F helpers; deferred until inline R3F canvas shots require shader helpers, keeping Phase 01 dependency footprint minimal. |
| Three.js & VFX | [Alchemist0823/three.quarks](https://github.com/Alchemist0823/three.quarks) | TypeScript | `MIT` | Tidak | Ya | Ya | `optional_phase02_vfx` | Audited MIT Three.js particle VFX system; compatible with Three.js v0.187 deterministic stepping when advanced emitters are required. |
| Three.js & VFX | [tsparticles/tsparticles](https://github.com/tsparticles/tsparticles) | TypeScript | `MIT` | Tidak | Ya | Ya | `optional_alternative_evaluated` | Audited v4.6.0 2D DOM/Canvas particles; omitted to avoid overlap with deterministic seeded 2D/3D particle presets. |
| Three.js & VFX | [pmndrs/postprocessing](https://github.com/pmndrs/postprocessing) | JavaScript | `Zlib` | Tidak | Ya | Ya | `optional_phase02_vfx` | Audited v6.39.6 Zlib post-processing passes for Three.js WebGLRenderer; registered for Phase 02 bloom/DOF/vignette passes. |
| Three.js & VFX | [dimforge/rapier](https://github.com/dimforge/rapier) | Rust | `Apache-2.0` | Tidak | Ya | Ya | `optional_wasm_simulation` | Audited Rust/WASM deterministic physics engine; registered for Phase 02 rigid-body simulations with fixed timestep. |
| Character Animation | [Mesh2Motion/mesh2motion-app](https://github.com/Mesh2Motion/mesh2motion-app) | TypeScript | `MIT / CC0-1.0` | Tidak | Ya | Ya | `selected_rig_convention_cc0` | Dual-licensed: code MIT, all 3D models/rigs/animations CC0-1.0. Adopted as CC0 humanoid rig & animation convention. |
| Character Animation | [freemocap/freemocap](https://github.com/freemocap/freemocap) | TypeScript | `AGPL-3.0` | Tidak | Tidak | Ya | `isolated_copyleft_rejected_core` | AGPL-3.0 markerless mocap with heavy numba/aniposelib/opencv-contrib stack; excluded from core bundle due to AGPL copyleft & multi-camera hardware requirement. |
| Character Animation | [cgtinker/BlendArMocap](https://github.com/cgtinker/BlendArMocap) | Python | `GPL-3.0` | Tidak | Tidak | Tidak | `rejected_dependency_conflict` | GPL-3.0 Blender add-on pinning legacy protobuf==3.20.2 & opencv-contrib; conflicts with modern Python 3.12+ and Android APK sandbox. |
| Character Animation | [Rokoko/rokoko-studio-live-blender](https://github.com/Rokoko/rokoko-studio-live-blender) | Python | `LGPL-3.0` | Tidak | Tidak | Tidak | `optional_retargeting_reference` | LGPL-3.0 Blender bone-naming & retargeting reference; desktop Rokoko Studio Live socket not used on Vivo X200 Pro. |
| Character Animation | [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | C++ | `Apache-2.0` | Tidak | Ya | Ya | `optional_pose_extractor` | Apache-2.0 pose/face landmark ML framework; compatible with Android ARM64 & Linux x86_64 as optional offline motion extractor. |
| Character Animation | [DanielSWolf/rhubarb-lip-sync](https://github.com/DanielSWolf/rhubarb-lip-sync) | C++ | `MIT` | Tidak | Ya | Ya | `selected_adapter_viseme_spec` | MIT C++ CLI generating Preston Blair A-H + X mouth cues from WAV; integrated via adapters/rhubarb_lipsync_adapter.py with off-screen VO fallback. |
| Character Animation | [asu37/Rigger](https://github.com/asu37/Rigger) | Python | `GPL-3.0` | Tidak | Tidak | Tidak | `isolated_copyleft_evaluated` | GPL-3.0 experimental Blender add-on (7 stars); not installed on Vivo X200 Pro to protect XDX Blender Studio stability. |
| Caption & Audio Intelligence | [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | C++ | `MIT` | Tidak | Ya | Ya | `selected_arm64_asr_target` | MIT C/C++ Whisper v1.9.6 with ARM NEON support; primary recommended offline ASR binary for Android ARM64 & CPU cloud. |
| Caption & Audio Intelligence | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Python | `MIT` | Tidak | Ya | Ya | `selected_optional_python_asr` | MIT CTranslate2 Whisper; declared as optional extra [asr] in pyproject.toml via adapters/whisper_caption_adapter.py. |
| Caption & Audio Intelligence | [m-bain/whisperX](https://github.com/m-bain/whisperX) | Python | `BSD-2-Clause` | Tidak | Tidak | Ya | `optional_word_alignment` | BSD-2-Clause word-level forced alignment; heavy PyTorch/pyannote dependency chain kept optional for cloud GPU runs. |
| Caption & Audio Intelligence | [jianfch/stable-ts](https://github.com/jianfch/stable-ts) | Python | `MIT` | Ya | Ya | Ya | `rejected_archived` | Repository is ARCHIVED (May 2026); superseded by faster-whisper and whisper.cpp. |
| Caption & Audio Intelligence | [remotion-dev/animated-captions](https://github.com/remotion-dev/animated-captions) | TypeScript | `UNLICENSED` | Tidak | Tidak | Ya | `blocked_unlicensed` | package.json declares 'license': 'UNLICENSED' and 'private': true; blocked by LicenseValidator—replaced by original XDX MIT caption presets + @remotion/captions. |
| Caption & Audio Intelligence | [neutral-Stage/remotion-captioneer](https://github.com/neutral-Stage/remotion-captioneer) | TypeScript | `MIT` | Tidak | Ya | Ya | `optional_mit_reference` | MIT v1.2.0 Remotion caption component; relies on external cloud ASR APIs by default, so local @remotion/captions + Whisper adapter is preferred. |
| Asset Providers | [Poly-Haven/Public-API](https://github.com/Poly-Haven/Public-API) | TypeScript | `AGPL-3.0 (API code) / CC0-1.0 (Assets)` | Tidak | Ya | Ya | `selected_asset_api` | Queried strictly over HTTPS REST (https://api.polyhaven.com) via adapters/polyhaven_adapter.py to discover/download CC0 HDRIs, PBR textures, and models on-demand. |
| Asset Providers | [Poly-Haven/polyhavenassets](https://github.com/Poly-Haven/polyhavenassets) | Python | `GPL-3.0` | Tidak | Tidak | Ya | `isolated_blender_addon_reference` | GPL-3.0 desktop Blender Asset Browser add-on; omitted in favor of XDX targeted HTTP CC0 cache manager safe for Android scoped storage. |
| Asset Providers | [Poly Haven (polyhaven.com)](https://polyhaven.com/) | Web/API | `CC0-1.0` | Tidak | Ya | Ya | `selected_asset_provider` | Verified HTTP 200 & JSON API (api.polyhaven.com); CC0 HDRIs, PBR textures, and 3D models downloaded on-demand only. |
| Asset Providers | [ambientCG (ambientcg.com)](https://ambientcg.com/) | Web/API | `CC0-1.0` | Tidak | Ya | Ya | `selected_asset_provider` | Verified HTTP 200 & v2 JSON API (2,943+ CC0 PBR materials); queried on-demand via adapters/ambientcg_adapter.py. |
| Asset Providers | [Kenney Assets (kenney.nl/assets)](https://kenney.nl/assets) | Web/API | `CC0-1.0` | Tidak | Ya | Ya | `selected_curated_catalog` | Verified HTTP 200; CC0 stylized low-poly/modular props & UI SFX compatible with mobile_guard budgets (note: noai meta tag respected—used only as standard 3D/audio assets, never for ML training). |
| Asset Providers | [Quaternius (quaternius.com)](https://quaternius.com/) | Web/API | `CC0-1.0` | Tidak | Ya | Ya | `selected_curated_catalog` | Verified HTTP 200; CC0 rigged low-poly stylized characters & modular environment packs ideal for Vivo X200 Pro & Three.js. |
| Asset Providers | [Google Fonts (fonts.google.com)](https://fonts.google.com/) | Web/API | `OFL-1.1 / Apache-2.0` | Tidak | Ya | Ya | `selected_typography_provider` | Verified HTTP 200; primary source for OFL-1.1 Indonesian & multi-genre typography (Plus Jakarta Sans, Inter, Space Grotesk, Merriweather, JetBrains Mono). |


---

# Integrasi Lintas Proyek XDX Blender Studio MCP (Android ARM64 & Cloud Runtime)

## 1. Prinsip Tanpa Modifikasi (`Zero-Touch Preservation`)
Repository `fiankuns/xdx-blender-studio` telah diaudit dan diuji (`17/17` unit & integration test lulus) **tanpa mengubah satu baris kode pun**. Seluruh mekanisme berikut tetap utuh:
- Autentikasi **HMAC-SHA256** (`BLENDER_AUTH_TOKEN` + batas skew `±60s` + `ReplayGuard` nonce cache) pada `/relay/register`, `/relay/poll`, `/relay/result`, dan TCP socket.
- Autentikasi **Bearer Token** waktu-konstan (`Authorization: Bearer <MCP_AUTH_TOKEN>`) pada `/mcp` dan `/studio`.
- Penolakan keras terhadap `BLENDER_HOST=0.0.0.0`.
- Perlindungan ANR 5 detik **Vivo X200 Pro** (`mobile_guard`: batas 4 thread Cycles, resolusi `rendered <= 640px`, larangan menulis ke `/tmp`, menggunakan `bpy.app.tempdir`).

## 2. Daftar Tool & Resource Aktual yang Ditemukan (`MCPProtocolHandler` `2025-03-26`)

### 8 MCP Tools Aktual
| Nama Tool | Kategori Keamanan | Fungsi Aktual |
|---|---|---|
| `get_mobile_device_profile` | `READ_ONLY` | Mengambil profil perangkat Vivo X200 Pro (Dimensity 9400 / Immortalis-G925), versi Blender, `bpy.app.tempdir`, dan batas `mobile_guard`. |
| `get_scene_info` | `READ_ONLY` | Membaca daftar objek scene, transformasi, jumlah vertex/poligon, kamera aktif, dan resolusi render. |
| `look` | `VISUAL_NON_MUTATING` | Menangkap PNG base64 (`viewport`, `angles`, `camera`; shading `material`, `solid`, `wireframe`, `rendered`) lalu memulihkan pengaturan render asli. |
| `execute_blender_code` | `MUTATING` (Diblokir pra-approval) | Menjalankan kode `bpy` pada main thread Blender (menolak penulisan ke `/tmp`). |
| `create_primitive` | `MUTATING` (Diblokir pra-approval) | Membuat primitif 3D (`cube`, `sphere`, `cylinder`, `cone`, `torus`, `plane`, `monkey`). |
| `modify_object` | `MUTATING` (Diblokir pra-approval) | Mengubah transformasi, mengganti nama, menyembunyikan, atau menghapus objek. |
| `set_material` | `MUTATING` (Diblokir pra-approval) | Mengatur material PBR Principled BSDF (`base_color`, `metallic`, `roughness`). |
| `configure_mobile_guard` | `MUTATING` (Diblokir pra-approval) | Mengatur batas thread Cycles (`1..8`), resolusi render (`128..1024`), dan sampel (`4..128`). |

### 3 MCP Resources Aktual
1. `ui://mcp-for-blender/viewport-v2` (`text/html;profile=mcp-app`)
2. `xdx://device/profile` (`application/json`)
3. `xdx://scene/summary` (`application/json`)

## 3. Cara Menghubungkan dari Proyek Baru Tanpa Komputer
Karena eksekusi Cloud Runtime berada di VM terisolasi dan pengguna bekerja menggunakan **Vivo X200 Pro (Android ARM64)**:
1. Gunakan endpoint **Outbound Relay** yang sudah dipasangkan (misalnya layanan Render `xdx-blender-studio` atau HTTPS/Tailscale).
2. Di sisi proyek `XDX-Autonomous-Video-Studio`, cukup ekspor variabel lingkungan pada sesi kerja (jangan pernah di-commit ke Git):
   ```bash
   export XDX_MCP_SERVER_URL="https://<your-xdx-relay-host>"
   export MCP_AUTH_TOKEN="<existing-mcp-auth-token>"
   ```
3. Jalankan pemeriksaan baca-saja:
   ```bash
   python3 scripts/mcp_discovery.py
   ```
   Adapter `XDXBlenderMCPAdapter` otomatis memeriksa `/health`, menjalankan `initialize` dan `tools/list`, serta menolak semua tool bermutasi sebelum `APPROVED`.


---

# Rencana Implementasi Phase 02 — XDX Autonomous Video Studio v3.3

Setelah fondasi modular, skema, registri, 16 pustaka preset, sistem aset 9 tahap, dan gerbang persetujuan 13 item selesai pada **Phase 01**, tahapan **Phase 02** berfokus pada eksekusi produksi end-to-end setelah persetujuan pengguna:

## Target Teknis Phase 02
1. **Live End-to-End XDX Relay Pairing & Smoke Render**:
   - Menghubungkan sesi Cloud `XDX-Autonomous-Video-Studio` ke server Relay aktif tempat **Vivo X200 Pro** terhubung (`relay_connected: true`).
   - Menjalankan smoke test pasca-approval (`get_mobile_device_profile` → `get_scene_info` → turntable style frame `look(mode="angles", shading="material")`).
2. **Headless Three.js WebGL Frame Sequence Renderer**:
   - Mengintegrasikan Playwright + Chromium headless (`/usr/bin/google-chrome`) dengan `engines/web/three_deterministic_scene.mjs` untuk mengekspor sequence PNG RGBA 1080x1920 frame-demi-frame secara deterministik dengan load barrier penuh.
3. **Remotion Full React Project & Master MP4 Render**:
   - Membangun bundle komposisi React/Remotion (`@remotion/bundler` + `@remotion/renderer`) yang menggabungkan sequence shot Blender, sequence shot Three.js, overlay grafis D3/Anime.js, komponen subtitle aman 9:16, dan pencampuran multi-track WAV 48 kHz.
4. **Indonesian TTS, Whisper Forced Alignment & Rhubarb Lip-Sync**:
   - Mengintegrasikan penyedia TTS Bahasa Indonesia berlisensi + kompilasi `whisper.cpp` / `faster-whisper` untuk penyelarasan kata aktual pasca-WAV, serta biner `rhubarb` untuk adegan dialog on-screen.
5. **Automated Closed-Loop Visual Self-Correction**:
   - Menghubungkan `VisualQualityControlEngine` dan evaluasi frame multimodal untuk me-render ulang shot yang gagal QC secara otomatis hingga maksimal 3 iterasi sebelum pengemasan `final.mp4`.


---

## 7. Daftar Lengkap 80 File Repository & Checksum SHA-256
```text
56021185676c67dc10274c8d4f5e14c5add47f1768af6f726251e401b06789c3  .env.example  (258 B)
95f178226cc08b402cf6619451ad7ec6eadcd5b77ff7115cc9677532cf1f83c4  .gitignore  (752 B)
8d89c3ffc6e89ac16ca7a10ae45c08a19e190359f2a79c74c0b4f1d6fba7ba1e  AGENTS.md  (3183 B)
e73d591a5597bb66c2097e59bbd755a64fbee2b7db2e99ad5f05539725032e60  MASTER_PROMPT.md  (11146 B)
ac39184a6107eea059548088d315c88332b66916d95651c66a803c0c9a49c6bc  README.md  (4701 B)
1cfc5a78e5528dec2bae79db36e124562c05c2c908fbaec8cc4709fe6dc012dd  SKILL.md  (2702 B)
59792780fc1beadeb8dac369e1e5b2c4f34399be64c8a54bba23b6e3b312958f  adapters/__init__.py  (564 B)
c292dbfc47eb28f719b938db065b118d25864c2ff292e3141f9d0322445f169b  adapters/ambientcg_adapter.py  (1889 B)
1adb06dc1532e1db8e0aeaf86a44f581ee0c7d3b74c2d21d0acebd9818475ddc  adapters/caption_lipsync_adapter.py  (5275 B)
f7bee79226972f57fe8e27af32888af82f1befccf420438475abdfdd29cff2ef  adapters/polyhaven_adapter.py  (3097 B)
6f2fc3fcde5d40fa69cf349b5e15acd53f7a6bb76a6db69fedf79b09654ab8ef  adapters/xdx_mcp_adapter.py  (12045 B)
1b65aa11475fbe342d1dc06c5323d5fcadecae29e95a0d34209135b1573128bc  docs/ARCHITECTURE_V3_3.md  (1969 B)
71f1d060520c4f9ef7f041a9f268b546462a54ed1c2d8493bd4874d7c9c7b310  docs/EXTERNAL_REPO_AUDIT.md  (12424 B)
1dab0607ddc2c0fb395c66b985dbbbbec7b65cc6ea5b925a5699fd20552f7d18  docs/MCP_INTEGRATION.md  (3266 B)
d4c90ae912f6588cab623bdff8875eff720a801e55aa9d759b21947060da5730  docs/PHASE_02_ROADMAP.md  (1821 B)
e669298da38df33e3899d032ae0235b880f204855006128b02714c701f516712  docs/v3_1_foundation/HYBRID_EXECUTION.md  (1063 B)
f2fa68198e2c0d3512b1a6dfeba942a1906511a48d5348583cfe74288ad35f46  docs/v3_1_foundation/MCP_EXECUTION.md  (989 B)
b63d1c84a7fdf3d4117453a584e5778a4dd0027a1bd816bf4d0313f7cfbf100c  docs/v3_1_foundation/rea_video_upstream.md  (1501 B)
e28961780b7544c36f0d9782093c5bd88c049df4edf032a9420498110d2d9f11  docs/v3_1_foundation/reference_analysis.md  (3573 B)
358488a90951d39dc59a66b80f383eca9e6b9fc9598b370c7c992dc67895feac  engines/__init__.py  (325 B)
48b78cf74302fe87b62a803f8b05ad521d0647892be5c60f4ddb3cfddc5e3034  engines/blender_xdx_engine.py  (2651 B)
e662168270ae0108cd909fdbfc8e9f617ef70cb870edecfb69f97af66926e30f  engines/ffmpeg_engine.py  (3748 B)
db14afe7bba972ebc8652354e8092145b9a2036665134992a6ca58cb52e47e38  engines/web/remotion_timeline_spec.mjs  (2032 B)
5d513fecb05157528a72fc58a77b8e0e1212ae8125e91dd95258f1a388c602b2  engines/web/three_deterministic_scene.mjs  (3187 B)
53ad3a72afa96f80b3c80f5e0f20a1d3f39497c3ccabdb120f5815491f6a11e6  engines/web_engines.py  (3184 B)
29ad9b47c6da0739017db79f6831d1cce7c6588364124a61e7239310081b2a65  intelligence/__init__.py  (2231 B)
b0dd797237b44f829eca903d1abf27ff4c954ec7b8cec682918ca9be188532a5  intelligence/asset_management.py  (29187 B)
86a20014a05677d0ba047d392ec559c3d8c2aaa74e1d89def063da57175ca7fa  intelligence/creative_pipeline.py  (36628 B)
030d1c5e57205ddac084f5a1f8508d5b3a15c2f72f85a22156983fd8afd20991  intelligence/rea_reference_intelligence.py  (12981 B)
404960ee9fb2eaf8962adccd60b2e5fbb94834b7e11e9af8b8177868e10f99ab  intelligence/state_and_approval.py  (12298 B)
25ca0d5f580f270e1b7a7e9988efc96b4edeae8b4d9fd8ee1dd450cb44711fca  intelligence/visual_qc_engine.py  (8798 B)
17cac08294398f2ced3dc393034d41b79d875397abb1c9830bb98eb49003d179  libraries/__init__.py  (179 B)
69b84a786c45e357c4862398fd69dcdc672b29227a1069573b44250052f862d9  libraries/asset_3d_library.json  (1893 B)
44e9a8df2d36c645fa51b0f90021674c57fd2748e3d0782268a9524fcbbbec66  libraries/audio_sfx_library.json  (1898 B)
b4cfe032c006fb6b1beedfff0c5b9c348e91439a30ba21aa2627073d61a396ac  libraries/camera_library.json  (2600 B)
f3fa424ff941aa5ec2d61b153544f26f87ea3e171a3a25a4a8cedb9d17098af7  libraries/caption_library.json  (2384 B)
0355bd3a7e9f8b802a88d257d63877fe744ad1208e36181a2dfb24bf159336cb  libraries/character_animation_library.json  (2691 B)
da043bc8294cfb090fcb509f6ad20cf1d127ca2f01cfe16e6ddcfb3a985235d5  libraries/environment_library.json  (3128 B)
a36a57f1af391792e9a5e79a73b5e245a061ddc1ee2c209ebdab04cfe353aa7d  libraries/facial_expression_library.json  (2439 B)
e24e9eca8dd69a25f59df12c61b8551f4a3782e71b0726cafa78a671f96842fa  libraries/lighting_library.json  (1929 B)
069fc951a3a95289c9d5c5e081ef210b84f746b24776578245541f03506a75b4  libraries/lip_sync_library.json  (2010 B)
8c5e69d89e9916789514c9c50726c438e1f1766da992893d59cdeacb6f6de6ef  libraries/loader.py  (3946 B)
6e19c04453b776cd1f9b21be2c9be78663c323adf1c09d0b0c6630b80e699f83  libraries/material_library.json  (1695 B)
684add47422c08e3450a458f083072573b019f5a445015f399d32980d26d0f5a  libraries/motion_library.json  (2774 B)
4571bc1fb4ff9a60d13b3e44f0c5407e1404ea0e33779eddd3adb78bef99d6c4  libraries/particle_library.json  (2121 B)
2e0487168039a13089987e713d814b081bccf966900ad3405348d26702bdde7f  libraries/transition_library.json  (1859 B)
a40ae913e344440ba47557dc61235135ea8d0c5e47d2061ae6a986d105f85343  libraries/typography_library.json  (2071 B)
e200a2294174117ab646ebc572a413eca9a3f7f6bb397e0d08d55078b65f8c2c  libraries/vfx_library.json  (2066 B)
cbc1f26aa3e54165539c21d1f7fede40cd9597445e0ba503573619e5723fb665  libraries/visual_explainer_library.json  (2143 B)
ed4c0222b7a354a1e2094f30e962dff528eba9f5dcc2d33c8f7db89369c8ccac  package-lock.json  (9457 B)
4fd7e8a9130375bbbeea8d1bdf2aa1ca38b241deee4ce3d20900eaac38ef0cdb  package.json  (804 B)
e8ca59168d072316286eb768be425b6da9282e7791e3c9eba540802fa8857083  pyproject.toml  (971 B)
768987f9fb7e71137402a0bac4161128c78030aa487b6a9ec0ee7bd36421f68f  registry/asset_registry.json  (7812 B)
1d5b474b5845bfccaad94023dfbd24811fffa821e4ce08ee35e2b417396083c7  registry/dependency_registry.json  (7711 B)
e217b210692eea9780d3280abb96913b8f2e26301cee8863ef656b7f8bac4849  registry/engine_registry.json  (4292 B)
bd1041d967ba9577940a3cecbf1ab830b54da970dc940615ba05ecab602f5743  registry/license_registry.json  (5199 B)
37f2a6c30dc666104f470a7014827f028c867fb57c1d6c5bb8527a369c3222ff  registry/repository_registry.json  (24007 B)
f289a5b862ef3355909bce0c5f68c4a3e55a3aa379346d5dc2a4e4e0845eb667  requirements.lock  (378 B)
b54954919932d8a343cef8d9e4737361ebf508f9bdfa645e142d8eb45714082c  schemas/approval_package.schema.json  (2903 B)
b0905ebfe2ce5d161cb9fb6e93bff7f6162d2b3b21724fe47c65d2f0af44ba03  schemas/asset_registry.schema.json  (3119 B)
345acf8a94d3882608ef28a6503d7c237ad2f293da802dabf22fa2088bfe32c4  schemas/dependency_registry.schema.json  (1138 B)
ed98675b570bb7937b7ccd2b879e961400fdc448181649de778d14841358e13d  schemas/engine_plan.schema.json  (3651 B)
e19c5b3ea91aa905abca6f0ebce27cc415b5360f744a2a873d2f229b54247162  schemas/preset_library.schema.json  (2164 B)
8fdc1bf86ea589018d9dd87e4fafc86a686bfafbdf6a025d6761799e986a7251  schemas/project_state.schema.json  (3366 B)
00917ae555157c1363cba27c4b3077d7677220672343a6f567d7c4adb22c38a8  schemas/qc_report.schema.json  (3362 B)
75a40849e3eb51de2781d3009e9f42c287efd208ca197ec153c5a031c35ce681  schemas/storyboard.schema.json  (5909 B)
e1fd501cd6c2d8492d720e3146c9d52daa7250eab371ec6c8ae3373958dc38bf  scripts/adaptive_detect.py  (1097 B)
1726e25285eb0ed29ba4f31d0260e8fc6f62348840b6a855ea4f24ca7e04afb4  scripts/approval_gate.py  (2463 B)
718a7528024e1f96ad2edae5067f57360c15a692e992845d476888d91865c489  scripts/mcp_discovery.py  (996 B)
77d451cd5ddc560b6e0652f4a29d2f4ed3868d5ff798f087be1cb2a82a933e97  scripts/rea_analyze.py  (1174 B)
a298046a89d434b621ac3d09a3e4bf0e20ab887f5698ea2d36db6fa690633609  scripts/xdx_studio.py  (4775 B)
25b6ea746d7d57d22dd9649464e9a13a23e88e9a8352327789cf734baa05027a  tests/fixtures/synthetic.mp4  (74732 B)
f037baba445ed06f9cb2c6b49d086e48fc24ac1b9e0ad61ac52956c77f38e99a  tests/fixtures/v3_1_regression/approval_gate_test.json  (926 B)
74855f668dc904fed189d38470e0af163d70189e84ca99f2c56acc1434cd1979  tests/fixtures/v3_1_regression/hybrid_approval_gate_test.json  (225 B)
3dcb1d8c14e799894c8442cdc345c421cbbcf9ec0940983da996005d945f9f53  tests/fixtures/v3_1_regression/real_candidates.json  (14877 B)
717ac81739ed2177582a75e516206eb4baed8cdc671f43aa2abe5324a968681b  tests/fixtures/v3_1_regression/synthetic_qc.json  (251 B)
b6d72a3f077d1b14a1a907592e4dcd996eb6810edaa5f826bb3d0264344078ea  tests/test_approval_state_rea_and_qc.py  (4988 B)
5515bf91f7d793a95d065883ace0b8f987004afa18ed9610ff5db9296183ac75  tests/test_asset_management.py  (5426 B)
8a084801ddc2b8efb73ba7b35e1915f630f7f9298399aaad25bb1a61e9a78967  tests/test_mcp_discovery_readonly.py  (4145 B)
4ba70e755e5a6444c2161cddd338902a245ce7a1d40c4edd08b1bfeaebe11016  tests/test_structure_schemas_and_runtimes.py  (4604 B)
```
