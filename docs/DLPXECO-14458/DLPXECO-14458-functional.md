# Functional Specification: DLPXECO-14458

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14458
**Generated from**: Acceptance criteria in Jira ticket DLPXECO-14458

---

## FR-001: Single-Use Body-Bound Confirmation Token

### Description
Confirmation tokens must be derived from the request body and consumed on first use so that a token cannot be replayed to authorize additional or different calls.

### Input
- `method` (string, required): HTTP method (GET, POST, DELETE, etc.)
- `resolved_path` (string, required): the resolved DCT API path with IDs substituted (e.g. `/vdbs/vdb-101/delete`)
- `request_body` (dict, optional): the JSON request body sent with the destructive call; may be empty for body-less operations
- `confirmation_token` (string, required on second call): token previously issued by the server

### Processing
1. On the first call (no `confirmation_token` provided):
   a. Compute `canonical_json(request_body)` — keys sorted lexicographically, no insignificant whitespace, stable number formatting (no trailing zeros for integers).
   b. Derive token: `HMAC-SHA256(per_process_secret, METHOD + " " + resolved_path + " " + canonical_json(request_body))`.
   c. Store `(token, timestamp)` in the in-memory pending-token set with TTL `DCT_CONFIRMATION_TOKEN_TTL` (default 3600s).
   d. Return `confirmation_required` response with the token, the TTL, and the `required_fields` array for the applicable confirmation level.
2. On the second call (`confirmation_token` provided):
   a. Recompute the expected token from the current `(method, resolved_path, request_body)`.
   b. Check the pending-token set: if token is absent (never issued or TTL expired) → return `confirmation_required` with a freshly issued token.
   c. If token is present but computed value does not match current `(method, path, body)` → return `confirmation_required` with a fresh token.
   d. If token matches: remove it from the pending-token set (mark consumed), proceed with execution.
   e. If token was already consumed: return `confirmation_required` with a fresh token; do not execute.
3. The pending-token set is in-memory only; a server restart clears it (per-process secret is preserved as today).
4. TTL sweep runs on every lookup — no background timer required.

### Output
- Success (confirmation verified, consumed): operation proceeds; response body is the DCT API result.
- Failure (replay, mismatch, expired): `{"status": "confirmation_required", "confirmation_token": "<new_token>", "required_fields": [...], "message": "<human message>"}` — no execution.
- Side effect: consumed token is removed from in-memory pending set.

### Acceptance Criteria
- [ ] AC-1: Given a token issued for body A at path P, when the same token is submitted with body B at path P, then `confirmation_required` is returned and the operation does not execute.
- [ ] AC-2: Given a token issued and consumed for (path P, body A), when the same (path, body, token) is replayed, then `confirmation_required` is returned and the operation does not execute a second time.
- [ ] AC-3: Given a body where keys are submitted in different order on the two calls, when the token is verified, then it matches (canonicalization is order-independent).
- [ ] AC-4: Given a token issued for body `{"a":1,"b":2}`, when submitted with body `{"a":1,"b":3}` (one value changed), then `confirmation_required` is returned.
- [ ] AC-5: Given 100 distinct-body provision calls with no active grant, then exactly 100 distinct confirmations are required.
- [ ] AC-6: Given a token issued before a server restart, when submitted after restart, then `confirmation_required` is returned (token store is cleared on restart).
- [ ] AC-7: Given existing item-scoped confirmation flows (e.g. `/vdbs/{id}/delete`), when confirmed and executed, then behavior is identical to pre-change except the token is now single-use.

---

## FR-002: Differentiated Confirmation Levels

### Description
The three confirmation levels (standard, elevated, manual) must impose distinct, machine-verifiable requirements so that they provide progressively stronger safety assurance.

### Input
- `confirmation_token` (string, required): single-use token from FR-001
- `confirmed_resource_name` (string, required for elevated and manual): the name or ID of the target resource as it would appear in DCT
- `acknowledged_impact` (boolean, required for manual, must be `true`): explicit acknowledgement that the caller understands the impact

### Processing
1. Look up the confirmation level for the operation from `config/mappings/manual_confirmation.txt`.
2. For `standard`: require only `confirmation_token` (after FR-001 verification).
3. For `elevated`:
   a. Require `confirmation_token` AND `confirmed_resource_name`.
   b. Resolve the resource name server-side from the URL path (e.g. extract `vdbId` from `/vdbs/{vdbId}/refresh`). If the name cannot be resolved without a privileged call, require the resource ID and state so in the message.
   c. Compare caller-supplied `confirmed_resource_name` against the resolved name/ID (case-insensitive string match).
   d. If mismatch: return `confirmation_required` with `required_fields: ["confirmation_token","confirmed_resource_name"]` and a message stating the expected value format.
4. For `manual`:
   a. Apply all elevated checks.
   b. Additionally require `acknowledged_impact: true`.
   c. If `acknowledged_impact` is absent or false: return `confirmation_required` with `required_fields: ["confirmation_token","confirmed_resource_name","acknowledged_impact"]`.
5. Every `confirmation_required` response MUST include a `required_fields` array listing all fields the level requires, regardless of which specific field was missing.

### Output
- Success: operation proceeds after all required fields are verified.
- Failure: `{"status": "confirmation_required", "confirmation_token": "<new_token>", "required_fields": [...], "message": "<level-specific message>"}`.

### Acceptance Criteria
- [ ] AC-1: Given a `standard` operation, when `confirmation_token` alone is submitted (after FR-001 verification), then the operation executes.
- [ ] AC-2: Given an `elevated` operation, when only `confirmation_token` is submitted (no `confirmed_resource_name`), then `confirmation_required` is returned with `required_fields: ["confirmation_token","confirmed_resource_name"]`.
- [ ] AC-3: Given an `elevated` operation, when `confirmed_resource_name` is submitted but does not match the resource's actual name/ID, then `confirmation_required` is returned and the operation does not execute.
- [ ] AC-4: Given a `manual` operation, when `confirmation_token` and correct `confirmed_resource_name` are submitted but `acknowledged_impact` is absent or false, then `confirmation_required` is returned.
- [ ] AC-5: Given a `manual` operation, when all three fields are correctly supplied, then the operation executes.
- [ ] AC-6: Every `confirmation_required` response (at any level) includes a non-empty `required_fields` array; no client needs to parse `message` text to determine what to send.
- [ ] AC-7: A regression test asserts that `manual` and `standard` are not mechanically equivalent (submitting only a token to a `manual`-gated operation is rejected).

---

## FR-003: Close Confirmation Coverage Gap

### Description
Add explicit confirmation rules for 13 previously ungated mutating operations and reactivate the keyword resolver as a fallback for any remaining ungated mutating operations, without gating read-shaped POSTs.

### Input
- `method` (string): HTTP method of the incoming request
- `path_template` (string): the matched URL template (e.g. `/vdbs/{vdbId}/refresh_by_timestamp`)
- `DCT_CONFIRMATION_FALLBACK` (env var): `keyword` (default) or `off`

### Processing
1. Add explicit entries to `config/mappings/manual_confirmation.txt` for:
   - 8 `refresh_*` actions on VDBs and VDB groups (level: `elevated`)
   - `POST /vdbs/{vdbId}/snapshots` (level: `standard`)
   - `POST /bookmarks` (level: `standard`)
   - `POST /vdb-groups` (level: `standard`)
   - `POST /database-templates` (level: `standard`)
   - `POST /hook-templates` (level: `standard`)
2. Re-wire `dynamic_confirmation.py`'s keyword resolver as a fallback in `config/loader.py`, invoked when no static rule matches and `DCT_CONFIRMATION_FALLBACK=keyword`:
   - Keywords: `("refresh","provision","delete","rollback","source config","snapshot")`
   - Explicit exclusion list (read-shaped POSTs that must NOT be gated): `/defaults`, `/search`, `/capacity`, `/validate-*`, `/find_by_*`, `/compatible_*`, `*-summary`, `/timeflow_range`, `/latest-snapshots`, `/runtime`, `/paas-snapshots/search`, `/environments/compatible_repositories_by_snapshot`, `/file-mapping/validate-file-mapping-by-snapshot`
3. Static explicit rules take precedence over keyword matches; keyword-matched operations get the fallback message template.
4. Do NOT add `create` to the keyword set; enumerate the four create actions explicitly instead.
5. If `DCT_CONFIRMATION_FALLBACK=off`, the keyword resolver is not invoked; resolution is identical to pre-change.
6. After implementation, `dynamic_confirmation.py` must have a live caller or be removed entirely — no unreachable code.

### Output
- For any previously-ungated operation in scope: a non-`none` confirmation level is returned.
- For exclusion-list POSTs: `none` (no gating).
- For operations not in static rules and fallback `off`: `none`.

### Acceptance Criteria
- [ ] AC-1: All 20 actions in PPM-1128's scope table resolve to a non-`none` confirmation level.
- [ ] AC-2: `POST /vdbs/provision_by_snapshot/defaults`, `POST /snapshots/search`, `POST /paas-snapshots/search`, `POST /environments/compatible_repositories_by_snapshot`, `POST /file-mapping/validate-file-mapping-by-snapshot` each resolve to `none`.
- [ ] AC-3: A test enumerates every mutating operation in the bundled spec and asserts each resolves to a non-`none` level or appears on a checked-in triaged exception list with a documented reason.
- [ ] AC-4: Explicit static rules take precedence over keyword fallback (verified by a test that configures an operation covered by both, asserting the static rule's message is used).
- [ ] AC-5: With `DCT_CONFIRMATION_FALLBACK=off`, pre-change resolution is reproduced exactly.
- [ ] AC-6: No unreachable confirmation resolver remains in the tree (verified by a grep test or import check).

---

## FR-004: Scoped Batch Grants

### Description
Allow a caller to declare a bounded set of N calls in advance, receive a single confirmation prompt, and then execute all N calls against the grant with each one individually checked and counted.

### Input
- `batch_intent` (dict, optional): caller-declared batch descriptor with:
  - `operation` (string, required): `"METHOD /path/template"` (e.g. `"POST /vdbs/provision_by_snapshot"`)
  - `targets` (list, required): list of canonical bodies or target identifiers — one entry per call in the batch
- `grant_token` (string, required on subsequent calls): token issued at batch confirmation
- `DCT_GRANT_TTL` (env var, integer, default 900): grant time-to-live in seconds

### Processing
1. When `batch_intent` is provided on the first call:
   a. Check that no `targets` entry maps to a floor operation (FR-007). If any does: refuse with an error naming the floor operations.
   b. Return `confirmation_required` with payload: `{"operation": ..., "count": N, "targets": [...], "targets_display": <truncated>}` and a new `batch_intent` token.
2. When `grant_token` is provided for a call in an active batch:
   a. Look up the grant by `grant_token`; verify it has not expired and has remaining count > 0.
   b. Verify the current call's canonical body appears in the grant's enumerated target list and has not already been consumed.
   c. If verified: mark the target consumed, decrement remaining count, proceed with execution. Include `grant_status: {"grant_id": ..., "remaining": ...}` in the response.
   d. If the body is not in the target list: return `confirmation_required` for this call individually.
   e. If remaining count is 0 or grant is expired: return `confirmation_required`.
3. Grants are bounded by count (= len(targets)) and TTL.
4. Without `batch_intent`, behavior is exactly FR-001 (per-call single confirmation).

### Output
- Initial call with `batch_intent`: `{"status": "confirmation_required", "batch_confirmation_token": ..., "operation": ..., "count": N, "targets": [...]}`.
- Subsequent calls against active grant: DCT API result + `grant_status: {"grant_id": ..., "remaining": N-k}`.
- Exhausted or expired grant: `{"status": "confirmation_required", ...}`.
- Floor operation in batch: `{"status": "error", "message": "Floor operations require individual confirmation: ..."}`.

### Acceptance Criteria
- [ ] AC-1: Given a 100-target batch, when `batch_intent` is submitted, then exactly one `confirmation_required` is returned containing `operation`, `count: 100`, and all 100 targets in a structured field.
- [ ] AC-2: After grant approval, all 100 calls execute with no further confirmation prompt; each response reports remaining grant count.
- [ ] AC-3: Call 101, or a call with a body not in the enumerated set, returns `confirmation_required`.
- [ ] AC-4: A grant that has reached TTL returns `confirmation_required` on any subsequent call.
- [ ] AC-5: A batch containing a floor operation (e.g. `POST /vdbs/{id}/delete`) is refused before issuing any grant, with a clear error message.
- [ ] AC-6: Without `batch_intent`, the behavior is exactly FR-001 (each call requires its own confirmation).

---

## FR-005: Elicitation-Based Enforcement

### Description
When the connected MCP client declares the elicitation capability, the server must obtain approval via `Context.elicit()` rather than returning advisory text, making enforcement independent of the model's choice to forward the instruction to the user.

### Input
- MCP session capabilities (negotiated at session start): whether `elicitation` capability is declared
- `DCT_CONFIRMATION_ENFORCEMENT` (env var): `strict` or `advisory` (default)

### Processing
1. At session start, inspect the negotiated capabilities for `ElicitationCapability`.
2. If a destructive operation is reached and the client declares elicitation:
   a. Build an elicitation schema from FR-002's `required_fields` for the applicable level.
   b. Call `Context.elicit(message=..., schema=...)` — blocking the operation until the user responds.
   c. If the user declines (or the elicitation times out): return an error; do not execute the operation.
   d. If the user approves: treat the elicitation response as the confirmation inputs; validate per FR-002; execute if valid.
3. If the client does NOT declare elicitation:
   - `advisory` (default): return `confirmation_required` advisory text — today's behavior.
   - `strict`: refuse the operation immediately with an error naming the missing `elicitation` capability.
4. Register `ToolAnnotations` on both dynamic tools:
   - `discovery`: `readOnlyHint=True`
   - `execute`: `readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`
5. Document that a client-side "always allow" on `execute` disables gating for all 798 endpoints; `strict` + elicitation is the supported alternative.

### Output
- Elicitation-capable client: `elicit()` call issued; user sees a structured prompt in their MCP client.
- Non-elicitation + `advisory`: `{"status": "confirmation_required", ...}` — existing behavior.
- Non-elicitation + `strict`: `{"status": "error", "message": "Elicitation capability required for destructive operations. Client capability: none declared."}`.
- `tools/list` response: both tools include `ToolAnnotations` with the specified hints.

### Acceptance Criteria
- [ ] AC-1: Against a client declaring elicitation capability, a destructive operation triggers an elicitation request; if the user declines, the operation does not execute.
- [ ] AC-2: The elicitation schema for an `elevated` operation requests `confirmed_resource_name`; for `manual`, additionally requests `acknowledged_impact`.
- [ ] AC-3: With `DCT_CONFIRMATION_ENFORCEMENT=strict` and a non-elicitation client, the operation is refused and the error names the missing capability.
- [ ] AC-4: With `DCT_CONFIRMATION_ENFORCEMENT=advisory` (default), a non-elicitation client receives the existing `confirmation_required` advisory response.
- [ ] AC-5: `tools/list` reports `readOnlyHint=true` for `discovery` and `readOnlyHint=false, destructiveHint=true, idempotentHint=false` for `execute`.
- [ ] AC-6: An elicitation approval satisfies the gate without the token ever being returned to the model (the model does not need to echo the token back).

---

## FR-006: Per-Identity Velocity Detection

### Description
Add a `batch_check:N:T` confirmation level that counts calls to a given operation within a sliding window per caller identity and triggers a confirmation when the threshold is exceeded.

### Input
- `batch_check:N:T` (confirmation level format): N = threshold count, T = window in seconds; parsed from `config/mappings/manual_confirmation.txt`
- `caller_identity` (string): `X-CLIENT-ID` header in embedded mode; stable per-process UUID in STDIO mode (minted unconditionally at startup, independent of telemetry)
- `method` (string): HTTP method
- `path_template` (string): the matched URL path template (not the resolved path)
- `DCT_BATCH_COUNTER_PERSISTENCE` (env var): `off` (default) or `file`

### Processing
1. `core/session.py` mints a session/identity UUID at startup unconditionally — not gated on telemetry being enabled.
2. `config/loader.py` parses `batch_check:N:T` as a confirmation level (alongside `manual`, `elevated`, `standard`, `retention_check:N`, `policy_impact_check:N`).
3. On each call matching a `batch_check:N:T` rule:
   a. Determine caller identity: `X-CLIENT-ID` header if present, else per-process UUID.
   b. Increment the counter keyed on `(caller_identity, method, path_template)` in a sliding window of T seconds.
   c. If count < N: proceed normally (no confirmation required).
   d. If count >= N: return `{"status": "batch_confirmation_required", "count": N, "window_seconds": T, "operation": "<method path>", "grant_continuation": <grant token structure>}`.
4. Counter is in-memory; with `DCT_BATCH_COUNTER_PERSISTENCE=file`, persist to a local file for survival across STDIO cycling. Default is `off` (reset on restart, documented).
5. Emit a telemetry/audit event on trigger (FR-008), regardless of whether the user confirms.

### Output
- Below threshold: operation proceeds transparently.
- At or above threshold: `{"status": "batch_confirmation_required", "count": N, "window_seconds": T, "operation": ..., "grant_continuation": ...}`.

### Acceptance Criteria
- [ ] AC-1: Two identities each making 3 calls to the same operation in the window (N=5) do not trigger; one identity making 6 does trigger.
- [ ] AC-2: Counter state is isolated per identity — identity A's counter does not affect identity B's.
- [ ] AC-3: A session/identity UUID exists and is accessible even when `IS_LOCAL_TELEMETRY_ENABLED=false`.
- [ ] AC-4: `batch_check:5:60` parses correctly and coexists with `manual`, `elevated`, `standard`, `retention_check:N`, `policy_impact_check:N` levels.
- [ ] AC-5: A velocity trigger emits an audit event (per FR-008) whether or not the user then confirms.
- [ ] AC-6: With `DCT_BATCH_COUNTER_PERSISTENCE=off` (default), a server restart resets all counters; this behavior is documented in the config summary.

---

## FR-007: Non-Relaxable Floor Operations

### Description
Define a checked-in set of operations that cannot be authorized by batch grant, standing approval, or any configuration change — each requires an individual single-use confirmation regardless of context.

### Input
- Floor operation list (checked in): any HTTP `DELETE`; any `POST` to a path ending in `/delete`; explicitly `POST /dsources/delete`, `DELETE /management/engines/{engineId}`, `DELETE /management/accounts/{id}`
- `batch_intent.targets` (list): checked for floor operations before any grant is issued
- Any relaxation mechanism (grant, standing approval, config)

### Processing
1. Define the floor list as a checked-in constant or config file, not a heuristic.
2. In grant issuance (FR-004): before issuing a grant token, check each target against the floor list. If any matches: refuse the entire batch grant with an error listing the floor operations.
3. In standing approval logic: standing approvals may not reference floor operations; attempts to create one are refused.
4. No configuration value may disable the floor check — asserted by test.
5. In any response produced by a grant or standing approval: include `authorization: {"type": "grant", "id": ..., "remaining": ...}`.

### Output
- Attempt to include floor operation in grant/standing approval: `{"status": "error", "message": "Floor operations require individual confirmation: [list]"}`.
- Execution under a grant (non-floor): response includes `authorization` field with grant metadata.
- No config combination causes a floor operation to skip individual confirmation.

### Acceptance Criteria
- [ ] AC-1: Attempting to include any floor operation (DELETE, POST to `/delete` path) in a batch grant is refused with a clear error naming the floor operations.
- [ ] AC-2: No combination of configuration values (`DCT_CONFIRMATION_ENFORCEMENT`, `DCT_CONFIRMATION_FALLBACK`, `DCT_GRANT_TTL`, etc.) causes a floor operation to execute without individual confirmation.
- [ ] AC-3: A test enumerates the full configuration surface and asserts no knob disables confirmation globally.
- [ ] AC-4: Standing approvals expire by both count and TTL, whichever comes first; a test verifies both expiry paths.
- [ ] AC-5: Responses executed under a grant carry `authorization: {"type": "grant", "id": ..., "remaining": ...}` in the response.

---

## FR-008: Audit Events for Every Gate Decision

### Description
Emit a structured audit event for every confirmation gate decision — required, approved, refused, expired, replayed, grant-covered, and velocity-triggered — always written locally regardless of telemetry opt-in status.

### Input
- Gate decision outcome: one of `required`, `approved`, `refused`, `expired`, `replay_rejected`, `grant_covered`, `batch_triggered`
- `caller_identity` (string): per FR-006 identity
- `method` (string), `path_template` (string): operation being gated
- `level` (string): the confirmation level applied
- `grant_id` (string, optional): grant ID if the call is grant-covered
- Velocity fields (for `batch_triggered`): `threshold_N`, `window_T`, `count_at_trigger`

### Processing
1. On every gate decision, construct an audit event dict with the specified fields.
2. Exclude from the event: secrets (API keys, HMAC key), `confirmed_resource_name` values, and request bodies.
3. Write the event to the local audit log regardless of `IS_LOCAL_TELEMETRY_ENABLED`.
4. If telemetry is enabled, also upload the event to the telemetry backend.
5. Each outcome maps to exactly one event — no duplicate or missing events.

### Output
- Audit event record written to local log: `{"event": "gate_decision", "outcome": ..., "caller_identity": ..., "method": ..., "path_template": ..., "level": ..., "grant_id": ..., "threshold_N": ..., "window_T": ..., "count_at_trigger": ..., "timestamp": ...}`.
- No field in the record contains a credential, request body, or `confirmed_resource_name`.

### Acceptance Criteria
- [ ] AC-1: Each of the 7 outcomes (`required`, `approved`, `refused`, `expired`, `replay_rejected`, `grant_covered`, `batch_triggered`) produces exactly one audit event with all specified fields.
- [ ] AC-2: No audit event contains a credential, request body, or `confirmed_resource_name` value (verified by grep/inspection test).
- [ ] AC-3: Audit records are produced and written locally with `IS_LOCAL_TELEMETRY_ENABLED=false`.
- [ ] AC-4: With `IS_LOCAL_TELEMETRY_ENABLED=true`, the same event is also forwarded to the telemetry backend.

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1: API backward compatibility | All existing `confirmation_required` response fields (`status`, `confirmation_token`, `message`) remain present in the new response shape; new fields are additive only | Contract test asserting response schema is a superset of previous schema; PR review | Pending | — |
| QR-2: Migration path for confirmation level behavior | FR-2 changes to `elevated`/`manual` are default-on; `FR-5` enforcement change defaults to `advisory`; documented in config summary and CHANGELOG | Config summary review; regression test asserting advisory default | Pending | — |
| QR-3: No secrets in logs or audit events | Audit events, application logs, and session telemetry must never contain API keys, HMAC secrets, `confirmed_resource_name`, or request bodies | Grep CI step scanning log output for known secret patterns; FR-008 AC-2 test | Pending | — |
| QR-4: No unreachable confirmation resolvers | Every confirmation resolver has a tested code path; dormant code is removed | Import/call graph assertion test; confirmed by deleting or wiring `dynamic_confirmation.py` | Pending | — |
| QR-5: Floor integrity | No configuration or code path bypasses floor operation individual confirmation | Exhaustive config combination test (FR-007 AC-3) | Pending | — |
| QR-6: Default config regression | STDIO + `DCT_API_KEY` default-config run must produce no new confirmation prompts and all existing prompts must behave identically | Full regression test suite run with default env | Pending | — |
| QR-7: Token store memory bound | In-memory consumed-token store does not grow unboundedly; TTL-based expiry enforced on every lookup | Memory footprint test: insert 10,000 tokens, advance clock past TTL, assert store is empty | Pending | — |

---

## Edge Cases

- EC-1: Empty request body — `canonical_json({})` must produce a stable, deterministic string (e.g. `"{}"`) so body-less operations get consistent tokens.
- EC-2: Body with nested objects and lists — canonicalization must recurse into nested structures and sort all object keys at every level.
- EC-3: Two concurrent requests with the same token arrive simultaneously — the consumed-token store must be thread-safe; only one proceeds, the other returns `confirmation_required`.
- EC-4: Clock skew between server restart and TTL check — tokens issued just before the TTL boundary must not be granted extra time; TTL is evaluated strictly against wall clock.
- EC-5: Elicitation timeout — `Context.elicit()` does not return (client disconnects mid-elicitation); server must not leave a pending confirmation in the store; operation must not execute.
- EC-6: `batch_intent.targets` list is empty (`[]`) — refuse the grant with a clear error ("batch must have at least one target").
- EC-7: `confirmed_resource_name` contains Unicode or special characters — comparison must be case-insensitive and handle normalization (NFC) consistently.
- EC-8: `batch_check:N:T` counter with T=1 and very high N — rapid window expiry must not cause integer underflow or negative counts.
- EC-9: Grant token submitted after the grant's TTL but before the TTL sweep runs — TTL check must be performed on every lookup, not only on background sweeps.
- EC-10: A floor operation is submitted individually (no batch) — it must still go through FR-001/FR-002 single-use confirmation flow and must NOT be skippable via any config.
- EC-11: `DCT_CONFIRMATION_FALLBACK=keyword` with a path that contains a keyword in a query parameter rather than the path (e.g. `?action=refresh`) — keyword matching applies to path template only, not query params.
- EC-12: Multiple confirmation levels match the same path (static + keyword fallback) — static rule must take precedence, with its own message text used.

## Error Scenarios

- ERR-1: HMAC computation fails (e.g. `hashlib` unavailable) → server startup fails with a clear error; do not fall back to a weaker token scheme.
- ERR-2: In-memory store write raises an exception (e.g. OOM) → log the error, return a 500-level MCP error; do not proceed with the destructive operation.
- ERR-3: `Context.elicit()` raises an exception in the MCP SDK → catch and log; return `confirmation_required` advisory response; do not execute the operation.
- ERR-4: `manual_confirmation.txt` cannot be parsed (malformed line) → log a warning naming the malformed line; skip it and continue loading remaining rules; emit a startup warning to the user.
- ERR-5: Grant token store exceeds a soft limit (e.g. 10,000 active grants) → log a warning; begin rejecting new grant requests until the store falls below the limit (do not silently drop old grants).
- ERR-6: `DCT_BATCH_COUNTER_PERSISTENCE=file` and the persistence file is corrupted → log the error, reset the counter to zero, document that counts from before the corruption are lost; do not crash.
- ERR-7: Velocity counter reaches threshold and the user declines the batch confirmation → counter is not reset; the next call increments from current count (no retry amnesty).

## Performance Considerations

- Confirmation token store is in-memory; at 1 request/second sustained, 3600s TTL, the store holds at most ~3600 entries. Each entry is approximately 100 bytes (HMAC hex + timestamp), so worst-case memory is ~360KB — negligible. Documented in architecture notes.
- Canonicalization (`canonical_json`) is `O(K log K)` in body key count. For typical DCT request bodies (< 50 keys, shallow nesting), this adds < 1ms per call. Deep recursion for nested objects: limit to 10 levels; log a warning and truncate if exceeded.
- Elicitation via `Context.elicit()` is inherently blocking (user response required); no server-side timeout is added (the MCP SDK manages its own timeout). Document that `strict` mode on non-elicitation clients adds zero latency — it fails immediately.
- Batch grant enumeration up to 1000 targets is supported; above 1000, `targets_display` is truncated to the first 50 in the response; the full list is retained internally for verification. Beyond 10,000 targets in a single grant, the request is refused with a clear limit error.
- Velocity counter lookups are `O(1)` hash table operations; the sliding window uses a deque per `(identity, method, path_template)` key. Memory scales with the number of active (identity, operation) pairs — bounded by connection count × operation count.
