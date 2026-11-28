"""FFmpeg & FFprobe Deterministic Media Processing & Validation Engine."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


class FFmpegEngine:
    """Executes real ffprobe inspection, full stream decode verification, and audio/video checks."""

    def is_available(self) -> bool:
        return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

    def version_info(self) -> dict[str, Any]:
        ffmpeg_bin = shutil.which("ffmpeg")
        ffprobe_bin = shutil.which("ffprobe")
        if not ffmpeg_bin or not ffprobe_bin:
            return {"available": False, "ffmpeg": None, "ffprobe": None}
        out = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, check=True).stdout
        first_line = out.splitlines()[0] if out else ""
        return {"available": True, "ffmpeg": ffmpeg_bin, "ffprobe": ffprobe_bin, "banner": first_line}

    def probe_media(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(f"Media file not found: {path}")
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        raw = json.loads(proc.stdout)
        streams = raw.get("streams", [])
        fmt = raw.get("format", {})
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        fps = None
        if v_stream and v_stream.get("r_frame_rate"):
            num_s, _, den_s = str(v_stream["r_frame_rate"]).partition("/")
            try:
                den = float(den_s) if den_s else 1.0
                fps = round(float(num_s) / den, 4) if den != 0 else None
            except ValueError:
                fps = None

        duration_s = None
        for cand in (
            v_stream.get("duration") if v_stream else None,
            fmt.get("duration"),
        ):
            if cand is not None:
                try:
                    val = float(cand)
                    if math.isfinite(val) and val > 0:
                        duration_s = round(val, 6)
                        break
                except ValueError:
                    pass

        return {
            "exists": True,
            "size_bytes": path.stat().st_size,
            "has_video": v_stream is not None,
            "has_audio": a_stream is not None,
            "codec_video": v_stream.get("codec_name") if v_stream else None,
            "codec_audio": a_stream.get("codec_name") if a_stream else None,
            "pix_fmt": v_stream.get("pix_fmt") if v_stream else None,
            "width": int(v_stream["width"]) if v_stream and "width" in v_stream else None,
            "height": int(v_stream["height"]) if v_stream and "height" in v_stream else None,
            "fps": fps,
            "duration_s": duration_s,
            "raw": raw,
        }

    def verify_full_decode(self, path: Path) -> dict[str, Any]:
        """Run `ffmpeg -v error -i <file> -f null -` to prove zero stream corruption."""
        if not path.is_file() or path.stat().st_size == 0:
            return {"ok": False, "errors": ["File missing or 0 bytes"]}
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        errs = [line.strip() for line in proc.stderr.splitlines() if line.strip()]
        return {"ok": proc.returncode == 0 and len(errs) == 0, "errors": errs}

    def measure_audio_peak_db(self, path: Path) -> float | None:
        """Max volume (dBFS) of the first audio stream via ``volumedetect``; None when there is no audio stream.

        Digital silence is returned as ``float('-inf')``.
        """
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0?", "-af", "volumedetect",
             "-vn", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        for line in proc.stderr.splitlines():
            if "max_volume:" in line:
                val = line.split("max_volume:", 1)[1].strip().split(" ")[0]
                try:
                    return float(val)
                except ValueError:
                    return float("-inf")
        return None
