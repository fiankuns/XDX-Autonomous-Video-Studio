"""Whisper & Caption Alignment Adapter + Rhubarb Viseme Lip-Sync Adapter.

Strictly distinguishes real ASR/alignment execution from deterministic script-estimated
cue timing (never claiming forced alignment when an ASR binary/model is absent).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

PRESTON_BLAIR_VISEMES = ("A", "B", "C", "D", "E", "F", "G", "H", "X")


class WhisperCaptionAdapter:
    """Detects available local Whisper engines and formats Remotion/SRT captions."""

    def detect_backends(self) -> dict[str, Any]:
        whisper_cpp = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
        whisperx_bin = shutil.which("whisperx")
        faster_whisper_installed = False
        try:
            import faster_whisper  # type: ignore  # noqa: F401

            faster_whisper_installed = True
        except ImportError:
            pass

        return {
            "whisper_cpp_binary": whisper_cpp,
            "faster_whisper_python": faster_whisper_installed,
            "whisperx_binary": whisperx_bin,
            "any_asr_ready": bool(whisper_cpp or faster_whisper_installed or whisperx_bin),
        }

    def build_script_estimated_captions(
        self,
        narration_segments: list[dict[str, Any]],
        *,
        max_words_per_cue: int = 6,
    ) -> dict[str, Any]:
        """Generate deterministic caption cues & SRT from planned narration segments."""
        cues: list[dict[str, Any]] = []
        cue_idx = 1
        for seg in narration_segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            start_s = float(seg["start_time_s"])
            end_s = float(seg["end_time_s"])
            words = text.split()
            chunks = [words[i : i + max_words_per_cue] for i in range(0, len(words), max_words_per_cue)]
            total_words = max(1, len(words))
            cursor = start_s
            for chunk in chunks:
                ratio = len(chunk) / total_words
                dur = (end_s - start_s) * ratio
                c_end = min(end_s, cursor + dur)
                cues.append(
                    {
                        "cue_id": f"CAP_{cue_idx:03d}",
                        "shot_id": seg.get("shot_id"),
                        "start_s": round(cursor, 3),
                        "end_s": round(c_end, 3),
                        "text": " ".join(chunk),
                        "alignment_source": "script_estimated_pre_tts",
                    }
                )
                cursor = c_end
                cue_idx += 1

        return {
            "alignment_verified_by_asr": False,
            "note": "Estimated from narration WPM schedule prior to WAV TTS generation; re-align after actual WAV exists.",
            "cues": cues,
            "srt": self.to_srt(cues),
        }

    @staticmethod
    def to_srt(cues: list[dict[str, Any]]) -> str:
        def _fmt_ts(sec: float) -> str:
            ms_total = max(0, round(sec * 1000))
            hrs, rem = divmod(ms_total, 3_600_000)
            mins, rem = divmod(rem, 60_000)
            secs, ms = divmod(rem, 1000)
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

        blocks: list[str] = []
        for idx, cue in enumerate(cues, 1):
            blocks.append(
                f"{idx}\n{_fmt_ts(float(cue['start_s']))} --> {_fmt_ts(float(cue['end_s']))}\n{cue['text']}"
            )
        return "\n\n".join(blocks) + ("\n" if blocks else "")


class RhubarbLipSyncAdapter:
    """Wraps DanielSWolf/rhubarb-lip-sync CLI if present; enforces off-screen VO lock otherwise."""

    def is_available(self) -> bool:
        return shutil.which("rhubarb") is not None

    def extract_visemes_or_fallback(
        self,
        wav_path: Path | None,
        *,
        has_onscreen_dialogue: bool,
    ) -> dict[str, Any]:
        if not has_onscreen_dialogue:
            return {
                "mode": "offscreen_vo",
                "preset_id": "lip_offscreen_narrator_lock",
                "rhubarb_executed": False,
                "cues": [],
                "note": "Off-screen narrator active; mouth remains on expression rig without fake lip-sync.",
            }

        rhubarb_bin = shutil.which("rhubarb")
        if rhubarb_bin and wav_path and wav_path.is_file():
            proc = subprocess.run(
                [rhubarb_bin, "-f", "json", str(wav_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            parsed = json.loads(proc.stdout)
            return {
                "mode": "viseme_track",
                "preset_id": "lip_rhubarb_preston_blair_9",
                "rhubarb_executed": True,
                "cues": parsed.get("mouthCues", []),
            }

        return {
            "mode": "blocked_or_offscreen_fallback",
            "preset_id": "lip_offscreen_narrator_lock",
            "rhubarb_executed": False,
            "valid_viseme_set": list(PRESTON_BLAIR_VISEMES),
            "cues": [],
            "note": "Rhubarb binary or dialogue WAV not yet available; defaulting to off-screen VO to prevent fake lip-sync.",
        }
