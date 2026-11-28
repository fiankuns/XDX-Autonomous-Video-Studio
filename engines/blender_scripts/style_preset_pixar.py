"""XDX style preset: Pixar-like stylized 3D (style bible ``xdx_pixar_stylized_3d_v1``).

Applies the style bible to a Blender scene: colour management, studio backdrop, softbox
key / warm fill / soft rim, EEVEE AO, telephoto camera, and a material factory (skin SSS,
clump hair, cotton/twill weave, rubber/canvas). Pure bpy, Android-safe (no /tmp, no addons).
Only touches objects/materials whose names start with ``prefix``.
"""
from __future__ import annotations

import math

try:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
except ImportError:  # imported outside Blender (tests)
    bpy = None
    Vector = None

STYLE_ID = "xdx_pixar_stylized_3d_v1"


def kelvin_rgb(k: float) -> tuple[float, float, float]:
    """Approximate black-body colour (Tanner Helland fit), 0..1."""
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(max(0.0, min(255.0, c)) / 255.0 for c in (r, g, b))


# ------------------------------------------------------------------ scene look
def apply_scene_look(scene=None, *, backdrop=(0.6, 0.6, 0.62)) -> dict:
    scene = scene or bpy.context.scene
    vs = scene.view_settings
    # Tested on device: AgX desaturates saturated yellows to pastel; Standard at -1.05 EV matches the blueprint.
    vs.view_transform = "Standard"
    vs.look = "None"
    look_used = "Standard"
    vs.exposure = -1.05
    scene.render.film_transparent = False
    world = scene.world or bpy.data.worlds.new("XDX_StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (*backdrop, 1.0)
        bg.inputs["Strength"].default_value = 0.9
    ee = getattr(scene, "eevee", None)
    if ee is not None:
        for attr, val in (("use_gtao", True), ("gtao_distance", 0.25), ("use_shadows", True),
                          ("shadow_ray_count", 2), ("use_raytracing", False), ("taa_render_samples", 16)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except (TypeError, AttributeError):
                    pass
    return {"style": STYLE_ID, "look": look_used, "backdrop": backdrop}


# ------------------------------------------------------------------ lights
def _area(name, loc, target, energy, size, kelvin):
    obj = bpy.data.objects.get(name)
    if obj is None:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
    obj.data.shape = "RECTANGLE"
    obj.data.size, obj.data.size_y = size, size * 0.75
    obj.data.energy = energy
    obj.data.color = kelvin_rgb(kelvin)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def apply_studio_lights(prefix: str, *, target=(0.0, 0.0, 0.85), key_energy=260.0) -> list[str]:
    """Front faces -Y. Key front-left high, warm fill front-right low, soft rim behind."""
    made = [
        _area(f"{prefix}Key", (-1.6, -2.2, 2.4), target, key_energy, 2.0, 6200),
        _area(f"{prefix}Fill", (1.9, -1.8, 1.0), target, key_energy * 0.45, 2.5, 4800),
        _area(f"{prefix}Rim", (0.4, 2.3, 2.2), target, key_energy * 0.35, 1.5, 6500),
    ]
    return [o.name for o in made]


def apply_camera(prefix: str, *, loc=(0.0, -6.0, 0.85), target=(0.0, 0.0, 0.8), lens=85.0, ortho_scale=None):
    name = f"{prefix}Cam"
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        bpy.context.scene.collection.objects.link(cam)
    cam.data.dof.use_dof = False
    if ortho_scale:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho_scale
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


# ------------------------------------------------------------------ materials
def _bsdf(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    return nt, b


def _set(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


def _weave_bump(nt, b, strength, scale):
    tex = nt.nodes.new("ShaderNodeTexWave")
    tex.wave_type = "BANDS"
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Distortion"].default_value = 1.5
    tex2 = nt.nodes.new("ShaderNodeTexNoise")
    tex2.inputs["Scale"].default_value = scale * 2.5
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "ADD"
    nt.links.new(tex.outputs["Fac"], mix.inputs[0])
    nt.links.new(tex2.outputs["Fac"], mix.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(mix.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])


def make_material(name: str, kind: str, rgb: tuple[float, float, float]):
    """kind: skin | hair | cotton | twill | rubber | canvas | eye_white | iris | glossy_dark | lip."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt, b = _bsdf(mat)
    _set(b, "Base Color", (*rgb, 1.0))
    if kind == "skin":
        _set(b, "Roughness", 0.45)
        _set(b, "Subsurface Weight", 0.25)
        _set(b, "Subsurface Radius", (1.0, 0.45, 0.25))
        _set(b, "Subsurface Scale", 0.02)
    elif kind == "hair":
        _set(b, "Roughness", 0.35)
        _set(b, "Coat Weight", 0.3)
        _set(b, "Coat Roughness", 0.25)
        _set(b, "Specular IOR Level", 0.6)
    elif kind in ("cotton", "twill"):
        _set(b, "Roughness", 0.85 if kind == "cotton" else 0.8)
        _set(b, "Sheen Weight", 0.35 if kind == "cotton" else 0.25)
        _weave_bump(nt, b, 0.15 if kind == "cotton" else 0.2, 220.0)
    elif kind == "rubber":
        _set(b, "Roughness", 0.65)
    elif kind == "canvas":
        _set(b, "Roughness", 0.9)
        _weave_bump(nt, b, 0.12, 160.0)
    elif kind == "eye_white":
        _set(b, "Roughness", 0.15)
        _set(b, "Coat Weight", 1.0)
    elif kind in ("iris", "glossy_dark"):
        _set(b, "Roughness", 0.2)
        _set(b, "Coat Weight", 0.8)
    elif kind == "lip":
        _set(b, "Roughness", 0.35)
        _set(b, "Subsurface Weight", 0.15)
    return mat


def srgb_hex_to_linear(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def apply_all(prefix: str) -> dict:
    look = apply_scene_look()
    lights = apply_studio_lights(prefix)
    cam = apply_camera(prefix)
    return {"look": look, "lights": lights, "camera": cam.name}
