"""Phase 01.5 Regression Tests — 12 Semantic Assets, Hardened Cache/URL/Zip, Real GLB/Geometry Converter,
Blender Shot Compiler, 7-Tier Preset Accuracy & Cross-Engine Compatibility (Categories 11–17)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from engines.blender_xdx_engine import BlenderXDXEngine
from engines.preset_executors import PresetExecutorEngine
from engines.web_engines import RemotionEngine, ThreeJSEngine
from intelligence.asset_management import (
    AssetBlockedError,
    AssetCacheManager,
    AssetQualityControl,
    AssetRegistryManager,
    AttributionLedger,
    IntelligentAssetPipeline,
    safe_extract_zip,
    sanitize_safe_identifier,
    validate_external_asset_url,
    verify_file_format_and_dependencies,
)
from intelligence.asset_style_converter import (
    HonestRiggingAndRetargetingAdapter,
    RealAssetStyleHarmonizer,
    RealGeometryAndTextureConverter,
    decode_gltf_buffer_zero,
    glb_to_gltf,
    gltf_to_glb,
)
from intelligence.creative_pipeline import PreProductionPackageBuilder
from intelligence.procedural_geometry import SemanticProceduralAssetGenerator
from libraries.loader import VALID_7_TIER_STATUSES, PresetLibraryRegistry

REQUIRED_12_ASSET_CATEGORIES = (
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
)


@pytest.mark.parametrize("category", REQUIRED_12_ASSET_CATEGORIES)
def test_12_semantic_procedural_asset_categories_and_real_geometry(category: str) -> None:
    gen = SemanticProceduralAssetGenerator()
    gltf_bytes, spec, tris = gen.generate_semantic_asset(f"prop_test_{category}_v1", semantic_category=category)

    assert spec["asset_type"] == category
    assert spec["is_placeholder"] is False
    assert len(spec["components"]) >= 5
    assert tris >= 60

    doc = json.loads(gltf_bytes.decode("utf-8"))
    assert len(doc["meshes"]) == len(spec["components"])
    assert len(doc["materials"]) >= 2

    # Roundtrip to binary GLB and back, then run real geometry scaling + Y->Z axis rotation + normal normalization
    glb_bytes = gltf_to_glb(doc)
    assert glb_bytes[:4] == b"glTF"
    parsed_doc, _ = glb_to_gltf(glb_bytes)

    conv = RealGeometryAndTextureConverter()
    transformed_doc, stats = conv.transform_gltf_geometry(
        parsed_doc,
        scale_factor=2.0,
        convert_axis="Y_UP_TO_Z_UP",
        normalize_normals=True,
        snap_bottom_to_ground=True,
    )
    assert stats["vertices_transformed"] > 20
    assert stats["normals_corrected"] == stats["vertices_transformed"]

    # Verify normals in binary buffer are unit length (~1.0)
    raw_bin = decode_gltf_buffer_zero(transformed_doc)
    first_nrm_acc = transformed_doc["accessors"][transformed_doc["meshes"][0]["primitives"][0]["attributes"]["NORMAL"]]
    bv = transformed_doc["bufferViews"][first_nrm_acc["bufferView"]]
    narr = np.frombuffer(raw_bin, dtype="<f4", count=first_nrm_acc["count"] * 3, offset=bv["byteOffset"]).reshape((-1, 3))
    norms = np.linalg.norm(narr, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)


def test_primitive_placeholder_blocked_in_production_and_attribution_preserved(tmp_path: Path) -> None:
    reg_copy = tmp_path / "asset_registry.json"
    orig_reg = Path(__file__).resolve().parent.parent / "registry" / "asset_registry.json"
    reg_copy.write_text(orig_reg.read_text(encoding="utf-8"), encoding="utf-8")

    ledger_path = tmp_path / "attribution_ledger.json"
    pipeline = IntelligentAssetPipeline(
        registry=AssetRegistryManager(reg_copy),
        cache=AssetCacheManager(tmp_path / "cloud_cache", tier="cloud"),
        android_cache=AssetCacheManager(tmp_path / "mobile_cache", tier="android_mobile"),
        attribution_ledger=AttributionLedger(ledger_path),
    )

    # 1. Unknown/unresolvable asset category MUST be BLOCKED rather than emitting a 12-triangle box
    with pytest.raises(AssetBlockedError):
        pipeline.procure_asset("prop_quantum_spaceship_xyz", category="prop_3d", allow_placeholder_greybox=False)

    # 2. Diagnostic placeholder greybox is marked PLACEHOLDER and rejected if re-inspected for final production
    grey = pipeline.procure_asset("prop_greybox_test", category="prop_3d", allow_placeholder_greybox=True)
    assert grey.asset_metadata["is_placeholder"] is True
    assert grey.asset_metadata["qc_status"] == "PLACEHOLDER"

    qc_final = AssetQualityControl().inspect(
        grey.asset_metadata,
        Path(grey.cached_path) if grey.cached_path else None,
        allow_placeholder_for_final=False,
    )
    assert qc_final["passed"] is False
    assert any("PLACEHOLDER" in issue for issue in qc_final["issues"])

    # 3. Valid production asset mirrors to Android cache (.glb) & records provenance in AttributionLedger
    font_res = pipeline.procure_asset("font_plus_jakarta_sans_v1", category="font_typography")
    clock_res = pipeline.procure_asset("prop_wall_clock_v1", category="prop_3d", mirror_to_android_cache=True)
    assert clock_res.android_cached_path is not None
    assert Path(clock_res.android_cached_path).suffix == ".glb"
    assert font_res.asset_metadata["attribution_required"] is True

    entries = AttributionLedger(ledger_path).list_entries()
    by_id = {e["asset_id"]: e for e in entries}
    assert "font_plus_jakarta_sans_v1" in by_id
    assert "SIL Open Font License" in by_id["font_plus_jakarta_sans_v1"]["attribution_text"]


def test_cache_hardening_safe_paths_ssrf_html_spoof_and_zip_slip(tmp_path: Path) -> None:
    # 1. Path traversal rejected
    for bad_id in ("../secret", "a/b", "a\\b", "..", "bad id!"):
        with pytest.raises(ValueError):
            sanitize_safe_identifier(bad_id)

    # 2. SSRF & unapproved hosts blocked
    for bad_url in (
        "http://dl.polyhaven.org/file.glb",
        "https://127.0.0.1/file.glb",
        "https://169.254.169.254/latest/meta-data",
        "https://192.168.1.10/asset.glb",
        "https://user:pass@dl.polyhaven.org/asset.glb",
        "https://untrusted-evil-host.example/asset.glb",
    ):
        with pytest.raises(ValueError):
            validate_external_asset_url(bad_url)
    assert validate_external_asset_url("https://dl.polyhaven.org/file/ph-assets/Models/glb/lamp.glb").startswith("https://")

    # 3. HTTP 200 HTML error page masquerading as .glb / .hdr is rejected
    with pytest.raises(ValueError):
        verify_file_format_and_dependencies(b"<!DOCTYPE html><html>Error 404</html>", ".glb")

    # 4. Zip-Slip path traversal inside archive is blocked
    malicious_zip = tmp_path / "slip.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../escaped.gltf", "{}")
    with pytest.raises(ValueError):
        safe_extract_zip(malicious_zip, tmp_path / "extract_out")

    # 5. Corrupted blob in cache is quarantined automatically
    cache = AssetCacheManager(tmp_path / "quarantine_test", tier="cloud")
    gen = SemanticProceduralAssetGenerator()
    gltf_bytes, _, _ = gen.generate_semantic_asset("prop_book_v1", semantic_category="book")
    cache.put("prop_book_v1", gltf_bytes, extension=".gltf")
    blob = cache.get("prop_book_v1")
    assert blob is not None
    blob.write_bytes(b"CORRUPTED_BYTES")
    assert cache.get("prop_book_v1") is None
    assert len(list(cache.quarantine_dir.glob("corrupt_*"))) == 1

    # 6. Honest rigging/retargeting status disclosure
    rig_spec = HonestRiggingAndRetargetingAdapter().create_retarget_specification("mesh2motion")
    assert rig_spec["bone_mapping_status"] == "UNIT_TESTED"
    assert rig_spec["animation_curve_transfer_status"] == "SPECIFICATION_ONLY"
    assert rig_spec["ik_foot_planting_solver_status"] == "SPECIFICATION_ONLY"


def test_blender_shot_compiler_preset_executors_and_cross_engine_compatibility(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "pkg_150s_cross"
    PreProductionPackageBuilder().build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id="cross_engine_150s",
        target_duration_s=150,
    )
    sb = json.loads((pkg_dir / "storyboard.json").read_text(encoding="utf-8"))
    cap_plan = json.loads((pkg_dir / "caption_audio_plan.json").read_text(encoding="utf-8"))

    # 1. Compile Blender shots offline & validate schema + AST + zero /tmp
    blender_compiler = BlenderXDXEngine()
    blender_shots = [s for s in sb["shots"] if s["primary_engine"] == "blender"]
    assert len(blender_shots) >= 10
    compiled_b = blender_compiler.compile_shot_plan(blender_shots[0], fps=sb["fps"])
    assert compiled_b["execution_mode"] == "OFFLINE_COMPILED_NOT_EXECUTED_ON_DEVICE"
    assert compiled_b["bpy_script_ast_valid"] is True
    assert len(compiled_b["collections"]) == 6
    assert len(compiled_b["character_setups"]) >= 1
    assert "/tmp" not in compiled_b["bpy_setup_script_preview"]

    # 2. Compile Three.js & Remotion master specs and verify cross-engine frame alignment
    three_shots = [s for s in sb["shots"] if s["primary_engine"] == "threejs"]
    assert len(three_shots) >= 5
    three_spec = ThreeJSEngine().compile_shot_spec(three_shots[0], fps=sb["fps"], seed=202601)
    assert three_spec["frame_count"] == three_shots[0]["duration_frames"]

    rem_master = RemotionEngine().compile_master_composition(sb, cap_plan)
    assert rem_master["durationInFrames"] == 4500
    assert sum(seq["durationInFrames"] for seq in rem_master["sequences"]) == 4500

    # 3. Verify all 16 preset libraries use honest 7-tier statuses (zero false RENDER_TESTED / VISUAL_QC_PASSED)
    lib_reg = PresetLibraryRegistry()
    libs = lib_reg.load_all(validate=True)
    for lib in libs.values():
        for p in lib["presets"]:
            assert p["test_status"] in VALID_7_TIER_STATUSES
            assert p["test_status"] not in {"RENDER_TESTED", "VISUAL_QC_PASSED"}

    # 4. Execute all 10 PresetExecutorEngine domains
    exe = PresetExecutorEngine()
    mot = exe.evaluate_object_motion(lib_reg.get_preset("motion_library", "mot_snappy_spring_pop"), local_frame=9, duration_frames=30)
    assert mot["progress"] > 0.0
    body = exe.evaluate_body_animation(lib_reg.get_preset("character_animation_library", "anim_idle_attentive_breath"), local_frame=15, duration_frames=90)
    assert body["ik_foot_lock"] is True
    face = exe.evaluate_facial_expression(lib_reg.get_preset("facial_expression_library", "expr_curious_engaged"), local_frame=8)
    assert face["shape_key_weights"]["brow_inner_up"] == pytest.approx(0.35)
    cam_eval = exe.evaluate_camera_motion(
        blender_shots[0]["camera"],
        lib_reg.get_preset("motion_library", "mot_cinematic_ease_inout"),
        local_frame=30,
        duration_frames=90,
    )
    assert len(cam_eval["position_m"]) == 3
    typo = exe.evaluate_kinetic_typography(lib_reg.get_preset("typography_library", "typo_jakarta_modern_explainer"), "Detik Jam Atom", local_frame=12)
    assert len(typo["words"]) == 3
    cap_eval = exe.evaluate_caption_event(lib_reg.get_preset("caption_library", "cap_xdx_bold_stroke_9x16"), "Pernahkah kamu menyenggol gelas kopi", local_frame=15, cue_duration_frames=60)
    assert cap_eval["line_count"] <= 2
    tr_eval = exe.evaluate_transition_state(lib_reg.get_preset("transition_library", "trans_cross_dissolve_12f"), overlap_frame_index=6)
    assert 0.0 < tr_eval["incoming_alpha"] < 1.0
    pt_eval = exe.evaluate_particle_state(lib_reg.get_preset("particle_library", "part_warm_dust_motes"), local_frame=30)
    assert len(pt_eval["sampled_particles"]) == 16

    test_img = Image.new("RGB", (64, 64), color=(140, 120, 100))
    graded = exe.apply_vfx_grade_to_image(lib_reg.get_preset("vfx_library", "vfx_aces_diorama_clean"), test_img)
    assert graded.size == (64, 64)

    # Also test PNG texture remapping
    img_buf = io.BytesIO()
    Image.new("RGBA", (2048, 1024), color=(100, 150, 200, 255)).save(img_buf, format="PNG")
    remapped_png, tex_stats = RealGeometryAndTextureConverter().remap_texture_png(img_buf.getvalue(), max_dimension=1024)
    assert max(tex_stats["remapped_size"]) == 1024
    assert remapped_png.startswith(b"\x89PNG")

    duck = exe.evaluate_audio_ducking_envelope(
        lib_reg.get_preset("audio_sfx_library", "aud_master_vo_indonesia_15lufs"),
        total_frames=60,
        vo_intervals_frames=[(10, 40)],
    )
    assert min(duck["bgm_gain_db_per_frame"]) == pytest.approx(-11.0, abs=0.5)
