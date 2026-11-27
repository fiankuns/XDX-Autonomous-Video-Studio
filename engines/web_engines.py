"""Python Bridges for Deterministic Three.js, Remotion, and REA-Video Engines."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

WEB_DIR = Path(__file__).resolve().parent / "web"
ROOT_DIR = Path(__file__).resolve().parent.parent


def assert_render_authorized(
    package_dir: Path,
    *,
    required_scope: str = "render_production",
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Fail-closed guard: block Three.js/Remotion/FFmpeg production renders without live trusted approval & dependency match."""
    from governance.canonical_manifest import verify_production_dependencies
    from governance.trusted_approval import assert_phase_boundary
    from intelligence.state_and_approval import ApprovalGate, ProjectStateManager

    pdir = Path(package_dir).resolve()
    rroot = (repo_root or ROOT_DIR).resolve()
    # 1. Verify phase boundary (blocks until Phase 02A execution is explicitly authorized)
    assert_phase_boundary(required_scope, action="web_engine_render")
    # 2. Verify live canonical manifest + Ed25519 signature + ledger + TTL + scope
    ctx = ProjectStateManager(pdir / "project_state.json").build_authorization_context(pdir)
    ApprovalGate().verify_live_execution_context(ctx, required_scope=required_scope)
    # 3. Verify external production dependencies (package.json, engines/web/*, REF-002 profile, guard scripts)
    dep_check = verify_production_dependencies(pdir, rroot)
    return {
        "authorized": True,
        "project_id": ctx.project_id,
        "manifest_digest": ctx.package_digest,
        "scope": required_scope,
        "dependencies_verified": dep_check,
    }


class ThreeJSEngine:
    """Executes deterministic Node/Three.js scene evaluation and compiles shot specs."""

    def is_available(self) -> bool:
        return bool(shutil.which("node") and (ROOT_DIR / "node_modules" / "three").is_dir())

    def run_self_test(self) -> dict[str, Any]:
        proc = subprocess.run(
            ["node", str(WEB_DIR / "three_deterministic_scene.mjs"), "--self-test"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout.strip())

    def compile_shot_spec(self, shot: dict[str, Any], *, fps: int, seed: int) -> dict[str, Any]:
        return {
            "shot_id": shot["shot_id"],
            "engine": "threejs",
            "module": "engines/web/three_deterministic_scene.mjs",
            "fps": fps,
            "frame_count": int(shot["end_frame"]) - int(shot["start_frame"]),
            "seed": seed,
            "camera": shot["camera"],
            "color_space": "SRGBColorSpace",
            "tone_mapping": "ACESFilmicToneMapping",
            "load_barrier_required": True,
        }


class RemotionEngine:
    """Compiles master Remotion composition manifests and verifies frame contiguity."""

    def is_available(self) -> bool:
        return bool(shutil.which("node") and (ROOT_DIR / "node_modules" / "remotion").is_dir())

    def run_self_test(self) -> dict[str, Any]:
        proc = subprocess.run(
            ["node", str(WEB_DIR / "remotion_timeline_spec.mjs"), "--self-test"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout.strip())

    def compile_master_composition(
        self,
        storyboard: dict[str, Any],
        caption_plan: dict[str, Any],
    ) -> dict[str, Any]:
        sequences = []
        for s in storyboard["shots"]:
            sequences.append(
                {
                    "shot_id": s["shot_id"],
                    "from": s["start_frame"],
                    "durationInFrames": s["duration_frames"],
                    "sourceEngine": s["primary_engine"],
                    "transitionIn": s["transition_in"],
                    "captionCueIds": s["caption_cue_ids"],
                }
            )
        return {
            "compositionId": f"XDXMaster_{storyboard['project_id']}",
            "fps": storyboard["fps"],
            "width": storyboard["width"],
            "height": storyboard["height"],
            "durationInFrames": storyboard["total_frames"],
            "sequences": sequences,
            "captionCount": len(caption_plan.get("cues", [])),
            "audioSpec": {
                "sampleRateHz": 48000,
                "targetLufs": -15.0,
                "truePeakDbtp": -1.0,
            },
        }
