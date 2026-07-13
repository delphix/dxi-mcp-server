# Test Plan: DLPXECO-14324

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14324
**Derived from**: `docs/DLPXECO-14324/DLPXECO-14324-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase. -->

---

## Test Approach

Two complementary tracks per `.claude/test/testing.md`:

1. **Automated pytest regression** (`tests/DLPXECO-14324-test.py`) — spawns the server as a subprocess via `fastmcp.Client` using `StdioServerParameters`, and for HTTP tests via an HTTP client connecting to the server running with `DCT_TRANSPORT=http`. Assertions are deterministic and CI-runnable.
2. **Scenario execution** (Claude drives MCP tools directly) — used for end-to-end validation against a live DCT instance where credentials are available in `.claude/settings.local.json`.

Runner: `pytest tests/DLPXECO-14324-test.py -v` (Track 2: against a live DCT once credentials are present).

## Environment / Landscape

- Landscape: Local development environment; no dedicated integration VM required for unit/pytest track.
- Service under test: `dct-mcp-server` binary (local clone, launched via `start_mcp_server_uv.sh` or `start_mcp_server_python.sh`).
- HTTP transport tests: server launched with `DCT_TRANSPORT=http DCT_AUTH_MODE=embedded` and `DCT_API_KEY` absent.
- Stdio transport tests: server launched with default env (no `DCT_TRANSPORT`, `DCT_API_KEY` set to test value).
- No VMs required (see `.claude/test/test-infra.md` for credential setup if live DCT is needed).

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Project baseline | Yes |
| FastMCP ≥ 2.13.2 (installed: 2.14.5) | `run_streamable_http_async()` and ContextVar middleware | Yes |
| DCT API (any version) | Transport/auth changes are MCP-layer only | No (smoke only if live DCT available) |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | Server starts successfully with `DCT_TRANSPORT=stdio` (default); registers tools; no HTTP port opened | FR-001 | Python 3.11, FastMCP 2.14+ | Server process starts, MCP tools respond over stdio, `netstat` shows no bound HTTP port |
| S2 | Server starts successfully with `DCT_TRANSPORT=http DCT_AUTH_MODE=embedded` (no `DCT_API_KEY`); binds to configured port | FR-001, FR-002 | Python 3.11, FastMCP 2.14+ | Server process starts, HTTP endpoint responds at `http://127.0.0.1:<DCT_HTTP_PORT>/` |
| S3 | HTTP request with valid `X-CLIENT-ID: user-abc` header causes tool execution to use identity `user-abc` | FR-002, FR-003 | Python 3.11, FastMCP 2.14+ | Tool response reflects correct identity; server log contains masked identity, not raw value |
| S4 | Two concurrent HTTP requests with different `X-CLIENT-ID` values use independent DCT clients — response from request A does not contain data belonging to identity B | FR-003 | Python 3.11, FastMCP 2.14+ | Concurrent requests each return data scoped to their identity; cross-user leakage = zero |
| S5 | HTTP request with missing `X-CLIENT-ID` header returns `AuthError` response with descriptive message | FR-006 | Python 3.11, FastMCP 2.14+ | Response body contains `auth_error` or equivalent error field; no tool execution occurs |
| S6 | HTTP request with empty `X-CLIENT-ID` header (`X-CLIENT-ID: `) returns `AuthError` | FR-006 | Python 3.11, FastMCP 2.14+ | Same as S5 |
| S7 | Tool generation runs at startup when `DCT_AUTH_MODE=embedded` (no `DCT_API_KEY`); bundled spec is used | FR-004 | Python 3.11, FastMCP 2.14+ | Startup succeeds; log contains "using bundled spec" or equivalent; tool list is non-empty |
| S8 | Tool execution in embedded mode logs telemetry with `caller_id` tag when `IS_LOCAL_TELEMETRY_ENABLED=true` | FR-005 | Python 3.11, FastMCP 2.14+ | Session log file for the caller ID exists; log entry contains the expected caller ID |
| S9 | Two concurrent callers each have isolated session log files (no shared entries) | FR-005 | Python 3.11, FastMCP 2.14+ | `logs/sessions/<id-a>.log` contains only identity-A entries; `logs/sessions/<id-b>.log` contains only identity-B entries |
| S10 | Tool argument containing `apk <token>` (raw API key prefix) is rejected by inline-secret guard | FR-007 | Python 3.11, FastMCP 2.14+ | Response body contains a `secret_guard_violation` or equivalent error field; the raw key is not echoed back |
| S11 | Tool argument containing a credential alias string (not matching secret pattern) passes through unblocked | FR-007 | Python 3.11, FastMCP 2.14+ | Tool executes normally; no secret guard error raised |
| S12 | Server logs never contain the raw `DCT_API_KEY` value or any `X-CLIENT-ID` value in plaintext | FR-008 | Python 3.11, FastMCP 2.14+ | `grep <actual_key>` over `logs/dct_mcp_server.log` returns zero matches after multiple tool calls |
| S13 | Server started with `DCT_TRANSPORT=http DCT_REQUIRE_TLS=false` emits a warning log at startup | FR-008 | Python 3.11, FastMCP 2.14+ | Log contains "TLS" and "warning" (case-insensitive) within startup output |
| S14 | Existing stdio single-user mode (`DCT_API_KEY` set, no `DCT_TRANSPORT`) still works end-to-end — a tool call succeeds | FR-001, backward compat AC-8 | Python 3.11, FastMCP 2.14+ | Tool response is non-error; server starts without modification to existing env var setup |
| S15 | All existing pytest tests in `tests/` pass without modification after this change | FR-001 (backward compat) | Python 3.11, FastMCP 2.14+ | `pytest tests/ -v` returns exit code 0, no existing test is broken |

## Out of Scope

- Load testing with >256 concurrent identities (LRU eviction behaviour is a non-goal for v1; tracked as an Open Question in the design doc).
- Encrypted credential vault integration (handled DCT-side; see DLPXECO-14322 notes).
- OAuth/OIDC token flows — the embedded auth contract uses `X-CLIENT-ID` (internal trust header), not Bearer tokens.
- TLS termination setup (the server itself does not terminate TLS; the embedding reverse-proxy does).
- Live DCT API response correctness — these tests mock or use bundled spec responses; correctness against a live DCT is covered by the existing scenario files in `.claude/test/testing/`.

## Test Data Requirements

- No live DCT credentials required for pytest track (Track 1) — the server is started with a mock API key (`DCT_API_KEY=test-key`); actual DCT calls can be intercepted with `pytest-mock` or `respx` (httpx mock).
- For Track 2 (scenario execution against live DCT): `DCT_API_KEY` and `DCT_BASE_URL` must be set in `.claude/settings.local.json` under `mcpServers.dct.env` (see `.claude/test/test-infra.md`).
- Test fixture: two synthetic `X-CLIENT-ID` values (`user-alice`, `user-bob`) used for cross-user leakage test (S4, S9).
- Bundled spec (`docs/api-external.yaml`) must exist in the worktree for S7 — verify before running.

## Exit Criteria

- All Required scenarios (S1–S15) PASS on Python 3.11 + FastMCP ≥ 2.13.2.
- S4 (cross-user leakage) must PASS with zero leaked entries — this is the safety-critical scenario.
- No scenario marked SKIPPED without a documented reason in the test run output.
- Smoke suite (`pytest tests/ -v` excluding DLPXECO-14324-test.py) PASSes — no regressions in existing tests.
- `grep <DCT_API_KEY_value> logs/dct_mcp_server.log` returns 0 results after S12.

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-14324.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-14324/DLPXECO-14324-functional.md → at least one scenario here
     - Versions column → must be a subset of docs/DLPXECO-14324/DLPXECO-14324-design.md ## Version Compatibility "Supported = Yes"
     Note: functional.md was not generated (vision phase skipped); FRs are defined in the design doc Notes section. -->
