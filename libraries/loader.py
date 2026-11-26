"""Reusable Production Preset Libraries Loader & Validator for XDX Studio v3.3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

LIBRARIES_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = LIBRARIES_DIR.parent / "schemas" / "preset_library.schema.json"

REQUIRED_16_LIBRARIES: tuple[str, ...] = (
    "motion_library",
    "character_animation_library",
    "facial_expression_library",
    "lip_sync_library",
    "camera_library",
    "caption_library",
    "typography_library",
    "transition_library",
    "vfx_library",
    "particle_library",
    "lighting_library",
    "material_library",
    "environment_library",
    "audio_sfx_library",
    "asset_3d_library",
    "visual_explainer_library",
)


class PresetLibraryRegistry:
    """Loads, validates, and queries all 16 reusable production preset libraries."""

    def __init__(self, libraries_dir: Path | None = None, schema_path: Path | None = None) -> None:
        self.libraries_dir = libraries_dir or LIBRARIES_DIR
        self.schema_path = schema_path or SCHEMA_PATH
        self._schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self._libraries: dict[str, dict[str, Any]] = {}

    def load_all(self, *, validate: bool = True) -> dict[str, dict[str, Any]]:
        loaded: dict[str, dict[str, Any]] = {}
        for lib_id in REQUIRED_16_LIBRARIES:
            path = self.libraries_dir / f"{lib_id}.json"
            if not path.is_file():
                raise FileNotFoundError(f"Missing required preset library: {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if validate:
                jsonschema.validate(instance=data, schema=self._schema)
            loaded[lib_id] = data
        self._libraries = loaded
        return loaded

    def get_library(self, library_id: str) -> dict[str, Any]:
        if not self._libraries:
            self.load_all(validate=True)
        if library_id not in self._libraries:
            raise KeyError(f"Unknown library_id: {library_id}")
        return self._libraries[library_id]

    def get_preset(self, library_id: str, preset_id: str) -> dict[str, Any]:
        lib = self.get_library(library_id)
        for preset in lib["presets"]:
            if preset["id"] == preset_id:
                return preset
        raise KeyError(f"Preset '{preset_id}' not found in '{library_id}'")

    def find_presets(
        self,
        *,
        library_id: str | None = None,
        engine: str | None = None,
        genre: str | None = None,
        only_tested: bool = False,
    ) -> list[dict[str, Any]]:
        if not self._libraries:
            self.load_all(validate=True)
        libs = [self._libraries[library_id]] if library_id else list(self._libraries.values())
        matches: list[dict[str, Any]] = []
        for lib in libs:
            for preset in lib["presets"]:
                if engine and engine not in preset["engine_compatibility"]:
                    continue
                if genre and preset.get("genres") and genre not in preset["genres"]:
                    continue
                if only_tested and preset["test_status"] != "tested":
                    continue
                matches.append({**preset, "_library_id": lib["library_id"]})
        return matches

    def summary_stats(self) -> dict[str, Any]:
        if not self._libraries:
            self.load_all(validate=True)
        total_presets = sum(len(lib["presets"]) for lib in self._libraries.values())
        by_status: dict[str, int] = {}
        for lib in self._libraries.values():
            for p in lib["presets"]:
                st = p["test_status"]
                by_status[st] = by_status.get(st, 0) + 1
        return {
            "library_count": len(self._libraries),
            "total_presets": total_presets,
            "by_test_status": by_status,
        }
