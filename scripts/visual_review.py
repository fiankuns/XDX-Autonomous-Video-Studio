#!/usr/bin/env python3
"""Independent Visual QC CLI (Phase 02A, VISUAL_ONLY_BENCHMARK).

    python scripts/visual_review.py checklist projects/<id>                  # what each shot must show
    python scripts/visual_review.py frames projects/<id> render.mp4 out_dir  # extract frames to inspect (+ contact sheet)
    python scripts/visual_review.py evaluate projects/<id> review.json --render render.mp4 --producer <id> [...]

Exit codes for ``evaluate``: 0 PASS, 1 WARN, 2 HARD_FAIL, 3 INCOMPLETE.
The checklist is written to ``projects/<id>/.reviews/visual_review_checklist.json`` (dot-dir: outside the signed
canonical manifest, so reviewing never changes the approved digest). Audio is not part of this review (Phase 04).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from intelligence.visual_semantic_qc import build_visual_review_checklist, evaluate_visual_review  # noqa: E402


def _checklist(pkg: Path) -> dict:
    chk = build_visual_review_checklist(pkg)
    out = pkg / ".reviews" / "visual_review_checklist.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return chk


def cmd_checklist(a: argparse.Namespace) -> int:
    print(json.dumps(_checklist(Path(a.package_dir)), indent=2, ensure_ascii=False))
    return 0


def cmd_frames(a: argparse.Namespace) -> int:
    if not shutil.which("ffmpeg"):
        print(json.dumps({"error": "ffmpeg not available"}))
        return 2
    chk = _checklist(Path(a.package_dir))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fps = chk["fps"]
    written = []
    for shot in chk["shots"]:
        for f in shot["frames_to_inspect"]:
            dst = out / f"{shot['shot_id']}_f{f:04d}.png"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{f / fps:.6f}", "-i", str(a.render),
                 "-frames:v", "1", str(dst)],
                check=True,
            )
            written.append(str(dst))
    sheet = out / "contact_sheet.png"
    cols = 3
    rows = len(chk["shots"])
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-pattern_type", "glob", "-i", str(out / "S*_f*.png"),
         "-vf", f"scale=360:-1,tile={cols}x{rows}:padding=6", "-frames:v", "1", str(sheet)],
        check=False,
    )
    print(json.dumps({"frames": written, "contact_sheet": str(sheet) if sheet.exists() else None}, indent=2))
    return 0


def cmd_evaluate(a: argparse.Namespace) -> int:
    chk = _checklist(Path(a.package_dir))
    review = json.loads(Path(a.review).read_text(encoding="utf-8"))
    res = evaluate_visual_review(
        chk,
        review,
        producer_ids=set(a.producer or []),
        render_path=Path(a.render) if a.render else None,
        reference_sha256=a.reference_sha256,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return {"PASS": 0, "WARN": 1, "HARD_FAIL": 2, "INCOMPLETE": 3}[res["status"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("checklist")
    p.add_argument("package_dir")
    p.set_defaults(fn=cmd_checklist)
    p = sub.add_parser("frames")
    p.add_argument("package_dir")
    p.add_argument("render")
    p.add_argument("out_dir")
    p.set_defaults(fn=cmd_frames)
    p = sub.add_parser("evaluate")
    p.add_argument("package_dir")
    p.add_argument("review")
    p.add_argument("--render")
    p.add_argument("--producer", action="append", help="producer agent/person id (repeatable)")
    p.add_argument("--reference-sha256", dest="reference_sha256")
    p.set_defaults(fn=cmd_evaluate)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
