#!/usr/bin/env python3
"""XDX visual workflow CLI (read-only checks; renders stay in scripts/render_phase02a_visual.py behind the guard).

  validate-inputs <package>                      input + environment validation
  timeline <package> [--chapter-seconds N]       canonical integer-frame timeline (+ logical chapters)
  contract <package>                             semantic visual contract per beat
  rerender-plan <package> --deps FILE [--cache FILE] [--update]   shots to re-render (hash + dependency based)
  retime <package> S001=5.5 S002=6                content-driven shot durations (only while the package is unapproved)
  apply-spec <package>                            validate shot_spec.json, compile action_events.json, suggest durations
  verify-actions <package>                        geometric verification of action_events.json (real scene probes, no pixels)
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
    for n in ("validate-inputs", "timeline", "contract", "rerender-plan", "verify-actions", "retime", "apply-spec", "delivery"):
        s = sub.add_parser(n)
        s.add_argument("package")
        if n == "timeline":
            s.add_argument("--chapter-seconds", type=float)
        if n == "retime":
            s.add_argument("durations", nargs="+", help="SHOT=seconds")
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
    elif a.cmd == "retime":
        r = vw.retime_package(pkg, {k: float(v) for k, v in (x.split("=") for x in a.durations)})
    elif a.cmd == "apply-spec":
        from intelligence import shot_spec as ss

        spec = ss.load_shot_spec(pkg)
        if spec is None:
            raise SystemExit("package has no shot_spec.json")
        tl = vw.canonical_timeline(pkg)
        issues = ss.validate_shot_spec(spec, tl)
        r = {"status": "BLOCKED" if issues else "OK", "issues": issues, "suggested_shot_seconds": ss.suggest_durations(spec, tl)}
        if not issues:
            (pkg / "action_events.json").write_text(json.dumps(ss.compile_action_events(spec), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif a.cmd == "verify-actions":
        from intelligence import action_choreography as ac
        from scripts.render_phase02a_visual import load_package_data, probe_frames

        spec = ac.load_action_events(pkg)
        if spec is None:
            raise SystemExit("package has no action_events.json")
        tl = vw.canonical_timeline(pkg)
        from intelligence import callout_contract as cc

        pr = probe_frames(load_package_data(pkg), sorted(set(ac.needed_frames(spec, tl["cues"])) | set(range(0, tl["total_frames"], 5))))
        r = ac.evaluate_events(spec, tl["cues"], pr)
        r["callouts"] = cc.evaluate_callouts(pr)
        if r["callouts"]["status"] != "OK":
            r["status"] = "BLOCKED"
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
            action_report=load(rd / f"{bid}_action_verification.json"),
            callout_report=load(rd / f"{bid}_callout_verification.json"),
        )
    _out(r)
    return 2 if r.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
