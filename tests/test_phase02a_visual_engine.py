"""Phase 02A visual engine (engines/web/phase02a_ac15s + scripts/render_phase02a_visual.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from governance.canonical_manifest import verify_production_dependencies

ROOT_DIR = Path(__file__).resolve().parent.parent
BENCH = ROOT_DIR / "projects" / "bench_p02a_ac_15s"
SCRIPT = ROOT_DIR / "scripts" / "render_phase02a_visual.py"
SCENE = ROOT_DIR / "engines" / "web" / "phase02a_ac15s"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT_DIR, capture_output=True, text=True, timeout=600)


def test_p02a_ve_01_production_render_fails_closed_without_approval() -> None:
    renders = BENCH / "renders"
    existed = renders.exists()
    res = _run(str(BENCH))
    assert res.returncode != 0
    assert "PhaseBoundaryBlockedError" in res.stderr or "ApprovalAuthorizationError" in res.stderr or "Error" in res.stderr
    assert renders.exists() == existed  # nothing written into the package


def test_p02a_ve_02_prototype_output_must_stay_outside_repo(tmp_path: Path) -> None:
    res = _run(str(BENCH), "--prototype", "--out", str(ROOT_DIR / "projects" / "bench_p02a_ac_15s" / "renders"))
    assert res.returncode != 0 and "outside the repository" in res.stderr
    res = _run(str(BENCH), "--prototype")
    assert res.returncode != 0 and "--out" in res.stderr
    res = _run(str(BENCH), "--frames", "1,2")
    assert res.returncode != 0 and "--prototype" in res.stderr


def test_p02a_ve_03_guard_hook_treats_renderer_as_production_render() -> None:
    ev = {"tool_name": "bash", "arguments": {"CommandLine": f"python scripts/render_phase02a_visual.py {BENCH} --prototype --out /tmp/x"}}
    p = subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "execution_guard_hook.py")], input=json.dumps(ev),
                       capture_output=True, text=True, cwd=ROOT_DIR)
    assert p.returncode == 2 and json.loads(p.stdout)["decision"] == "block"


def test_p02a_ve_04_scene_reads_captions_from_package_and_is_pinned() -> None:
    scene = (SCENE / "scene.js").read_text(encoding="utf-8")
    cap = json.loads((BENCH / "caption_audio_plan.json").read_text(encoding="utf-8"))
    for cue in cap["cues"]:
        assert cue["text"] not in scene, "caption text must come from the signed package, not the scene"
    assert "window.__XDX_PACKAGE" in scene and "EXPECTED_SHOTS" in scene
    for banned in ("Math.random", "Date.now", "performance.now", "requestAnimationFrame"):
        assert banned not in scene, f"non-deterministic API {banned} in scene"
    for debug in ("SHOT 0", "f0", "Phase 02A •", "XDX Phase"):
        assert debug not in (SCENE / "index.html").read_text(encoding="utf-8")
    deps = json.loads((BENCH / "production_dependencies.json").read_text(encoding="utf-8"))["dependencies"]
    for f in ("engines/web/phase02a_ac15s/scene.js", "engines/web/phase02a_ac15s/index.html", "scripts/render_phase02a_visual.py"):
        assert f in deps
    verify_production_dependencies(BENCH, ROOT_DIR)


def _can_render() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return bool((shutil.which("google-chrome") or shutil.which("chromium")) and shutil.which("ffmpeg")
                and (ROOT_DIR / "node_modules" / "three").is_dir()
                and (ROOT_DIR / "node_modules" / "@fontsource" / "plus-jakarta-sans").is_dir())


@pytest.mark.skipif(not _can_render(), reason="headless Chrome / playwright / node_modules not available")
def test_p02a_ve_05_prototype_preview_renders_real_frames(tmp_path: Path) -> None:
    import cv2 as cv
    import numpy as np

    res = _run(str(BENCH), "--prototype", "--out", str(tmp_path), "--frames", "30,270")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["status"] == "NON_PRODUCTION_PROTOTYPE"
    imgs = [cv.imread(str(tmp_path / f"bench_p02a_ac_15s_f{f:04d}.png")) for f in (30, 270)]
    for img in imgs:
        assert img is not None and img.shape[:2] == (1920, 1080)
        assert float(np.std(img)) > 20  # real content, not a blank frame
    assert float(np.mean(np.abs(imgs[0].astype(int) - imgs[1].astype(int)))) > 10  # different shots
