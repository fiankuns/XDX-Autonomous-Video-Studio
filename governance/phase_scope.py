"""Phase 02A scope policy — VISUAL_ONLY_BENCHMARK (scope revision 2026-11-28).

All audio work (TTS, voice-over, music, sound effects, lip sync, audio mixing, forced alignment) is deferred to
Phase 04. Phase 02A spends its budget only on visual quality: characters & assets, semantic visual storytelling,
animation & object interaction, mechanism visualisation, camera, lighting/shadow/material/texture, composition &
transitions, independent visual QC and comparison against REF-002.

Rules enforced from this module:

* A render without audio is a valid ``VISUAL_ONLY_BENCHMARK``; a missing audio stream is never a QC defect.
* Export WITHOUT an audio track (Remotion ``muted: true``). A silent track that is present anyway is flagged as an
  unnecessary track (low severity, WARN) — it is not a QC failure.
* Captions remain the representation of the narration and are the yardstick for visual/story alignment.
* Tool calls or shell commands that would develop or generate audio are rejected with ``PhaseScopeDeferredError``.

This module does NOT relax any security rule: the trusted approval channel, canonical manifest and Phase 02
execution boundary in ``governance.trusted_approval`` are unchanged and still apply to every render.
"""

from __future__ import annotations

import re
from typing import Any

ACTIVE_PHASE = "02A"
PHASE02A_DELIVERY_PROFILE = "VISUAL_ONLY_BENCHMARK"
MASTER_DELIVERY_PROFILE = "MASTER_WITH_AUDIO"
DELIVERY_PROFILES = frozenset({PHASE02A_DELIVERY_PROFILE, MASTER_DELIVERY_PROFILE})
AUDIO_DEFERRED_TO_PHASE = "04"

DEFERRED_AUDIO_CAPABILITIES = frozenset(
    {"tts", "voice_over", "music", "sound_effects", "lip_sync", "audio_mix", "forced_alignment"}
)

VISUAL_FOCUS_AREAS = (
    "character_and_asset_quality",
    "semantic_visual_storytelling",
    "animation_and_object_interaction",
    "mechanism_visualization",
    "camera_and_cinematography",
    "lighting_shadow_material_texture",
    "composition_and_transitions",
    "independent_visual_qc",
    "reference_comparison_REF-002",
)

# Tool names (MCP or host) that generate / process audio.
_AUDIO_TOOL = re.compile(
    r"(generate_speech|text_to_speech|\btts\b|_tts_|tts_|speech_synth|voice_?over|design_voice|"
    r"generate_music|compose_music|music_gen|sound_effect|generate_sfx|\bsfx\b|lip_?sync|viseme|"
    r"audio_mix|mix_audio|ducking|forced_align|transcribe_audio)",
    re.IGNORECASE,
)
# Shell commands that run audio tooling.
_AUDIO_CMD = re.compile(
    r"(\b(piper|espeak(-ng)?|coqui|tts|rhubarb|whisper(\.cpp)?|faster-whisper|whisperx|sox|bark|elevenlabs)\b"
    r"|\bffmpeg\b.*(\s-(c:a|acodec)\s+(?!none)\w+|-af\s|loudnorm|amix|sidechaincompress|\.(wav|mp3|aac|flac|ogg|m4a)\b))",
    re.IGNORECASE,
)


class PhaseScopeDeferredError(PermissionError):
    """Raised when work outside the active phase scope (audio in Phase 02A) is requested."""

    code = "PHASE_SCOPE_DEFERRED"

    def __init__(self, message: str) -> None:
        super().__init__(f"[{self.code}] {message}")


def audio_policy(delivery_profile: str = PHASE02A_DELIVERY_PROFILE) -> dict[str, Any]:
    if delivery_profile not in DELIVERY_PROFILES:
        raise ValueError(f"Unknown delivery profile {delivery_profile!r}; expected one of {sorted(DELIVERY_PROFILES)}")
    if delivery_profile == PHASE02A_DELIVERY_PROFILE:
        return {
            "delivery_profile": PHASE02A_DELIVERY_PROFILE,
            "audio_track": "OMIT",
            "missing_audio_is_defect": False,
            "silent_audio_track": "WARN_UNNECESSARY_TRACK",
            "captions_represent_narration": True,
            "audio_deferred_to_phase": AUDIO_DEFERRED_TO_PHASE,
        }
    return {
        "delivery_profile": MASTER_DELIVERY_PROFILE,
        "audio_track": "REQUIRED",
        "missing_audio_is_defect": True,
        "silent_audio_track": "HARD_FAIL",
        "captions_represent_narration": False,
        "audio_deferred_to_phase": None,
    }


def assert_capability_in_scope(capability: str, *, phase: str = ACTIVE_PHASE) -> None:
    if phase == "02A" and capability in DEFERRED_AUDIO_CAPABILITIES:
        raise PhaseScopeDeferredError(
            f"'{capability}' is deferred to Phase {AUDIO_DEFERRED_TO_PHASE}; Phase 02A is {PHASE02A_DELIVERY_PROFILE} "
            "and must not spend agent quota on audio."
        )


def classify_audio_tool(tool_name: str) -> bool:
    return bool(_AUDIO_TOOL.search(str(tool_name or "")))


def classify_audio_command(command: str) -> bool:
    return bool(_AUDIO_CMD.search(str(command or "")))


def assert_tool_in_scope(tool_name: str, *, phase: str = ACTIVE_PHASE) -> None:
    if phase == "02A" and classify_audio_tool(tool_name):
        raise PhaseScopeDeferredError(
            f"Audio tool '{tool_name}' is out of scope in Phase 02A (deferred to Phase {AUDIO_DEFERRED_TO_PHASE})."
        )


def assert_command_in_scope(command: str, *, phase: str = ACTIVE_PHASE) -> None:
    if phase == "02A" and classify_audio_command(command):
        raise PhaseScopeDeferredError(
            f"Audio command is out of scope in Phase 02A (deferred to Phase {AUDIO_DEFERRED_TO_PHASE})."
        )


def remotion_render_options(delivery_profile: str = PHASE02A_DELIVERY_PROFILE) -> dict[str, Any]:
    """Render options for ``@remotion/renderer.renderMedia`` per delivery profile."""
    audio_policy(delivery_profile)  # validates
    if delivery_profile == PHASE02A_DELIVERY_PROFILE:
        # muted:true -> Remotion writes no audio stream at all (preferred over a silent AAC track).
        return {"codec": "h264", "pixelFormat": "yuv420p", "muted": True}
    return {"codec": "h264", "pixelFormat": "yuv420p", "audioCodec": "aac", "muted": False}
