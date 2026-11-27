# XDX internal reference database — staged import

Status: METADATA_ONLY; original MP4 objects have NOT been uploaded. Do not claim retrieval, REA analysis, integration or production success. The two source files are in the user's seed ZIP. Import the originals only if rights-cleared for private storage. Keep the existing private Studio repository and Blender backend unchanged. Phase 01.5 is not executed by this import.

Additive directory, do not overwrite root files. The registry paths are relative to this directory. Use Git LFS only for reference MP4s, with the existing authorized Git session. Verify the size and SHA-256 from reference_registry.json before staging and after a fresh checkout. Never create dummy LFS pointers or placeholders. Use the existing Studio REA CLI after source verification, and review actual frames and audio; baseline detection is not a complete multimodal analysis. Read integration/AGENT_REFERENCE_RULES.md. No reference grants production approval. Preserve previous analyses and profiles. Until media is available, report MEDIA_MISSING rather than ask the analyzer to invent results.

Remaining tasks: import original MP4s and remaining seed files; verify LFS fresh checkout; integrate the read-only selector with existing Studio planning and approval interfaces; run regression tests. No Blender mutations, pairing changes, or production renders.
