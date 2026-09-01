# Implementation Tasks: DLPXECO-14458

**Spec**: docs/DLPXECO-14458/DLPXECO-14458-functional.md
**Design**: docs/DLPXECO-14458/DLPXECO-14458-design.md

---

## Task 1: Add 5 New Config Env Vars  [parallel][model:haiku]

### Description
Extend `src/dct_mcp_server/config/config.py` to load and expose five new environment variables required by FR-001 (token TTL), FR-003 (fallback mode), FR-005 (enforcement mode), FR-004 (grant TTL), and FR-006 (counter persistence). Also update `print_config_help()`. This task modifies only `config.py` and is fully independent.

### Spec References
- FR-001 (config): `DCT_CONFIRMATION_TOKEN_TTL` — token store TTL, default 3600s
- FR-003 (config): `DCT_CONFIRMATION_FALLBACK` — `keyword` | `off`, default `keyword`
- FR-005 (config): `DCT_CONFIRMATION_ENFORCEMENT` — `strict` | `advisory`, default `advisory`
- FR-004 (config): `DCT_GRANT_TTL` — batch grant TTL, default 900s
- FR-006 (config): `DCT_BATCH_COUNTER_PERSISTENCE` — `off` | `file`, default `off`

### Sub-tasks (TDD)
- [x] **RED**: Tests for new config keys can be written — `assert config["confirmation_token_ttl"] == 3600`
- [x] **GREEN**: Add the 5 keys to `get_dct_config()` and `print_config_help()`
- [x] **REFACTOR**: Group new keys under a comment block in config.py

### Depends On
- None

### Acceptance Criteria
- [ ] `get_dct_config()` returns all 5 new keys with documented defaults
- [ ] `print_config_help()` documents all 5 new env vars
- [ ] No existing keys are changed

---

## Task 2: Unconditional Process Identity UUID in session.py  [parallel][model:haiku]

### Description
Extend `src/dct_mcp_server/core/session.py` to mint a `PROCESS_IDENTITY` UUID at module import time, unconditionally (not gated on `IS_LOCAL_TELEMETRY_ENABLED`). Expose `get_process_identity()`. Update `get_current_session_id()` to fall back to the process identity when no telemetry session is active.

### Spec References
- FR-006 (AC-3): Session/identity UUID exists and is accessible with `IS_LOCAL_TELEMETRY_ENABLED=false`

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.core.session import get_process_identity; assert get_process_identity() is not None` — NameError: `get_process_identity` not defined
- [x] **GREEN**: Add `PROCESS_IDENTITY = str(uuid.uuid4())` at module level; add `get_process_identity()` function
- [x] **REFACTOR**: Ensure `get_current_session_id()` falls back to `PROCESS_IDENTITY` when no active session

### Depends On
- None

### Acceptance Criteria
- [ ] `get_process_identity()` returns a non-empty UUID string at all times
- [ ] `get_process_identity()` returns the same value within a process lifetime
- [ ] `get_current_session_id()` returns `PROCESS_IDENTITY` when no telemetry session is active

---

## Task 3: Config Mapping Files (manual_confirmation.txt additions + new files)  [parallel][model:haiku]

### Description
Add 13 new explicit rules to `config/mappings/manual_confirmation.txt` for FR-003 (8 refresh actions, snapshot, bookmark, vdb-group, database-template, hook-template). Create two new mapping files: `read_exclusions.txt` (read-shaped POST paths that must not be gated) and `floor_operations.txt` (floor operation patterns for FR-007).

### Spec References
- FR-003 (AC-1, AC-2): 20 actions gated; read-shaped POSTs return `none`
- FR-007 (AC-1, AC-2): Floor operations defined in checked-in file

### Sub-tasks (TDD)
- [x] **RED**: Test that `POST /vdbs/{id}/refresh_by_timestamp` resolves to non-`none` — currently fails (no static rule)
- [x] **GREEN**: Add 13 rules to `manual_confirmation.txt`; create `read_exclusions.txt` and `floor_operations.txt`
- [x] **REFACTOR**: Add comments grouping the 13 new rules under "RULE 9: Refresh Actions" and "RULE 10: Create Actions"

### Depends On
- None

### Acceptance Criteria
- [ ] All 8 refresh actions resolve to `elevated` level via static rules
- [ ] `POST /vdbs/{id}/snapshots`, `POST /bookmarks`, `POST /vdb-groups`, `POST /database-templates`, `POST /hook-templates` resolve to `standard`
- [ ] `read_exclusions.txt` contains all 8 read-shaped POST path patterns from FR-003
- [ ] `floor_operations.txt` contains DELETE wildcard and POST `/delete` patterns

---

## Task 4: ConsumedTokenStore and GrantStore (confirmation_store.py)  [parallel][model:sonnet]

### Description
Create `src/dct_mcp_server/tools/core/confirmation_store.py` with two thread-safe in-memory singletons: `ConsumedTokenStore` (dict[token → expiry timestamp] with TTL sweep on every lookup) and `GrantStore` (dict[grant_id → GrantEntry] with count + TTL enforcement). Both are module-level singletons reset on server restart.

### Spec References
- FR-001 (AC-2): Token replay returns `confirmation_required` — consumed token is never executed again
- FR-004 (AC-1 through AC-6): Batch grant lifecycle
- FR-007 (AC-4): Standing approvals expire by both count and TTL

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.confirmation_store import ConsumedTokenStore; store = ConsumedTokenStore(); store.add("tok", 1); assert store.is_consumed("tok")` — ImportError
- [x] **GREEN**: Implement `ConsumedTokenStore` with `add(token, ttl_seconds)`, `is_consumed(token)` (also sweeps expired), `consume(token)` returning bool (True if token was present and not expired). Implement `GrantStore` with `create_grant(grant_id, operation, targets, ttl_seconds)`, `consume_target(grant_id, target_canonical) → GrantConsumeResult`, `get_remaining(grant_id) → int | None`
- [x] **REFACTOR**: Extract `_sweep_expired()` helper; ensure thread-safety with `threading.Lock`; add module docstring

### Depends On
- Task 1 (config keys for TTL values)

### Acceptance Criteria
- [ ] `ConsumedTokenStore.consume(token)` returns True once, False on replay
- [ ] Expired tokens (TTL elapsed) are swept on every `is_consumed`/`consume` call
- [ ] `GrantStore.consume_target()` counts remaining correctly; returns `GRANT_EXHAUSTED` when count=0 or TTL expired
- [ ] Both stores are thread-safe under concurrent access
- [ ] EC-3: Two concurrent requests with same token — only one proceeds

---

## Task 5: Audit Event Emitter (audit.py)  [parallel][model:sonnet]

### Description
Create `src/dct_mcp_server/tools/core/audit.py` with `emit_gate_event(outcome, identity, method, path_template, level, grant_id=None, velocity_fields=None)`. Always writes to the local audit log regardless of `IS_LOCAL_TELEMETRY_ENABLED`. Never logs secrets, request bodies, or `confirmed_resource_name`.

### Spec References
- FR-008 (AC-1 through AC-4): 7 outcomes, no credential leakage, always-local write

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.audit import emit_gate_event; emit_gate_event("required", "id-1", "POST", "/vdbs", "standard")` — ImportError
- [x] **GREEN**: Implement `emit_gate_event()` using `get_logger()` from `core.logging`; include all 7 outcome types; validate that no credential fields are included
- [x] **REFACTOR**: Extract `_build_audit_record()` helper; add `VALID_OUTCOMES` constant

### Depends On
- None

### Acceptance Criteria
- [ ] All 7 outcome types (`required`, `approved`, `refused`, `expired`, `replay_rejected`, `grant_covered`, `batch_triggered`) produce exactly one log entry
- [ ] Audit records contain no API keys, HMAC secrets, or request bodies
- [ ] Records are written with `IS_LOCAL_TELEMETRY_ENABLED=false`

---

## Task 6: Floor Operations Guard (floor_operations.py)  [model:haiku]

### Description
Create `src/dct_mcp_server/tools/core/floor_operations.py` that loads `config/mappings/floor_operations.txt` at import time and exposes `is_floor_operation(method, path) → bool`. HMAC initialization failure at import must raise immediately (per ERR-1).

### Spec References
- FR-007 (AC-1, AC-2): No floor operation can be granted or skip individual confirmation

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.floor_operations import is_floor_operation; assert is_floor_operation("DELETE", "/vdbs/vdb-123")` — ImportError
- [x] **GREEN**: Load `floor_operations.txt`; match any DELETE and any POST ending in `/delete`
- [x] **REFACTOR**: Cache the loaded rules; add `is_floor_operation` docstring

### Depends On
- Task 3 (floor_operations.txt)

### Acceptance Criteria
- [ ] `is_floor_operation("DELETE", "/anything")` returns True
- [ ] `is_floor_operation("POST", "/vdbs/{id}/delete")` returns True
- [ ] `is_floor_operation("POST", "/vdbs/provision_by_snapshot")` returns False
- [ ] `is_floor_operation("GET", "/vdbs")` returns False

---

## Task 7: Sliding-Window Velocity Counter (velocity_counter.py)  [model:sonnet]

### Description
Create `src/dct_mcp_server/tools/core/velocity_counter.py` with a sliding-window per-identity velocity counter keyed on `(caller_identity, method, path_template)`. Exposes `increment_and_check(identity, method, path_template, N, T) → (triggered: bool, count: int)`. Supports optional file persistence via `DCT_BATCH_COUNTER_PERSISTENCE=file`.

### Spec References
- FR-006 (AC-1, AC-2, AC-5, AC-6): Per-identity isolation, velocity trigger, no retry amnesty

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.velocity_counter import increment_and_check; triggered, count = increment_and_check("id-1", "POST", "/vdbs/provision_by_snapshot", N=5, T=60); assert not triggered` — ImportError
- [x] **GREEN**: Implement sliding window with `collections.deque` per key; lock-protected; N-1 calls don't trigger; Nth call does
- [x] **REFACTOR**: Extract `_evict_old_entries(deque, window_start)` helper; add file persistence path

### Depends On
- Task 2 (PROCESS_IDENTITY for default identity)

### Acceptance Criteria
- [ ] Two identities each making 3 calls (N=5) → neither triggers; one identity making 6 → triggers
- [ ] Counter state is isolated per identity
- [ ] Counter is NOT reset when user declines batch confirmation (no retry amnesty — ERR-7)
- [ ] `DCT_BATCH_COUNTER_PERSISTENCE=off` resets counters on restart

---

## Task 8: Differentiated Confirmation Level Validator (confirmation_levels.py)  [parallel][model:sonnet]

### Description
Create `src/dct_mcp_server/tools/core/confirmation_levels.py` implementing `validate_elevated(path, confirmed_resource_name) → dict` and `validate_manual(path, confirmed_resource_name, acknowledged_impact) → dict`. Also exposes `build_required_fields(level) → list[str]` used in every `confirmation_required` response.

### Spec References
- FR-002 (AC-1 through AC-7): Differentiated level checks and required_fields

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.confirmation_levels import validate_elevated, build_required_fields; result = validate_elevated("/vdbs/vdb-123/refresh", None); assert result["requires_further_confirmation"]` — ImportError
- [x] **GREEN**: Implement `validate_elevated()` (resource name extraction from path + case-insensitive match) and `validate_manual()` (elevated checks + acknowledged_impact). `build_required_fields()` returns the list for the level
- [x] **REFACTOR**: Extract `_extract_resource_id(path) → str | None`; add EC-7 Unicode normalization (NFC + casefold)

### Depends On
- None

### Acceptance Criteria
- [ ] `elevated` with no `confirmed_resource_name` → required_fields includes `confirmed_resource_name`
- [ ] `elevated` with wrong name → requires_further_confirmation=True
- [ ] `manual` with all correct → passes
- [ ] `manual` with missing `acknowledged_impact` → required_fields includes `acknowledged_impact`
- [ ] EC-7: Unicode/case comparison uses NFC + casefold
- [ ] AC-7: `manual` and `standard` are not mechanically equivalent

---

## Task 9: Extend Config Loader (loader.py)  [model:sonnet]

### Description
Extend `src/dct_mcp_server/config/loader.py` to: (1) parse `batch_check:N:T` level format (two colons), (2) invoke `dynamic_confirmation.get_confirmation_for_operation_dynamic` as a keyword fallback when `DCT_CONFIRMATION_FALLBACK=keyword` and no static rule matches, after applying `read_exclusions.txt`. Also update `clear_cache()` to handle any new in-memory stores.

### Spec References
- FR-003 (AC-4, AC-5, AC-6): Static rules first; keyword fallback second; `off` reproduces pre-change
- FR-006 (AC-4): `batch_check:5:60` parses correctly alongside existing conditional levels

### Sub-tasks (TDD)
- [x] **RED**: Test that `batch_check:5:60` level parses to `(level="batch_check", N=5, T=60)` — currently the two-colon split would break the existing parser
- [x] **GREEN**: Update `_parse_conditional_level(level_str)` to handle `batch_check:N:T`; update `get_confirmation_for_operation()` to invoke keyword fallback after static rules when `DCT_CONFIRMATION_FALLBACK=keyword` env var is set; load `read_exclusions.txt` and check before keyword match
- [x] **REFACTOR**: Extract `_load_read_exclusions()` cached loader; extract `_is_read_exclusion(path) → bool`

### Depends On
- Task 3 (read_exclusions.txt)

### Acceptance Criteria
- [ ] `batch_check:5:60` parses to N=5, T=60 without breaking existing rule parsing
- [ ] `DCT_CONFIRMATION_FALLBACK=off` → keyword resolver not invoked; output identical to pre-change
- [ ] `DCT_CONFIRMATION_FALLBACK=keyword` → keyword resolver invoked when no static match
- [ ] Read-shaped POSTs in `read_exclusions.txt` resolve to `none` even with keyword fallback on
- [ ] Static rule takes precedence over keyword fallback

---

## Task 10: Wire dynamic_confirmation.py as Live Fallback  [model:haiku]

### Description
Update `src/dct_mcp_server/tools/core/dynamic_confirmation.py` to apply the `read_exclusions.txt` list before returning a keyword-matched level, ensuring read-shaped POSTs resolve to `none`. Update the module docstring to reflect its status as a live utility (not dormant). Remove any unreachable code paths.

### Spec References
- FR-003 (AC-6, QR-4): No unreachable confirmation resolver; `dynamic_confirmation.py` has a live caller

### Sub-tasks (TDD)
- [x] **RED**: `get_confirmation_for_operation_dynamic("POST", "/vdbs/provision_by_snapshot/defaults")` currently returns a keyword match for "provision" — test asserts it returns `none`
- [x] **GREEN**: Before returning a keyword match, check if path is in read exclusions (loaded from `read_exclusions.txt` via loader); if so, return `_none()`
- [x] **REFACTOR**: Update module docstring; remove the lazy circular import of `get_cached_spec` and instead accept `spec=None` gracefully with a direct call to static resolver first

### Depends On
- Task 3 (read_exclusions.txt), Task 9 (loader.py updated)

### Acceptance Criteria
- [ ] `get_confirmation_for_operation_dynamic("POST", "/vdbs/provision_by_snapshot/defaults")` returns `none`
- [ ] `get_confirmation_for_operation_dynamic("POST", "/snapshots/search")` returns `none`
- [ ] `dynamic_confirmation.py` has a live caller (confirmation_resolver.py) after Task 11

---

## Task 11: Extend Confirmation Resolver with Fallback  [model:sonnet]

### Description
Extend `src/dct_mcp_server/tools/core/confirmation_resolver.py` to add `check_confirmation_with_fallback()` that calls `get_confirmation_for_operation` (static rules first, already includes keyword fallback via updated loader) then evaluates `batch_check` level by delegating to velocity counter. Also adds `required_fields` to every confirmation result.

### Spec References
- FR-003 (AC-4): Static rules take precedence; keyword fallback via loader
- FR-006 (AC-4): `batch_check:N:T` coexists with other levels
- FR-002 (AC-6): `required_fields` in every confirmation response

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation_with_fallback` — ImportError
- [x] **GREEN**: Add `check_confirmation_with_fallback(method, path, body, identity, context)` that extends existing `check_confirmation()` with: (a) `required_fields` from `build_required_fields(level)`, (b) `batch_check` level handling via `increment_and_check`
- [x] **REFACTOR**: Deprecate old `check_confirmation()` in favour of `check_confirmation_with_fallback()`; keep backward-compat wrapper

### Depends On
- Task 7 (velocity_counter.py), Task 8 (confirmation_levels.py), Task 9 (loader.py), Task 10 (dynamic_confirmation.py)

### Acceptance Criteria
- [ ] `required_fields` is always present in the returned dict
- [ ] `batch_check` level triggers velocity counter and returns `batch_confirmation_required` when threshold exceeded
- [ ] Old `check_confirmation()` still works (backward compat)

---

## Task 12: Rewrite confirmation_token.py with Body-Bound Tokens  [model:sonnet]

### Description
Rewrite `src/dct_mcp_server/tools/core/confirmation_token.py` to include `canonical_json(body)` in the HMAC input and add `verify_and_consume_token(token, method, path, body) → bool` that delegates consumed-token state to `ConsumedTokenStore` from `confirmation_store.py`.

### Spec References
- FR-001 (AC-1 through AC-7): Body-bound tokens, single-use consumption, replay rejection

### Sub-tasks (TDD)
- [x] **RED**: `from dct_mcp_server.tools.core.confirmation_token import verify_and_consume_token; assert verify_and_consume_token("bad", "POST", "/vdbs/provision", {})` is False — ImportError
- [x] **GREEN**: Add `canonical_json(body)`, update `make_confirmation_token(method, path, body)`, add `verify_and_consume_token()` that checks store for replay and body binding
- [x] **REFACTOR**: Ensure backward compat for callers that pass no body (`body=None` defaults to `{}`); preserve existing `verify_confirmation_token()` with deprecation note

### Depends On
- Task 4 (confirmation_store.py), Task 1 (config for TTL)

### Acceptance Criteria
- [ ] Body with different key order produces identical token (AC-3: order-independent)
- [ ] Replay of consumed token returns False (AC-2)
- [ ] Token for body A does not verify with body B (AC-1, AC-4)
- [ ] EC-1: Empty body `{}` produces stable token
- [ ] EC-2: Nested objects are recursively sorted

---

## Task 13: Integrate All Systems into dynamic.py  [model:opus]

### Description
Integrate the full confirmation hardening into `src/dct_mcp_server/tools/core/dynamic.py`. This is the largest and most complex task — it touches the `execute()` function to add: body-bound token verification (FR-001), differentiated level checks (FR-002), batch_intent parameter and grant lifecycle (FR-004), `Context.elicit()` integration for elicitation-capable clients (FR-005), velocity counter (FR-006), floor operation enforcement (FR-007), and audit event emission (FR-008). Also registers `ToolAnnotations` on both tools (FR-005 AC-5).

### Spec References
- FR-001 (AC-7): Existing flows unchanged except tokens are now single-use
- FR-002 (AC-1–7): Level-specific validation in execute path
- FR-004 (AC-1–6): batch_intent + grant_token parameters
- FR-005 (AC-1–6): elicit() path + strict enforcement + ToolAnnotations
- FR-006 (AC-1–6): Velocity detection per identity
- FR-007 (AC-1–5): Floor check on every destructive call
- FR-008 (AC-1–4): Audit event on every gate decision

### Sub-tasks (TDD)
- [x] **RED**: Tests asserting `required_fields` is in confirmation response, replay returns `confirmation_required`, floor op in batch is refused
- [x] **GREEN**: Extend `execute()` signature with `batch_intent`, `grant_token`, `confirmed_resource_name`, `acknowledged_impact`; thread the new confirmation pipeline through the gate (Step 4); register ToolAnnotations
- [x] **REFACTOR**: Extract `_run_confirmation_gate()` helper; document every FR in inline comments; ensure `_make_execute_fn` signature matches updated docstring

### Depends On
- Tasks 4–12 (all dependencies)

### Acceptance Criteria
- [ ] SC-1 (FR-001): Replaying used token returns `confirmation_required`
- [ ] SC-2 (FR-004): 100-target batch requires exactly one confirmation
- [ ] SC-5 (FR-002): `elevated` and `manual` require demonstrably different inputs
- [ ] SC-6 (FR-005): Elicitation decline prevents execution
- [ ] SC-7 (FR-005): `strict` + non-elicitation client → refused
- [ ] SC-8 (FR-007): Floor op cannot be executed under batch grant
- [ ] SC-9 (FR-008): Audit events produced with telemetry disabled
- [ ] SC-10: Default config (STDIO + DCT_API_KEY) fully regression-free

---

## Execution Order

Tasks 1, 2, 3, 4, 5, 8 (parallel wave 1) → Tasks 6, 7, 9 (parallel wave 2, after 3) → Task 10 (after 9) → Task 11 (after 10) → Task 12 (after 4, 11) → Task 13 (after all)

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Config env vars | PENDING |
| Task 2: session.py PROCESS_IDENTITY | PENDING |
| Task 3: Config mapping files | PENDING |
| Task 4: confirmation_store.py | PENDING |
| Task 5: audit.py | PENDING |
| Task 6: floor_operations.py | PENDING |
| Task 7: velocity_counter.py | PENDING |
| Task 8: confirmation_levels.py | PENDING |
| Task 9: loader.py extensions | PENDING |
| Task 10: dynamic_confirmation.py wiring | PENDING |
| Task 11: confirmation_resolver.py fallback | PENDING |
| Task 12: confirmation_token.py rewrite | PENDING |
| Task 13: dynamic.py integration | PENDING |
