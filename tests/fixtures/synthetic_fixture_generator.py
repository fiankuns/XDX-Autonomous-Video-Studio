"""Deterministic Synthetic MP4 Test Fixture Generator (Phase 01.6C Section 4.E).

Ensures external audit environments can always reproduce REA-Video and Visual QC tests even if
``tests/fixtures/synthetic.mp4`` was stripped during archive transport. Generates a 4.0-second
(120 frames @ 30fps, 320x240) multi-scene MP4 with four distinct color/pattern segments at
0-1s, 1-2s, 2-3s (high-contrast cut), and 3-4s so both FFmpeg scene detection and OpenCV
adaptive MAD detection trigger deterministically.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ensure_deterministic_synthetic_mp4(target_path: Path) -> Path:
    """Return ``target_path`` if already present and non-empty, else generate it deterministically."""
    if target_path.is_file() and target_path.stat().st_size > 1024:
        return target_path

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError(f"Missing '{target_path}' and 'ffmpeg' binary is unavailable to regenerate it.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = (
        "color=c=0x1e3a5f:s=320x240:r=30:d=1.0,drawbox=x=20:y=20:w=90:h=90:color=0xf4a261:t=fill[v0];"
        "color=c=0x2a5c84:s=320x240:r=30:d=1.0,drawbox=x=160:y=30:w=110:h=110:color=0xe9c46a:t=fill[v1];"
        "color=c=0xf1faee:s=320x240:r=30:d=1.0,drawbox=x=40:y=80:w=240:h=80:color=0xe63946:t=fill[v2];"
        "color=c=0x264653:s=320x240:r=30:d=1.0,drawbox=x=90:y=40:w=140:h=160:color=0x2a9d8f:t=fill[v3];"
        "[v0][v1][v2][v3]concat=n=4:v=1:a=0[outv]"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "30",
        "-crf",
        "23",
        str(target_path),
    ]
    subprocess.run(cmd, check=True, timeout=30)
    return target_path
