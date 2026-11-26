# XDX Autonomous Video Studio v3.3

Fondasi produksi video otonom hybrid generasi **v3.3** yang dibangun di atas arsitektur **v3.1** tanpa menghilangkan kemampuan pendahulunya. Mengorkestrasi **XDX Blender Studio MCP (Android ARM64 Vivo X200 Pro & Cloud Relay)**, **Three.js (`v0.187.0`)**, **Remotion (`v4.0`)**, **REA-Video Intelligence**, dan **FFmpeg (`v6.1+`)** di atas satu master timeline deterministik berbasis frame dengan **13-Item Mandatory Approval Gate**.

---

## Arsitektur Direktori Modular

```text
XDX-Autonomous-Video-Studio/
├── MASTER_PROMPT.md          # Protokol Utama Mengikat v3.3 (Bahasa Indonesia)
├── SKILL.md                  # Definisi Skill Agen Otonom v3.3
├── AGENTS.md                 # Panduan Peran Agen & Batas Keamanan
├── README.md                 # Dokumentasi Utama Proyek
├── pyproject.toml            # Konfigurasi Paket Python v3.3.0
├── requirements.lock         # Lockfile Dependensi Python Teruji
├── package.json              # Paket Web/3D/Timeline Deterministik
├── package-lock.json         # Lockfile Dependensi Node.js Teruji
├── engines/                  # Blender XDX, Three.js, Remotion, dan FFmpeg Engines
├── intelligence/             # 14 Modul Core Intelligence & 11 Komponen Asset Management
├── adapters/                 # Cross-Project XDX MCP, Poly Haven, ambientCG, Whisper & Rhubarb
├── libraries/                # 16 Pustaka Preset Produksi Tervalidasi Schema
├── registry/                 # Dependency, Asset, License, Engine, dan Repository Registries
├── schemas/                  # 8 JSON Schema Draft 2020-12 Formal
├── scripts/                  # CLI Eksekusi, Preflight, Approval Gate, REA Analyze & MCP Discovery
├── tests/                    # Suite Pengujian Otomatis Pytest + Fixture Regresi v3.1
└── docs/                     # Audit 38 Sumber Eksternal, Arsitektur, Integrasi MCP & Roadmap Phase 02
```

---

## Pembagian Tugas Hybrid Pipeline

| Engine | Peran Produksi | Kontrak Deterministik |
|---|---|---|
| **Blender MCP XDX** | Karakter 3D, rigging/IK, ekspresi, acting, set diorama, PBR lighting, render sinematik | Frame integer via `fiankuns/xdx-blender-studio` (`mobile_guard` Vivo X200 Pro aman ANR) |
| **Three.js (`v0.187.0`)** | Procedural 3D, simulasi, visualisasi teknis/sejarah cutaway, VFX & partikel | Evaluasi `frame / fps` + PRNG `Mulberry32` + `ACESFilmic` / `sRGB` |
| **Remotion (`v4.0`)** | Master timeline `[start_frame, end_frame)`, compositing, caption, transisi, mixing audio | Zero-gap integer frames @ `30 fps`, `1080x1920` (`9:16` default) |
| **REA-Video** | Analisis forensik video referensi & Quality Control visual pasca-render | `ffprobe` + FFmpeg scene select + OpenCV HSV/Laplacian MAD |
| **FFmpeg (`v6.1+`)** | Encoding akhir `H.264 yuv420p` + `AAC 48 kHz` dan verifikasi decode penuh | `ffmpeg -v error -i output.mp4 -f null -` |

---

## Workflow Tanpa Komputer (Android ARM64 Vivo X200 Pro + Cloud Runtime)

1. **Blender 3D berjalan di Vivo X200 Pro** menggunakan add-on `xdx_blender_vivo_x200_pro_addon.zip` (Zero Termux, Zero Open Ports) yang terhubung keluar (*Outbound Authenticated Relay* HMAC-SHA256) ke server `xdx-blender-studio` di Cloud/Tailscale.
2. **XDX Autonomous Video Studio v3.3 berjalan di Cloud Runtime** untuk menjalankan riset, penyusunan paket pra-produksi 13 item, evaluasi Three.js/Remotion/Chromium headless, FFmpeg, dan memanggil endpoint `/mcp` milik XDX Relay menggunakan `XDX_MCP_SERVER_URL` dan `MCP_AUTH_TOKEN` — tanpa merusak pairing atau mengubah repository `xdx-blender-studio`.

---

## Perintah Cepat & Pengujian

```bash
# 1. Pemeriksaan runtime & discovery XDX MCP baca-saja (tanpa mengubah scene Blender)
python3 scripts/xdx_studio.py preflight

# 2. Validasi seluruh JSON Schema, 5 Registry, dan 16 Production Preset Libraries
python3 scripts/xdx_studio.py validate-all

# 3. Buat contoh paket pra-produksi 13 item (otomatis berhenti pada WAITING_APPROVAL)
python3 scripts/xdx_studio.py plan \
  --project-id demo_01 \
  --topic "Mengapa Jam Dinding Berdetak Lebih Keras Saat Malam?" \
  --genres edukasi horor komedi_absurd \
  --out /tmp/xdx_demo_pkg

# 4. Verifikasi fingerprint SHA-256 Approval Gate (kompatibel v3.1 & v3.3)
python3 scripts/approval_gate.py /tmp/xdx_demo_pkg --strict-schema

# 5. Jalankan seluruh suite pengujian otomatis Phase 01
pytest -v
```

Lihat dokumentasi mendalam di:
- [`docs/EXTERNAL_REPO_AUDIT.md`](docs/EXTERNAL_REPO_AUDIT.md)
- [`docs/ARCHITECTURE_V3_3.md`](docs/ARCHITECTURE_V3_3.md)
- [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md)
- [`docs/PHASE_02_ROADMAP.md`](docs/PHASE_02_ROADMAP.md)