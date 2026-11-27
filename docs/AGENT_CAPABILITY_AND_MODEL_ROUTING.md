# Laporan Kemampuan Native Antigravity, Routing Model, Permissions & Batasan Jujur (Phase 01.6A)

Dokumen ini disusun berdasarkan pemeriksaan dokumentasi resmi `https://antigravity.google/docs/*` dan pengujian runtime aktual pada VM remote `jetski_remote_agents_3p_devbox` (`Ubuntu 24.04` · `Python 3.12.16` · `Node v22.23.5`).

---

## 1. Kemampuan Multi-Agent Native Antigravity yang Terverifikasi

| Komponen | Dokumentasi Resmi Antigravity | Status Aktual di Runtime Ini | Klasifikasi Jujur |
|---|---|---|---|
| **Subagent Dinamis (`define_subagent` & `invoke_subagent`)** | Mendukung pembuatan subagent sesi dengan konteks percakapan bersih (*fresh context*), kontrol `enable_write_tools`, `enable_mcp_tools`, `enable_subagent_tools`, serta komunikasi `send_message` & `manage_subagents`. | **TERSEDIA & DIUJI LIVE** (Producer + Independent Verifier dijalankan pada konteks terisolasi). | `RUNTIME_TESTED` |
| **Built-in Subagents** | `research`, `browser`, `self`, `teamwork`. | Terdaftar aktif di sesi ini: `research` (sandbox baca-saja), `self`, `teamwork`, `teamwork_preview`. | `RUNTIME_TESTED` |
| **Custom Workspace Subagents (`.agents/agents/*.md`)** | YAML frontmatter: `name`, `description`, `tools`, `mainAgent`, `subagent`, `model` (`inherit`/`flash`/`pro`), `commandExecutionPolicy` (`off`/`auto`/`eager`/`sandbox`), `skills`. | 10 definisi agen dibuat & divalidasi ketat terhadap daftar tool resmi agar bebas risiko *hang* akibat nama tool salah eja. | `SCHEMA_VALIDATED` & `UNIT_TESTED` |
| **Workspace Skills (`.agents/skills/*/SKILL.md`)** | YAML frontmatter: `name` (opsional), `description` (wajib). | 4 skill routing workspace dibuat + 8 skill sistem aktif (`rea-video`, `threejs`, `xdx-blender-vivo`, `generative_ui`, `github`, `env-setup`, `migrate-workflows`, `web-app-development`). | `RUNTIME_TESTED` |
| **Workspace Rules (`AGENTS.md` & `.agents/rules/*.md`)** | `AGENTS.md` tanpa frontmatter (`always_on`); `.agents/rules/*.md` wajib ber-frontmatter `trigger: always_on \| model_decision \| glob \| manual` (`< 24.000` byte/file). | 3 aturan modular di `.agents/rules/` dibuat & divalidasi ukuran byte dan frontmatter-nya. | `UNIT_TESTED` |
| **Mode Workspace Subagent (`inherit` vs `branch`/`share`)** | App/CLI lokal mendukung `inherit`, `branch` (Git worktree), dan `share`. | Di lingkungan remote devbox ini, kebijakan sistem mewajibkan `Workspace="inherit"`; mode `branch` dan `share` **tidak didukung**. Eksklusivitas tulis dijaga deterministik oleh `TaskHandoffManager`. | `HONEST_LIMITATION_DOCUMENTED` |
| **Multi-Agent Slash Modes (`/swarm`, `/boost`, `/teamwork`)** | Dipicu pengguna dari kotak prompt UI/CLI Antigravity. | Direkomendasikan sesuai skala tugas; tidak dapat dipanggil paksa oleh agen dari dalam Python. | `USER_INITIATED_SURFACE` |

---

## 2. Laporan Routing Model (`Gemini 4 Neon` & `Gemini 4 Hydrogen` vs Subagent Enum)

1. **Tingkat Sesi Antigravity (`Orchestrator` Selector)**:
   - Berdasarkan dokumentasi resmi `https://antigravity.google/docs/models`, mode **Orchestrator** pada Google AI Pro / Google AI Ultra memasangkan **Gemini 4 Neon** (planner utama berkapasitas 512K token, level `Low`/`Medium`/`High`/`Extra`) dengan **Gemini 4 Hydrogen** (executor cepat untuk pencarian, pengeditan kode, dan pengujian). Pada akun Gemini Enterprise, Orchestrator memasangkan **Gemini 4 Carbon (High)** dengan **Gemini 4 Hydrogen (High)**.
   - Pemilihan pasangan model sesi ini dikendalikan langsung oleh pengguna melalui menu **Model Selector** di Antigravity App/CLI; kode Python XDX Studio tidak mengarang atau memalsukan ID model internal.
2. **Tingkat Pemanggilan Tool `invoke_subagent`**:
   - Skema tool `invoke_subagent` pada runtime menerima enum `Model` terbatas: `["inherit", "flash_lite", "flash", "pro"]`.
   - Sesuai aturan sistem Antigravity, XDX Studio menggunakan `Model="inherit"` secara default kecuali pengguna secara eksplisit memerintahkan tier berbeda (misal reviewer lintas model/tier).

---

## 3. Laporan Kebijakan Izin Agen (`governance/permission_policy.py`)

- **Default-Deny & Validasi Tool**: Setiap tool di luar `OFFICIAL_ANTIGRAVITY_TOOLS` atau tool MCP yang belum terklasifikasi langsung ditolak (`PermissionDeniedError` / `UnclassifiedMCPToolError`).
- **Isolasi Baca-Saja Independent Verification (`17`–`20`)**: `preproduction_verifier`, `visual_critic`, `technical_auditor`, dan `success_auditor` ditolak keras apabila mencoba memakai `write_to_file`/`replace_file_content` atau mengklaim `owned_artifacts` (`ReadOnlyAgentOwnershipError`), serta diawasi checksum SHA-256 sebelum dan sesudah review (`SilentArtifactMutationError`).
- **Eksklusivitas Scene Blender (`09`)**: Hanya `blender_specialist` (`max_concurrent_instances = 1`) yang diizinkan memanggil tool mutasi MCP Blender, dan hanya setelah `ExecutionAuthorizationContext` berstatus `APPROVED` terverifikasi live.
- **Status Lifecycle Hooks (`.agents/hooks.json`)**: Dokumentasi kontrak `PreToolUse` (`decision: "deny" | "ask" | "allow"`) telah dipetakan penuh dan dijadwalkan untuk implementasi `governance/execution_guard.py` pada **Phase 01.6D**; Phase 01.6A belum mengklaim pemblokiran berbasis `hooks.json` selesai.
