"""character_tools needs bpy at runtime; here we only check it parses and exposes the expected API."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "engines" / "blender_scripts" / "character_tools.py"
EXPECTED = {"create_curve", "convert_to_mesh", "join_objects", "apply_all_modifiers", "apply_transforms",
            "add_outline", "sculpt_grab", "sculpt_inflate", "smooth_mesh", "symmetrize_mesh",
            "create_material", "assign_material", "silhouette_bbox", "front_view_extent_px", "set_viewport_view"}


def test_character_tools_parses_and_exposes_api():
    tree = ast.parse(SRC.read_text())
    funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert EXPECTED <= funcs


def test_character_tools_never_touches_camera_or_light_or_tmp():
    text = SRC.read_text()
    assert "/tmp" not in text.replace("never /tmp", "")
    assert '"Camera"' not in text and '"Light"' not in text
