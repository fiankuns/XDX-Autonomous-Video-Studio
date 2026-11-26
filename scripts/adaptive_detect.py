#!/usr/bin/env python3
"""OpenCV HSV + Laplacian + Pixel MAD Candidate Shot Detector (v3.1/v3.3 compatible)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from intelligence.rea_reference_intelligence import adaptive_detect_candidates


def detect(path: str | Path) -> dict:
    return adaptive_detect_candidates(Path(path))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    result = detect(args.video)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{len(result['abrupt_candidates'])} abrupt candidates; "
        f"{len(result['sustained_change_candidates'])} sustained candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
