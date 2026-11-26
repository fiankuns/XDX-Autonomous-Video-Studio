"""Tests for Repository Structure, Schemas, Registries, Preset Libraries, Lockfiles & Runtime Availability."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import jsonschema

from engines.ffmpeg_engine import FFmpegEngine
from engines.web_engines import RemotionEngine, ThreeJSEngine
from libraries.loader import REQUIRED_16_LIBRARIES, PresetLibraryRegistry

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_modular_repository_structure_and_gitignore() -> None:
    required_paths = [
        "MASTER_PROMPT.md",
        "SKILL.md",
        "AGENTS.md",
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "package.json",
        "package-lock.json",
        ".gitignore",
        "engines",
        "intelligence",
        "adapters",
        "libraries",
        "registry",
        "schemas",
        "scripts",
        "tests",
        "docs",
    ]
    for rel in required_paths:
        assert (ROOT_DIR / rel).exists(), f"Missing required modular path: {rel}"

    gitignore = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("node_modules/", ".xdx_cache/", "*.blend", "*.glb", ".env", "*auth_token*"):
        assert pattern in gitignore


def test_all_schemas_and_five_registries_valid() -> None:
    schemas_dir = ROOT_DIR / "schemas"
    reg_dir = ROOT_DIR / "registry"

    schema_files = list(schemas_dir.glob("*.schema.json"))
    assert len(schema_files) >= 8
    for sf in schema_files:
        schema_obj = json.loads(sf.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema_obj)

    dep_schema = json.loads((schemas_dir / "dependency_registry.schema.json").read_text(encoding="utf-8"))
    for reg_name in (
        "dependency_registry.json",
        "engine_registry.json",
        "license_registry.json",
        "repository_registry.json",
    ):
        data = json.loads((reg_dir / reg_name).read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=dep_schema)

    repo_reg = json.loads((reg_dir / "repository_registry.json").read_text(encoding="utf-8"))
    # 2 project repos + 33 external GitHub repos + 5 asset sites = 40 entries
    assert len(repo_reg["entries"]) == 40

    asset_schema = json.loads((schemas_dir / "asset_registry.schema.json").read_text(encoding="utf-8"))
    asset_reg = json.loads((reg_dir / "asset_registry.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=asset_reg, schema=asset_schema)


def test_all_16_production_preset_libraries() -> None:
    registry = PresetLibraryRegistry()
    loaded = registry.load_all(validate=True)
    assert len(loaded) == 16
    for lib_id in REQUIRED_16_LIBRARIES:
        assert lib_id in loaded
        for preset in loaded[lib_id]["presets"]:
            for key in ("id", "name", "parameters", "version", "source", "license", "engine_compatibility", "test_status"):
                assert key in preset

    stats = registry.summary_stats()
    assert stats["library_count"] == 16
    assert stats["total_presets"] >= 48
    blender_cams = registry.find_presets(library_id="camera_library", engine="blender")
    assert len(blender_cams) >= 3


def test_lockfiles_and_actual_runtime_availability() -> None:
    req_lock = (ROOT_DIR / "requirements.lock").read_text(encoding="utf-8")
    for pkg in ("pydantic==", "jsonschema==", "numpy==", "opencv-python-headless==", "pytest=="):
        assert pkg in req_lock

    pkg_lock = json.loads((ROOT_DIR / "package-lock.json").read_text(encoding="utf-8"))
    assert pkg_lock.get("lockfileVersion") in (2, 3)

    ffmpeg = FFmpegEngine()
    assert ffmpeg.is_available() is True
    vinfo = ffmpeg.version_info()
    assert "ffmpeg version" in vinfo["banner"]

    three = ThreeJSEngine()
    assert three.is_available() is True
    three_res = three.run_self_test()
    assert three_res["status"] == "ok"
    assert three_res["identical"] is True
    assert three_res["sample"]["threeVersion"] == "187"

    remotion = RemotionEngine()
    assert remotion.is_available() is True
    rem_res = remotion.run_self_test()
    assert rem_res["status"] == "ok"
    assert rem_res["totalFrames"] == 300

    # Honest check: Chromium is available on cloud VM, local desktop Blender is not
    assert bool(shutil.which("google-chrome") or shutil.which("chromium")) is True
    proc = subprocess.run(["python3", "scripts/xdx_studio.py", "validate-all"], cwd=str(ROOT_DIR), capture_output=True, text=True, check=True)
    assert '"status": "VALIDATED"' in proc.stdout
