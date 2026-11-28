#!/usr/bin/env python3
"""Phase 02A visual renderer (VISUAL_ONLY_BENCHMARK) for bench_p02a_ac_15s.

    # production: requires a live trusted approval (Ed25519 token, canonical manifest, ledger, TTL, scope),
    # an open Phase 02 boundary and pinned dependencies; output goes to projects/<id>/renders/
    python scripts/render_phase02a_visual.py projects/bench_p02a_ac_15s

    # prototype: human-run visual iteration only; output MUST be outside the repository and is stamped
    # NON_PRODUCTION_PROTOTYPE (never a deliverable, never recorded in the package)
    python scripts/render_phase02a_visual.py projects/bench_p02a_ac_15s --prototype --out ~/xdx_proto

Rendering: headless Chrome + SwiftShader WebGL, one deterministic PNG per frame (pure function of the frame
index), encoded to H.264 yuv420p WITHOUT an audio track (``-an``; audio is deferred to Phase 04). Captions and shot
ranges are read from the package (caption_audio_plan.json, storyboard.json). The result is checked with
VisualQualityControlEngine(delivery_profile="VISUAL_ONLY_BENCHMARK"); semantic acceptance still needs an independent
review via scripts/visual_review.py.

The execution guard hook classifies this script as a production render command (blocked for agents without approval).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from governance.phase_scope import PHASE02A_DELIVERY_PROFILE  # noqa: E402

SCENE_DIR = ROOT_DIR / "engines" / "web" / "phase02a_ac15s"
BENCH_ID = "bench_p02a_ac_15s"
CHROME_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--enable-webgl",
               "--ignore-gpu-blocklist", "--force-color-profile=srgb"]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_package_data(pkg: Path) -> dict:
    sb = json.loads((pkg / "storyboard.json").read_text(encoding="utf-8"))
    cap = json.loads((pkg / "caption_audio_plan.json").read_text(encoding="utf-8"))
    if sb["project_id"] != BENCH_ID:
        raise SystemExit(f"This scene is authored for {BENCH_ID}, not {sb['project_id']}")
    return {
        "project_id": sb["project_id"],
        "total_frames": sb["total_frames"],
        "fps": sb["fps"],
        "shots": [[s["shot_id"], s["start_frame"], s["end_frame"]] for s in sb["shots"]],
        "cues": [[c["shot_id"], c["start_s"], c["end_s"], c["text"], c.get("highlighted_keyword") or ""] for c in cap["cues"]],
    }


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def render_frames(data: dict, frames_dir: Path, frames: list[int]) -> None:
    from playwright.sync_api import sync_playwright

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT_DIR)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    errors: list[str] = []
    try:
        with sync_playwright() as pw:
            kw = {"executable_path": chrome} if chrome else {}
            browser = pw.chromium.launch(headless=True, args=CHROME_ARGS, **kw)
            page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(f"window.__XDX_PACKAGE = {json.dumps(data, ensure_ascii=False)};")
            page.goto(f"http://127.0.0.1:{port}/engines/web/phase02a_ac15s/index.html")
            page.wait_for_function("window.__ready !== undefined || window.__xdxError", timeout=120000)
            if errors:
                raise RuntimeError(f"Scene failed to load: {errors[:2]}")
            page.evaluate("window.__ready")
            for f in frames:
                page.evaluate(f"window.renderFrame({int(f)})")
                page.screenshot(path=str(frames_dir / f"f{f:04d}.png"), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            browser.close()
    finally:
        srv.shutdown()
    if errors:
        raise RuntimeError(f"Scene errors during render: {errors[:2]}")


def encode(frames_dir: Path, fps: int, out_mp4: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", str(fps), "-i", str(frames_dir / "f%04d.png"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-an",
         "-movflags", "+faststart", str(out_mp4)],
        check=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package_dir")
    ap.add_argument("--prototype", action="store_true", help="non-production visual iteration (output outside the repo)")
    ap.add_argument("--out", help="output directory (required with --prototype; must be outside the repository)")
    ap.add_argument("--frames", help="comma-separated frame list for previews (prototype only)")
    a = ap.parse_args()

    pkg = Path(a.package_dir).resolve()
    data = load_package_data(pkg)

    if a.prototype:
        if not a.out:
            raise SystemExit("--prototype requires --out <dir outside the repository>")
        out_dir = Path(a.out).expanduser().resolve()
        if _inside(out_dir, ROOT_DIR):
            raise SystemExit("Prototype output must be outside the repository (it is never a production deliverable)")
        status = "NON_PRODUCTION_PROTOTYPE"
        auth = None
    else:
        if a.frames:
            raise SystemExit("--frames is only allowed with --prototype")
        from engines.web_engines import assert_render_authorized

        auth = assert_render_authorized(pkg, required_scope="render_production")  # fail closed
        out_dir = pkg / "renders"
        status = "PRODUCTION_RENDER_AUTHORIZED"

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(data["total_frames"]))
    with tempfile.TemporaryDirectory(prefix="xdx_p02a_frames_") as tmp:
        tdir = Path(tmp)
        render_frames(data, tdir, frames)
        if a.frames:
            for f in frames:
                shutil.copy2(tdir / f"f{f:04d}.png", out_dir / f"{BENCH_ID}_f{f:04d}.png")
            print(json.dumps({"status": status, "preview_frames": len(frames), "out_dir": str(out_dir)}, indent=2))
            return 0
        mp4 = out_dir / f"{BENCH_ID}_visual_only.mp4"
        encode(tdir, data["fps"], mp4)

    from intelligence.visual_qc_engine import VisualQualityControlEngine

    qc = VisualQualityControlEngine().evaluate_video(mp4, delivery_profile=PHASE02A_DELIVERY_PROFILE)
    manifest = {
        "schema": "xdx.phase02a-render-manifest.v1",
        "status": status,
        "delivery_profile": PHASE02A_DELIVERY_PROFILE,
        "project_id": data["project_id"],
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "output": mp4.name,
        "output_sha256": _sha256(mp4),
        "scene_sha256": {p.name: _sha256(p) for p in sorted(SCENE_DIR.glob("*")) if p.is_file()},
        "authorization": auth,
        "technical_qc_status": qc["overall_status"],
        "technical_qc_defects": qc["defects"],
        "independent_visual_review": "PENDING (scripts/visual_review.py; reviewer must not be the producer)",
    }
    (out_dir / f"{BENCH_ID}_render_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("status", "output", "output_sha256", "technical_qc_status")}, indent=2))
    return 0 if qc["overall_status"] in {"PASS", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
