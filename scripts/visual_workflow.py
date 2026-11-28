#!/usr/bin/env python3
"""XDX visual workflow CLI (read-only checks; renders stay in scripts/render_phase02a_visual.py behind the guard).

  validate-inputs <package>                      input + environment validation
  timeline <package> [--chapter-seconds N]       canonical integer-frame timeline (+ logical chapters)
  contract <package>                             semantic visual contract per beat
  rerender-plan <package> --deps FILE [--cache FILE] [--update]   shots to re-render (hash + dependency based)
  delivery <package> --render-dir DIR [--review RESULT.json]      production delivery validation

Exit codes: 0 OK/WARN, 2 BLOCKED. Audio, TTS, music, SFX and lip sync are out of scope until Phase 04.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from intelligence import visual_workflow as vw  # noqa: E402


def _out(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("validate-inputs", "timeline", "contract", "rerender-plan", "delivery"):
        s = sub.add_parser(n)
        s.add_argument("package")
        if n == "timeline":
            s.add_argument("--chapter-seconds", type=float)
        if n == "rerender-plan":
            s.add_argument("--deps", required=True)
            s.add_argument("--cache")
            s.add_argument("--update", action="store_true")
        if n == "delivery":
            s.add_argument("--render-dir", required=True)
            s.add_argument("--review")
    a = ap.parse_args()
    pkg = Path(a.package).resolve()

    if a.cmd == "validate-inputs":
        r = vw.validate_inputs(pkg)
    elif a.cmd == "timeline":
        tl = vw.canonical_timeline(pkg)
        r = vw.plan_chapters(tl, a.chapter_seconds) if a.chapter_seconds else tl
    elif a.cmd == "contract":
        r = vw.semantic_contract(pkg)
    elif a.cmd == "rerender-plan":
        deps = json.loads(Path(a.deps).read_text(encoding="utf-8"))
        cur = vw.shot_input_hashes(pkg, deps)
        cache = Path(a.cache) if a.cache else None
        prev = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.is_file() else None
        r = {**vw.plan_selective_rerender(cur, prev), "shot_hashes": cur}
        if a.update and cache:
            cache.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    else:
        rd = Path(a.render_dir)
        bid = json.loads((pkg / "storyboard.json").read_text(encoding="utf-8"))["project_id"]
        load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None  # noqa: E731
        sa = load(rd / f"{bid}_caption_safe_area.json")
        r = vw.validate_delivery(
            rd / f"{bid}_visual_only.mp4",
            package_dir=pkg,
            render_manifest=load(rd / f"{bid}_render_manifest.json") or {},
            asset_bindings=load(pkg / "asset_bindings.json") or {"bindings": []},
            evidence=load(rd / f"{bid}_shot_evidence.json"),
            review_result=load(Path(a.review)) if a.review else None,
            safe_area_report=sa["issues"] if sa else None,
        )
    _out(r)
    return 2 if r.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
