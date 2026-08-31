# Vision: DLPXECO-14458

## Problem Statement

The MCP server's confirmation system is the only safety layer between an LLM-authored plan and destructive DCT operations, yet verified analysis (2026-08-04/05) found it materially weaker than the PPMs it underpins assume. Five compounding defects — token replay, decorative confirmation levels, coverage gaps on 13 of 20 target mutating operations, a dormant keyword resolver, and no enforcement independent of client goodwill — mean a model can silently execute unlimited destructive calls after a single user confirmation. In local/STDIO deployments there is no host-side interception layer to compensate, making these server-side defects the sole risk-bearing mechanism.

## Goals

- G1: Make every confirmation token single-use and body-bound, so a confirmed token cannot be replayed to authorize additional or different calls.
- G2: Differentiate confirmation levels (standard, elevated, manual) with distinct, machine-verifiable requirements — elevated requires confirmed resource name; manual requires resource name plus impact acknowledgement.
- G3: Close the coverage gap by adding explicit rules for the 8 refresh actions, snapshot, bookmark, VDB group, database-template, and hook-template endpoints, and reactivate the keyword resolver as a fallback for remaining ungated mutating operations.
- G4: Introduce scoped batch grants so a single user approval can cover an explicitly enumerated set of N calls without requiring N individual confirmations, while still enforcing each call against the grant.
- G5: Add elicitation-based enforcement using the MCP SDK's `Context.elicit()` so that on elicitation-capable clients the user is asked by protocol rather than by the model's choice, and `strict` mode refuses operations from non-elicitation clients.
- G6: Introduce per-identity velocity detection (`batch_check:N:T`) keyed on (caller_identity, method, path_template), with unconditional session identity minting regardless of telemetry state.
- G7: Define a non-relaxable floor of operations (any HTTP DELETE, any POST to a `/delete` path, and named collection deletes) that no grant, standing approval, or config can bypass.
- G8: Emit an immutable local audit event for every gate decision regardless of telemetry opt-in status.

## Non-Goals

- NG1: Host-side interception in the DCT AI Assistant — converting `confirmation_required` into a LangGraph HITL interrupt, scoping "allow always" to `(method, path)`, or rendering enumerated batch prompts in apigw-services (separate story).
- NG2: DCT-side RBAC policy for who may hold standing approvals.
- NG3: Vocabulary and message wording standardization (PPM-1129 Lever 4), including generic wording the FR-3 fallback introduces.
- NG4: Tool annotation work beyond the two dynamic tools (`discovery` and `execute`).
- NG5: Persona-toolset action renaming.
- NG6: Changes to the existing STDIO + `DCT_API_KEY` single-user flow behavior beyond strictly safer defaults — all new behavior is default-on-and-strictly-safer or gated behind a config knob that defaults to today's behavior.

## Success Criteria

- SC1: Replaying a used confirmation token (identical path, body, and token) returns `confirmation_required` and does not execute the operation a second time.
- SC2: 100 distinct provision calls without a batch grant each require their own confirmation; with a 100-target batch grant they require exactly one.
- SC3: All 20 actions in PPM-1128's scope table resolve to a non-`none` confirmation level.
- SC4: Read-shaped POSTs (`/defaults`, `/search`, `/validate-*`, `/compatible_*`, etc.) do not receive a confirmation gate.
- SC5: `elevated` and `manual` confirmation levels require demonstrably different inputs and a regression test asserts they are not mechanically equivalent.
- SC6: On an elicitation-capable MCP client, declining the elicitation prompt prevents the destructive operation from executing.
- SC7: `DCT_CONFIRMATION_ENFORCEMENT=strict` with a non-elicitation client refuses the operation and names the missing capability.
- SC8: No floor operation (HTTP DELETE, POST to `/delete` paths) can be executed under a batch grant or standing approval.
- SC9: Audit events are produced with `IS_LOCAL_TELEMETRY_ENABLED=false`, contain all required fields, and contain no credentials or request bodies.
- SC10: Existing STDIO + `DCT_API_KEY` default-config usage is fully regression-free — no prompt is added to a flow that had none before, and no existing confirmation flow changes behavior.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| AI Assistant product (PPM-1175/1572) | Confirmation system holds up under automated LLM plans without requiring host-side safety nets to be in place first |
| Local/STDIO MCP users | Server enforces safety on its own when there is no host-side interception layer |
| Security / Compliance | Audit log of every gate decision, including declined and replayed tokens, with no credential leakage |
| DCT platform team | Coverage of all 20 batch-targeted operations; no silent mass-provisioning or mass-delete via LLM |
| Developers of external MCP clients | Machine-readable `required_fields` in every confirmation response so client UIs can render the correct form without parsing prose |
| PPM-1128 / PPM-1126 / PPM-1127 | These PPMs' assumptions that the confirmation layer is enforced are validated by this story |

## Constraints

- Must not alter existing behavior under default configuration; every new behavior is either default-on-and-strictly-safer (FR-1, FR-2, FR-3) or gated behind a config knob that defaults to today's behavior (FR-5 `DCT_CONFIRMATION_ENFORCEMENT=advisory`).
- No net-new third-party dependencies beyond what is already in the MCP SDK (`elicitation`, `ToolAnnotations` are already available in the bundled SDK version — no version bump required).
- Python 3.11+ only; async-first architecture; all tool functions use `@log_tool_execution`.
- The consumed-token store and grant store are in-memory with TTL; persistence across restarts is not required and off by default.
- `DCT_CONFIRMATION_FALLBACK=keyword` default means the fallback keyword resolver must not gate read-shaped POSTs — the exclusion list is checked in, not heuristic-only.
- Per-process HMAC secret is preserved as today; tokens issued before a server restart are rejected after it.
- No unreachable confirmation resolver may remain in the tree after FR-3 is implemented.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FR-1 body-canonicalization breaks existing item-scoped confirmation flows where body key order varies between calls | Medium | High | Add deterministic canonicalization (sorted keys) and include a regression test covering at least 5 existing item-scoped flows; introduce under feature flag if needed |
| FR-3 keyword fallback gates read-shaped POSTs (e.g. `/vdbs/provision_by_snapshot/defaults` called during provisioning), producing double prompts | High | High | Maintain and enforce a checked-in exclusion list; add a test that asserts all 8 listed read-shaped POST paths resolve to `none` with `DCT_CONFIRMATION_FALLBACK=keyword` |
| FR-5 elicitation integration causes blocking behavior in clients that declare `elicitation` capability but handle it asynchronously or with delay | Low | Medium | Test against at least one elicitation-capable reference client (Claude Desktop or MCP Inspector); document timeout behavior |
| FR-4 batch grants introduce a new attack surface (grant token replay or grant overextension) | Medium | High | Grants are bounded by exact target enumeration, TTL, and count; floor operations cannot be granted; each grant has a unique ID logged in the audit trail |
| In-memory consumed-token store becomes a memory pressure source under high request volume | Low | Medium | Enforce TTL-based expiry (`DCT_CONFIRMATION_TOKEN_TTL`, default 3600s); document memory footprint estimate (one token entry ≈ 100 bytes, 3600 tokens/hour at 1 req/s ≈ 360KB) |
| Removing `dynamic_confirmation.py` dormant code breaks an import assertion in `tests/test_remove_auto_mode.py` | High | Low | Update or replace the test during FR-3 implementation; the file either gains a live caller or is deleted — not left dormant |
| `batch_check:N:T` velocity detection uses per-process identity in STDIO mode; STDIO process cycling resets counters, reducing detection effectiveness | Medium | Medium | Document explicitly; make persistence opt-in via `DCT_BATCH_COUNTER_PERSISTENCE=file`; default to `off` with a startup note |
| FR-2 resource-name resolution for `elevated` level requires an additional DCT API call, adding latency | Low | Medium | Resolve server-side only where name is in the URL path; fall back to requiring the resource ID if name cannot be resolved without a privileged call, and document in the response |
