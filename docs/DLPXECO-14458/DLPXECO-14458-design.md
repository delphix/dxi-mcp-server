# Feature Design: DLPXECO-14458

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14458
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). -->

---

## Summary

<!-- Guidance: One paragraph (3–5 sentences). What this feature does, who it is for, why it is being built now. -->

This feature hardens the DCT MCP server's confirmation system across eight functional dimensions: single-use body-bound tokens (FR-001), differentiated confirmation levels (FR-002), closed coverage gaps for previously ungated mutating operations (FR-003), scoped batch grants (FR-004), elicitation-based enforcement via the MCP SDK (FR-005), per-identity velocity detection (FR-006), a non-relaxable floor of operations (FR-007), and immutable local audit events for every gate decision (FR-008). It is primarily for the security and compliance team, AI assistant product integrators, and local/STDIO MCP users who rely on the confirmation system as the sole safety layer between an LLM-authored plan and destructive DCT operations. The changes are being built now because verified analysis (2026-08-04/05) found five compounding defects — token replay, decorative confirmation levels, coverage gaps, a dormant keyword resolver, and no enforcement independent of client goodwill — that allow a model to silently execute unlimited destructive calls after a single user confirmation. FR-001, FR-002, and FR-003 are default-on-and-strictly-safer; all other new behaviours are gated behind config knobs that default to today's behaviour.

---

## Affected Components

<!-- Guidance: Tick [x] for components this feature changes; leave [ ] for the rest. Components come from .claude/architecture.md Layer Map. -->

- [x] `tools/core/confirmation_token.py` — Rewrite to body-bound HMAC + single-use consumed-token store
- [x] `tools/core/confirmation_resolver.py` — Add keyword-fallback dispatch (FR-003)
- [x] `tools/core/dynamic_confirmation.py` — Wire as live fallback or remove (FR-003 QR-4)
- [x] `tools/core/dynamic.py` — Integrate new confirmation flow, elicitation, ToolAnnotations, batch_intent, velocity (FR-001 through FR-006)
- [x] `config/config.py` — New env vars: DCT_CONFIRMATION_TOKEN_TTL, DCT_CONFIRMATION_ENFORCEMENT, DCT_CONFIRMATION_FALLBACK, DCT_GRANT_TTL, DCT_BATCH_COUNTER_PERSISTENCE
- [x] `config/loader.py` — Parse `batch_check:N:T` level; wire keyword fallback after static rules (FR-003, FR-006)
- [x] `config/mappings/manual_confirmation.txt` — Add 13 explicit rules for refresh/snapshot/bookmark/vdb-group/template endpoints (FR-003)
- [x] `core/session.py` — Mint session/identity UUID unconditionally at startup, independent of telemetry (FR-006)
- [ ] `main.py` — No functional change; startup sequence unchanged
- [ ] `toolsgenerator/driver.py` — No change
- [ ] `tools/__init__.py` — No change
- [ ] `tools/core/meta_tools.py` — No change
- [ ] `tools/core/tool_factory.py` — No change
- [ ] `tools/*_endpoints_tool.py` — No change (pre-built tools are not the primary confirmation gate)
- [ ] `dct_client/client.py` — No change
- [ ] `testing/cli.py` — No change
- [ ] `core/logging.py` — No change
- [ ] `core/decorators.py` — No change
- [ ] `core/exceptions.py` — No change

---

## Architecture Changes

### Schema / Config Changes

<!-- Guidance: Every change to schema files, config formats, or persisted state shapes. -->

| Field / Config | Type | Location | Notes |
|----------------|------|----------|-------|
| `DCT_CONFIRMATION_TOKEN_TTL` | integer (seconds) | env var → `config.py` | New. TTL for pending-token store entries. Default 3600. Preserves today's per-process secret behaviour unchanged. |
| `DCT_CONFIRMATION_ENFORCEMENT` | `strict` \| `advisory` | env var → `config.py` | New. Controls behaviour when client lacks elicitation capability. Default `advisory` = today's behaviour. |
| `DCT_CONFIRMATION_FALLBACK` | `keyword` \| `off` | env var → `config.py` | New. Enables keyword resolver as fallback behind static rules. Default `keyword`; `off` reproduces pre-change resolution. |
| `DCT_GRANT_TTL` | integer (seconds) | env var → `config.py` | New. TTL for batch grant entries. Default 900. |
| `DCT_BATCH_COUNTER_PERSISTENCE` | `off` \| `file` | env var → `config.py` | New. Whether velocity counters survive STDIO process restart. Default `off`. |
| `batch_check:N:T` level | string pattern | `config/mappings/manual_confirmation.txt` | New format. Parsed by `loader.py` alongside existing `retention_check:N` and `policy_impact_check:N`. |
| `config/mappings/read_exclusions.txt` | text file | new file | Checked-in list of read-shaped POST path patterns that must not be gated by keyword fallback (FR-003). |
| `config/mappings/floor_operations.txt` | text file | new file | Checked-in list of floor operation patterns (any HTTP DELETE; any POST ending `/delete`; named collection deletes) that no grant or config can bypass (FR-007). |

**confirmation_required response shape changes (additive — backward compatible):**

| New field | Type | Present when | Purpose |
|-----------|------|-------------|---------|
| `required_fields` | `list[str]` | always | Machine-readable list of fields the confirmation level requires (FR-002) |
| `ttl_seconds` | int | always | Token TTL from `DCT_CONFIRMATION_TOKEN_TTL` |
| `confirmation_token` | string | always | Refreshed single-use token (existing field; semantics tightened) |
| `batch_confirmation_token` | string | batch grant confirmation | Token authorising the declared batch |
| `grant_status` | dict | response under active grant | `{"grant_id": ..., "remaining": N}` |
| `authorization` | dict | response under grant/standing approval | `{"type": "grant", "id": ..., "remaining": ...}` |

---

### Source Files to Modify

<!-- Guidance: One row per file. The path must exist in the repo. Group by component. -->

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/tools/core/confirmation_token.py` | Rewrite `make_confirmation_token` to include `canonical_json(body)` in HMAC input; add `verify_and_consume_token(token, method, path, body)` that delegates consumed-token state to `ConsumedTokenStore` in `confirmation_store.py` | FR-001 |
| `src/dct_mcp_server/tools/core/confirmation_resolver.py` | Add `check_confirmation_with_fallback` that calls `get_confirmation_for_operation` (static rules first) then delegates to `dynamic_confirmation.get_confirmation_for_operation_dynamic` when fallback=keyword and no static match; add `batch_check` level evaluation | FR-003, FR-006 |
| `src/dct_mcp_server/tools/core/dynamic_confirmation.py` | Remove dormant status and wire `get_confirmation_for_operation_dynamic` as a live utility called by `confirmation_resolver.py`; update module docstring to reflect live caller; keep `HOT_CONFIRM_KEYWORDS` but apply read-exclusion list before returning a level | FR-003, QR-4 |
| `src/dct_mcp_server/tools/core/dynamic.py` | Integrate new confirmation gate: call `verify_and_consume_token` (FR-001); apply differentiated level checks for `elevated`/`manual` (FR-002); integrate `Context.elicit()` path for elicitation-capable clients (FR-005); register `ToolAnnotations` on `discovery` (readOnlyHint=True) and `execute` (readOnlyHint=False, destructiveHint=True, idempotentHint=False); handle `batch_intent` parameter and grant token, enforcing floor-operation check before issuing any grant (FR-004); integrate velocity counter (FR-006); enforce floor check on all calls (FR-007); emit audit events (FR-008) | FR-001, FR-002, FR-004, FR-005, FR-006, FR-007, FR-008 |
| `src/dct_mcp_server/config/config.py` | Add five new env vars to `get_dct_config()` and `print_config_help()`: `DCT_CONFIRMATION_TOKEN_TTL` (default 3600), `DCT_CONFIRMATION_ENFORCEMENT` (default `advisory`), `DCT_CONFIRMATION_FALLBACK` (default `keyword`), `DCT_GRANT_TTL` (default 900), `DCT_BATCH_COUNTER_PERSISTENCE` (default `off`) | FR-001, FR-003, FR-005, FR-006 |
| `src/dct_mcp_server/config/loader.py` | Extend `load_manual_confirmation_rules` to tolerate `batch_check:N:T` format (two colons); update `get_confirmation_for_operation` to invoke keyword fallback when `DCT_CONFIRMATION_FALLBACK=keyword` and no static rule matches, after applying `read_exclusions.txt`; update `clear_cache()` to also clear new in-memory stores | FR-003, FR-006 |
| `src/dct_mcp_server/config/mappings/manual_confirmation.txt` | Add 13 explicit rules: 8 `refresh_*` actions on VDBs and VDB groups (level: `elevated`), `POST /vdbs/{vdbId}/snapshots` (standard), `POST /bookmarks` (standard), `POST /vdb-groups` (standard), `POST /database-templates` (standard), `POST /hook-templates` (standard); enumerate 4 create actions explicitly | FR-003 |
| `src/dct_mcp_server/core/session.py` | Mint a `PROCESS_IDENTITY` UUID unconditionally at module import time (not gated on `IS_LOCAL_TELEMETRY_ENABLED`); expose `get_process_identity()` for use as caller identity in velocity counter and audit events; update `get_current_session_id()` to return the process identity when no telemetry session is active | FR-006 |

---

### New Files (if any)

<!-- Guidance: Path + one-line purpose. -->

- `src/dct_mcp_server/tools/core/confirmation_levels.py` — Implements `validate_elevated()` and `validate_manual()` — resource-name resolution (from URL path) and `acknowledged_impact` check for FR-002 differentiated levels; exposes `build_required_fields(level)` used in every `confirmation_required` response. (FR-002)
- `src/dct_mcp_server/tools/core/confirmation_store.py` — Thread-safe in-memory `ConsumedTokenStore` (dict[token → expiry timestamp] with TTL sweep on every lookup, strict wall-clock comparison) and `GrantStore` (dict[grant_id → GrantEntry] with count + TTL enforcement); both stores are module-level singletons reset on server restart. (FR-001, FR-004)
- `src/dct_mcp_server/tools/core/velocity_counter.py` — Sliding-window per-identity velocity counter keyed on `(caller_identity, method, path_template)`; optional file persistence controlled by `DCT_BATCH_COUNTER_PERSISTENCE`; exposes `increment_and_check(identity, method, path_template, N, T)` returning `(triggered: bool, count: int)`; counter is not reset on user-decline of the batch confirmation (no retry amnesty). (FR-006)
- `src/dct_mcp_server/tools/core/audit.py` — Emits `gate_decision` structured events to the local audit log on every confirmation outcome; always writes locally regardless of `IS_LOCAL_TELEMETRY_ENABLED`; never logs secrets, request bodies, or `confirmed_resource_name` values; exposes `emit_gate_event(outcome, identity, method, path_template, level, grant_id, velocity_fields)`. (FR-008)
- `src/dct_mcp_server/config/mappings/read_exclusions.txt` — Checked-in list of path patterns (one per line) that the keyword fallback must not gate; enforces FR-003's requirement that read-shaped POSTs resolve to `none`. (FR-003)
- `src/dct_mcp_server/config/mappings/floor_operations.txt` — Checked-in list of floor operation patterns (METHOD|path_pattern) that no grant, standing approval, or config can bypass; loaded by `floor_operations.py` at startup. (FR-007)
- `src/dct_mcp_server/tools/core/floor_operations.py` — Loads `floor_operations.txt`; exposes `is_floor_operation(method, path)` used by batch grant issuance (FR-004) and the individual confirmation gate; HMAC initialization failure at module import raises immediately to abort startup. (FR-007)

---

## Version Compatibility

<!-- Guidance: Pull the version table from architecture.md and mark branching per version. -->

| Dimension | Supported? | Branch? | Notes |
|-----------|-----------|---------|-------|
| Python 3.11+ | Yes | No | All new code uses Python 3.11+ constructs (`str \| None`, `dict[k, v]`, `asyncio`-safe threading); no 3.9/3.10 support needed |
| FastMCP 2.13.2+ | Yes | No | `Context.elicit()`, `ElicitationCapability`, and `ToolAnnotations` are already present in the bundled SDK; no version bump required |
| DCT API versions | Yes | No | All changes are server-side; no DCT API version branching — the confirmation gate sits between the MCP call and the DCT HTTP request |
| `DCT_TOOLSET=dynamic` (primary) | Yes | No | Primary path; all FRs apply |
| `DCT_TOOLSET=<fixed toolset>` | Yes | Partial | FR-001/FR-002/FR-003 apply via `check_confirmation` in pre-built tools; FR-004/FR-005/FR-006/FR-008 are wired in `dynamic.py` only — pre-built tools gain them when they call through `dynamic.execute()`, but standalone pre-built tools retain their existing simpler confirmation flow. No regression introduced. |
| STDIO single-user mode | Yes | No | Default config unchanged; `advisory` enforcement default means no new prompts added; velocity counter keyed on stable per-process UUID |
| Embedded / HTTP multi-tenant mode | Yes | Partial | Caller identity uses `X-CLIENT-ID` header when present (FR-006); `strict` enforcement + elicitation is the recommended path for embedded deployments |

---

## Platform Behavior Notes

<!-- Guidance: Flag each "Key Platform Behavior" from .claude/architecture.md that this feature interacts with. -->

- **API key prefix (`apk `)**: N/A — no changes to `DCTAPIClient`; token handling is server-side only.
- **SSL default `verify=false`**: N/A — no changes to HTTP client behavior.
- **Retries / exponential backoff**: N/A — confirmation gate is in the MCP layer, not the HTTP client.
- **Toolset config cache (`loader.py` `@lru_cache`)**: Affects — the five new env vars are loaded once via `get_dct_config()` at startup (not cached separately); `load_manual_confirmation_rules` lru_cache applies to the static rules and is cleared by `clear_cache()`. The new in-memory `ConsumedTokenStore` and `GrantStore` are mutable singletons — they are intentionally not lru_cached and reset on server restart. If `manual_confirmation.txt` is edited at runtime, `clear_cache()` must be called as today.
- **Telemetry opt-in (`IS_LOCAL_TELEMETRY_ENABLED`)**: Affects — audit events (FR-008) are written to the local audit log path **unconditionally**, regardless of this flag. Upload to the telemetry backend remains opt-in. The session UUID (FR-006) is now minted unconditionally, decoupled from the telemetry-enabled decision.
- **Per-process HMAC secret**: Affects — the secret continues to be `os.urandom(32)` generated at module import; tokens issued before a restart are rejected after it. The consumed-token store is also in-memory and clears on restart. These behaviours are preserved and documented.
- **Async-first architecture**: Affects — `ConsumedTokenStore` and `GrantStore` must be thread-safe (stdlib `threading.Lock`); `Context.elicit()` is awaited within the `async def execute()` function; `velocity_counter.py` increment-and-check is synchronous but lock-protected.

---

## Open Questions / Risks

<!-- Guidance: One bullet per item. Blocking items at the top. -->

- R: FR-001 body canonicalization may break existing item-scoped confirmation flows if the caller constructs the body with different key order on the two calls — Mitigation: implement `canonical_json` (sorted keys, stable number formatting) and add a regression test covering at least 5 existing item-scoped flows; run with `DCT_CONFIRMATION_FALLBACK=off` for one release if needed.
- R: FR-003 keyword fallback may gate read-shaped POSTs (e.g. `POST /vdbs/provision_by_snapshot/defaults` called during provisioning), producing double prompts — Mitigation: enforce `read_exclusions.txt` before keyword matching; add a test asserting all 8 listed read-shaped POST paths resolve to `none` with `DCT_CONFIRMATION_FALLBACK=keyword`.
- R: Removing/rewiring `dynamic_confirmation.py` breaks the import assertion in `tests/test_remove_auto_mode.py` — Mitigation: update or replace that test as part of FR-003 implementation; the file either gets a live caller or is deleted.
- R: FR-004 batch grants introduce a new grant-token attack surface — Mitigation: grants are bounded by exact target enumeration, TTL, and count; floor operations cannot be granted; each grant has a unique ID in the audit trail.
- R: FR-005 elicitation causes blocking in clients that declare capability but handle it asynchronously — Mitigation: test against Claude Desktop or MCP Inspector reference client; document timeout behavior.
- R: In-memory consumed-token store becomes memory pressure under high request volume — Mitigation: TTL-based expiry on every lookup (default 3600s); document footprint estimate (~360KB at 1 req/s sustained); add a soft limit warning in the store.
- Q: Should FR-005 enforcement default flip from `advisory` to `strict` after one release, as suggested in the ticket? — Owner: TBD; out of scope for this story but should be a follow-up in the release notes.
- Q: Is FR-004's `batch_intent` caller-declared contract acceptable to all MCP clients in scope? Clients that do not send `batch_intent` see per-call prompts — Owner: AI Assistant product team; noted in ticket open questions.
- R: `batch_check:N:T` velocity counter in STDIO mode resets on process cycling, reducing detection effectiveness — Mitigation: document explicitly; make persistence opt-in via `DCT_BATCH_COUNTER_PERSISTENCE=file`; default `off` with startup note.
- R: FR-002 resource-name resolution for `elevated` level may require an extra DCT API call, adding latency — Mitigation: resolve from URL path only (extract `vdbId` from path); fall back to requiring the resource ID if name cannot be resolved without a privileged call; document in response message.
- R: FR-002 `confirmed_resource_name` comparison must handle Unicode — case-insensitive match using `.casefold()` and NFC normalization is required; a naive `.lower()` is insufficient for non-ASCII resource names (EC-7 from functional spec).
- R: FR-001 consumed-token TTL check is lookup-driven (no background timer) — implementors must perform a strict wall-clock comparison at every lookup (`now >= expiry` → reject) so a token submitted nanoseconds after its TTL boundary is correctly rejected on the same lookup that sweeps it (EC-9 from functional spec).
- R: HMAC initialization failure at startup (e.g. `hashlib` unavailable or `os.urandom` blocked) must abort server startup with a clear error — never silently fall back to a weaker token scheme (ERR-1 from functional spec); add an assertion at module import time.
- R: After a velocity trigger (FR-006) the user may decline the batch confirmation — the counter must NOT reset to zero after a decline; the next call increments from the current count (ERR-7 from functional spec, no retry amnesty); this must be explicitly tested and documented in the velocity counter implementation.

---

## Acceptance Criteria

<!-- Guidance: Pulled from Jira ticket and functional spec; each AC maps to at least one FR-*. -->
<!-- Note: Quality Rules QR-2 in the functional spec references FR-2 (= FR-002) and FR-5 (= FR-005) using shorthand notation. The zero-padded forms are canonical throughout this document. -->

### FR-001: Single-Use Body-Bound Confirmation Token

- [ ] AC-1: Confirm a token for body A at path P, then submit that token with body B at path P → `confirmation_required` returned, operation does not execute.
- [ ] AC-2: Confirm and execute (path P, body A), then replay the identical (path, body, token) → `confirmation_required` returned, operation does not execute a second time.
- [ ] AC-3: Submit body with keys in different order on the two calls → token verifies (canonicalization is order-independent).
- [ ] AC-4: Submit token issued for `{"a":1,"b":2}` with body `{"a":1,"b":3}` → `confirmation_required`.
- [ ] AC-5: 100 distinct-body provision calls with no active grant → exactly 100 distinct confirmations required.
- [ ] AC-6: Token issued before server restart submitted after restart → `confirmation_required` (token store cleared on restart).
- [ ] AC-7: Existing item-scoped confirmation flows behave identically to pre-change except tokens are now single-use.

### FR-002: Differentiated Confirmation Levels

- [ ] AC-1: `standard` operation — `confirmation_token` alone succeeds.
- [ ] AC-2: `elevated` operation — `confirmation_token` alone (no `confirmed_resource_name`) → `confirmation_required` with `required_fields: ["confirmation_token","confirmed_resource_name"]`.
- [ ] AC-3: `elevated` operation — wrong `confirmed_resource_name` → `confirmation_required`, no execution.
- [ ] AC-4: `manual` operation — token and correct name but no `acknowledged_impact` → `confirmation_required`.
- [ ] AC-5: `manual` operation — all three fields correctly supplied → operation executes.
- [ ] AC-6: Every `confirmation_required` response includes non-empty `required_fields`; no client needs to parse `message` to determine what to send.
- [ ] AC-7: Regression test asserts `manual` and `standard` are not mechanically equivalent.

### FR-003: Close Confirmation Coverage Gap

- [ ] AC-1: All 20 actions in PPM-1128's scope table resolve to a non-`none` confirmation level.
- [ ] AC-2: `POST /vdbs/provision_by_snapshot/defaults`, `POST /snapshots/search`, `POST /paas-snapshots/search`, `POST /environments/compatible_repositories_by_snapshot`, `POST /file-mapping/validate-file-mapping-by-snapshot` each resolve to `none`.
- [ ] AC-3: Test enumerates every mutating operation in the bundled spec and asserts each resolves to a non-`none` level or appears on the checked-in triaged exception list with a documented reason.
- [ ] AC-4: Explicit static rules take precedence over keyword fallback (verified by test using an operation covered by both).
- [ ] AC-5: `DCT_CONFIRMATION_FALLBACK=off` reproduces pre-change resolution exactly.
- [ ] AC-6: No unreachable confirmation resolver remains in the tree.

### FR-004: Scoped Batch Grants

- [ ] AC-1: 100-target batch → exactly one `confirmation_required` containing `operation`, `count: 100`, and all 100 targets in a structured field.
- [ ] AC-2: After grant approval, all 100 calls execute with no further prompt; each response reports remaining grant count.
- [ ] AC-3: Call 101, or a call with a body not in the enumerated set → `confirmation_required`.
- [ ] AC-4: Grant at TTL → `confirmation_required` on any subsequent call.
- [ ] AC-5: Batch containing a floor operation → refused before issuing any grant, with clear error.
- [ ] AC-6: Without `batch_intent`, behavior is exactly FR-001 per-call confirmation.

### FR-005: Elicitation-Based Enforcement

- [ ] AC-1: Elicitation-capable client → destructive operation triggers `elicit()`; user decline → operation does not execute.
- [ ] AC-2: Elicitation schema for `elevated` requests `confirmed_resource_name`; for `manual`, also requests `acknowledged_impact`.
- [ ] AC-3: `DCT_CONFIRMATION_ENFORCEMENT=strict` + non-elicitation client → operation refused naming missing capability.
- [ ] AC-4: `DCT_CONFIRMATION_ENFORCEMENT=advisory` (default) → non-elicitation client receives existing advisory response.
- [ ] AC-5: `tools/list` reports `readOnlyHint=true` for `discovery`; `readOnlyHint=false, destructiveHint=true, idempotentHint=false` for `execute`.
- [ ] AC-6: Elicitation approval satisfies the gate without the token being returned to the model.

### FR-006: Per-Identity Velocity Detection

- [ ] AC-1: Two identities each making 3 calls to same operation (N=5) → no trigger; one identity making 6 → trigger.
- [ ] AC-2: Counter state isolated per identity — identity A's counter does not affect identity B's.
- [ ] AC-3: Session/identity UUID exists and is accessible with `IS_LOCAL_TELEMETRY_ENABLED=false`.
- [ ] AC-4: `batch_check:5:60` parses correctly and coexists with `manual`, `elevated`, `standard`, `retention_check:N`, `policy_impact_check:N`.
- [ ] AC-5: Velocity trigger emits an audit event (FR-008) whether or not the user confirms.
- [ ] AC-6: With `DCT_BATCH_COUNTER_PERSISTENCE=off` (default), server restart resets all counters; documented.

### FR-007: Non-Relaxable Floor Operations

- [ ] AC-1: Including any floor operation (DELETE, POST to `/delete` path) in a batch grant → refused with clear error naming the floor operations.
- [ ] AC-2: No combination of config values causes a floor operation to execute without individual confirmation.
- [ ] AC-3: Test enumerates the full configuration surface and asserts no knob disables confirmation globally.
- [ ] AC-4: Standing approvals expire by both count and TTL, whichever comes first; both expiry paths verified by test.
- [ ] AC-5: Responses executed under a grant carry `authorization: {"type":"grant","id":...,"remaining":...}`.

### FR-008: Audit Events for Every Gate Decision

- [ ] AC-1: Each of the 7 outcomes (`required`, `approved`, `refused`, `expired`, `replay_rejected`, `grant_covered`, `batch_triggered`) produces exactly one audit event with all specified fields.
- [ ] AC-2: No audit event contains a credential, request body, or `confirmed_resource_name` value.
- [ ] AC-3: Audit records produced and written locally with `IS_LOCAL_TELEMETRY_ENABLED=false`.
- [ ] AC-4: With `IS_LOCAL_TELEMETRY_ENABLED=true`, the event is also forwarded to the telemetry backend.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/DLPXECO-14458/DLPXECO-14458-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/DLPXECO-14458/DLPXECO-14458-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh DLPXECO-14458 --step design -->
