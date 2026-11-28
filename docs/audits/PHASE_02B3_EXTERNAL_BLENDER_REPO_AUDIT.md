# Phase 02B.3 — External Blender repository audit

Method: read GitHub pages, `git ls-remote` for HEAD SHAs, shallow clones into `/home/claude/ext` (read only, **nothing executed or installed**). Clones are not committed. Status of upstream: as of 2026-11-28.

| # | Repo | Pinned HEAD | Licence (verified from LICENSE file unless noted) | Verdict |
|---|---|---|---|---|
| 1 | jangtrinh/design-os-3d-blender | 7b981a0c05 | **PolyForm Shield 1.0.0** (README says free/source-available; page summary said MIT — wrong) | Ideas only; no code copy (no resale/competing product clause). Needs macOS/Linux + Blender 5.2; Android not addressed. Knowledge on proportions, topology, fidelity gate adapted in our words |
| 2 | jordanfxlab/blend-ai | 01f4310cfd | **AGPL-3.0-or-later** | Do not mix into MIT core. Read-only reference (tool surface, mesh-analysis checklist). Add-on is bpy+stdlib only, server needs `mcp` SDK + uv |
| 3 | shefq/blendrelay-mcp | f080d89cea | MIT server / GPL-3.0-or-later add-on (from page, LICENSE files not opened) | Not compatible with our MCP (would add a second MCP/gateway: forbidden). Desktop paths (Windows) |
| 4 | shakystar/mesh-workbench | f9fc2d7f14 | **MIT** (LICENSE opened; Blender deps separately licensed) | Best reuse candidate: JSON-recipe modeling, silhouette/gap/curvature QC, local patch rebuild. Runs inside Blender with its bundled NumPy; **Android ARM64 untested**. Not integrated yet |
| 5 | blender-studio-pipeline (projects.blender.org, redirected to blender-studio-tools) | not resolved | LICENSE exists, type not read | UNVERIFIED. Useful concepts: CloudRig docs, asset pipeline. Needs Git LFS |
| 6 | makehumancommunity/mpfb2 | d9648f3257 | Separate `LICENSE.CODE.md` / `LICENSE.ASSETS.md`, contents not read | UNVERIFIED; likely copyleft code — treat as external add-on, never bundle. Base-mesh route for realistic humans, not for chibi |
| 7 | Fleynaro/blender-cad | d0739f9137 | **No LICENSE file** | All rights reserved: do not copy. Parametric/boolean assembly ideas only (needs SciPy for solver) |
| 8 | strike-digital/asset_bridge | 41abe1c574 | **No LICENSE file** | Do not copy/use. Poly Haven/ambientCG fetch is covered by our `AutomaticAssetDownloader` + `LicenseValidator` |
| sec. | sverchok, OmooNodes, procedural_room, ai-character-studio, blender-asset-pipeline | — | — | **NOT AUDITED** in this pass (limited scope; rate limits); no claims |
| ext | Rigify, Blender Studio Character Library, Quaternius, Poly Haven, ambientCG | — | — | NOT VERIFIED here; licence must pass `LicenseValidator` at download time |

## Capability comparison vs XDX
- **Already have:** asset registry/licence/cache (`asset_management.py`), procedural geometry, retarget map, visual QC, outline/material helpers (`character_tools.py`).
- **Improved now:** alpha-aware silhouette gate (`intelligence/design_fidelity_gate.py`), Blender Production Skill, Production/Error Memory entries.
- **Reusable later (needs approval):** mesh-workbench recipes and QC (MIT) after an Android ARM64 smoke test inside the real Blender.
- **Incompatible / rejected:** blendrelay-mcp (second MCP), blend-ai (AGPL), blender-cad/asset_bridge (no licence), design-os code (PolyForm Shield).
- **Need external dependency:** mesh-workbench (NumPy inside Blender), MPFB (Blender add-on), CloudRig.

## Report: integrated vs not
- Integrated (code): `design_fidelity_gate.py` (original, 3 tests). Integrated (knowledge): Blender Production Skill, 5 Production Memory techniques tagged `RESEARCHED`.
- Executed from upstream: **none**. Android limits: none of the 8 repos documents Android ARM64; all Blender-add-on claims remain unverified on the Vivo X200 Pro.
- Stopped before any scene mutation or render that was not approved.
