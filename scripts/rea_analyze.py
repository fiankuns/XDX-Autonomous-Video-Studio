#!/usr/bin/env python3
"""REA-Video v3.3 Reference Analyzer CLI (preserves rea-video-id/scripts/analyze.py + OpenCV adaptive detector)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from intelligence.rea_reference_intelligence import REAReferenceIntelligence


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--threshold", type=float, default=0.30)
    args = p.parse_args()

    if not (0.0 < args.threshold < 1.0):
        p.error("threshold must be between 0 and 1")

    engine = REAReferenceIntelligence()
    report = engine.analyze_video(args.input, args.out, scene_threshold=args.threshold)
    print(
        f"{len(report['ffmpeg_scene_candidates'])} candidate shots; "
        f"{len(report['adaptive_opencv_candidates']['abrupt_candidates'])} adaptive hits; output: {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
