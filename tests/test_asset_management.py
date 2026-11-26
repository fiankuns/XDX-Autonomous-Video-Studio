"""Tests for Intelligent Asset Management (All 11 Components, Cache, License Validator & 9-Step Order)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.asset_management import (
    AssetCacheManager,
    AssetDiscoveryEngine,
    AssetQualityControl,
    AssetRegistryManager,
    AssetStyleHarmonizer,
    CharacterRetargetingEngine,
    CrossEngineAssetConverter,
    IntelligentAssetPipeline,
    LicenseValidationError,
    LicenseValidator,
    ProceduralAssetGenerator,
    RepositoryRegistryManager,
)


def test_license_validator_accepts_permissive_and_blocks_unlicensed_or_copyleft() -> None:
    validator = LicenseValidator()
    assert validator.validate("MIT")["valid"] is True
    assert validator.validate("CC0-1.0")["attribution_required"] is False
    assert validator.validate("OFL-1.1")["attribution_required"] is True

    with pytest.raises(LicenseValidationError):
        validator.validate("UNLICENSED")

    with pytest.raises(LicenseValidationError):
        validator.validate("UNKNOWN_CUSTOM_XYZ")

    # AGPL-3.0 and GPL-3.0 cannot be directly bundled into MIT core
    with pytest.raises(LicenseValidationError):
        validator.validate("AGPL-3.0", require_direct_bundle=True)
    with pytest.raises(LicenseValidationError):
        validator.validate("GPL-3.0", require_direct_bundle=True)


def test_cache_manager_sha256_integrity_and_lru_quota(tmp_path: Path) -> None:
    cache = AssetCacheManager(cache_dir=tmp_path / "cache", max_cache_bytes=500)
    rec1 = cache.put("prop_a", b"A" * 200, extension=".bin")
    assert len(rec1["sha256"]) == 64
    blob_a = cache.get("prop_a")
    assert blob_a is not None and blob_a.read_bytes() == b"A" * 200

    # Adding 2nd & 3rd items exceeding 500 bytes evicts oldest LRU entry
    cache.put("prop_b", b"B" * 200, extension=".bin")
    cache.put("prop_c", b"C" * 200, extension=".bin")
    assert cache.get("prop_a") is None
    assert cache.get("prop_b") is not None
    assert cache.get("prop_c") is not None

    # Corrupting cached file on disk triggers SHA-256 mismatch rejection
    blob_b = cache.get("prop_b")
    assert blob_b is not None
    blob_b.write_bytes(b"TAMPERED")
    assert cache.get("prop_b") is None


def test_9_step_asset_procurement_procedural_and_external_and_retargeting(tmp_path: Path) -> None:
    reg_copy = tmp_path / "asset_registry.json"
    orig_reg = Path(__file__).resolve().parent.parent / "registry" / "asset_registry.json"
    reg_copy.write_text(orig_reg.read_text(encoding="utf-8"), encoding="utf-8")

    pipeline = IntelligentAssetPipeline(
        registry=AssetRegistryManager(reg_copy),
        repo_registry=RepositoryRegistryManager(),
        cache=AssetCacheManager(tmp_path / "xdx_cache"),
        license_validator=LicenseValidator(),
        procedural=ProceduralAssetGenerator(),
        harmonizer=AssetStyleHarmonizer(),
        converter=CrossEngineAssetConverter(),
        qc=AssetQualityControl(),
    )

    # 1. Unknown asset falls through to Step 6 Procedural glTF 2.0 -> Harmonize -> QC -> Cache
    res_proc = pipeline.procure_asset("prop_custom_lamp_v1", category="prop_3d", target_engine="threejs", persist_registry=True)
    assert res_proc.resolution_source == "procedural_generated"
    assert res_proc.steps_executed == [
        "1_check_registry",
        "2_check_cache",
        "3_discover_external_asset",
        "4_validate_license_and_compatibility",
        "6_generate_procedural_fallback",
        "7_harmonize_global_style_bible",
        "8_validate_asset_quality",
        "9_persist_for_reuse",
    ]
    assert res_proc.qc_report["passed"] is True
    assert res_proc.qc_report["triangle_count_measured"] == 12
    assert res_proc.cached_path is not None
    gltf_doc = json.loads(Path(res_proc.cached_path).read_text(encoding="utf-8"))
    assert gltf_doc["asset"]["version"] == "2.0"

    # 2. Second request hits Registry + Cache directly without regenerating
    res_hit = pipeline.procure_asset("prop_custom_lamp_v1", category="prop_3d", target_engine="threejs")
    assert res_hit.resolution_source == "registry_and_cache"

    # 3. External discovery with UNLICENSED asset is blocked at Step 4
    bad_pipeline = IntelligentAssetPipeline(
        registry=AssetRegistryManager(reg_copy),
        cache=AssetCacheManager(tmp_path / "xdx_cache"),
        external_lookup_fn=lambda aid, cat: {
            "provider": "UnlicensedRepo",
            "license_spdx": "UNLICENSED",
            "compatible_engines": ["threejs"],
            "inline_bytes": b"{}",
        },
    )
    with pytest.raises(LicenseValidationError):
        bad_pipeline.procure_asset("prop_bad_unlicensed", category="prop_3d")

    # 4. Character Retargeting & Storyboard Discovery
    retarget = CharacterRetargetingEngine().create_retarget_map("mesh2motion")
    assert retarget["bone_mapping"]["hips"] == "Hips"
    assert retarget["ik_foot_plant_enforced"] is True

    reqs = AssetDiscoveryEngine().infer_requirements_from_storyboard(
        {
            "shots": [
                {
                    "shot_id": "S001",
                    "primary_engine": "blender",
                    "environment_id": "env_kamar_indonesia_modular_v1",
                    "asset_ids": ["char_hero_diorama_base_v1", "prop_custom_lamp_v1"],
                }
            ]
        }
    )
    assert len(reqs) == 3
