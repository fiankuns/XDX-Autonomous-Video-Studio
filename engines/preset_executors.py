"""Executable Deterministic Preset Evaluators across 10 Production Domains (v3.4).

Provides real frame-indexed mathematical & pixel evaluators for:
1. Body animation (`evaluate_body_animation`)
2. Facial expression (`evaluate_facial_expression`)
3. Camera motion (`evaluate_camera_motion`)
4. Object motion (`evaluate_object_motion`)
5. Kinetic typography (`evaluate_kinetic_typography`)
6. Caption layout (`evaluate_caption_event`)
7. Transition (`evaluate_transition_state`)
8. Particle (`evaluate_particle_state`)
9. VFX image/color grade (`evaluate_vfx_grade` + `apply_vfx_grade_to_image`)
10. Audio event & BGM sidechain ducking (`evaluate_audio_ducking_envelope`)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _cubic_bezier_1d(u: float, p1y: float, p2y: float) -> float:
    t = _clamp01(u)
    inv = 1.0 - t
    return 3.0 * inv * inv * t * p1y + 3.0 * inv * t * t * p2y + t * t * t


def _damped_spring(frame: int, fps: int, *, mass: float = 0.8, damping: float = 12.0, stiffness: float = 180.0) -> float:
    if frame <= 0:
        return 0.0
    t = frame / max(1, fps)
    omega0 = math.sqrt(stiffness / max(0.05, mass))
    zeta = damping / (2.0 * math.sqrt(stiffness * max(0.05, mass)))
    if zeta < 1.0:
        omega_d = omega0 * math.sqrt(1.0 - zeta * zeta)
        val = 1.0 - math.exp(-zeta * omega0 * t) * (
            math.cos(omega_d * t) + (zeta / math.sqrt(1.0 - zeta * zeta)) * math.sin(omega_d * t)
        )
        return round(val, 6)
    return round(1.0 - (1.0 + omega0 * t) * math.exp(-omega0 * t), 6)


def _mulberry32(seed: int):
    state = seed & 0xFFFFFFFF

    def _next() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return _next


class PresetExecutorEngine:
    """Deterministic frame-based execution engine for motion, camera, caption, particle, VFX, and audio presets."""

    # 1. Object / Curve Motion
    def evaluate_object_motion(
        self,
        preset: dict[str, Any],
        *,
        local_frame: int,
        duration_frames: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        params = preset["parameters"]
        mtype = params.get("type", "cubic_bezier")
        u = _clamp01(local_frame / max(1, duration_frames - 1))

        if mtype == "spring":
            progress = _damped_spring(
                local_frame,
                fps,
                mass=float(params.get("mass", 0.8)),
                damping=float(params.get("damping", 12.0)),
                stiffness=float(params.get("stiffness", 180.0)),
            )
            squash = 0.0
        elif mtype == "elastic_out":
            amp = float(params.get("amplitude", 1.2))
            period_f = max(2.0, float(params.get("period_frames", 9.0)))
            progress = 1.0 if u >= 1.0 else (amp * math.pow(2.0, -8.0 * u) * math.sin((local_frame * 2.0 * math.pi) / period_f) + 1.0)
            squash = float(params.get("squash_stretch_factor", 0.1)) * (1.0 - u)
        else:
            cp = params.get("control_points", [0.42, 0.0, 0.18, 1.0])
            progress = _cubic_bezier_1d(u, float(cp[1]), float(cp[3]))
            squash = 0.0

        jitter = [0.0, 0.0, 0.0]
        if "micro_jitter_seed" in params:
            rng = _mulberry32(int(params["micro_jitter_seed"]) + local_frame * 17)
            amp_j = float(params.get("jitter_amp_m", 0.003))
            jitter = [round((rng() - 0.5) * 2.0 * amp_j, 6) for _ in range(3)]

        return {
            "preset_id": preset["id"],
            "local_frame": local_frame,
            "progress": round(progress, 6),
            "scale_xyz": [round(1.0 - squash * 0.5, 5), round(1.0 + squash, 5), round(1.0 - squash * 0.5, 5)],
            "jitter_offset_m": jitter,
        }

    # 2. Procedural Body Animation Keyframe Curve Generator
    def evaluate_body_animation(
        self,
        preset: dict[str, Any],
        *,
        local_frame: int,
        duration_frames: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        p = preset["parameters"]
        phase = (local_frame / max(1, int(p.get("cycle_frames", 90)))) * 2.0 * math.pi
        breath_pitch = float(p.get("chest_pitch_deg", 1.5)) * math.sin(phase)
        u = _clamp01(local_frame / max(1, duration_frames - 1))
        hip_shift = float(p.get("hip_shift_m", 0.0)) * math.sin(u * math.pi)
        head_yaw = float(p.get("head_yaw_deg", p.get("neck_lookback_deg", 0.0))) * _cubic_bezier_1d(u, 0.1, 0.95)
        blink_interval = int(p.get("blink_interval_frames", 75))
        blink_weight = 1.0 if (local_frame > 0 and (local_frame % blink_interval) in {0, 1, 2}) else 0.0

        return {
            "preset_id": preset["id"],
            "local_frame": local_frame,
            "ik_foot_lock": bool(p.get("ik_foot_lock", True)),
            "chest_pitch_deg": round(breath_pitch, 4),
            "hip_shift_x_m": round(hip_shift, 5),
            "head_yaw_deg": round(head_yaw, 4),
            "auto_blink_weight": blink_weight,
            "rig_execution_note": "Procedural curve evaluated deterministically; full armature deformation requires Blender bpy.",
        }

    # 3. Facial Expression Shape-Key Evaluator
    def evaluate_facial_expression(
        self,
        preset: dict[str, Any],
        *,
        local_frame: int,
        blend_in_frames: int = 8,
    ) -> dict[str, Any]:
        ramp = _clamp01(local_frame / max(1, blend_in_frames))
        weights: dict[str, float] = {}
        for k, v in preset["parameters"].items():
            if k == "pupil_scale":
                weights[k] = round(1.0 + (float(v) - 1.0) * ramp, 4)
            elif isinstance(v, (int, float)):
                weights[k] = round(float(v) * ramp, 4)
        return {"preset_id": preset["id"], "local_frame": local_frame, "shape_key_weights": weights}

    # 4. Camera Motion Evaluator
    def evaluate_camera_motion(
        self,
        camera_spec: dict[str, Any],
        motion_preset: dict[str, Any],
        *,
        local_frame: int,
        duration_frames: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        mot = self.evaluate_object_motion(motion_preset, local_frame=local_frame, duration_frames=duration_frames, fps=fps)
        w = _clamp01(mot["progress"])
        p0 = camera_spec["position_start"]
        p1 = camera_spec["position_end"]
        pos = [round(float(p0[i]) + (float(p1[i]) - float(p0[i])) * w + mot["jitter_offset_m"][i], 5) for i in range(3)]
        focal = float(camera_spec["focal_length_mm"])
        sensor = float(camera_spec["sensor_width_mm"])
        fov_deg = math.degrees(2.0 * math.atan(sensor / (2.0 * focal)))
        return {
            "local_frame": local_frame,
            "position_m": pos,
            "target_m": [float(v) for v in camera_spec["target"]],
            "focal_length_mm": focal,
            "horizontal_fov_deg": round(fov_deg, 4),
            "roll_deg": float(camera_spec.get("roll_deg", 0.0)),
            "dof_fstop": float(camera_spec.get("dof_fstop", 4.0)),
        }

    # 5. Kinetic Typography Evaluator
    def evaluate_kinetic_typography(
        self,
        typo_preset: dict[str, Any],
        text: str,
        *,
        local_frame: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        words = [w for w in text.split() if w]
        word_states = []
        for idx, word in enumerate(words):
            stagger_frame = local_frame - idx * 3
            scale = _damped_spring(max(0, stagger_frame), fps) if stagger_frame > 0 else 0.0
            opacity = _clamp01(stagger_frame / 5.0)
            word_states.append({"word": word, "scale": round(scale, 4), "opacity": round(opacity, 4)})
        return {
            "preset_id": typo_preset["id"],
            "heading_font": typo_preset["parameters"]["heading_font"],
            "body_font": typo_preset["parameters"]["body_font"],
            "words": word_states,
        }

    # 6. Caption Safe-Zone & Active Word Evaluator
    def evaluate_caption_event(
        self,
        caption_preset: dict[str, Any],
        cue_text: str,
        *,
        local_frame: int,
        cue_duration_frames: int,
        frame_width: int = 1080,
        frame_height: int = 1920,
    ) -> dict[str, Any]:
        p = caption_preset["parameters"]
        words = [w for w in cue_text.split() if w]
        max_lines = int(p.get("max_lines", 2))
        mid = max(1, math.ceil(len(words) / max_lines))
        lines = [" ".join(words[:mid])]
        if words[mid:]:
            lines.append(" ".join(words[mid:]))
        lines = lines[:max_lines]

        active_idx = min(max(0, len(words) - 1), int((local_frame / max(1, cue_duration_frames)) * max(1, len(words))))
        safe_bottom_px = round(frame_height * (1.0 - float(p.get("safe_bottom_pct", 0.18))))
        return {
            "preset_id": caption_preset["id"],
            "lines": lines,
            "line_count": len(lines),
            "active_word_index": active_idx,
            "active_word": words[active_idx] if words else "",
            "safe_box_px": [round(frame_width * 0.08), safe_bottom_px - 180, round(frame_width * 0.92), safe_bottom_px],
        }

    # 7. Editorial Transition Evaluator
    def evaluate_transition_state(
        self,
        transition_preset: dict[str, Any],
        *,
        overlap_frame_index: int,
    ) -> dict[str, Any]:
        p = transition_preset["parameters"]
        ov = int(p.get("overlap_frames", 0))
        if ov <= 0:
            return {"preset_id": transition_preset["id"], "type": "cut", "outgoing_alpha": 0.0, "incoming_alpha": 1.0, "offset_x_norm": 0.0}
        u = _clamp01(overlap_frame_index / max(1, ov))
        smooth = _cubic_bezier_1d(u, 0.2, 0.9)
        ttype = p.get("type", "dissolve")
        if ttype == "directional_whip":
            return {
                "preset_id": transition_preset["id"],
                "type": ttype,
                "outgoing_alpha": round(1.0 - smooth, 4),
                "incoming_alpha": round(smooth, 4),
                "offset_x_norm": round(1.0 - smooth, 4),
                "motion_blur": float(p.get("motion_blur_strength", 0.5)) * math.sin(u * math.pi),
            }
        return {
            "preset_id": transition_preset["id"],
            "type": "dissolve",
            "outgoing_alpha": round(1.0 - smooth, 4),
            "incoming_alpha": round(smooth, 4),
            "offset_x_norm": 0.0,
        }

    # 8. Deterministic Seeded Particle Evaluator
    def evaluate_particle_state(
        self,
        particle_preset: dict[str, Any],
        *,
        local_frame: int,
        fps: int = 30,
        sample_limit: int = 16,
    ) -> dict[str, Any]:
        p = particle_preset["parameters"]
        seed = int(p.get("seed", 101))
        count = min(sample_limit, int(p.get("count", 60)))
        rng = _mulberry32(seed)
        t = local_frame / max(1, fps)
        bounds = p.get("bounds_m", [3.0, 2.5, 3.0])
        gravity = float(p.get("gravity_mps2", 0.0))
        speed = float(p.get("speed_mps", p.get("burst_velocity_mps", 0.1)))

        particles = []
        for idx in range(count):
            x0 = (rng() - 0.5) * float(bounds[0])
            y0 = rng() * float(bounds[1])
            z0 = (rng() - 0.5) * float(bounds[2])
            vx = (rng() - 0.5) * speed
            vy = (rng() - 0.2) * speed
            vz = (rng() - 0.5) * speed
            px = x0 + vx * t
            py = y0 + vy * t + 0.5 * gravity * t * t
            pz = z0 + vz * t
            particles.append({"index": idx, "pos": [round(px, 5), round(py, 5), round(pz, 5)]})

        return {"preset_id": particle_preset["id"], "frame": local_frame, "sampled_particles": particles}

    # 9. VFX Color Grade & Vignette Pixel Processor
    def apply_vfx_grade_to_image(self, vfx_preset: dict[str, Any], image: Image.Image) -> Image.Image:
        p = vfx_preset["parameters"]
        arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        exposure_gain = math.pow(2.0, float(p.get("exposure_ev", 0.0)))
        arr = arr * exposure_gain

        # ACES Filmic rational approximation
        a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
        arr = np.clip((arr * (a * arr + b)) / (arr * (c * arr + d) + e), 0.0, 1.0)

        contrast = float(p.get("contrast", 1.0))
        arr = np.clip((arr - 0.5) * contrast + 0.5, 0.0, 1.0)

        sat = float(p.get("saturation", 1.0))
        luma = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2])[:, :, None]
        arr = np.clip(luma + (arr - luma) * sat, 0.0, 1.0)

        vig = float(p.get("vignette", 0.0))
        if vig > 0.0:
            h, w, _ = arr.shape
            yy, xx = np.ogrid[:h, :w]
            ny = (yy - h / 2.0) / max(1.0, h / 2.0)
            nx = (xx - w / 2.0) / max(1.0, w / 2.0)
            dist2 = nx * nx + ny * ny
            mask = np.clip(1.0 - vig * dist2 * 0.5, 0.25, 1.0)[:, :, None]
            arr = arr * mask

        out_u8 = np.clip(np.round(arr * 255.0), 0, 255).astype(np.uint8)
        return Image.fromarray(out_u8, mode="RGB")

    # 10. Audio Ducking & SFX Envelope Evaluator
    def evaluate_audio_ducking_envelope(
        self,
        audio_preset: dict[str, Any],
        *,
        total_frames: int,
        vo_intervals_frames: list[tuple[int, int]],
        fps: int = 30,
    ) -> dict[str, Any]:
        p = audio_preset["parameters"]
        duck_db = float(p.get("bgm_duck_db", -11.0))
        attack_f = max(1, round((float(p.get("duck_attack_ms", 60.0)) / 1000.0) * fps))
        release_f = max(1, round((float(p.get("duck_release_ms", 280.0)) / 1000.0) * fps))

        gains_db: list[float] = []
        cur = 0.0
        for f in range(total_frames):
            speaking = any(s <= f < e for s, e in vo_intervals_frames)
            target = duck_db if speaking else 0.0
            step = abs(duck_db) / (attack_f if speaking else release_f)
            if cur > target:
                cur = max(target, cur - step)
            elif cur < target:
                cur = min(target, cur + step)
            gains_db.append(round(cur, 3))

        return {
            "preset_id": audio_preset["id"],
            "target_lufs": float(p.get("target_lufs", -15.0)),
            "true_peak_dbtp": float(p.get("true_peak_dbtp", -1.0)),
            "bgm_gain_db_per_frame": gains_db,
        }
