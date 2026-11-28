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


def _scene_hashes() -> dict:
    """Hashes of the topic scene plus the generic xdx_core modules/assets it imports (all pixels depend on them)."""
    files = [p for p in sorted(SCENE_DIR.glob("*")) if p.is_file()]
    files += [p for p in sorted((ROOT_DIR / "engines" / "web" / "xdx_core").rglob("*.js")) if p.is_file()]
    return {p.relative_to(ROOT_DIR / "engines" / "web").as_posix(): _sha256(p) for p in files}


def load_package_data(pkg: Path) -> dict:
    sb = json.loads((pkg / "storyboard.json").read_text(encoding="utf-8"))
    cap = json.loads((pkg / "caption_audio_plan.json").read_text(encoding="utf-8"))
    if sb["project_id"] != BENCH_ID:
        raise SystemExit(f"This scene is authored for {BENCH_ID}, not {sb['project_id']}")
    cb = json.loads((pkg / "character_bible.json").read_text(encoding="utf-8"))
    hero = next(c for c in cb["characters"] if c.get("role") == "hero")
    return {
        "style_bible_id": cb["style_bible_id"],
        "character_palette": list(hero["color_palette"]),
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


def render_frames(data: dict, frames_dir: Path, frames: list[int]) -> list[dict]:
    rects: list[dict] = []
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
                r = page.evaluate("(() => { const b = document.getElementById('capbox'); const r = b.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, o: parseFloat(getComputedStyle(b).getPropertyValue('--o') || '1'), t: b.textContent.length}; })()")
                if r["t"] and r["o"] > 0.95 and r["w"] > 0:
                    rects.append({"frame": int(f), "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]})
                page.screenshot(path=str(frames_dir / f"f{f:04d}.png"), clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
            browser.close()
    finally:
        srv.shutdown()
    if errors:
        raise RuntimeError(f"Scene errors during render: {errors[:2]}")
    return rects


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
    ap.add_argument("--animatic", action="store_true",
                    help="whole-video motion preview: every 3rd frame (10 fps) from the SAME engine (prototype only)")
    ap.add_argument("--shot", help="per-shot motion preview: all frames of one shot, e.g. S002 (prototype only)")
    ap.add_argument("--preview", action="store_true",
                    help="storyboard-first style frames: one keyframe per caption cue + contact sheet for owner review (prototype only)")
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
        if a.frames or a.preview or a.animatic or a.shot:
            raise SystemExit("--frames/--preview/--animatic/--shot are only allowed with --prototype")
        from engines.web_engines import assert_render_authorized

        auth = assert_render_authorized(pkg, required_scope="render_production")  # fail closed
        out_dir = pkg / "renders"
        status = "PRODUCTION_RENDER_AUTHORIZED"

    out_dir.mkdir(parents=True, exist_ok=True)
    preview_cues = []
    if a.preview:
        from intelligence.visual_semantic_qc import build_visual_review_checklist

        chk = build_visual_review_checklist(pkg)
        preview_cues = [(c["cue_id"], c["inspect_frame"], c["text"]) for sh in chk["shots"] for c in sh["caption_sync"]]
        frames = [f for _, f, _ in preview_cues]
    elif a.animatic:
        frames = list(range(0, data["total_frames"], 3))
    elif a.shot:
        rng = next((s for s in data["shots"] if s[0] == a.shot), None)
        if rng is None:
            raise SystemExit(f"unknown shot {a.shot}")
        frames = list(range(rng[1], rng[2]))
    else:
        frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(data["total_frames"]))
    with tempfile.TemporaryDirectory(prefix="xdx_p02a_frames_") as tmp:
        tdir = Path(tmp)
        rects = render_frames(data, tdir, frames)
        if a.animatic or a.shot:
            import shutil as _sh
            seq = out_dir / "_seq"
            seq.mkdir(exist_ok=True)
            for i, f in enumerate(frames):
                _sh.copy2(tdir / f"f{f:04d}.png", seq / f"f{i:04d}.png")
            name = f"{BENCH_ID}_{'animatic' if a.animatic else 'shot_' + a.shot}.mp4"
            rate = data["fps"] // 3 if a.animatic else data["fps"]
            encode(seq, rate, out_dir / name)
            _sh.rmtree(seq)
            print(json.dumps({"status": status, "motion_preview": name, "frames": len(frames), "sha256": _sha256(out_dir / name)}, indent=2))
            return 0
        if a.preview:
            names = []
            for cid, f, _ in preview_cues:
                dst = out_dir / f"style_{cid}_f{f:04d}.png"
                shutil.copy2(tdir / f"f{f:04d}.png", dst)
                names.append(dst)
            sheet = out_dir / "style_frames_contact_sheet.png"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-pattern_type", "glob", "-i", str(out_dir / "style_CAP_*.png"),
                            "-vf", "scale=360:-1,tile=4x2:padding=6", "-frames:v", "1", str(sheet)], check=True)
            state = json.loads((pkg / "project_state.json").read_text(encoding="utf-8"))
            man = {
                "schema": "xdx.style-frames.v1",
                "status": "STYLE_FRAMES_FOR_OWNER_REVIEW",
                "purpose": "Storyboard-first gate: the owner approves the look of every caption beat before the full render.",
                "project_id": data["project_id"],
                "package_digest": state.get("package_digest"),
                "scene_sha256": _scene_hashes(),
                "frames": [{"cue_id": cid, "frame": f, "caption": txt, "file": f"style_{cid}_f{f:04d}.png"} for cid, f, txt in preview_cues],
                "contact_sheet": sheet.name,
                "contact_sheet_sha256": _sha256(sheet),
            }
            (out_dir / "style_frames_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps({"status": status, "style_frames": len(names), "contact_sheet": str(sheet)}, indent=2))
            return 0
        if a.frames:
            for f in frames:
                shutil.copy2(tdir / f"f{f:04d}.png", out_dir / f"{BENCH_ID}_f{f:04d}.png")
            print(json.dumps({"status": status, "preview_frames": len(frames), "out_dir": str(out_dir)}, indent=2))
            return 0
        mp4 = out_dir / f"{BENCH_ID}_visual_only.mp4"
        encode(tdir, data["fps"], mp4)
        from intelligence.visual_workflow import build_shot_evidence, check_caption_safe_area, semantic_contract

        safe_issues = check_caption_safe_area(rects)
        (out_dir / f"{BENCH_ID}_caption_safe_area.json").write_text(json.dumps({"frames_checked": len(rects), "issues": safe_issues}, indent=2) + "\n", encoding="utf-8")
        contract = semantic_contract(pkg)
        ev_dir = out_dir / "shot_evidence"
        ev_dir.mkdir(exist_ok=True)
        for b in contract["beats"]:
            for f in set(b["evidence_frames"]):
                shutil.copy2(tdir / f"f{f:04d}.png", ev_dir / f"f{f:04d}.png")
        (out_dir / f"{BENCH_ID}_shot_evidence.json").write_text(
            json.dumps(build_shot_evidence(contract, ev_dir, _sha256(mp4)), indent=2) + "\n", encoding="utf-8")

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
        "scene_sha256": _scene_hashes(),
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
