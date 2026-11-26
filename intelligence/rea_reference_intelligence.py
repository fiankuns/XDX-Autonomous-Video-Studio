"""REA-Video Reference Intelligence Engine (v3.3).

Preserves and unifies:
1. Upstream `JuneYaooo/rea-video` CLI integration when installed (`rea-video --help`).
2. v3.1 `rea-video-id` FFprobe + FFmpeg scene candidate & frame evidence extractor.
3. v3.1 `adaptive_detect.py` OpenCV HSV histogram + Laplacian + pixel MAD detector.
4. Explicit separation of `measurement`, `observation`, `inference`, and `unknown`.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np
from PIL import Image


def extract_frame_features(im: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute subtitle-safe HSV histogram, normalized RGB patch, and grayscale image."""
    small = cv.resize(im, (96, 128), interpolation=cv.INTER_AREA)[:94]
    hsv = cv.cvtColor(small, cv.COLOR_BGR2HSV)
    hist = cv.calcHist([hsv], [0, 1], None, [24, 12], [0, 180, 0, 256])
    hist = cv.normalize(hist, None, alpha=1, norm_type=cv.NORM_L1)
    gray = cv.cvtColor(small, cv.COLOR_BGR2GRAY)
    return small.astype(np.float32) / 255.0, hist, gray


def frame_feature_diff(
    a: tuple[np.ndarray, np.ndarray, np.ndarray],
    b: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> float:
    pixel = float(np.mean(np.abs(a[0] - b[0])))
    hist = float(cv.compareHist(a[1], b[1], cv.HISTCMP_BHATTACHARYYA))
    edge = float(np.mean(np.abs(cv.Laplacian(a[2], cv.CV_32F) - cv.Laplacian(b[2], cv.CV_32F))) / 255.0)
    return 0.55 * pixel + 0.40 * hist + 0.05 * min(edge, 1.0)


def adaptive_detect_candidates(video_path: Path) -> dict[str, Any]:
    """Run OpenCV adaptive MAD cut & sustained-change candidate detection (v3.1 compatible)."""
    cap = cv.VideoCapture(str(video_path))
    fps = float(cap.get(cv.CAP_PROP_FPS))
    if not cap.isOpened() or fps <= 0:
        raise ValueError(f"Video/FPS unavailable for {video_path}")

    scores: list[float] = []
    frames: list[int] = []
    prev = None
    idx = 0
    stride = max(1, round(fps / 15.0))

    while cap.grab():
        if idx % stride == 0:
            ok, im = cap.retrieve()
            if not ok:
                break
            now = extract_frame_features(im)
            if prev is not None:
                scores.append(frame_feature_diff(prev, now))
                frames.append(idx)
            prev = now
        idx += 1
    cap.release()

    s = np.array(scores, dtype=np.float64)
    ts = np.array(frames, dtype=np.float64) / fps if len(frames) else np.array([], dtype=np.float64)
    hits: list[dict[str, Any]] = []

    for i, val in enumerate(s):
        window = s[max(0, i - 30) : min(len(s), i + 31)]
        med = float(np.median(window))
        mad = float(np.median(np.abs(window - med)))
        threshold = max(0.075, med + 5.0 * 1.4826 * mad, med * 2.2)
        if val >= threshold and val >= float(np.max(s[max(0, i - 2) : min(len(s), i + 3)])):
            hits.append(
                {
                    "time_s": round(float(ts[i]), 3),
                    "score": round(float(val), 4),
                    "threshold": round(threshold, 4),
                    "type": "abrupt_candidate",
                }
            )

    sustained: list[dict[str, Any]] = []
    run: list[int] = []
    min_run = max(4, round(0.35 * fps / stride))
    for i, val in enumerate(s):
        if val >= 0.035:
            run.append(i)
        else:
            if len(run) >= min_run:
                sustained.append(
                    {
                        "start_s": round(float(ts[run[0]]), 3),
                        "end_s": round(float(ts[run[-1]]), 3),
                        "type": "sustained_change_candidate",
                    }
                )
            run = []
    if len(run) >= min_run:
        sustained.append(
            {
                "start_s": round(float(ts[run[0]]), 3),
                "end_s": round(float(ts[run[-1]]), 3),
                "type": "sustained_change_candidate",
            }
        )

    merged: list[dict[str, Any]] = []
    for h in hits:
        if merged and h["time_s"] - merged[-1]["time_s"] < 0.35:
            if h["score"] > merged[-1]["score"]:
                merged[-1] = h
        else:
            merged.append(h)

    return {
        "source": video_path.name,
        "fps": fps,
        "decoded_frames": idx,
        "sample_stride_frames": stride,
        "abrupt_candidates": merged,
        "sustained_change_candidates": sustained,
        "warning": (
            "Heuristic candidates; visual review required. Sustained changes may be camera/object motion. "
            "No certified recall or precision."
        ),
    }


class REAReferenceIntelligence:
    """Reference video deconstruction & Style Bible synthesis engine."""

    def upstream_cli_available(self) -> bool:
        return shutil.which("rea-video") is not None

    def analyze_video(
        self,
        video_path: Path,
        output_dir: Path,
        *,
        scene_threshold: float = 0.30,
    ) -> dict[str, Any]:
        src = video_path.resolve()
        out = output_dir.resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Reference video not found: {src}")
        for binary in ("ffmpeg", "ffprobe"):
            if not shutil.which(binary):
                raise RuntimeError(f"Required media binary '{binary}' missing from PATH")

        out.mkdir(parents=True, exist_ok=True)
        frames_dir = out / "frames"
        frames_dir.mkdir(exist_ok=True)

        meta = json.loads(
            subprocess.run(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(src)],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        v_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
        if not v_stream:
            raise ValueError("No video stream in reference input")

        duration = float(v_stream.get("duration") or meta["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid video duration")

        scene_proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-i",
                str(src),
                "-an",
                "-vf",
                f"scale=320:-2,select='gt(scene,{scene_threshold})',showinfo",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        raw_pts = [float(x) for x in re.findall(r"pts_time:([-+0-9.eE]+)", scene_proc.stderr)]
        cuts = [0.0]
        for t in sorted(set(raw_pts)):
            if t > cuts[-1] + 0.08 and t < duration - 0.08:
                cuts.append(t)
        cuts.append(duration)

        shots: list[dict[str, Any]] = []
        thumb_paths: list[Path] = []
        for idx, (start_s, end_s) in enumerate(zip(cuts, cuts[1:]), 1):
            sid = f"S{idx:03d}"
            evidence: list[dict[str, Any]] = []
            for label, t in [
                ("start", start_s),
                ("mid", (start_s + end_s) / 2.0),
                ("end", max(start_s, end_s - min(0.08, (end_s - start_s) / 3.0))),
            ]:
                frame_file = frames_dir / f"{sid}_{label}.jpg"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-nostdin",
                        "-y",
                        "-ss",
                        f"{t:.6f}",
                        "-i",
                        str(src),
                        "-map",
                        "0:v:0",
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale=640:-2",
                        str(frame_file),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if label == "mid" and frame_file.is_file():
                    thumb_paths.append(frame_file)
                evidence.append(
                    {
                        "requested_time_s": round(t, 6),
                        "file": str(frame_file.relative_to(out)) if frame_file.is_file() else None,
                    }
                )

            shots.append(
                {
                    "id": sid,
                    "start_s": round(start_s, 6),
                    "end_s": round(end_s, 6),
                    "duration_s": round(end_s - start_s, 6),
                    "frames": evidence,
                    "status": "candidate_unreviewed",
                }
            )

        adaptive = adaptive_detect_candidates(src)
        contact_sheet = self._build_contact_sheet(thumb_paths, out / "contact_sheet.jpg")

        report = {
            "schema": "rea-video-id.v3.3",
            "upstream_rea_video_cli_installed": self.upstream_cli_available(),
            "measurements": {
                "duration_s": round(duration, 6),
                "width": int(v_stream.get("width", 0)),
                "height": int(v_stream.get("height", 0)),
                "codec": v_stream.get("codec_name"),
                "fps": adaptive["fps"],
                "decoded_frames": adaptive["decoded_frames"],
            },
            "ffmpeg_scene_candidates": shots,
            "adaptive_opencv_candidates": adaptive,
            "contact_sheet": str(contact_sheet.relative_to(out)) if contact_sheet else None,
            "epistemic_boundaries": {
                "measured": ["container_duration", "resolution", "codec", "decoded_frame_count"],
                "heuristic_candidates": ["ffmpeg_scene_cuts", "opencv_abrupt_and_sustained_candidates"],
                "unknown_without_extra_tools": [
                    "original_3d_engine_identity",
                    "original_generation_prompts",
                    "verified_asr_transcript",
                    "stem_separated_bgm_source",
                ],
            },
        }
        (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (out / "reference_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (out / "timeline.json").write_text(
            json.dumps(
                {
                    "schema": "rea-video-id.baseline.v1",
                    "duration_s": duration,
                    "threshold": scene_threshold,
                    "shots": shots,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        md_lines = [
            f"# Analisis Referensi REA-Video v3.3 — `{src.name}`",
            "",
            f"- **Durasi Terukur**: {duration:.3f} detik ({adaptive['decoded_frames']} frame @ {adaptive['fps']:.2f} fps)",
            f"- **Resolusi & Codec**: {v_stream.get('width')}x{v_stream.get('height')} (`{v_stream.get('codec_name')}`)",
            f"- **Kandidat Shot FFmpeg**: {len(shots)} segmen kandidat",
            f"- **Kandidat Abrupt OpenCV**: {len(adaptive['abrupt_candidates'])} kandidat",
            f"- **Upstream `rea-video` CLI Terpasang**: `{self.upstream_cli_available()}`",
            "",
            "| Shot | Mulai (s) | Akhir (s) | Durasi (s) | Status |",
            "|---|---:|---:|---:|---|",
            *[
                f"| {s['id']} | {s['start_s']:.3f} | {s['end_s']:.3f} | {s['duration_s']:.3f} | `{s['status']}` |"
                for s in shots
            ],
            "",
            "## Batasan Bukti",
            "- Kandidat cut adalah heuristik sinyal visual, bukan kebenaran mutlak sebelum inspeksi gambar.",
            "- Tidak mengklaim engine asli, prompt asli, atau transkripsi ASR tanpa alat yang diverifikasi.",
        ]
        (out / "REPORT_BASELINE.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        return report

    @staticmethod
    def _build_contact_sheet(images: list[Path], target: Path, cols: int = 3) -> Path | None:
        valid = [p for p in images if p.is_file()]
        if not valid:
            return None
        opened = [Image.open(p).convert("RGB") for p in valid[:12]]
        cell_w, cell_h = 320, int(320 * opened[0].height / max(1, opened[0].width))
        rows = math.ceil(len(opened) / cols)
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), color=(15, 18, 24))
        for i, im in enumerate(opened):
            resized = im.resize((cell_w, cell_h))
            r, c = divmod(i, cols)
            sheet.paste(resized, (c * cell_w, r * cell_h))
            im.close()
        sheet.save(target, format="JPEG", quality=85)
        return target
