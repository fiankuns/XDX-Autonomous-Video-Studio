"""Visual Quality Control & Bounded Self-Correction Engine (v3.3).

Executes real FFprobe/FFmpeg full decode verification and OpenCV frame signal measurements
(luminance, contrast, sharpness, blank/corrupt frame detection), outputting schema-valid
QC reports with a strict max-3-retries-per-shot self-correction loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2 as cv
import jsonschema
import numpy as np

from engines.ffmpeg_engine import FFmpegEngine
from governance.phase_scope import PHASE02A_DELIVERY_PROFILE, audio_policy

ROOT_DIR = Path(__file__).resolve().parent.parent
QC_SCHEMA_PATH = ROOT_DIR / "schemas" / "qc_report.schema.json"


class VisualQualityControlEngine:
    """Runs technical media verification + OpenCV visual signal inspection + self-correction planning."""

    MAX_RETRIES_PER_SHOT = 3
    SILENCE_PEAK_DBFS = -90.0

    def __init__(self, ffmpeg: FFmpegEngine | None = None, schema_path: Path | None = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegEngine()
        self._schema = json.loads((schema_path or QC_SCHEMA_PATH).read_text(encoding="utf-8"))

    def evaluate_video(
        self,
        video_path: Path,
        *,
        require_audio: bool = False,
        current_attempt: int = 0,
        delivery_profile: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a rendered MP4.

        ``delivery_profile="VISUAL_ONLY_BENCHMARK"`` (Phase 02A): a missing audio stream is never a defect, the
        expected export has no audio track, and a track that is present anyway (silent or not) is only a low
        severity WARN. ``require_audio=True`` is contradictory with that profile and is rejected.
        """
        defects: list[dict[str, Any]] = []
        policy = audio_policy(delivery_profile) if delivery_profile else None
        if policy and policy["delivery_profile"] == PHASE02A_DELIVERY_PROFILE and require_audio:
            raise ValueError("require_audio=True contradicts delivery_profile VISUAL_ONLY_BENCHMARK (audio deferred to Phase 04)")
        if policy and policy["missing_audio_is_defect"]:
            require_audio = True
        if not video_path.is_file() or video_path.stat().st_size == 0:
            report = {
                "schema_version": "3.3.0",
                "target_file": str(video_path),
                "overall_status": "HARD_FAIL",
                "technical_qc": {
                    "exists": video_path.is_file(),
                    "non_empty": False,
                    "size_bytes": 0,
                    "full_decode_ok": False,
                    "decode_errors": ["Target file missing or 0 bytes"],
                    "has_video_stream": False,
                    "has_audio_stream": False,
                    "codec_video": None,
                    "codec_audio": None,
                    "width": None,
                    "height": None,
                    "fps": None,
                    "duration_s": None,
                    "decoded_frames": 0,
                },
                "visual_qc": {
                    "sampled_frames": 0,
                    "mean_luma": 0.0,
                    "contrast_std": 0.0,
                    "sharpness_laplacian": 0.0,
                    "blank_or_corrupt_frames": 0,
                    "dimension_scores": {"technical_integrity": 0.0},
                },
                "defects": [
                    {
                        "defect_id": "DEF_MISSING_FILE",
                        "severity": "critical",
                        "shot_id": None,
                        "description": "Output video missing or empty",
                        "recommended_fix": "Re-run shot/master render and verify disk output path.",
                    }
                ],
                "self_correction_plan": self._build_retry_plan(
                    defects_present=True,
                    current_attempt=current_attempt,
                    actions=["Re-execute render job and check FFmpeg exit status."],
                ),
            }
            if policy:
                report["audio_policy"] = {**policy, "audio_track_present": False, "audio_peak_dbfs": None}
            jsonschema.validate(instance=report, schema=self._schema)
            return report

        probe = self.ffmpeg.probe_media(video_path)
        decode = self.ffmpeg.verify_full_decode(video_path)

        cap = cv.VideoCapture(str(video_path))
        lumas: list[float] = []
        contrasts: list[float] = []
        sharpness_vals: list[float] = []
        blank_frames = 0
        total_decoded = 0
        idx = 0
        while cap.grab():
            total_decoded += 1
            if idx % 3 == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
                    mean_l = float(np.mean(gray))
                    std_c = float(np.std(gray))
                    lap_var = float(cv.Laplacian(gray, cv.CV_64F).var())
                    lumas.append(mean_l)
                    contrasts.append(std_c)
                    sharpness_vals.append(lap_var)
                    if std_c < 1.5 or mean_l < 2.0 or mean_l > 253.0:
                        blank_frames += 1
            idx += 1
        cap.release()

        if not decode["ok"]:
            defects.append(
                {
                    "defect_id": "DEF_DECODE_CORRUPTION",
                    "severity": "critical",
                    "shot_id": None,
                    "description": f"FFmpeg decode errors: {decode['errors'][:2]}",
                    "recommended_fix": "Re-encode corrupt clip with libx264 yuv420p.",
                }
            )
        if require_audio and not probe["has_audio"]:
            defects.append(
                {
                    "defect_id": "DEF_MISSING_AUDIO",
                    "severity": "critical",
                    "shot_id": None,
                    "description": "Master delivery requires an AAC audio stream, but none was found.",
                    "recommended_fix": "Mux validated 48 kHz master WAV into Remotion/FFmpeg output.",
                }
            )
        audio_peak: float | None = None
        if policy and probe["has_audio"]:
            audio_peak = self.ffmpeg.measure_audio_peak_db(video_path)
            silent = audio_peak is None or audio_peak <= self.SILENCE_PEAK_DBFS
            if policy["delivery_profile"] == PHASE02A_DELIVERY_PROFILE:
                defects.append(
                    {
                        "defect_id": "DEF_UNNECESSARY_SILENT_AUDIO_TRACK" if silent else "DEF_AUDIO_OUT_OF_PHASE_SCOPE",
                        "severity": "low",
                        "shot_id": None,
                        "description": (
                            "Visual-only benchmark carries a silent audio track that is not needed."
                            if silent
                            else "Visual-only benchmark carries audible audio although audio is deferred to Phase 04."
                        ),
                        "recommended_fix": "Export without an audio track (Remotion renderMedia muted:true / ffmpeg -an).",
                    }
                )
            elif silent:
                defects.append(
                    {
                        "defect_id": "DEF_SILENT_AUDIO_TRACK",
                        "severity": "critical",
                        "shot_id": None,
                        "description": "Master delivery audio stream is digitally silent.",
                        "recommended_fix": "Mux the validated narration/music master before export.",
                    }
                )
        if blank_frames > 0:
            defects.append(
                {
                    "defect_id": "DEF_BLANK_FRAMES",
                    "severity": "high",
                    "shot_id": None,
                    "description": f"Detected {blank_frames} near-blank or flat-exposure sampled frames.",
                    "recommended_fix": "Check asset load barrier, camera clipping planes, and lighting intensity.",
                }
            )

        mean_luma = round(float(np.mean(lumas)) if lumas else 0.0, 3)
        contrast_std = round(float(np.mean(contrasts)) if contrasts else 0.0, 3)
        sharp_score = round(float(np.mean(sharpness_vals)) if sharpness_vals else 0.0, 3)

        exposure_score = 4.5 if 25.0 <= mean_luma <= 225.0 else 2.0
        contrast_score = 4.5 if contrast_std >= 12.0 else 2.0
        integrity_score = 5.0 if (decode["ok"] and probe["has_video"]) else 0.0

        critical_any = any(d["severity"] == "critical" for d in defects)
        overall = "HARD_FAIL" if critical_any else ("WARN" if defects else "PASS")

        report = {
            "schema_version": "3.3.0",
            "target_file": str(video_path),
            "overall_status": overall,
            "technical_qc": {
                "exists": True,
                "non_empty": probe["size_bytes"] > 0,
                "size_bytes": probe["size_bytes"],
                "full_decode_ok": decode["ok"],
                "decode_errors": decode["errors"],
                "has_video_stream": probe["has_video"],
                "has_audio_stream": probe["has_audio"],
                "codec_video": probe["codec_video"],
                "codec_audio": probe["codec_audio"],
                "width": probe["width"],
                "height": probe["height"],
                "fps": probe["fps"],
                "duration_s": probe["duration_s"],
                "decoded_frames": total_decoded,
            },
            "visual_qc": {
                "sampled_frames": len(lumas),
                "mean_luma": mean_luma,
                "contrast_std": contrast_std,
                "sharpness_laplacian": sharp_score,
                "blank_or_corrupt_frames": blank_frames,
                "dimension_scores": {
                    "technical_integrity": integrity_score,
                    "exposure_balance": exposure_score,
                    "contrast_separation": contrast_score,
                },
            },
            "defects": defects,
            "self_correction_plan": self._build_retry_plan(
                defects_present=len(defects) > 0,
                current_attempt=current_attempt,
                actions=[d["recommended_fix"] for d in defects],
            ),
        }
        if policy:
            report["audio_policy"] = {
                **policy,
                "audio_track_present": bool(probe["has_audio"]),
                "audio_peak_dbfs": None if audio_peak is None or audio_peak == float("-inf") else round(audio_peak, 2),
            }
        jsonschema.validate(instance=report, schema=self._schema)
        return report

    def _build_retry_plan(
        self,
        *,
        defects_present: bool,
        current_attempt: int,
        actions: list[str],
    ) -> dict[str, Any]:
        clamped_attempt = max(0, min(int(current_attempt), self.MAX_RETRIES_PER_SHOT))
        can_retry = defects_present and clamped_attempt < self.MAX_RETRIES_PER_SHOT
        if defects_present and not can_retry:
            actions = [*actions, "Max 3 self-correction attempts exhausted; halt shot as PARTIAL/BLOCKED and report to user."]
        return {
            "max_retries_per_shot": self.MAX_RETRIES_PER_SHOT,
            "current_attempt": clamped_attempt,
            "requires_re_render": can_retry,
            "requires_new_approval": False,
            "actions": actions,
        }
