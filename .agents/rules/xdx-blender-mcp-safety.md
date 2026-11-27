---
trigger: model_decision
description: "Gunakan aturan ini saat berinteraksi dengan XDX Blender Studio MCP, skrip bpy Blender Android Vivo X200 Pro, atau adapter MCP."
---
# XDX Studio v4.0 — Blender MCP & Vivo X200 Pro Safety Rule

1. Sebelum proyek mencapai status `APPROVED` melalui persetujuan pengguna yang sah, hanya tool dalam `READ_ONLY_ALLOWLIST` (`get_mobile_device_profile`, `get_scene_info`) dan `look` non-rendered yang boleh dipanggil. Tool tak dikenal wajib ditolak (`UnclassifiedMCPToolError`).
2. Hanya **satu** instance `blender_specialist` (`max_concurrent_instances = 1`) yang boleh memutasi satu scene Blender pada waktu yang sama.
3. Pertahankan seluruh batas `mobile_guard` pada perangkat Android ARM64 **Vivo X200 Pro** dan gunakan `bpy.app.tempdir` (dilarang keras menulis ke `/tmp`).
4. Bedakan secara jujur ke-6 tingkat verifikasi MCP: `source_code_discovery`, `in_process_protocol_test`, `local_http_integration_test`, `live_remote_relay_reachable`, `live_android_blender_connected`, dan `actual_visual_feedback_verified`.
