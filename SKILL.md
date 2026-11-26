---
name: xdx-autonomous-video-studio
version: 3.3.0
replaces: xdx-reference-to-hybrid-video (v3.1)
description: Universal multi-genre autonomous video production studio (v3.3). Performs REA-Video reference forensics, topic research, script/storyboard/camera/character/motion planning, 9-step CC0/procedural asset procurement, 13-item approval-gated hybrid orchestration across XDX Blender MCP (Android ARM64 Vivo X200 Pro & Cloud Relay), Three.js, Remotion, and FFmpeg, plus Visual QC & Self-Correction.
---
# XDX Autonomous Video Studio Skill v3.3

1. **Baca Protokol Utama Terlebih Dahulu**: Selalu baca `MASTER_PROMPT.md` dan `AGENTS.md` sebelum memulai tugas apa pun. Gunakan Bahasa Indonesia.
2. **Jalankan Preflight Baca-Saja**:
   ```bash
   python3 scripts/xdx_studio.py preflight
   python3 scripts/xdx_studio.py validate-all
   ```
   Periksa ketersediaan aktual Python, Node, Three.js, Remotion, FFmpeg/FFprobe, serta status koneksi XDX Blender MCP (`scripts/mcp_discovery.py`) tanpa mengubah scene Blender sedikit pun.
3. **Analisis Referensi (Bila Ada Video Referensi)**:
   - Gunakan `rea-video` upstream bila terpasang, atau jalankan `python3 scripts/rea_analyze.py INPUT.mp4 --out OUTPUT_DIR` (menggabungkan FFprobe, kandidat scene FFmpeg, dan detektor adaptif OpenCV `scripts/adaptive_detect.py`).
   - Pisahkan pengukuran, observasi visual, inferensi, dan hal yang tidak diketahui.
4. **Susun Paket Pra-Produksi 13 Item & Berhenti di `WAITING_APPROVAL`**:
   - Gunakan `PreProductionPackageBuilder` (`python3 scripts/xdx_studio.py plan --project-id <ID> --topic "<Topik>" --genres <genre...> --out projects/<ID>`) atau susun manual sesuai `schemas/*.schema.json`.
   - Verifikasi keutuhan dan fingerprint SHA-256 melalui `python3 scripts/approval_gate.py projects/<ID> --strict-schema`.
   - Tampilkan ke-13 item wajib kepada pengguna dan berhenti penuh pada status `WAITING_APPROVAL`.
5. **Pengadaan Aset 9 Tahap & Preset Libraries**:
   - Gunakan `libraries/` (16 pustaka preset tervalidasi) dan `IntelligentAssetPipeline` (`intelligence/asset_management.py`) sesuai urutan 9 tahap. Jangan pernah mengunduh seluruh pustaka aset sekaligus atau menyimpan aset besar/token di GitHub.
6. **Eksekusi Pasca-Approval & QC**:
   - Hanya setelah persetujuan eksplisit pengguna terhadap versi paket terbaru tercatat dan terverifikasi (`RECORD_MATCH_ONLY` + verifikasi pesan asli pengguna), jalankan produksi hybrid sesuai `engine_plan.json`, diikuti `VisualQualityControlEngine` (`FFprobe` + decode penuh `FFmpeg` + inspeksi frame OpenCV + maksimal 3 percobaan Self-Correction per shot).
   - Jangan pernah melakukan substitusi engine secara diam-diam bila suatu tool terblokir (`BLOCKED`).
