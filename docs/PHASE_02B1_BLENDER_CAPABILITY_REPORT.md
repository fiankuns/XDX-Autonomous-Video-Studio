# Phase 02B.1 — Live Blender MCP Capability Verification (baca-saja)

Hasil bukti: `docs/evidence/phase02b1/blender_capability_probe.json`. Benchmark: `docs/benchmarks/bench_p02b_char_10s.json` (PLANNED, belum dieksekusi).

## Terverifikasi (benar-benar dijalankan)
- Koneksi live ke Blender 5.3.0 di Vivo X200 Pro (Dimensity 9400, Immortalis-G925, 8 core), Python 3.13.
- Penemuan tool MCP: 8 tool (execute_blender_code, create_primitive, get_mobile_device_profile, get_scene_info, look, modify_object, set_material, configure_mobile_guard).
- `get_mobile_device_profile`, `get_scene_info`, introspeksi `bpy` baca-saja (hash scene sama sebelum dan sesudah), tangkapan `look` viewport material 256 px (±0,5 detik).

## Terdeteksi saja (API ada, BELUM diuji jalan)
- Render: hanya `BLENDER_EEVEE`; Cycles TIDAK tersedia.
- Operator terdaftar: armature, IK, constraint, parent, modifier, keyframe, bake, export/import glTF, export FBX, render.
- Constraint: IK, Spline IK, Damped Track, Track To, Copy Rotation/Location, Limit Rotation, Stretch To, dll. Modifier Armature/Subsurf ada.
- Add-on aktif: io_scene_gltf2, io_scene_fbx, pose_library, add-on XDX.

## Temuan penting
1. **Sesi Blender berubah di tengah pemeriksaan.** Panggilan pertama `get_scene_info` melaporkan scene Badgir (79 objek); panggilan berikutnya melaporkan scene default (3 objek, belum disimpan, tidak dirty). Pekerjaan Badgir sebelumnya tidak ada di sesi live. Artinya: scene tidak persisten, jadi setiap tahap 02B harus menyimpan/ekspor hasil.
2. Guard mobile: maks render 640 px, 32 sampel, ANR 3,5 detik per panggilan. Belum diketahui apakah 640 berlaku per sisi (portrait 540×960 mungkin melebihi).
3. Scene default fps 24 (produksi 30), resolusi 1920×1080: perubahan itu mutasi, ditunda.

## Belum bisa ditentukan (perlu uji di 02B.2)
Perilaku IK di build ini, waktu render per frame, batas memori karakter+diorama, fidelitas GLB ke Three.js, API koleksi bone.

## Kepatuhan
Tidak ada modeling, mutasi scene, render, GLB, `configure_mobile_guard`, atau perubahan pairing/auth/relay/repo Blender. Token tidak disimpan. Execution Guard dan Trusted Approval tetap berlaku; probe yang dijalankan hanya introspeksi tanpa tulis. Audio ditunda ke Phase 04.

## Benchmark 02B (10 detik, 300 frame, 30 fps)
3 shot (B001 akting panas + kipas, B002 menoleh + cut, B003 macro remote + callout + pergeseran cahaya) dengan Bima dari character bible, teknik REF-001 (akting), REF-002 (cutaway/callout), REF-003 (pencahayaan, highlight objek). Kriteria sama dengan 02A. Eksekusi menunggu persetujuan Anda.
