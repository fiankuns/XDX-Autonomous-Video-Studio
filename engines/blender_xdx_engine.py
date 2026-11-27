"""Approved Shot-to-Blender Scene & Animation Compiler Engine (v3.4).

Translates a hierarchical approved storyboard shot + assets + character setups + motion +
lighting/material/environment presets into a complete, schema-validated Blender compilation
manifest and AST-verified `bpy` script WITHOUT executing on the user's device during Phase 01.5.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent
BLENDER_MANIFEST_SCHEMA_PATH = ROOT_DIR / "schemas" / "blender_shot_manifest.schema.json"


def _kelvin_to_rgb(kelvin: float) -> list[float]:
    temp = max(1500.0, min(15000.0, float(kelvin))) / 100.0
    if temp <= 66.0:
        r = 1.0
        g = max(0.0, min(1.0, (99.4708 * (temp ** 0.0 if temp <= 1 else __import__("math").log(temp)) - 161.1195) / 255.0))
        b = 0.0 if temp <= 19.0 else max(0.0, min(1.0, (138.5177 * __import__("math").log(temp - 10.0) - 305.0448) / 255.0))
    else:
        r = max(0.0, min(1.0, 1.292936 * ((temp - 60.0) ** -0.1332047)))
        g = max(0.0, min(1.0, 1.129891 * ((temp - 60.0) ** -0.0755148)))
        b = 1.0
    return [round(r, 4), round(g, 4), round(b, 4)]


class BlenderXDXEngine:
    """Compiles approved storyboard shots into complete, offline-validated Blender scene packages."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._schema = json.loads((schema_path or BLENDER_MANIFEST_SCHEMA_PATH).read_text(encoding="utf-8"))

    def compile_shot_plan(
        self,
        shot: dict[str, Any],
        *,
        fps: int = 30,
        resolution: tuple[int, int] = (1080, 1920),
        style_bible: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        shot_id = str(shot["shot_id"])
        start_f = int(shot["start_frame"])
        end_f = int(shot["end_frame"])
        local_frames = end_f - start_f
        trans_spec = shot.get("transition_spec") or {}
        head_handles = int(trans_spec.get("render_handle_frames_head", 0))
        tail_handles = int(trans_spec.get("render_handle_frames_tail", 0))
        total_render_frames = local_frames + head_handles + tail_handles

        cam = shot["camera"]
        mid_frame = max(1, local_frames // 2)
        p0 = [float(v) for v in cam["position_start"]]
        p1 = [float(v) for v in cam["position_end"]]
        pmid = [round((p0[i] + p1[i]) * 0.5, 4) for i in range(3)]
        tgt = [float(v) for v in cam["target"]]

        collections = [
            {"name": "COL_Environment", "purpose": "Modular diorama walls, floor, ceiling cutaway"},
            {"name": "COL_Characters", "purpose": "Hero & supporting rigged armatures and meshes"},
            {"name": "COL_Props", "purpose": "Semantic procedural & CC0 glTF/GLB props"},
            {"name": "COL_Lighting", "purpose": "Key, Fill, Rim & practical diorama light rigs"},
            {"name": "COL_Cameras", "purpose": "Locked-sensor 36mm shot camera & focus target"},
            {"name": "COL_VFX", "purpose": "Dust motes, volumetric fog & contact shadow catchers"},
        ]

        asset_loading_plan = [
            {
                "asset_id": aid,
                "target_collection": "COL_Characters" if aid.startswith("char_") else "COL_Props",
                "import_op": "bpy.ops.import_scene.gltf",
                "safe_cache_relpath": f"xdx_assets/{aid}.glb",
                "axis_conversion": "Y_UP_TO_Z_UP",
                "unit_scale_m": 1.0,
            }
            for aid in shot.get("asset_ids", [])
            if not aid.startswith("font_")
        ]

        char_setups = []
        for cid in shot.get("character_ids", []):
            char_setups.append(
                {
                    "character_id": cid,
                    "armature_name": f"ARM_{cid}",
                    "action_name": f"ACT_{shot_id}_{cid}",
                    "ik_constraints": ["IK_Foot_L", "IK_Foot_R", "IK_Hand_L", "IK_Hand_R"],
                    "facial_shape_keys": {"brow_inner_up": 0.35, "blink": 0.0, "smile_soft": 0.2},
                    "keyframes": [
                        {"frame": 0, "bone": "torso", "location_delta": [0.0, 0.0, 0.0], "interpolation": "BEZIER"},
                        {"frame": min(6, mid_frame), "bone": "torso", "location_delta": [0.0, 0.0, -0.015], "interpolation": "BEZIER"},
                        {"frame": mid_frame, "bone": "hand_ik.R", "location_delta": [0.12, -0.18, 0.22], "interpolation": "BEZIER"},
                        {"frame": max(1, local_frames - 1), "bone": "torso", "location_delta": [0.0, 0.0, 0.0], "interpolation": "BEZIER"},
                    ],
                }
            )

        light_preset = str(shot.get("lighting_preset_id", "light_cozy_warm_interior"))
        is_horror = "horror" in light_preset
        lighting_rig = {
            "preset_id": light_preset,
            "lights": [
                {
                    "name": f"LGT_{shot_id}_Key",
                    "type": "AREA",
                    "energy_watts": 45.0 if is_horror else 140.0,
                    "color_rgb": _kelvin_to_rgb(4300 if is_horror else 3900),
                    "location": [2.2, -2.4, 2.8],
                    "size_m": 1.2,
                },
                {
                    "name": f"LGT_{shot_id}_Fill",
                    "type": "AREA",
                    "energy_watts": 10.0 if is_horror else 55.0,
                    "color_rgb": _kelvin_to_rgb(5400),
                    "location": [-2.5, -1.8, 1.9],
                    "size_m": 1.8,
                },
                {
                    "name": f"LGT_{shot_id}_Rim",
                    "type": "SPOT",
                    "energy_watts": 85.0,
                    "color_rgb": [0.22, 0.74, 0.97] if is_horror else _kelvin_to_rgb(4800),
                    "location": [0.0, 2.4, 2.6],
                    "size_m": 0.5,
                },
            ],
        }

        material_bindings = [
            {
                "preset_id": mp_id,
                "shader": "Principled BSDF",
                "roughness": 0.72 if "clay" in mp_id else 0.58,
                "metallic": 0.0,
                "bevel_radius_m": 0.006,
            }
            for mp_id in (shot.get("material_preset_ids") or ["mat_diorama_matte_clay"])
        ]

        bpy_script = self._generate_safe_bpy_script(
            shot_id=shot_id,
            fps=fps,
            total_render_frames=total_render_frames,
            resolution=resolution,
            collections=collections,
            camera_focal_mm=float(cam["focal_length_mm"]),
            camera_sensor_mm=float(cam["sensor_width_mm"]),
            p0=p0,
            pmid=pmid,
            p1=p1,
            mid_frame=mid_frame,
            tgt=tgt,
            lighting_rig=lighting_rig,
        )
        assert "/tmp" not in bpy_script
        ast.parse(bpy_script)
        compile(bpy_script, f"<xdx_shot_{shot_id}>", "exec")

        manifest = {
            "schema_version": "3.4.0",
            "shot_id": shot_id,
            "engine": "blender",
            "execution_mode": "OFFLINE_COMPILED_NOT_EXECUTED_ON_DEVICE",
            "scene_spec": {
                "scene_name": f"XDX_{shot_id}",
                "fps": int(fps),
                "frame_start": 0,
                "frame_end": max(0, total_render_frames - 1),
                "global_frame_range": [start_f, end_f],
                "unit_system": "METRIC",
                "scale_length": 1.0,
                "color_management": {
                    "display_device": "sRGB",
                    "view_transform": "AgX",
                    "style_bible": (style_bible or {}).get("id", "xdx_stylized_diorama_v3_4"),
                },
            },
            "collections": collections,
            "asset_loading_plan": asset_loading_plan,
            "environment_setup": {
                "environment_id": str(shot.get("environment_id", "env_kamar_indonesia_modular_v1")),
                "collection": "COL_Environment",
                "footprint_m": [4.0, 4.0, 3.0],
                "cutaway_walls": ["front", "right"],
            },
            "character_setups": char_setups,
            "camera_rig": {
                "camera_name": f"CAM_{shot_id}",
                "sensor_width_mm": float(cam["sensor_width_mm"]),
                "focal_length_mm": float(cam["focal_length_mm"]),
                "dof_fstop": float(cam.get("dof_fstop", 4.0)),
                "track_target": tgt,
                "keyframes": [
                    {"frame": 0, "location": p0},
                    {"frame": mid_frame, "location": pmid},
                    {"frame": max(1, total_render_frames - 1), "location": p1},
                ],
            },
            "lighting_rig": lighting_rig,
            "material_bindings": material_bindings,
            "render_settings": {
                "engine": "BLENDER_EEVEE_NEXT",
                "resolution_x": int(resolution[0]),
                "resolution_y": int(resolution[1]),
                "samples": 32,
                "file_format": "PNG",
                "mobile_guard_policy": {
                    "max_cycles_threads": 4,
                    "preview_max_resolution": 640,
                    "forbid_tmp_path": True,
                    "output_base_expr": f"os.path.join(bpy.app.tempdir, '{shot_id}_####.png')",
                },
            },
            "output_manifest": {
                "frame_count": total_render_frames,
                "handle_frames_head": head_handles,
                "handle_frames_tail": tail_handles,
                "frame_pattern": f"{shot_id}_%04d.png",
                "verification_rules": [
                    f"Verify exact {total_render_frames} non-empty RGBA/RGB PNG frames exist",
                    "Verify zero missing frame indices from 0000 to frame_end",
                ],
            },
            "mcp_preflight_sequence": [
                {"tool": "get_mobile_device_profile", "arguments": {}},
                {"tool": "get_scene_info", "arguments": {}},
            ],
            "bpy_script_ast_valid": True,
            "bpy_setup_script_preview": bpy_script,
        }
        jsonschema.validate(instance=manifest, schema=self._schema)
        return manifest

    @staticmethod
    def _generate_safe_bpy_script(
        *,
        shot_id: str,
        fps: int,
        total_render_frames: int,
        resolution: tuple[int, int],
        collections: list[dict[str, str]],
        camera_focal_mm: float,
        camera_sensor_mm: float,
        p0: list[float],
        pmid: list[float],
        p1: list[float],
        mid_frame: int,
        tgt: list[float],
        lighting_rig: dict[str, Any],
    ) -> str:
        col_names = [c["name"] for c in collections]
        lines = [
            "import bpy, os",
            "scene = bpy.context.scene",
            "scene.unit_settings.system = 'METRIC'",
            "scene.unit_settings.scale_length = 1.0",
            f"scene.render.fps = {int(fps)}",
            "scene.frame_start = 0",
            f"scene.frame_end = {max(0, total_render_frames - 1)}",
            f"scene.render.resolution_x = {int(resolution[0])}",
            f"scene.render.resolution_y = {int(resolution[1])}",
            "scene.render.image_settings.file_format = 'PNG'",
            "scene.render.threads_mode = 'FIXED'",
            "scene.render.threads = 4",
            f"scene.render.filepath = os.path.join(bpy.app.tempdir, '{shot_id}_####.png')",
            f"for cname in {col_names!r}:",
            "    if cname not in bpy.data.collections:",
            "        col = bpy.data.collections.new(cname)",
            "        scene.collection.children.link(col)",
            f"cam_data = bpy.data.cameras.new('CAM_{shot_id}')",
            f"cam_data.sensor_width = {camera_sensor_mm}",
            f"cam_data.lens = {camera_focal_mm}",
            f"cam_obj = bpy.data.objects.new('CAM_{shot_id}', cam_data)",
            "bpy.data.collections['COL_Cameras'].objects.link(cam_obj)",
            "scene.camera = cam_obj",
            f"tgt_empty = bpy.data.objects.new('TGT_{shot_id}', None)",
            f"tgt_empty.location = {tuple(tgt)!r}",
            "bpy.data.collections['COL_Cameras'].objects.link(tgt_empty)",
            "trk = cam_obj.constraints.new(type='TRACK_TO')",
            "trk.target = tgt_empty",
            "trk.track_axis = 'TRACK_NEGATIVE_Z'",
            "trk.up_axis = 'UP_Y'",
            f"for f_idx, loc in [(0, {tuple(p0)!r}), ({mid_frame}, {tuple(pmid)!r}), ({max(1, total_render_frames - 1)}, {tuple(p1)!r})]:",
            "    cam_obj.location = loc",
            "    cam_obj.keyframe_insert(data_path='location', frame=f_idx)",
        ]
        for lgt in lighting_rig["lights"]:
            lines.extend(
                [
                    f"ldata = bpy.data.lights.new(name={lgt['name']!r}, type={lgt['type']!r})",
                    f"ldata.energy = {float(lgt['energy_watts'])}",
                    f"ldata.color = {tuple(lgt['color_rgb'])!r}",
                    f"lobj = bpy.data.objects.new(name={lgt['name']!r}, object_data=ldata)",
                    f"lobj.location = {tuple(lgt['location'])!r}",
                    "bpy.data.collections['COL_Lighting'].objects.link(lobj)",
                ]
            )
        return "\n".join(lines) + "\n"
