# Feature Design: DLPXECO-14324

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14324
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME". -->

---

## Summary

This feature adds HTTP transport, per-request identity resolution, and secret-safe execution to the DCT MCP server to support DCT-embedded deployment mode. Existing stdio transport and single-user `DCT_API_KEY` mode are preserved as the default and must not regress. The changes are additive: a new `DCT_TRANSPORT` env var selects the transport, a new `DCT_AUTH_MODE` env var selects standalone (existing) versus embedded (new) authentication, and a per-request client registry replaces the global `DCTAPIClient` singleton when embedded mode is active. A credential-alias mechanism and an inline-secret guard are also introduced so that tool arguments never carry raw secrets in either mode.

## Affected Components

Based on the layer map in `.claude/architecture.md`:

- [x] Entry point — `main.py` (transport selection, startup decoupled from user credential)
- [x] Config — `config/config.py` (new env vars: `DCT_TRANSPORT`, `DCT_AUTH_MODE`, `DCT_HTTP_HOST`, `DCT_HTTP_PORT`)
- [x] HTTP client — `dct_client/client.py` (factory method for per-request client, secret guard, no key logging)
- [x] Infrastructure — `core/session.py` (per-caller telemetry scoping)
- [x] Infrastructure — `core/decorators.py` (`@log_tool_execution` reads caller identity from ContextVar)
- [x] Infrastructure — `core/exceptions.py` (new `AuthError` subclass)
- [x] Tool registration — `tools/__init__.py` (accepts client registry instead of singleton)
- [x] Dynamic tool generation — `toolsgenerator/driver.py` (spec loaded from bundled source when no user credential is present at startup)
- [ ] Toolset config files — `config/toolsets/*.txt` (no changes required)
- [ ] Confirmation rules — `config/mappings/manual_confirmation.txt` (no changes required)
- [ ] Pre-built tool modules — `tools/*_endpoints_tool.py` (no changes required to existing tools)
- [ ] Dynamic tool generation helpers — `tools/core/tool_factory.py` (no changes required)
- [ ] Spec helpers — `tools/core/meta_tools.py` (no changes required)

## Architecture Changes

### Schema / Config Changes

New environment variables handled in `config/config.py`:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `DCT_TRANSPORT` | string | `stdio` | `stdio` or `http`; selects FastMCP run method |
| `DCT_AUTH_MODE` | string | `standalone` | `standalone` (API key from env) or `embedded` (X-CLIENT-ID header per request) |
| `DCT_HTTP_HOST` | string | `127.0.0.1` | Bind address for HTTP transport |
| `DCT_HTTP_PORT` | integer | `8765` | Listen port for HTTP transport |
| `DCT_REQUIRE_TLS` | bool | `true` | Enforce TLS check on HTTP endpoint (logged warning if `false`) |

`DCT_API_KEY` becomes optional when `DCT_AUTH_MODE=embedded`; the startup validation in `config.py` is relaxed accordingly.

No schema files, database tables, or persisted state shapes are changed.

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/config/config.py` | Add `DCT_TRANSPORT`, `DCT_AUTH_MODE`, `DCT_HTTP_HOST`, `DCT_HTTP_PORT`, `DCT_REQUIRE_TLS`; make `DCT_API_KEY` optional in embedded mode | FR-001, FR-002, FR-008 |
| `src/dct_mcp_server/main.py` | Select transport via `DCT_TRANSPORT`: use `run_stdio_async()` (default) or, for HTTP, call `app.streamable_http_app()` directly (to inject custom Starlette middleware for X-CLIENT-ID extraction), then run uvicorn manually — `run_streamable_http_async()` takes no middleware args so it cannot be used directly in embedded mode; decouple tool-gen from `DCTAPIClient` init; replace singleton `dct_client` with `ClientRegistry` in embedded mode; add TLS warning log | FR-001, FR-002, FR-003, FR-004, FR-008 |
| `src/dct_mcp_server/dct_client/client.py` | Add `DCTAPIClient.for_identity(account_id, base_url)` factory; add `_mask_secret(key)` helper used in all log lines; never log raw `api_key`; add `SecretGuard.check(kwargs)` static method | FR-003, FR-007, FR-008 |
| `src/dct_mcp_server/core/session.py` | Add `get_or_create_caller_session(caller_id)` and `end_caller_session(caller_id)` so each caller gets its own telemetry log file; keep global session for backward compat | FR-005 |
| `src/dct_mcp_server/core/decorators.py` | `@log_tool_execution` reads `_CALLER_ID_VAR` ContextVar to tag telemetry entries with the caller; delegates to caller session when in embedded mode | FR-005 |
| `src/dct_mcp_server/core/exceptions.py` | Add `AuthError(MCPError)` raised by `auth.py` on missing/invalid identity | FR-006 |
| `src/dct_mcp_server/tools/__init__.py` | `register_all_tools(app, client_or_registry)` accepts either a singleton `DCTAPIClient` or a `ClientRegistry`; passes registry through to each tool module's `register_tools()` | FR-003 |
| `src/dct_mcp_server/toolsgenerator/driver.py` | In embedded mode (or when `DCT_API_KEY` is absent), skip live-spec download and load bundled `docs/api-external.yaml` directly; `get_dct_config()` call guarded so missing key does not abort startup | FR-004 |

### New Files (if any)

- `src/dct_mcp_server/core/auth.py` — `AuthContext` dataclass (`account_id`, `api_key`, `auth_mode`); custom Starlette ASGI middleware (`ClientIDMiddleware`) that reads `X-CLIENT-ID` from each HTTP request scope and sets `_CALLER_ID_VAR` ContextVar; `resolve_auth() -> AuthContext` (reads ContextVar at tool-call time); raises `AuthError` on missing/invalid identity; never logs raw credentials. **Covers FR-002 and FR-006.**
- `src/dct_mcp_server/core/client_registry.py` — `ClientRegistry`: thread-safe dict keyed by identity hash; `get_client(auth_ctx: AuthContext) -> DCTAPIClient`; creates a new `DCTAPIClient` instance per unique identity; `close_all()` for clean shutdown; bounded by LRU limit (default 256) to prevent unbounded growth. **Covers FR-003.**

## Version Compatibility

This server targets the DCT API version served by the connected appliance. There is no client-side version branching in the MCP server itself — the OpenAPI spec version drives endpoint availability. The new features are transport and auth-layer changes that are independent of the DCT API version.

| Version | Supported? | Branch? | Notes |
|---------|------------|---------|-------|
| DCT API (all versions) | Yes | No | HTTP transport and auth changes are in the MCP server layer only; no DCT API version dependency |
| Python 3.11+ | Yes | No | Project baseline is 3.11+; ContextVar (3.7+) and asyncio.to_thread (3.9+) are already available, but the 3.11 floor is set by other project dependencies |
| FastMCP ≥ 2.13.2 | Yes | No | `run_http_async(transport="streamable-http")` and `get_http_request()` (from `fastmcp.server.dependencies`) both available in this range; installed version is 2.14.5 |

## Platform Behavior Notes

Key platform behaviors from `CLAUDE.md` and `architecture.md` that this feature interacts with:

- **API key prefix** (`apk ` prepended by `DCTAPIClient`): Affects — in embedded mode the `Authorization` header is not used; the client constructed via `for_identity(account_id)` must not prepend `apk ` to an account ID. The X-CLIENT-ID header is an internal DCT trust header, not an Authorization value.
- **SSL defaults to `verify=false`**: Affects — in HTTP transport mode a TLS enforcement check is added (`DCT_REQUIRE_TLS`). The existing `DCT_VERIFY_SSL` controls outbound client verification; the new flag guards the inbound HTTP listener.
- **Retries with exponential backoff**: N/A — retry logic in `DCTAPIClient.make_request` is unchanged.
- **Toolset config cache** (`@lru_cache` in `loader.py`): N/A — toolset files are unchanged; cache behavior is unchanged.
- **Telemetry off by default** (`IS_LOCAL_TELEMETRY_ENABLED`): Affects — per-caller session scoping is only active when telemetry is enabled. When disabled, the decorator's identity tagging is a no-op, preserving existing behavior.
- **Dynamic tool generation writes to `$TEMP/dct_mcp_tools/`**: Affects — in embedded mode the startup path skips the live spec download and reads the bundled `docs/api-external.yaml` instead; the generated modules still write to the same temp directory.
- **Global `dct_client` singleton in `main.py`**: Affects — in embedded mode this singleton is replaced by a `ClientRegistry`. In standalone mode the singleton is preserved. The lifespan manager's `finally` block is updated to call `client_registry.close_all()` when a registry is in use.
- **`run_streamable_http_async()` takes no middleware arguments**: Affects — the design must call `app.streamable_http_app()` directly and wrap the returned Starlette app with custom middleware before passing it to uvicorn. This is how `ClientIDMiddleware` is injected into the request pipeline to extract `X-CLIENT-ID`.

## Open Questions / Risks

- R: `resolve_auth()` reads a ContextVar that is only set when `ClientIDMiddleware` is active (HTTP embedded mode). In stdio or standalone mode the ContextVar is unset; calling `resolve_auth()` in those paths must return `None` or the standalone API key, not raise. — Mitigation: `resolve_auth()` checks `DCT_AUTH_MODE` first; unit tests cover both branches.
- R: LRU eviction of `ClientRegistry` entries will close the underlying `httpx.AsyncClient`; if an in-flight request is using that client it may see a connection error. — Mitigation: Set LRU size generously (default 256); log eviction at DEBUG. For v1 use a simple TTL dict; revisit if multi-thousand-user load is observed.
- R: Inline-secret guard (FR-007) requires heuristics to detect raw API keys in tool arguments. False positives would block legitimate requests. — Mitigation: Match specifically on `apk ` prefix and on strings > 32 chars that look like base64-encoded tokens. Provide clear error message so the user knows to use a credential reference instead.
- Q: Should credential-by-reference (FR-007) be wired to a specific DCT credential vault API, or is it sufficient to pass the alias string through to DCT unmodified in this iteration? — Owner: Shreyas Kulkarni. Current assumption: pass the alias string through; DCT resolves it server-side.
- R: TLS enforcement (`DCT_REQUIRE_TLS`) is a logged warning only in v1 — it does not terminate the server. If DCT embeds this server with `DCT_REQUIRE_TLS=false` and the operator forgets to re-enable it, secrets may be sent over plaintext. — Mitigation: Default to `true`; document the production deployment requirement clearly.
- R: `toolsgenerator/driver.py` calls `get_dct_config()` which currently raises `ValueError` if `DCT_API_KEY` is missing. In embedded mode no API key is present at startup. — Mitigation: Add a `require_key=False` parameter to `get_dct_config()`, used by the driver in embedded mode.

## Acceptance Criteria

- [ ] AC-1: Server starts and registers tools over streamable-HTTP transport when `DCT_TRANSPORT=http`; stdio remains default and unchanged when `DCT_TRANSPORT` is unset or `stdio`.
- [ ] AC-2: In embedded mode (`DCT_AUTH_MODE=embedded`), each tool invocation reads the caller's identity from the `X-CLIENT-ID` request header; two concurrent requests with different identities result in zero cross-user leakage (verified by test).
- [ ] AC-3: Tool generation runs successfully at startup in embedded mode, sourcing the bundled/appliance-local OpenAPI spec without requiring `DCT_API_KEY`.
- [ ] AC-4: A request with a missing or malformed `X-CLIENT-ID` header returns a clear auth error response; no fallback to any default identity occurs.
- [ ] AC-5: Telemetry (when enabled) is scoped per caller; each caller's session log is independent.
- [ ] AC-6: Raw API keys and account IDs are never written to `logs/dct_mcp_server.log` or session log files.
- [ ] AC-7: Tool arguments containing a string matching the raw-secret pattern (`apk ` prefix or base64-like token > 32 chars) are rejected with a descriptive error; a credential alias passes through unblocked.
- [ ] AC-8: Existing stdio + `DCT_API_KEY` single-user mode continues to work; all existing tests pass.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME/$NAME-vision.md → MUST NOT appear in Architecture Changes
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->

## Notes

**Functional spec**: The vision phase was skipped for this ticket. Functional requirements (FR-001 through FR-008) are derived directly from the eight scope items in DLPXECO-14324 and are listed below for cross-reference.

| FR | Scope item |
|----|------------|
| FR-001 | HTTP transport — `DCT_TRANSPORT=stdio\|http`; `run_http_async(transport="streamable-http")` |
| FR-002 | Embedded auth — read `X-CLIENT-ID` header per request via `fastmcp.server.dependencies.get_http_request()` |
| FR-003 | Per-request client — `ClientRegistry` keyed by identity; no cross-user leakage |
| FR-004 | Startup tool gen without user credential — bundled spec as primary source in embedded mode |
| FR-005 | Per-caller session/telemetry scoping |
| FR-006 | Auth error on missing/invalid identity; no fallback |
| FR-007 | Credential-by-reference + inline-secret guard |
| FR-008 | Secret hygiene — no logging of keys/identities; TLS required on HTTP endpoint |
