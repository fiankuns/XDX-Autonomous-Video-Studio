# Mesh Workbench (vendored source snapshot)
- Upstream: https://github.com/shakystar/mesh-workbench — commit f9fc2d7f149ef77ad73dee59b4686ee76705b7f3 (v0.1.0)
- License: MIT, Copyright (c) 2026 Mesh Workbench contributors (see LICENSE). Attribution required; kept here.
- Contents: `src/mesh_workbench/**/*.py|json` zipped unmodified (no docs/images/examples). Blender itself is a separate dependency under its own license.
- Purpose: selective modeling/QC functions run inside Blender 5.3 on Android via bpy + NumPy. No MCP/gateway is installed. Reviewed for network/subprocess use (subprocess only in cli.py, not loaded).
- Do not edit the zip; our adapters live in `engines/blender_scripts/`.
