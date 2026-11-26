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
