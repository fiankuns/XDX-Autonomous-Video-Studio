# Arsitektur Sistem XDX Autonomous Video Studio v3.3

## 1. Evolusi dari v3.1 ke v3.3
Seluruh fondasi `XDX_Autonomous_Video_Studio_v3_1` dipertahankan penuh:
- Kontrak 11 berkas inti pra-produksi dengan sidik jari SHA-256 kanonis (`scripts/approval_gate.py`).
- Detektor kandidat cut adaptif OpenCV (`scripts/adaptive_detect.py`) dan baseline FFprobe/FFmpeg (`scripts/rea_analyze.py`).
- Protokol larangan substitusi engine secara diam-diam dan wajib berhenti pada `WAITING_APPROVAL`.

Pembaruan utama pada **v3.3**:
1. **14 Modul Core Intelligence Terimplementasi**: Mampu dijalankan dan diuji secara otomatis lintas 8 genre tunggal maupun kombinasi genre.
2. **11 Komponen Intelligent Asset Management**: Mencakup alur pengadaan 9 tahap, validasi lisensi fail-closed, cache SHA-256 terisolasi di `.xdx_cache/`, generator glTF 2.0 prosedural, harmonisasi Global Style Bible, konversi sumbu lintas engine (`+Z` Blender ↔ `+Y` glTF/Three.js), dan retargeting tulang karakter.
3. **16 Production Preset Libraries**: Seluruhnya divalidasi terhadap `schemas/preset_library.schema.json`.
4. **13-Item Approval Gate Manifest**: Memvalidasi kelengkapan 13 komponen pra-produksi sebelum izin render diberikan.
5. **Cross-Project XDX Blender MCP Adapter**: Mendukung discovery protokol nyata secara baca-saja tanpa memodifikasi `fiankuns/xdx-blender-studio`.

## 2. Kontrak Master Timeline Deterministik
- **Frame Indexing**: Zero-based integer interval `[start_frame, end_frame)` pada `30 fps` default (`1080x1920`, `9:16`).
- **Kontinuitas Ketat**: Shot `i` dimulai tepat pada `end_frame` shot `i - 1`; tidak boleh ada celah (*gap*) maupun tumpang-tindih tak terhitung (*unaccounted overlap*).
- **Konsistensi Lintas Engine**:
  - Skala dunia: `1.0 unit = 1.0 meter`.
  - Tone mapping & ruang warna: `ACESFilmic` → pengiriman `sRGB / Rec.709` (`yuv420p`).
  - Rentang material diorama: `roughness` dikunci ke `[0.30, 0.88]`, `metallic <= 0.45`, dengan bevel halus `6 mm`.
