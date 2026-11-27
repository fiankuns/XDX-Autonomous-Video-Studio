# XDX Studio v4.0 — Phase 01.6D Implementation Plan & Phase 01.6C Remaining Limitations

## 1. Purpose & Phase Boundary

Phase 01.6C (`feat/phase-01.6c-universal-creative-intelligence`) intentionally enforces a **Production Approval Freeze** (`ProductionApprovalFrozenError` in `orchestration/shared_state.py` and `PhaseBoundaryExecutionBlockedError` in `orchestration/dependency_scheduler.py`):

- All transitions to `APPROVED` and post-approval production states (`ASSET_PROCUREMENT`, `BLENDER_BUILD`, `ANIMATION`, `RENDERING`, `COMPOSITING`, `VISUAL_QC`, `FINAL_AUDIT`, `COMPLETED`) are strictly blocked prior to Phase 01.6D.
- Agent-crafted approval dictionaries, `actor` labels, unvalidated digests, `trusted_channel_verified=False`, and boolean configuration flags (`allow_production_approval=True`, `allow_phase02_roles=True`) are all rejected fail-closed.
- Zero video rendering, zero 3D asset modeling, zero animation execution, and zero Blender scene mutations occur in Phase 01.6C.

Phase 01.6D will unlock **Trusted Human Approval** and **Runtime Execution Guard Hooks** without weakening any Phase 01.5, 01.6A, 01.6B, or 01.6C invariants.

---

## 2. Explicit Remaining Limitations at End of Phase 01.6C

1. **Production Approval Remains Frozen Until Phase 01.6D**:
   - `SharedProjectStateMachine.transition("APPROVED", ...)` raises `ProductionApprovalFrozenError` unconditionally in Phase 01.6C. Out-of-band human cryptographic approval verification and channel authenticity are scheduled for Phase 01.6D (`DEF-P016B-015`).
2. **Narration, Audio, and Caption Timestamps Are `ESTIMATED` Only**:
   - All pre-production packages use `NarrationTimingIntelligence` (`ESTIMATED`, 130–160 WPM adaptive Indonesian range, `audio_speed_multiplier=1.0`, zero forced speed-up). Actual TTS synthesis, forced alignment, word-level WAV timestamps, and full lip-sync remain scheduled for Phase 04.
3. **Checkpoint Recovery Tested Across Local Subprocesses & Portable Bundles (Not Cross-VM)**:
   - `CheckpointManager` verifies SHA-256 lineage, automatic fallback from corrupted `latest_checkpoint.json`, and secret-scanned portable bundle export/import across local processes/directories. True multi-host cross-VM distributed recovery is NOT claimed without cross-VM runtime evidence.
4. **Antigravity Native Subagent Transcript Files on Remote Devbox**:
   - On this remote devbox host, subagent execution is verified via Antigravity's live `invoke_subagent` tool returns and `manage_subagents(action="list")` ledger (`conversationId`, `type`, `role`, `state`). Where local `transcript.jsonl` files are not materialized inside the VM filesystem, `NativeAgentExecutionAdapter` records explicit `host_dispatch_verified=True` host dispatcher receipts and separates `native_subagent` from `recorded_workflow_replay` and `sequential_fallback_honest`.
5. **External Audit Environments Without Optional Binaries**:
   - Python-only audit containers without `node_modules`, `chromium`, or `fiankuns/xdx-blender-studio` cleanly report `UNKNOWN` for host-only LLM capabilities and gracefully skip optional external-repo/browser checks while keeping 100% deterministic Python validation and `tests/fixtures/synthetic.mp4` regeneration passing.
6. **Zero Live Vivo X200 Pro Blender MCP Connection Claimed**:
   - `xdx-blender-studio` remains untouched; MCP inspection remains read-only and never claims `LIVE_INVOCATION_VERIFIED` for Android Vivo X200 Pro without live authenticated transport telemetry.

---

## 3. Phase 01.6D Architecture Plan — Trusted Human Approval & Runtime Execution Guard

### 3.1 Trusted Human Approval Channel & Verifier (`governance/trusted_approval_verifier.py`)
- Replace any caller-supplied approval dictionary with an **out-of-band signed human approval envelope** bound to:
  - `project_id`
  - `package_version`
  - `package_digest` (live recomputed SHA-256 of all 13 mandatory items + `approval_package_manifest.json`)
  - `approved_scopes` (explicit list such as `["asset_procurement", "blender_build", "render_preview"]`)
  - `human_actor_id` + `trusted_channel_id` + `channel_signature` / HMAC / Ed25519 or host-verified interactive approval token
  - `issued_at_utc` & `expires_at_utc` (strict TTL)
  - `nonce` (single-use anti-replay stored in SQLite `execution_memory`)
- Live re-verification before **every** post-approval stage (`ASSET_PROCUREMENT`, `BLENDER_BUILD`, `ANIMATION`, `RENDERING`, `COMPOSITING`): any file hash drift in any approval-sensitive artifact automatically revokes `APPROVED` and transitions back to `REVISION_REQUIRED`.

### 3.2 Lifecycle Execution Guard Hooks (`.agents/hooks.json` & `governance/execution_guard.py`)
- Implement deterministic pre-tool and post-tool guard hooks enforcing:
  1. Block mutating Blender MCP calls, Three.js/Remotion render commands, and `projects/*/renders/**` writes unless a live, non-expired `ExecutionAuthorizationContext` passes `TrustedHumanApprovalVerifier`.
  2. Enforce `fiankuns/xdx-blender-studio` read-only protection, zero `/tmp` writes in Android `bpy` scripts, and `reference_database/**/original.mp4` + `prior_analysis.*` immutability.
  3. Block `master_director` from invoking `preproduction_verifier` / `visual_critic` / `technical_auditor` / `success_auditor` inside the same conversation context or self-approving.

### 3.3 Phase 01.6D Acceptance Criteria & Defect Closure
- Close `DEF-P016B-015` in `registry/master_audit_defect_registry.json` from `SCHEDULED` → `VERIFIED` only after dedicated negative security tests prove:
  - Forged/agent-crafted approval envelopes fail closed.
  - Expired, replayed, scope-mismatched, or post-approval-tampered packages immediately block execution.
  - Pre-approval render/Blender/modeling tool invocations are intercepted by `.agents/hooks.json` ExecutionGuard.
- Maintain 100% pass rate across all Phase 01..01.6C regression tests (101+ tests) with zero regressions.
