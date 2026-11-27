# XDX v4.0 — Phase 01.6D Audit: Trusted Human Approval & Execution Guard

- Base: `c90356389c24d6d1279b8490e25b788e13a4d7f6` (branch `feat/phase-01.6c-universal-creative-intelligence`)
- Branch: `feat/phase-01.6d-execution-security` (no merge to main, no force-push, no history rewrite)
- Not done, by design: Phase 02, rendering, modeling, animation, Blender MCP changes, authentication changes.

## 1. What changed

| Area | Files |
|---|---|
| Trusted Human Approval (central, v3.4 + v4) | `governance/trusted_approval.py` (new), `intelligence/state_and_approval.py`, `orchestration/shared_state.py` |
| Canonical SHA-256 manifest | `governance/canonical_manifest.py` (new) — `compute_package_digest` delegates to it |
| Execution guard paths | `ApprovalGate.verify_live_execution_context` (MCP adapter + `scripts/approval_gate.py`), `ProjectStateManager.transition`, `scripts/execution_guard_hook.py` (new pre-tool hook) |
| Human-side tooling | `scripts/trusted_approval.py` (`keygen` / `sign` / `status` / `digest`) |
| Trust root | `registry/trusted_approvers.json` (0 keys → channel UNAVAILABLE → BLOCKED), `schemas/trusted_approvers.schema.json` |
| Narration estimator | `intelligence/universal_preproduction.py`, `intelligence/preproduction_verifier_engine.py` |
| Test profiles | `tests/conftest.py` (`core` default / `full_integration`), `tests/test_phase01_6d_execution_security.py` (new, 10 tests) |
| Registry | `registry/master_audit_defect_registry.json` (31 entries: 27 VERIFIED, 4 SCHEDULED) |

`governance/__init__.py` became lazy to avoid a circular import; `.gitignore` already excludes runtime checkpoints/locks
(nothing runtime is committed). Schema edits are additive (`approval_nonce` in v3.4 history, registry version enum).

## 2. Design

**Trusted channel.** Approval = single-line `XDX-SIGNED-APPROVAL <base64url envelope>` with an Ed25519 signature
over the canonical payload `{schema, channel, project_id, package_version, manifest_digest (full 64-hex), scopes,
nonce, issued_at, expires_at}`. The private key lives only on the human's device (`keygen`/`sign` refuse paths inside
the repo); the repo holds public keys. The channel is `UNAVAILABLE` (production `BLOCKED`) when no unrevoked key is
registered or when `registry/trusted_approvers.json` differs from the committed HEAD (agent-injected key).

**Single gate for every path.** v3.4 `record_explicit_user_approval`, v4 `approve_via_trusted_gate` (the only v4
route to `APPROVED`; `transition("APPROVED")` with actor labels / dicts is rejected and a fabricated
`VerifiedApproval` is re-verified by signature), `verify_live_execution_context` (MCP + CLI), and
`transition()` into production states all call `TrustedApprovalGuard`.

**Replay / revocation.** Hash-chained append-only ledger `<package>/.approvals/approval_ledger.jsonl`
(excluded from the manifest): nonce consumed exactly once; `REVOKED` events are permanent. Nonces are also stored
in state history, so deleting the ledger cannot re-enable a consumed token.

**Freeze.** The unconditional 01.6C freeze is replaced by the guard. Approval opens only with a valid signature;
execution scopes (everything except `mcp_preflight`) stay behind `assert_phase_boundary` (`PHASE02_EXECUTION_ENABLED
= False`), so no mutation/render can run in 01.6D even with a valid approval.

**Threat model limit.** Protects against forged approval *data* via all official paths; it cannot stop a process
that rewrites the guard source, or a malicious key commit that the human merges — registry changes need human review.

## 3. Enforcement evidence (tests)

| Attack / rule | Result | Test |
|---|---|---|
| Chat phrase, unsigned `XDX-APPROVE`, malformed / multi-line token | `UNSIGNED_OR_MALFORMED` | `test_forged_wrong_key_tampered_payload_and_malformed_tokens_rejected` |
| Attacker key using a registered key_id; payload edited after signing | `SIGNATURE_INVALID` | same |
| Unknown key id | `UNKNOWN_OR_REVOKED_KEY` | same |
| Cross-project / wrong version / stale digest | `BINDING_MISMATCH` | `test_binding_expiry_and_scope_rules` |
| Expired, issued in future, TTL > 72h | `EXPIRED` | same |
| Scope not covered / unknown scope | `SCOPE_MISMATCH` | same + `test_invalid_state_transitions_ai_self_approval_expiry_and_revocation` |
| Any of 8 previously uncovered inputs (or any new file) changed | digest changes → blocked | `test_canonical_manifest_covers_every_production_input_without_exception` |
| Symlink / missing required input | rejected | same |
| Replay of consumed token (v3.4 and v4), even after ledger deletion | `REPLAY` | `test_ledger_tamper_and_cli_cannot_bypass`, `test_v4_state_machine_only_accepts_trusted_gate` |
| Ledger line edited | `LEDGER_TAMPERED` → BLOCKED | `test_ledger_tamper_and_cli_cannot_bypass` |
| Record un-revoked + state hand-set to APPROVED | `REVOKED` (ledger wins) | `test_invalid_state_transitions_ai_self_approval_expiry_and_revocation` |
| Forged on-disk approval_record + APPROVED state | `UNSIGNED_OR_MALFORMED` (MCP: blocked) | security tests |
| v4 actor label + agent dict / fabricated VerifiedApproval | rejected | `test_v4_state_machine_only_accepts_trusted_gate` |
| CLI `approval_gate.py --check` in fresh process | `TRUSTED_CHANNEL_UNAVAILABLE` (repo has 0 keys) | `test_ledger_tamper_and_cli_cannot_bypass` |
| Repo trust registry modified without commit | channel UNAVAILABLE | `test_uncommitted_trust_registry_change_makes_channel_unavailable` |
| Valid approval → MCP mutation / render | `PHASE02_EXECUTION_NOT_STARTED` | `test_mcp_mutation_never_executes_in_phase_01_6d` |
| Pre-tool hook: unclassified tool, mutation, `blender -b`, `remotion render`, bad JSON | exit 2 (block) | `test_pre_tool_execution_guard_hook_fails_closed` |
| Narration estimate > target × 1.02 | CRIT_06 FAIL | `test_23_...` (bench A 60s replay now rejected; 70s passes), `test_narration_estimate_over_target_is_not_pass` |

## 4. Test results

| Profile | Environment | Result |
|---|---|---|
| core | clean clone, `GIT_LFS_SKIP_SMUDGE=1` (pointer files only) | **112 passed, 1 skipped** (`requires_lfs`) |
| full_integration | real MP4s hydrated via `git lfs pull` | **113 passed** (see `full_integration_with_media.txt`) |
| full_integration (negative) | clean clone, no media | **112 passed, 1 error** — media absence fails the run, not skipped |

Reference media SHA-256 (`reference_media_sha256_verify.json`, `scripts/xdx_studio.py validate-all` → `VALIDATED`):
- REF-001 `12f9e1d992fc6f71f56c4c1116a91def3f6ca70bf1c55aa2618281ae4a71879d` — VERIFIED
- REF-002 `042ad39d5fc318a7491dab0f100432d02e7ad1c04806f7cc92a74fdf350f6b01` — VERIFIED

## 5. Defect registry delta

- `DEF-P016B-015` SCHEDULED → **VERIFIED** (trusted approval + guard).
- New VERIFIED: `DEF-P016D-024` (manifest covered only 11 files), `-025` (forged/replay/CLI/MCP bypass),
  `-026` (narration PASS over target — all 4 benchmarks overrun 5–13%), `-027` (Full Integration profile).
- Carried forward, SCHEDULED: `-028` action-target 109/109 claim, `-029` host hook wiring (`.agents/hooks.json`),
  `-030` semantic storyboard & reviewer accuracy, `-031` cross-VM persistence.

## 6. Known consequences / open items

1. The four 01.6C benchmark packages still carry the old (11-file) digest and a CRIT_06 PASS that is now known to be
   wrong. They stay `WAITING_APPROVAL`; any approval must be signed against the new canonical digest
   (`python3 scripts/trusted_approval.py digest --package projects/<id>`), and the packages should be regenerated
   later (not re-run here per the quota rule).
2. Until the owner registers a public key (commit to `registry/trusted_approvers.json`), production stays BLOCKED.
3. Host hook wiring is pending (DEF-P016D-029).
