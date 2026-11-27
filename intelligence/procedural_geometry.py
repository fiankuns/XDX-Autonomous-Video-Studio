"""Multi-Component Semantic Procedural 3D Asset Generator (glTF 2.0 & GLB) — v3.4.

Generates authentic, multi-part, multi-material 3D diorama assets with unit-length normals,
UV coordinates, accurate meter dimensions, and validated SemanticAssetSpec manifests across
12 required production categories:
1. lamp (Lampu)
2. table (Meja)
3. chair (Kursi)
4. bed (Kasur)
5. door (Pintu)
6. window (Jendela)
7. wardrobe (Lemari)
8. book (Buku)
9. clock (Jam)
10. tree (Pohon)
11. modular_building (Bangunan Modular)
12. simple_vehicle (Kendaraan Sederhana)

Strictly separates production procedural assets from `primitive_placeholder` greyboxes.
"""

from __future__ import annotations

import base64
import json
import math
import struct
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parent.parent
SEMANTIC_SPEC_SCHEMA_PATH = ROOT_DIR / "schemas" / "semantic_asset_spec.schema.json"

SUPPORTED_PROCEDURAL_CATEGORIES: tuple[str, ...] = (
    "lamp",
    "table",
    "chair",
    "bed",
    "door",
    "window",
    "wardrobe",
    "book",
    "clock",
    "tree",
    "modular_building",
    "simple_vehicle",
    "pedestal_chart",
)

INDONESIAN_CATEGORY_ALIASES: dict[str, str] = {
    "lampu": "lamp",
    "lamp": "lamp",
    "meja": "table",
    "desk": "table",
    "table": "table",
    "kursi": "chair",
    "chair": "chair",
    "kasur": "bed",
    "ranjang": "bed",
    "bed": "bed",
    "pintu": "door",
    "door": "door",
    "jendela": "window",
    "window": "window",
    "lemari": "wardrobe",
    "rak": "wardrobe",
    "wardrobe": "wardrobe",
    "cabinet": "wardrobe",
    "buku": "book",
    "book": "book",
    "jam": "clock",
    "clock": "clock",
    "pohon": "tree",
    "tanaman": "tree",
    "tree": "tree",
    "bangunan": "modular_building",
    "gedung": "modular_building",
    "rumah": "modular_building",
    "modular_building": "modular_building",
    "kendaraan": "simple_vehicle",
    "mobil": "simple_vehicle",
    "vehicle": "simple_vehicle",
    "simple_vehicle": "simple_vehicle",
    "pedestal": "pedestal_chart",
    "chart": "pedestal_chart",
    "pedestal_chart": "pedestal_chart",
}


def infer_semantic_category(asset_id_or_name: str) -> str | None:
    lowered = asset_id_or_name.lower().replace("-", "_")
    for key, canonical in INDONESIAN_CATEGORY_ALIASES.items():
        if key in lowered.split("_") or key in lowered:
            return canonical
    return None


class MeshPrimitiveBuilder:
    """Builds indexed triangle meshes with POSITION, NORMAL, and TEXCOORD_0."""

    @staticmethod
    def _normalize(vx: float, vy: float, vz: float) -> tuple[float, float, float]:
        length = math.sqrt(vx * vx + vy * vy + vz * vz)
        if length < 1e-9:
            return (0.0, 1.0, 0.0)
        return (vx / length, vy / length, vz / length)

    @classmethod
    def box(
        cls,
        width: float,
        height: float,
        depth: float,
        *,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict[str, Any]:
        cx, cy, cz = center
        hx, hy, hz = width / 2.0, height / 2.0, depth / 2.0
        faces = [
            # normal, 4 corners (CCW)
            ((0.0, 0.0, 1.0), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
            ((0.0, 0.0, -1.0), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)]),
            ((0.0, 1.0, 0.0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)]),
            ((0.0, -1.0, 0.0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
            ((1.0, 0.0, 0.0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)]),
            ((-1.0, 0.0, 0.0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
        ]
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        indices: list[int] = []
        face_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

        for nrm, corners in faces:
            base = len(positions)
            for idx_c, (px, py, pz) in enumerate(corners):
                positions.append((cx + px, cy + py, cz + pz))
                normals.append(nrm)
                uvs.append(face_uv[idx_c])
            indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

        return {"positions": positions, "normals": normals, "uvs": uvs, "indices": indices}

    @classmethod
    def frustum(
        cls,
        radius_bottom: float,
        radius_top: float,
        height: float,
        *,
        radial_segments: int = 20,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        axis: str = "Y",
    ) -> dict[str, Any]:
        """Build a closed cylinder/cone/frustum with smooth side normals and flat caps."""
        cx, cy, cz = center
        y0, y1 = -height / 2.0, height / 2.0
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        indices: list[int] = []

        def _orient(px: float, py: float, pz: float) -> tuple[float, float, float]:
            if axis == "Z":
                return (cx + px, cy - pz, cz + py)
            if axis == "X":
                return (cx + py, cy + px, cz + pz)
            return (cx + px, cy + py, cz + pz)

        def _orient_n(nx: float, ny: float, nz: float) -> tuple[float, float, float]:
            if axis == "Z":
                return cls._normalize(nx, -nz, ny)
            if axis == "X":
                return cls._normalize(ny, nx, nz)
            return cls._normalize(nx, ny, nz)

        slope = (radius_bottom - radius_top) / max(height, 1e-6)
        # Side ring vertices
        for i in range(radial_segments + 1):
            u = i / radial_segments
            theta = u * 2.0 * math.pi
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            nrm = _orient_n(cos_t, slope, sin_t)
            positions.append(_orient(radius_bottom * cos_t, y0, radius_bottom * sin_t))
            normals.append(nrm)
            uvs.append((u, 0.0))
            positions.append(_orient(radius_top * cos_t, y1, radius_top * sin_t))
            normals.append(nrm)
            uvs.append((u, 1.0))

        for i in range(radial_segments):
            b = i * 2
            indices.extend([b, b + 2, b + 3, b, b + 3, b + 1])

        # Bottom cap
        if radius_bottom > 1e-5:
            c_idx = len(positions)
            positions.append(_orient(0.0, y0, 0.0))
            normals.append(_orient_n(0.0, -1.0, 0.0))
            uvs.append((0.5, 0.5))
            ring_start = len(positions)
            for i in range(radial_segments + 1):
                theta = (i / radial_segments) * 2.0 * math.pi
                cos_t, sin_t = math.cos(theta), math.sin(theta)
                positions.append(_orient(radius_bottom * cos_t, y0, radius_bottom * sin_t))
                normals.append(_orient_n(0.0, -1.0, 0.0))
                uvs.append((0.5 + 0.5 * cos_t, 0.5 + 0.5 * sin_t))
            for i in range(radial_segments):
                indices.extend([c_idx, ring_start + i, ring_start + i + 1])

        # Top cap
        if radius_top > 1e-5:
            c_idx = len(positions)
            positions.append(_orient(0.0, y1, 0.0))
            normals.append(_orient_n(0.0, 1.0, 0.0))
            uvs.append((0.5, 0.5))
            ring_start = len(positions)
            for i in range(radial_segments + 1):
                theta = (i / radial_segments) * 2.0 * math.pi
                cos_t, sin_t = math.cos(theta), math.sin(theta)
                positions.append(_orient(radius_top * cos_t, y1, radius_top * sin_t))
                normals.append(_orient_n(0.0, 1.0, 0.0))
                uvs.append((0.5 + 0.5 * cos_t, 0.5 + 0.5 * sin_t))
            for i in range(radial_segments):
                indices.extend([c_idx, ring_start + i + 1, ring_start + i])

        return {"positions": positions, "normals": normals, "uvs": uvs, "indices": indices}

    @classmethod
    def uv_sphere(
        cls,
        radius: float,
        *,
        width_segments: int = 16,
        height_segments: int = 12,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict[str, Any]:
        cx, cy, cz = center
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        indices: list[int] = []

        for iy in range(height_segments + 1):
            v = iy / height_segments
            phi = v * math.pi
            for ix in range(width_segments + 1):
                u = ix / width_segments
                theta = u * 2.0 * math.pi
                nx = -math.cos(theta) * math.sin(phi)
                ny = math.cos(phi)
                nz = math.sin(theta) * math.sin(phi)
                positions.append((cx + radius * nx, cy + radius * ny, cz + radius * nz))
                normals.append(cls._normalize(nx, ny, nz))
                uvs.append((u, 1.0 - v))

        stride = width_segments + 1
        for iy in range(height_segments):
            for ix in range(width_segments):
                a = iy * stride + ix
                b = a + 1
                c = a + stride
                d = c + 1
                if iy != 0:
                    indices.extend([a, d, b])
                if iy != height_segments - 1:
                    indices.extend([a, c, d])

        return {"positions": positions, "normals": normals, "uvs": uvs, "indices": indices}


def assemble_multi_node_gltf(
    asset_id: str,
    materials_spec: list[dict[str, Any]],
    parts: list[dict[str, Any]],
    *,
    extra_asset_extras: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Pack multiple named mesh parts & PBR materials into a valid glTF 2.0 document."""
    slot_to_mat_idx: dict[str, int] = {}
    gltf_materials: list[dict[str, Any]] = []
    for idx, m in enumerate(materials_spec):
        slot_to_mat_idx[m["slot_name"]] = idx
        mat_entry: dict[str, Any] = {
            "name": m["slot_name"],
            "pbrMetallicRoughness": {
                "baseColorFactor": [round(float(x), 4) for x in m["base_color_rgba"]],
                "roughnessFactor": round(float(m["roughness"]), 4),
                "metallicFactor": round(float(m["metallic"]), 4),
            },
        }
        if m.get("alpha_mode") == "BLEND":
            mat_entry["alphaMode"] = "BLEND"
        if m.get("emissive_rgb"):
            mat_entry["emissiveFactor"] = [round(float(x), 4) for x in m["emissive_rgb"]]
        gltf_materials.append(mat_entry)

    binary_chunks: list[bytes] = []
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    child_nodes: list[dict[str, Any]] = []
    byte_offset = 0
    total_triangles = 0

    def _append_chunk(raw: bytes, target: int | None) -> int:
        nonlocal byte_offset
        pad = (4 - (len(raw) % 4)) % 4
        padded = raw + (b"\x00" * pad)
        bv_idx = len(buffer_views)
        bv: dict[str, Any] = {"buffer": 0, "byteOffset": byte_offset, "byteLength": len(raw)}
        if target is not None:
            bv["target"] = target
        buffer_views.append(bv)
        binary_chunks.append(padded)
        byte_offset += len(padded)
        return bv_idx

    for part in parts:
        geom = part["geometry"]
        pos = geom["positions"]
        nrm = geom["normals"]
        uv = geom["uvs"]
        idx_list = geom["indices"]
        total_triangles += len(idx_list) // 3

        pos_bytes = b"".join(struct.pack("<fff", *p) for p in pos)
        nrm_bytes = b"".join(struct.pack("<fff", *n) for n in nrm)
        uv_bytes = b"".join(struct.pack("<ff", *t) for t in uv)
        idx_bytes = b"".join(struct.pack("<H", i) for i in idx_list)

        bv_pos = _append_chunk(pos_bytes, 34962)
        bv_nrm = _append_chunk(nrm_bytes, 34962)
        bv_uv = _append_chunk(uv_bytes, 34962)
        bv_idx = _append_chunk(idx_bytes, 34963)

        xs = [p[0] for p in pos]
        ys = [p[1] for p in pos]
        zs = [p[2] for p in pos]

        acc_pos = len(accessors)
        accessors.append(
            {
                "bufferView": bv_pos,
                "componentType": 5126,
                "count": len(pos),
                "type": "VEC3",
                "min": [round(min(xs), 6), round(min(ys), 6), round(min(zs), 6)],
                "max": [round(max(xs), 6), round(max(ys), 6), round(max(zs), 6)],
            }
        )
        acc_nrm = len(accessors)
        accessors.append({"bufferView": bv_nrm, "componentType": 5126, "count": len(nrm), "type": "VEC3"})
        acc_uv = len(accessors)
        accessors.append({"bufferView": bv_uv, "componentType": 5126, "count": len(uv), "type": "VEC2"})
        acc_idx = len(accessors)
        accessors.append({"bufferView": bv_idx, "componentType": 5123, "count": len(idx_list), "type": "SCALAR"})

        mesh_idx = len(meshes)
        meshes.append(
            {
                "name": f"{part['name']}_mesh",
                "primitives": [
                    {
                        "attributes": {"POSITION": acc_pos, "NORMAL": acc_nrm, "TEXCOORD_0": acc_uv},
                        "indices": acc_idx,
                        "material": slot_to_mat_idx[part["material_slot"]],
                    }
                ],
            }
        )
        child_nodes.append(
            {
                "name": part["name"],
                "mesh": mesh_idx,
                "translation": [round(float(c), 5) for c in part.get("translation", (0.0, 0.0, 0.0))],
            }
        )

    full_bin = b"".join(binary_chunks)
    uri = "data:application/octet-stream;base64," + base64.b64encode(full_bin).decode("ascii")

    root_idx = len(child_nodes)
    all_nodes = [*child_nodes, {"name": asset_id, "children": list(range(len(child_nodes)))}]

    asset_block: dict[str, Any] = {"version": "2.0", "generator": "XDX-SemanticProceduralGenerator-v3.4"}
    if extra_asset_extras:
        asset_block["extras"] = extra_asset_extras

    gltf_doc = {
        "asset": asset_block,
        "scene": 0,
        "scenes": [{"name": f"{asset_id}_scene", "nodes": [root_idx]}],
        "nodes": all_nodes,
        "materials": gltf_materials,
        "meshes": meshes,
        "buffers": [{"byteLength": len(full_bin), "uri": uri}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    return gltf_doc, total_triangles


class SemanticProceduralAssetGenerator:
    """Produces production-grade multi-component 3D assets and validates SemanticAssetSpec."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._spec_schema = json.loads((schema_path or SEMANTIC_SPEC_SCHEMA_PATH).read_text(encoding="utf-8"))

    def supports_category(self, category_or_hint: str) -> bool:
        return infer_semantic_category(category_or_hint) is not None

    def generate_semantic_asset(
        self,
        asset_id: str,
        *,
        semantic_category: str | None = None,
    ) -> tuple[bytes, dict[str, Any], int]:
        """Generate `(gltf_bytes, semantic_spec_dict, triangle_count)` for a supported category."""
        cat = semantic_category if semantic_category in SUPPORTED_PROCEDURAL_CATEGORIES else infer_semantic_category(semantic_category or asset_id)
        if cat is None or cat not in SUPPORTED_PROCEDURAL_CATEGORIES:
            raise ValueError(
                f"No production procedural generator for '{asset_id}' (category='{semantic_category}'). "
                "Refusing to emit a fake 12-triangle box as a production asset."
            )

        builder = getattr(self, f"_build_{cat}")
        dims, shape_desc, func_geom, mats, parts, components_meta, articulated = builder()

        spec: dict[str, Any] = {
            "schema_version": "3.4.0",
            "asset_id": asset_id,
            "asset_type": cat,
            "is_placeholder": False,
            "shape_description": shape_desc,
            "functional_geometry": func_geom,
            "dimensions_m": dims,
            "components": components_meta,
            "material_assignments": mats,
            "visual_style": "xdx_stylized_diorama_v3_4",
            "rig_requirements": {
                "requires_armature": len(articulated) > 0,
                "articulated_parts": articulated,
            },
            "source_and_license": {
                "source_provider": "XDX Semantic Procedural Generator v3.4",
                "source_url": f"local://semantic-procedural/{cat}/{asset_id}",
                "license_spdx": "MIT",
                "attribution_required": False,
                "attribution_text": None,
            },
            "geometry_budget": {"min_triangles": 60, "max_triangles": 12000},
            "engine_compatibility": ["blender", "threejs"],
        }
        jsonschema.validate(instance=spec, schema=self._spec_schema)

        gltf_doc, tri_count = assemble_multi_node_gltf(
            asset_id,
            mats,
            parts,
            extra_asset_extras={"semantic_type": cat, "is_placeholder": False, "component_count": len(parts)},
        )
        if tri_count < spec["geometry_budget"]["min_triangles"]:
            raise RuntimeError(f"Generated '{cat}' has too few triangles ({tri_count}) for production quality.")
        return json.dumps(gltf_doc, indent=2).encode("utf-8"), spec, tri_count

    def generate_primitive_placeholder_box(self, asset_id: str) -> tuple[bytes, dict[str, Any], int]:
        """Explicitly tagged PLACEHOLDER greybox — NEVER allowed to pass final production Asset QC."""
        mats = [{"slot_name": "placeholder_magenta", "base_color_rgba": [1.0, 0.0, 0.8, 1.0], "roughness": 0.8, "metallic": 0.0}]
        parts = [
            {
                "name": "placeholder_proxy_box",
                "material_slot": "placeholder_magenta",
                "translation": (0.0, 0.25, 0.0),
                "geometry": MeshPrimitiveBuilder.box(0.5, 0.5, 0.5),
            }
        ]
        spec: dict[str, Any] = {
            "schema_version": "3.4.0",
            "asset_id": asset_id,
            "asset_type": "primitive_placeholder",
            "is_placeholder": True,
            "shape_description": "Temporary proxy bounding box for blocking only (NOT FOR FINAL RENDER).",
            "functional_geometry": "12-triangle axis-aligned bounding proxy.",
            "dimensions_m": {"width": 0.5, "height": 0.5, "depth": 0.5},
            "components": [
                {
                    "component_id": "proxy_box",
                    "role": "blocking_placeholder",
                    "primitive_kind": "box",
                    "material_slot": "placeholder_magenta",
                    "local_offset_m": [0.0, 0.25, 0.0],
                }
            ],
            "material_assignments": mats,
            "visual_style": "diagnostic_placeholder",
            "rig_requirements": {"requires_armature": False, "articulated_parts": []},
            "source_and_license": {
                "source_provider": "XDX Diagnostic Greybox",
                "source_url": f"local://placeholder/{asset_id}",
                "license_spdx": "MIT",
                "attribution_required": False,
                "attribution_text": None,
            },
            "geometry_budget": {"min_triangles": 12, "max_triangles": 12},
            "engine_compatibility": ["blender", "threejs"],
        }
        jsonschema.validate(instance=spec, schema=self._spec_schema)
        gltf_doc, tris = assemble_multi_node_gltf(
            asset_id,
            mats,
            parts,
            extra_asset_extras={"semantic_type": "primitive_placeholder", "is_placeholder": True},
        )
        return json.dumps(gltf_doc, indent=2).encode("utf-8"), spec, tris

    # ---- 12 Production Semantic Category Builders ----

    def _build_lamp(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "brass_stand", "base_color_rgba": [0.78, 0.62, 0.28, 1.0], "roughness": 0.38, "metallic": 0.42},
            {"slot_name": "linen_shade", "base_color_rgba": [0.96, 0.91, 0.79, 1.0], "roughness": 0.78, "metallic": 0.0},
            {"slot_name": "warm_bulb", "base_color_rgba": [1.0, 0.93, 0.72, 1.0], "roughness": 0.30, "metallic": 0.0, "emissive_rgb": [1.0, 0.82, 0.45]},
        ]
        parts = [
            {"name": "lamp_base", "material_slot": "brass_stand", "translation": (0.0, 0.015, 0.0), "geometry": B.frustum(0.11, 0.09, 0.03, radial_segments=24)},
            {"name": "lamp_stem", "material_slot": "brass_stand", "translation": (0.0, 0.21, 0.0), "geometry": B.frustum(0.016, 0.014, 0.36, radial_segments=16)},
            {"name": "lamp_socket", "material_slot": "brass_stand", "translation": (0.0, 0.39, 0.0), "geometry": B.frustum(0.025, 0.025, 0.04, radial_segments=16)},
            {"name": "lamp_bulb", "material_slot": "warm_bulb", "translation": (0.0, 0.43, 0.0), "geometry": B.uv_sphere(0.038, width_segments=16, height_segments=12)},
            {"name": "lamp_shade", "material_slot": "linen_shade", "translation": (0.0, 0.45, 0.0), "geometry": B.frustum(0.16, 0.09, 0.18, radial_segments=24)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "bulb" not in p["name"] else "uv_sphere", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 0.32, "height": 0.54, "depth": 0.32},
            "Stylized desk/bedside lamp with weighted circular brass base, slender stem, glowing bulb, and flared linen shade.",
            "5-component radial lamp silhouette suitable for close-up desk & interior lighting motivation.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_table(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "teak_wood", "base_color_rgba": [0.55, 0.35, 0.18, 1.0], "roughness": 0.62, "metallic": 0.0},
            {"slot_name": "rubber_foot", "base_color_rgba": [0.16, 0.18, 0.20, 1.0], "roughness": 0.82, "metallic": 0.0},
        ]
        parts = [
            {"name": "table_top", "material_slot": "teak_wood", "translation": (0.0, 0.73, 0.0), "geometry": B.box(1.20, 0.04, 0.70)},
            {"name": "apron_front", "material_slot": "teak_wood", "translation": (0.0, 0.68, 0.29), "geometry": B.box(1.06, 0.06, 0.025)},
            {"name": "apron_back", "material_slot": "teak_wood", "translation": (0.0, 0.68, -0.29), "geometry": B.box(1.06, 0.06, 0.025)},
        ]
        for idx, (lx, lz) in enumerate([(-0.52, -0.28), (0.52, -0.28), (-0.52, 0.28), (0.52, 0.28)], 1):
            parts.append({"name": f"leg_{idx}", "material_slot": "teak_wood", "translation": (lx, 0.36, lz), "geometry": B.frustum(0.022, 0.032, 0.68, radial_segments=14)})
            parts.append({"name": f"glide_{idx}", "material_slot": "rubber_foot", "translation": (lx, 0.01, lz), "geometry": B.frustum(0.024, 0.022, 0.02, radial_segments=12)})
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "box" if p["name"].startswith(("table", "apron")) else "frustum_cone", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.20, "height": 0.75, "depth": 0.70},
            "Indonesian teak study/work table with tabletop slab, structural apron rails, 4 tapered legs, and floor glides.",
            "True open leg clearance underneath tabletop at 0.75m ergonomic height for seated characters.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_chair(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "teak_frame", "base_color_rgba": [0.52, 0.33, 0.17, 1.0], "roughness": 0.60, "metallic": 0.0},
            {"slot_name": "fabric_cushion", "base_color_rgba": [0.24, 0.44, 0.68, 1.0], "roughness": 0.80, "metallic": 0.0},
        ]
        parts = [
            {"name": "seat_base", "material_slot": "teak_frame", "translation": (0.0, 0.43, 0.0), "geometry": B.box(0.46, 0.03, 0.46)},
            {"name": "seat_cushion", "material_slot": "fabric_cushion", "translation": (0.0, 0.465, 0.01), "geometry": B.box(0.43, 0.04, 0.43)},
            {"name": "backrest_panel", "material_slot": "fabric_cushion", "translation": (0.0, 0.76, -0.20), "geometry": B.box(0.42, 0.24, 0.04)},
            {"name": "stile_left", "material_slot": "teak_frame", "translation": (-0.20, 0.67, -0.20), "geometry": B.frustum(0.018, 0.016, 0.48, radial_segments=12)},
            {"name": "stile_right", "material_slot": "teak_frame", "translation": (0.20, 0.67, -0.20), "geometry": B.frustum(0.018, 0.016, 0.48, radial_segments=12)},
        ]
        for idx, (lx, lz) in enumerate([(-0.19, -0.19), (0.19, -0.19), (-0.19, 0.19), (0.19, 0.19)], 1):
            parts.append({"name": f"chair_leg_{idx}", "material_slot": "teak_frame", "translation": (lx, 0.215, lz), "geometry": B.frustum(0.016, 0.022, 0.43, radial_segments=12)})
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "box" if "seat" in p["name"] or "panel" in p["name"] else "frustum_cone", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 0.46, "height": 0.91, "depth": 0.46},
            "Wooden diorama dining/study chair with upholstered seat cushion, vertical backrest stiles, and 4 tapered legs.",
            "0.46m seat height matching 0.75m desk clearance for character sitting poses.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_bed(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "bed_wood", "base_color_rgba": [0.48, 0.30, 0.16, 1.0], "roughness": 0.64, "metallic": 0.0},
            {"slot_name": "mattress_linen", "base_color_rgba": [0.94, 0.95, 0.97, 1.0], "roughness": 0.84, "metallic": 0.0},
            {"slot_name": "blanket_indigo", "base_color_rgba": [0.20, 0.36, 0.62, 1.0], "roughness": 0.82, "metallic": 0.0},
        ]
        parts = [
            {"name": "bed_frame", "material_slot": "bed_wood", "translation": (0.0, 0.18, 0.0), "geometry": B.box(1.10, 0.16, 2.04)},
            {"name": "headboard", "material_slot": "bed_wood", "translation": (0.0, 0.55, -0.99), "geometry": B.box(1.12, 0.90, 0.06)},
            {"name": "mattress", "material_slot": "mattress_linen", "translation": (0.0, 0.35, 0.02), "geometry": B.box(1.02, 0.20, 1.94)},
            {"name": "blanket", "material_slot": "blanket_indigo", "translation": (0.0, 0.37, 0.32), "geometry": B.box(1.05, 0.21, 1.32)},
            {"name": "pillow_left", "material_slot": "mattress_linen", "translation": (-0.25, 0.49, -0.74), "geometry": B.frustum(0.14, 0.14, 0.42, radial_segments=16, axis="X")},
            {"name": "pillow_right", "material_slot": "mattress_linen", "translation": (0.25, 0.49, -0.74), "geometry": B.frustum(0.14, 0.14, 0.42, radial_segments=16, axis="X")},
        ]
        for idx, (lx, lz) in enumerate([(-0.50, -0.96), (0.50, -0.96), (-0.50, 0.96), (0.50, 0.96)], 1):
            parts.append({"name": f"bed_leg_{idx}", "material_slot": "bed_wood", "translation": (lx, 0.05, lz), "geometry": B.frustum(0.03, 0.035, 0.10, radial_segments=12)})
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "pillow" in p["name"] or "leg" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.12, "height": 1.00, "depth": 2.04},
            "Single/twin bedroom bed with wooden headboard, raised frame, white mattress, indigo blanket, and cylindrical bolster pillows.",
            "Layered bedroom hero prop with distinct headboard, mattress, pillows, and blanket.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_door(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "door_wood", "base_color_rgba": [0.50, 0.32, 0.18, 1.0], "roughness": 0.58, "metallic": 0.0},
            {"slot_name": "brushed_steel", "base_color_rgba": [0.76, 0.79, 0.82, 1.0], "roughness": 0.32, "metallic": 0.45},
        ]
        parts = [
            {"name": "jamb_left", "material_slot": "door_wood", "translation": (-0.46, 1.05, 0.0), "geometry": B.box(0.06, 2.10, 0.12)},
            {"name": "jamb_right", "material_slot": "door_wood", "translation": (0.46, 1.05, 0.0), "geometry": B.box(0.06, 2.10, 0.12)},
            {"name": "lintel_top", "material_slot": "door_wood", "translation": (0.0, 2.07, 0.0), "geometry": B.box(0.98, 0.06, 0.12)},
            {"name": "door_leaf", "material_slot": "door_wood", "translation": (0.0, 1.02, 0.0), "geometry": B.box(0.84, 2.02, 0.045)},
            {"name": "panel_upper", "material_slot": "door_wood", "translation": (0.0, 1.48, 0.026), "geometry": B.box(0.62, 0.70, 0.015)},
            {"name": "panel_lower", "material_slot": "door_wood", "translation": (0.0, 0.56, 0.026), "geometry": B.box(0.62, 0.70, 0.015)},
            {"name": "handle_rose", "material_slot": "brushed_steel", "translation": (0.33, 1.00, 0.032), "geometry": B.frustum(0.028, 0.028, 0.012, radial_segments=16, axis="Z")},
            {"name": "handle_lever", "material_slot": "brushed_steel", "translation": (0.28, 1.00, 0.055), "geometry": B.frustum(0.011, 0.011, 0.12, radial_segments=14, axis="X")},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "handle" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 0.98, "height": 2.10, "depth": 0.14},
            "Architectural wooden doorway with jambs, lintel, paneled door leaf, circular escutcheon rose, and lever handle.",
            "Standard 2.10m x 0.98m architectural door assembly with articulated door_leaf and handle_lever.",
            mats,
            parts,
            comps,
            ["door_leaf", "handle_lever"],
        )

    def _build_window(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "window_frame_paint", "base_color_rgba": [0.92, 0.93, 0.95, 1.0], "roughness": 0.52, "metallic": 0.05},
            {"slot_name": "clear_glass", "base_color_rgba": [0.68, 0.86, 0.98, 0.38], "roughness": 0.12, "metallic": 0.0, "alpha_mode": "BLEND"},
        ]
        parts = [
            {"name": "window_sill", "material_slot": "window_frame_paint", "translation": (0.0, 0.03, 0.03), "geometry": B.box(1.16, 0.06, 0.18)},
            {"name": "frame_top", "material_slot": "window_frame_paint", "translation": (0.0, 1.27, 0.0), "geometry": B.box(1.10, 0.06, 0.10)},
            {"name": "frame_left", "material_slot": "window_frame_paint", "translation": (-0.52, 0.65, 0.0), "geometry": B.box(0.06, 1.24, 0.10)},
            {"name": "frame_right", "material_slot": "window_frame_paint", "translation": (0.52, 0.65, 0.0), "geometry": B.box(0.06, 1.24, 0.10)},
            {"name": "mullion_vertical", "material_slot": "window_frame_paint", "translation": (0.0, 0.65, 0.0), "geometry": B.box(0.04, 1.18, 0.06)},
            {"name": "transom_horizontal", "material_slot": "window_frame_paint", "translation": (0.0, 0.68, 0.0), "geometry": B.box(0.98, 0.04, 0.06)},
            {"name": "glass_pane", "material_slot": "clear_glass", "translation": (0.0, 0.66, 0.0), "geometry": B.box(0.98, 1.16, 0.012)},
            {"name": "curtain_rod", "material_slot": "window_frame_paint", "translation": (0.0, 1.36, 0.07), "geometry": B.frustum(0.012, 0.012, 1.26, radial_segments=16, axis="X")},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "rod" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.26, "height": 1.38, "depth": 0.18},
            "Framed four-pane architectural window with projecting sill, cross mullions, translucent BLEND glass, and curtain rod.",
            "Supports daylight transmission and interior/exterior camera framing.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_wardrobe(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "cabinet_oak", "base_color_rgba": [0.58, 0.40, 0.24, 1.0], "roughness": 0.60, "metallic": 0.0},
            {"slot_name": "metal_pull", "base_color_rgba": [0.22, 0.24, 0.28, 1.0], "roughness": 0.35, "metallic": 0.40},
        ]
        parts = [
            {"name": "plinth_base", "material_slot": "cabinet_oak", "translation": (0.0, 0.05, 0.0), "geometry": B.box(1.00, 0.10, 0.56)},
            {"name": "carcass_body", "material_slot": "cabinet_oak", "translation": (0.0, 1.02, -0.02), "geometry": B.box(1.02, 1.84, 0.54)},
            {"name": "crown_trim", "material_slot": "cabinet_oak", "translation": (0.0, 1.97, 0.0), "geometry": B.box(1.08, 0.06, 0.60)},
            {"name": "door_left", "material_slot": "cabinet_oak", "translation": (-0.255, 1.02, 0.265), "geometry": B.box(0.49, 1.80, 0.025)},
            {"name": "door_right", "material_slot": "cabinet_oak", "translation": (0.255, 1.02, 0.265), "geometry": B.box(0.49, 1.80, 0.025)},
            {"name": "pull_left", "material_slot": "metal_pull", "translation": (-0.05, 1.02, 0.295), "geometry": B.frustum(0.009, 0.009, 0.16, radial_segments=14)},
            {"name": "pull_right", "material_slot": "metal_pull", "translation": (0.05, 1.02, 0.295), "geometry": B.frustum(0.009, 0.009, 0.16, radial_segments=14)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "pull" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.08, "height": 2.00, "depth": 0.60},
            "Two-door wooden wardrobe/cabinet with plinth base, main carcass, crown molding, twin doors, and cylindrical pulls.",
            "Full-height 2.0m bedroom/archive storage cabinet with articulated left and right doors.",
            mats,
            parts,
            comps,
            ["door_left", "door_right"],
        )

    def _build_book(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "hardcover_crimson", "base_color_rgba": [0.62, 0.16, 0.18, 1.0], "roughness": 0.66, "metallic": 0.0},
            {"slot_name": "cream_pages", "base_color_rgba": [0.95, 0.92, 0.84, 1.0], "roughness": 0.85, "metallic": 0.0},
            {"slot_name": "gold_ribbon", "base_color_rgba": [0.85, 0.68, 0.24, 1.0], "roughness": 0.45, "metallic": 0.25},
        ]
        parts = [
            {"name": "cover_bottom", "material_slot": "hardcover_crimson", "translation": (0.0, 0.004, 0.0), "geometry": B.box(0.21, 0.006, 0.29)},
            {"name": "cover_top", "material_slot": "hardcover_crimson", "translation": (0.0, 0.046, 0.0), "geometry": B.box(0.21, 0.006, 0.29)},
            {"name": "page_block", "material_slot": "cream_pages", "translation": (0.006, 0.025, 0.0), "geometry": B.box(0.195, 0.036, 0.278)},
            {"name": "rounded_spine", "material_slot": "hardcover_crimson", "translation": (-0.102, 0.025, 0.0), "geometry": B.frustum(0.024, 0.024, 0.29, radial_segments=18, axis="Z")},
            {"name": "bookmark_tail", "material_slot": "gold_ribbon", "translation": (0.02, 0.003, 0.165), "geometry": B.box(0.018, 0.002, 0.06)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "spine" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 0.23, "height": 0.05, "depth": 0.33},
            "Hardcover chronicle book with top/bottom boards, rounded spine, recessed cream paper block, and gold bookmark.",
            "Macro-ready tabletop & historical archive prop.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_clock(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "clock_rim_dark", "base_color_rgba": [0.15, 0.18, 0.24, 1.0], "roughness": 0.42, "metallic": 0.25},
            {"slot_name": "clock_dial_ivory", "base_color_rgba": [0.96, 0.95, 0.91, 1.0], "roughness": 0.70, "metallic": 0.0},
            {"slot_name": "clock_hands_crimson", "base_color_rgba": [0.72, 0.15, 0.15, 1.0], "roughness": 0.40, "metallic": 0.20},
        ]
        parts = [
            {"name": "casing_drum", "material_slot": "clock_rim_dark", "translation": (0.0, 0.0, 0.0), "geometry": B.frustum(0.18, 0.18, 0.05, radial_segments=28, axis="Z")},
            {"name": "dial_face", "material_slot": "clock_dial_ivory", "translation": (0.0, 0.0, 0.026), "geometry": B.frustum(0.155, 0.155, 0.006, radial_segments=28, axis="Z")},
            {"name": "hour_hand", "material_slot": "clock_rim_dark", "translation": (0.032, 0.02, 0.033), "geometry": B.box(0.085, 0.012, 0.004)},
            {"name": "minute_hand", "material_slot": "clock_hands_crimson", "translation": (0.0, 0.052, 0.036), "geometry": B.box(0.009, 0.125, 0.004)},
            {"name": "center_pin", "material_slot": "clock_hands_crimson", "translation": (0.0, 0.0, 0.039), "geometry": B.frustum(0.012, 0.012, 0.008, radial_segments=12, axis="Z")},
        ]
        for h in range(12):
            ang = (h / 12.0) * 2.0 * math.pi
            mx, my = 0.132 * math.sin(ang), 0.132 * math.cos(ang)
            parts.append(
                {
                    "name": f"tick_{h:02d}",
                    "material_slot": "clock_rim_dark",
                    "translation": (mx, my, 0.031),
                    "geometry": B.box(0.008, 0.020 if h % 3 == 0 else 0.012, 0.004),
                }
            )
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if p["name"] in {"casing_drum", "dial_face", "center_pin"} else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 0.36, "height": 0.36, "depth": 0.06},
            "Wall clock with circular dark bezel, ivory dial, 12 radial hour tick markers, articulated hour/minute hands, and center cap.",
            "Articulated `hour_hand` and `minute_hand` nodes for time-passage, explainer, and suspense shots.",
            mats,
            parts,
            comps,
            ["hour_hand", "minute_hand"],
        )

    def _build_tree(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "bark_brown", "base_color_rgba": [0.38, 0.25, 0.15, 1.0], "roughness": 0.85, "metallic": 0.0},
            {"slot_name": "foliage_lush", "base_color_rgba": [0.22, 0.56, 0.28, 1.0], "roughness": 0.76, "metallic": 0.0},
        ]
        parts = [
            {"name": "trunk_main", "material_slot": "bark_brown", "translation": (0.0, 0.75, 0.0), "geometry": B.frustum(0.18, 0.10, 1.50, radial_segments=16)},
            {"name": "branch_left", "material_slot": "bark_brown", "translation": (-0.24, 1.35, 0.05), "geometry": B.frustum(0.05, 0.03, 0.55, radial_segments=10, axis="X")},
            {"name": "branch_right", "material_slot": "bark_brown", "translation": (0.22, 1.42, -0.05), "geometry": B.frustum(0.05, 0.03, 0.50, radial_segments=10, axis="X")},
            {"name": "canopy_center", "material_slot": "foliage_lush", "translation": (0.0, 2.05, 0.0), "geometry": B.uv_sphere(0.68, width_segments=16, height_segments=12)},
            {"name": "canopy_left", "material_slot": "foliage_lush", "translation": (-0.42, 1.72, 0.12), "geometry": B.uv_sphere(0.46, width_segments=14, height_segments=10)},
            {"name": "canopy_right", "material_slot": "foliage_lush", "translation": (0.40, 1.78, -0.10), "geometry": B.uv_sphere(0.44, width_segments=14, height_segments=10)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "uv_sphere" if "canopy" in p["name"] else "frustum_cone", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.72, "height": 2.73, "depth": 1.36},
            "Stylized tropical diorama shade tree with tapered bark trunk, side branches, and three clustered spherical foliage crowns.",
            "Exterior street & park diorama vegetation asset.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_modular_building(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "stucco_cream", "base_color_rgba": [0.93, 0.89, 0.81, 1.0], "roughness": 0.78, "metallic": 0.0},
            {"slot_name": "terracotta_roof", "base_color_rgba": [0.72, 0.32, 0.20, 1.0], "roughness": 0.70, "metallic": 0.0},
            {"slot_name": "plinth_stone", "base_color_rgba": [0.36, 0.39, 0.43, 1.0], "roughness": 0.84, "metallic": 0.0},
        ]
        parts = [
            {"name": "foundation_plinth", "material_slot": "plinth_stone", "translation": (0.0, 0.12, 0.0), "geometry": B.box(4.20, 0.24, 3.40)},
            {"name": "main_walls", "material_slot": "stucco_cream", "translation": (0.0, 1.62, 0.0), "geometry": B.box(4.00, 2.76, 3.20)},
            {"name": "roof_eaves", "material_slot": "terracotta_roof", "translation": (0.0, 3.08, 0.0), "geometry": B.box(4.46, 0.16, 3.66)},
            {"name": "roof_crown", "material_slot": "terracotta_roof", "translation": (0.0, 3.56, 0.0), "geometry": B.frustum(2.55, 0.90, 0.82, radial_segments=4)},
            {"name": "porch_canopy", "material_slot": "terracotta_roof", "translation": (0.0, 2.35, 1.85), "geometry": B.box(1.60, 0.10, 0.65)},
            {"name": "entrance_step", "material_slot": "plinth_stone", "translation": (0.0, 0.08, 1.82), "geometry": B.box(1.30, 0.16, 0.40)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "crown" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 4.46, "height": 3.97, "depth": 4.02},
            "Modular Indonesian civic/residential miniature building with stone plinth, cream stucco walls, porch canopy, and hipped terracotta roof.",
            "Modular street/neighborhood diorama structure.",
            mats,
            parts,
            comps,
            [],
        )

    def _build_simple_vehicle(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "car_body_blue", "base_color_rgba": [0.18, 0.46, 0.82, 1.0], "roughness": 0.36, "metallic": 0.32},
            {"slot_name": "cabin_glass", "base_color_rgba": [0.65, 0.84, 0.96, 0.55], "roughness": 0.15, "metallic": 0.0, "alpha_mode": "BLEND"},
            {"slot_name": "tire_rubber", "base_color_rgba": [0.14, 0.15, 0.17, 1.0], "roughness": 0.86, "metallic": 0.0},
            {"slot_name": "headlight_warm", "base_color_rgba": [1.0, 0.95, 0.78, 1.0], "roughness": 0.25, "metallic": 0.0, "emissive_rgb": [1.0, 0.90, 0.60]},
        ]
        parts = [
            {"name": "chassis_lower", "material_slot": "car_body_blue", "translation": (0.0, 0.44, 0.0), "geometry": B.box(1.68, 0.42, 3.40)},
            {"name": "cabin_upper", "material_slot": "car_body_blue", "translation": (0.0, 0.92, -0.15), "geometry": B.box(1.48, 0.54, 1.85)},
            {"name": "windshield_band", "material_slot": "cabin_glass", "translation": (0.0, 0.93, -0.15), "geometry": B.box(1.50, 0.38, 1.88)},
            {"name": "headlight_l", "material_slot": "headlight_warm", "translation": (-0.58, 0.48, 1.71), "geometry": B.frustum(0.09, 0.09, 0.04, radial_segments=14, axis="Z")},
            {"name": "headlight_r", "material_slot": "headlight_warm", "translation": (0.58, 0.48, 1.71), "geometry": B.frustum(0.09, 0.09, 0.04, radial_segments=14, axis="Z")},
        ]
        for name, wx, wz in [("wheel_fl", -0.82, 1.05), ("wheel_fr", 0.82, 1.05), ("wheel_rl", -0.82, -1.05), ("wheel_rr", 0.82, -1.05)]:
            parts.append({"name": name, "material_slot": "tire_rubber", "translation": (wx, 0.30, wz), "geometry": B.frustum(0.30, 0.30, 0.20, radial_segments=18, axis="X")})
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if p["name"].startswith(("wheel", "headlight")) else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.84, "height": 1.19, "depth": 3.44},
            "Stylized miniature city car with lower body, upper cabin, translucent window band, 2 emissive headlights, and 4 cylindrical wheels.",
            "Articulated 4-wheel street vehicle for traffic & civic service shots.",
            mats,
            parts,
            comps,
            ["wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"],
        )

    def _build_pedestal_chart(self) -> tuple[Any, ...]:
        B = MeshPrimitiveBuilder
        mats = [
            {"slot_name": "stage_base", "base_color_rgba": [0.20, 0.24, 0.32, 1.0], "roughness": 0.65, "metallic": 0.10},
            {"slot_name": "bar_primary", "base_color_rgba": [0.24, 0.56, 0.96, 1.0], "roughness": 0.50, "metallic": 0.08},
            {"slot_name": "bar_accent", "base_color_rgba": [0.98, 0.76, 0.24, 1.0], "roughness": 0.50, "metallic": 0.08},
        ]
        parts = [
            {"name": "pedestal_plinth", "material_slot": "stage_base", "translation": (0.0, 0.06, 0.0), "geometry": B.frustum(0.75, 0.72, 0.12, radial_segments=28)},
            {"name": "column_a", "material_slot": "bar_primary", "translation": (-0.26, 0.42, 0.0), "geometry": B.box(0.28, 0.60, 0.28)},
            {"name": "column_b", "material_slot": "bar_accent", "translation": (0.26, 0.67, 0.0), "geometry": B.box(0.28, 1.10, 0.28)},
        ]
        comps = [
            {"component_id": p["name"], "role": p["name"], "primitive_kind": "frustum_cone" if "plinth" in p["name"] else "box", "material_slot": p["material_slot"], "local_offset_m": list(p["translation"])}
            for p in parts
        ]
        return (
            {"width": 1.50, "height": 1.22, "depth": 1.50},
            "Circular 3D data comparison stage plinth with twin articulated comparison columns.",
            "3D explainer quantitative comparison prop.",
            mats,
            parts,
            comps,
            ["column_a", "column_b"],
        )
