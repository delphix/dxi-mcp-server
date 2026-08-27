# Implementation Tasks: DLPXECO-14324

**Design**: docs/DLPXECO-14324/DLPXECO-14324-design.md

---

<!-- Directives:
     [parallel]    = task can run simultaneously with others (disjoint file sets)
     [model:haiku] = mechanical: 1-2 files, complete spec, straightforward edits
     [model:sonnet]= integration: multiple files, coordination or pattern-matching
     [model:opus]  = architecture: design judgment, broad codebase understanding
-->

## Progress Tracker

| Task | Description | Status |
|------|-------------|--------|
| T1 | Add AuthError to exceptions.py | pending |
| T2 | Extend config.py with new env vars | pending |
| T3 | Create core/auth.py (AuthContext, middleware, ContextVar) | pending |
| T4 | Create core/client_registry.py (LRU ClientRegistry) | pending |
| T5 | Extend dct_client/client.py (for_identity, _mask_secret, SecretGuard) | pending |
| T6 | Extend core/session.py (per-caller session scoping) | pending |
| T7 | Update core/decorators.py (read _CALLER_ID_VAR) | pending |
| T8 | Update tools/__init__.py (accept ClientRegistry) | pending |
| T9 | Update toolsgenerator/driver.py (bundled spec fallback) | pending |
| T10 | Update main.py (transport selection, HTTP mode, lifespan) | pending |

---

## Task 1: Add AuthError to exceptions.py  [parallel][model:haiku]

### Description
Add a new `AuthError(MCPError)` exception class to `src/dct_mcp_server/core/exceptions.py`.
This is a prerequisite for auth.py (T3). Must run first because T3 imports `AuthError`.

### Spec References
- FR-006: Auth error on missing/invalid identity; no fallback

### Sub-tasks (TDD)
- [ ] **RED**: Import `AuthError` from `dct_mcp_server.core.exceptions` in a test — expect `ImportError`
- [ ] **GREEN**: Add `class AuthError(MCPError): pass` to exceptions.py
- [ ] **REFACTOR**: Add a docstring explaining when this is raised

---

## Task 2: Extend config.py with new env vars  [parallel][model:haiku]

### Description
Add five new env var fields to `get_dct_config()` in `src/dct_mcp_server/config/config.py`:
- `DCT_TRANSPORT` (default `stdio`)
- `DCT_AUTH_MODE` (default `standalone`)
- `DCT_HTTP_HOST` (default `127.0.0.1`)
- `DCT_HTTP_PORT` (default `8765`)
- `DCT_REQUIRE_TLS` (default `True`)

Make `DCT_API_KEY` optional (no ValueError) when `DCT_AUTH_MODE=embedded`.
Add optional `require_key=False` parameter to `get_dct_config()` for use by the toolsgenerator.

### Spec References
- FR-001: HTTP transport — `DCT_TRANSPORT=stdio|http`
- FR-002: Embedded auth — `DCT_AUTH_MODE=embedded`
- FR-008: TLS enforcement — `DCT_REQUIRE_TLS=true` default

### Sub-tasks (TDD)
- [ ] **RED**: `test_S1_StdioTransport::test_default_transport_is_stdio` → FAIL (key not in config)
- [ ] **GREEN**: Add all five fields to the config dict; relax API key validation when embedded
- [ ] **REFACTOR**: Update `print_config_help()` to document new env vars

---

## Task 3: Create core/auth.py  [model:sonnet]

### Description
Create `src/dct_mcp_server/core/auth.py` with:
- `_CALLER_ID_VAR: ContextVar[Optional[str]]` — stores X-CLIENT-ID per-request
- `AuthContext` dataclass (`account_id`, `api_key`, `auth_mode`)
- `ClientIDMiddleware` — Starlette ASGI middleware that reads `x-client-id` header, sets `_CALLER_ID_VAR`, raises `AuthError` if missing or empty
- `resolve_auth() -> AuthContext` — reads ContextVar; raises `AuthError` in embedded mode when unset; returns standalone key-based AuthContext otherwise

Depends on T1 (AuthError) and T2 (config has auth_mode).

### Spec References
- FR-002: Embedded auth — X-CLIENT-ID header per request
- FR-006: AuthError on missing/invalid identity; no fallback

### Sub-tasks (TDD)
- [ ] **RED**: `TestS3_ClientIdIdentityResolution::test_caller_id_context_var_is_set_by_middleware` → FAIL (ImportError)
- [ ] **GREEN**: Write auth.py with all components; middleware sets ContextVar, raises on empty/missing
- [ ] **REFACTOR**: Extract `_validate_caller_id(value)` helper; ensure no raw values are logged

---

## Task 4: Create core/client_registry.py  [model:sonnet]

### Description
Create `src/dct_mcp_server/core/client_registry.py` with:
- `ClientRegistry`: thread-safe LRU dict (default size 256) keyed by identity hash
- `get_client(auth_ctx: AuthContext) -> DCTAPIClient`: returns cached or new client
- `close_all()`: closes all managed httpx clients cleanly

Depends on T3 (AuthContext) and T5 (DCTAPIClient.for_identity).

### Spec References
- FR-003: Per-request client; no cross-user leakage

### Sub-tasks (TDD)
- [ ] **RED**: `TestS4_CrossUserIsolation::test_client_registry_creates_separate_clients_per_identity` → FAIL
- [ ] **GREEN**: Write ClientRegistry with LRU OrderedDict; get_client() creates new DCTAPIClient per identity hash
- [ ] **REFACTOR**: Add docstring; add DEBUG log on eviction; lock all mutations

---

## Task 5: Extend dct_client/client.py  [parallel][model:sonnet]

### Description
Add to `src/dct_mcp_server/dct_client/client.py`:
- `_mask_secret(value: str) -> str` module-level helper — masks secrets for logging
- `DCTAPIClient.for_identity(account_id: str, base_url: str) -> DCTAPIClient` classmethod — creates client using X-CLIENT-ID (no `apk ` prefix on account_id; uses internal trust header)
- `SecretGuard` class with `check(kwargs: dict) -> None` static method — raises `DCTClientError` if any value matches `apk ` prefix or is base64-like token > 32 chars
- Ensure `self.api_key` is never logged raw; use `_mask_secret()` in all log lines

### Spec References
- FR-003: Per-request client factory
- FR-007: Credential-by-reference + inline-secret guard
- FR-008: Secret hygiene

### Sub-tasks (TDD)
- [ ] **RED**: `TestS12_SecretHygiene::test_mask_secret_hides_api_key` → FAIL (ImportError)
- [ ] **GREEN**: Add `_mask_secret`, `for_identity`, `SecretGuard` to client.py
- [ ] **REFACTOR**: Ensure `Authorization` header never appears in logs; review all `logger.*` calls

---

## Task 6: Extend core/session.py  [parallel][model:haiku]

### Description
Add to `src/dct_mcp_server/core/session.py`:
- `get_or_create_caller_session(caller_id: str) -> logging.Logger` — creates or returns a per-caller session logger keyed by `caller_id`
- `end_caller_session(caller_id: str) -> None` — ends a caller's session and closes its logger
- Public API: expose both via module-level functions alongside existing `start_session` / `end_session`

Keep the global session for backward compatibility in standalone mode.

### Spec References
- FR-005: Per-caller session/telemetry scoping

### Sub-tasks (TDD)
- [ ] **RED**: `TestS8_PerCallerTelemetry::test_get_or_create_caller_session_creates_session` → FAIL
- [ ] **GREEN**: Add `get_or_create_caller_session` and `end_caller_session` to `SessionManager` and expose as module functions
- [ ] **REFACTOR**: Consolidate caller-session logic with existing session dict; ensure no global-session interference

---

## Task 7: Update core/decorators.py  [model:haiku]

### Description
Update `@log_tool_execution` in `src/dct_mcp_server/core/decorators.py` to:
- Import `_CALLER_ID_VAR` from `core.auth` (guarded import to avoid circular)
- Read caller ID from ContextVar at decoration time
- When telemetry is enabled and a caller ID is present, delegate `log_tool_call()` to the per-caller session logger (`get_or_create_caller_session`)
- When caller ID is absent (standalone mode), use existing global session behavior unchanged

Depends on T3 (auth.py) and T6 (session.py).

### Spec References
- FR-005: Per-caller session/telemetry scoping

### Sub-tasks (TDD)
- [ ] **RED**: `TestS8_PerCallerTelemetry::test_tool_execution_tags_telemetry_with_caller_id` → FAIL
- [ ] **GREEN**: Add ContextVar read to both sync and async wrapper paths in `@log_tool_execution`
- [ ] **REFACTOR**: Extract `_get_session_id_for_log()` helper; add inline comment explaining fallback

---

## Task 8: Update tools/__init__.py  [parallel][model:haiku]

### Description
Update `register_all_tools(app, dct_client)` in `src/dct_mcp_server/tools/__init__.py` to accept either:
- A plain `DCTAPIClient` singleton (existing standalone mode — unchanged)
- A `ClientRegistry` instance (new embedded mode)

The function signature stays the same (`client_or_registry` parameter name for clarity internally); callers pass either type. Pass it through to each tool module's `register_tools()`.

Depends on T4 (ClientRegistry type).

### Spec References
- FR-003: Per-request client registry

### Sub-tasks (TDD)
- [ ] **RED**: `TestS14_BackwardCompatStdioMode::test_register_all_tools_still_accepts_single_client` — will pass after T8 since signature is unchanged
- [ ] **GREEN**: Add type union check inside `register_all_tools`; no external signature change needed
- [ ] **REFACTOR**: Add docstring documenting both accepted types

---

## Task 9: Update toolsgenerator/driver.py  [parallel][model:sonnet]

### Description
Update `src/dct_mcp_server/toolsgenerator/driver.py` to:
- Guard `get_dct_config()` call so missing `DCT_API_KEY` does not abort startup in embedded mode (use `require_key=False` where applicable)
- When `DCT_AUTH_MODE=embedded` (or `DCT_API_KEY` is absent), skip live spec download and load bundled `docs/api-external.yaml` directly
- Log "using bundled spec" when this path is taken
- `load_api_endpoints_from_toolsets()` must also handle `require_key=False` path

Depends on T2 (config knows about auth_mode and require_key).

### Spec References
- FR-004: Startup tool gen without user credential

### Sub-tasks (TDD)
- [ ] **RED**: `TestS7_EmbeddedModeToolGeneration::test_config_get_dct_config_accepts_require_key_false` → FAIL
- [ ] **GREEN**: Add `require_key=False` param to `get_dct_config()`; update driver to call it; add bundled spec fallback path
- [ ] **REFACTOR**: Extract `_should_use_bundled_spec()` helper to make the decision point explicit

---

## Task 10: Update main.py  [model:opus]

### Description
Update `src/dct_mcp_server/main.py` to:
1. Read `DCT_TRANSPORT` from config — `stdio` (default) or `http`
2. Read `DCT_AUTH_MODE` — `standalone` (default) or `embedded`
3. In **standalone mode**: unchanged behavior — create global `DCTAPIClient`, run `run_stdio_async()`
4. In **HTTP + embedded mode**:
   - Skip global `DCTAPIClient` creation; create `ClientRegistry` instead
   - Wrap `app.streamable_http_app()` with `ClientIDMiddleware` using Starlette wrapping
   - Run via `uvicorn.run(wrapped_app, host=..., port=...)` in a thread-pool executor (asyncio-compatible)
   - Log TLS warning when `DCT_REQUIRE_TLS=false`
5. Update `lifespan` to call `client_registry.close_all()` when a registry is in use
6. Update `register_all_tools()` call to pass registry when embedded

Depends on all other tasks (T1–T9).

### Spec References
- FR-001: HTTP transport selection
- FR-002: Embedded auth via middleware injection
- FR-003: Per-request ClientRegistry in embedded mode
- FR-004: Tool gen without API key at startup
- FR-008: TLS warning log

### Sub-tasks (TDD)
- [ ] **RED**: `TestS2_HttpTransportEmbeddedMode::test_embedded_mode_does_not_require_api_key` — currently fails; `TestS1_StdioTransport::test_default_transport_is_stdio` — also currently fails
- [ ] **GREEN**: Implement transport selection, HTTP mode with uvicorn, embedded mode startup sequence
- [ ] **REFACTOR**: Extract `_run_http_server(app, config)` coroutine; ensure lifespan handles both cleanup paths cleanly

---
