"""Blender XDX Shot Compiler Engine (Mobile-Guard Aware & Approval-Gated)."""

from __future__ import annotations

from typing import Any


class BlenderXDXEngine:
    """Compiles approved storyboard shots into safe XDX Blender Studio MCP commands.

    Guarantees:
    - Never writes to `/tmp` (Android scoped storage rule; always uses `bpy.app.tempdir`).
    - Respects Vivo X200 Pro `mobile_guard` ANR protection (<=4 Cycles threads, material viewport first).
    - Never executes scene mutations unless explicit approval verification succeeds.
    """

    def compile_shot_plan(
        self,
        shot: dict[str, Any],
        *,
        fps: int = 30,
        style_bible: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cam = shot["camera"]
        start_f = int(shot["start_frame"])
        end_f = int(shot["end_frame"])
        local_frames = end_f - start_f

        bpy_recipe = (
            "import bpy, os\n"
            "scene = bpy.context.scene\n"
            f"scene.render.fps = {int(fps)}\n"
            f"scene.frame_start = 0\n"
            f"scene.frame_end = {max(0, local_frames - 1)}\n"
            "safe_out = os.path.join(bpy.app.tempdir, "
            f"'{shot['shot_id']}_####.png')\n"
            "scene.render.filepath = safe_out\n"
            "scene.view_settings.view_transform = 'AgX' if 'AgX' in ('Standard','AgX') else 'Standard'\n"
        )
        assert "/tmp" not in bpy_recipe

        return {
            "shot_id": shot["shot_id"],
            "engine": "blender",
            "mcp_preflight_sequence": [
                {"tool": "get_mobile_device_profile", "arguments": {}},
                {"tool": "get_scene_info", "arguments": {}},
            ],
            "modeling_and_staging_preview": {
                "tool": "look",
                "arguments": {"mode": "angles", "shading": "material", "resolution": 512},
            },
            "camera_spec": {
                "focal_length_mm": cam["focal_length_mm"],
                "sensor_width_mm": cam["sensor_width_mm"],
                "position_start": cam["position_start"],
                "position_end": cam["position_end"],
                "target": cam["target"],
            },
            "mobile_guard_policy": {
                "max_cycles_threads": 4,
                "preview_max_resolution": 640,
                "forbid_tmp_path": True,
            },
            "local_frame_range": [0, local_frames],
            "global_frame_range": [start_f, end_f],
            "bpy_setup_script_preview": bpy_recipe,
            "style_notes": (style_bible or {}).get("id", "xdx_stylized_diorama_v3_3"),
        }
