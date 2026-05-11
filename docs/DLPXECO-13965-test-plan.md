# Test Plan: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Generated from**: Acceptance criteria in `docs/DLPXECO-13965-design.md` (AC-1 through AC-19)
**Test file**: `tests/dlpxeco-13965-test.py` (single pytest module, per project convention `tests/<ticket>-test.py`)
**Framework**: `pytest` + `pytest-asyncio` + `fastmcp` stdio client (per `.claude/rules/testing.md`)

---

## Scope

This plan covers automated tests for the four bulk VDB actions added by DLPXECO-13965. All 19 acceptance criteria from `docs/DLPXECO-13965-design.md` are covered by exactly one test function each. No manual MCP-client testing is needed for code merge (the PR may still include a manual smoke-test note for reviewer reference per `.claude/rules/testing.md`).

**Important — tool name**: per the corrected design, the four bulk actions live on a NEW MCP tool named `vdb_bulk_tool` (implemented in `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py`). All bulk-action test calls use `vdb_bulk_tool(action="bulk_start", vdbIds=[...])`, NOT `vdb_tool(action="bulk_start", ...)` or `data_tool(action="bulk_start", ...)`. Single-VDB regression tests (test 16) continue to use the existing `vdb_tool` / `data_tool` to prove those tools are unchanged.

The test suite runs without a live DCT instance. Mocking is at the `DCTAPIClient.make_request` boundary — the server subprocess is real (spawned via the same `start_mcp_server_uv.sh` script the project uses in production), but the client's HTTP transport is monkey-patched to return canned responses.

## Fixtures

### `mcp_client` (module-scoped, async)

Spawns the MCP server as a subprocess with `DCT_TOOLSET=self_service` and a stubbed `DCT_API_KEY` / `DCT_BASE_URL`. Returns an open `fastmcp.Client` connected over stdio. Tears down at module end.

```python
@pytest_asyncio.fixture(scope="module")
async def mcp_client():
    env = {
        "DCT_API_KEY": "test-key-not-real",
        "DCT_BASE_URL": "http://localhost:0",   # unreachable; tests mock the HTTP layer
        "DCT_TOOLSET": "self_service",
        "DCT_BULK_CONCURRENCY": "5",
        "PYTHONPATH": "src",
    }
    params = StdioServerParameters(command="bash", args=["start_mcp_server_uv.sh"], env=env)
    async with Client(params) as client:
        yield client
```

### `mock_dct` (function-scoped, autouse for bulk tests)

Patches `dct_mcp_server.dct_client.client.DCTAPIClient.make_request` to a recorder that returns pre-programmed responses keyed by (method, path). Tracks `call_count`, per-call args, and supports per-call delays and failure injection.

```python
class MockDCT:
    def __init__(self):
        self.calls = []                     # list of {method, path, params, json}
        self.responses = {}                 # (method, path) -> {"status": int, "body": dict}
        self.delay = None                   # asyncio.sleep duration per call (for concurrency test)
        self.in_flight = 0
        self.max_in_flight = 0

    async def make_request(self, method, endpoint, params=None, json=None):
        self.calls.append({"method": method, "path": endpoint, "params": params, "json": json})
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            resp = self.responses.get((method, endpoint), {"status": 200, "body": {"jobId": f"job-{len(self.calls)}"}})
            if resp["status"] >= 500:
                raise DCTClientError(f"HTTP {resp['status']}: {resp['body']}")
            return resp["body"]
        finally:
            self.in_flight -= 1

    @property
    def call_count(self):
        return len(self.calls)
```

### `concurrency_probe` (function-scoped)

Sets `DCT_BULK_CONCURRENCY=3` in the environment and returns a primed `MockDCT` with `delay=0.05`. Used only by AC-6.

---

## Test Scenarios

All bulk-action test functions invoke the new tool: `await mcp_client.call_tool("vdb_bulk_tool", {"action": "bulk_start", "vdbIds": [...]})`.

| # | AC | Test function | What it verifies |
|---|----|---------------|------------------|
| 1 | AC-1 | `test_bulk_start_all_success` | `vdb_bulk_tool(action="bulk_start", vdbIds=[3 ids])`, all 200 → `status="success"`, `total=3`, `succeeded` has all 3, `failed=[]`, `jobs` has 3 entries with `vdbId` + `jobId`. |
| 2 | AC-2 | `test_bulk_start_partial_failure` | 3 vdbIds, 2 succeed + 1 returns 500 → `status="partial_success"`, `succeeded.length==2`, `failed.length==1`, `failed[0]["error"]` non-empty string, `jobs.length==2`. |
| 3 | AC-3 | `test_bulk_start_all_failed` | 3 vdbIds, all 500 → `status="failed"`, `succeeded==[]`, `failed.length==3`, `jobs==[]`. |
| 4 | AC-4 | `test_bulk_start_empty_list_raises` | `vdbIds=[]` → `MCPError` raised (or equivalent client-visible error); `mock_dct.call_count == 0`. |
| 5 | AC-5 | `test_bulk_start_single_element` | `vdbIds=["vdb-1"]` → `total=1`, single success entry, schema matches. |
| 6 | AC-6 | `test_bulk_start_respects_concurrency_cap` | `DCT_BULK_CONCURRENCY=3`, 20 vdbIds, each call delayed 50 ms → `mock_dct.max_in_flight <= 3` AND `mock_dct.call_count == 20`. |
| 7 | AC-7 | `test_bulk_stop_above_threshold_returns_confirmation` | `vdb_bulk_tool(action="bulk_stop", vdbIds=[6 ids])`, `confirmed` absent → response `status="confirmation_required"`, `confirmation_level="manual"`, message contains `"6"`; `mock_dct.call_count == 0`. |
| 8 | AC-8 | `test_bulk_stop_above_threshold_with_confirmed` | Same 6 vdbIds with `confirmed=True` → executes; `mock_dct.call_count == 6`; response `status` is `success` (or `partial_success` depending on mock setup — assert in `{"success", "partial_success"}`). |
| 9 | AC-9 | `test_bulk_stop_below_threshold_no_confirmation` | `vdb_bulk_tool(action="bulk_stop", vdbIds=[3 ids])`, no `confirmed` → executes immediately; `status="success"`; `mock_dct.call_count == 3`; NO `confirmation_required` envelope. |
| 10 | AC-10 | `test_bulk_disable_above_threshold_returns_confirmation` | `vdb_bulk_tool(action="bulk_disable", vdbIds=[6 ids])`, no `confirmed` → confirmation envelope; `mock_dct.call_count == 0`. |
| 11 | AC-11 | `test_bulk_enable_no_confirmation_even_at_size` | `vdb_bulk_tool(action="bulk_enable", vdbIds=[6 ids])`, no `confirmed` → executes immediately; `status="success"`; `mock_dct.call_count == 6`; no confirmation envelope. |
| 12 | AC-12 | `test_unknown_bulk_action_rejected` | `vdb_bulk_tool(action="bulk_unknown", vdbIds=["vdb-1"])` → `MCPError`-like error; `mock_dct.call_count == 0`. |
| 13 | AC-13 | `test_vdbIds_must_be_list` | `vdbIds="vdb-1"` (string) → validation error; `mock_dct.call_count == 0`. |
| 14 | AC-14 | `test_response_schema_stable` | 2 vdbIds, all succeed → `set(resp.keys()) == {"status", "total", "succeeded", "failed", "jobs"}`. |
| 15 | AC-15 | `test_logging_one_info_n_debug` | 3 vdbIds, all succeed, capture via `caplog` → exactly 1 INFO record matching `^bulk_start completed:` AND exactly 3 DEBUG records matching `^bulk_start vdb=`. No record contains the literal `DCT_API_KEY` value. |
| 16 | AC-16 | `test_single_vdb_action_unchanged` | Two assertions on the EXISTING single-VDB tools (NOT `vdb_bulk_tool`): `vdb_tool(action="start", vdbId="vdb-1")` under `self_service` and `data_tool(action="start_vdb", vdbId="vdb-1")` under `continuous_data_admin` (separate sub-tests for the two toolsets) return the same response shape as before — namely the raw DCT response (not the aggregate). Confirms that adding the new tool did NOT modify the existing single-VDB handlers. |
| 17 | AC-17 | `test_self_service_exposes_vdb_bulk_tool` | Spawn server with `DCT_TOOLSET=self_service`; call `tools/list`; assert `vdb_bulk_tool` is in the tool list AND its description/docstring advertises all four `bulk_*` action names. |
| 18 | AC-18 | `test_continuous_data_admin_exposes_vdb_bulk_tool` | Spawn server with `DCT_TOOLSET=continuous_data_admin`; assert `vdb_bulk_tool` is in the tool list AND advertises all four `bulk_*` actions. Cross-toolset symmetry: the LLM invokes the same `vdb_bulk_tool(action="bulk_start", vdbIds=[...])` regardless of which toolset is active. |
| 19 | AC-19 | `test_reporting_insights_has_no_vdb_bulk_tool` | Spawn server with `DCT_TOOLSET=reporting_insights`; assert `vdb_bulk_tool` is NOT in the tool list at all. (Stronger than the prior plan's per-action check — the whole tool is absent in this toolset.) |

## Per-test mocking detail

### Success path (tests 1, 5, 6, 11, 14, 15, 16, 17–19)

`mock_dct.responses` is left at its default (returns `{"jobId": f"job-{n}"}` with status 200 for every call).

### Partial failure (test 2)

```python
mock_dct.responses = {
    ("POST", "/vdbs/vdb-1/start"): {"status": 200, "body": {"jobId": "job-1"}},
    ("POST", "/vdbs/vdb-2/start"): {"status": 200, "body": {"jobId": "job-2"}},
    ("POST", "/vdbs/vdb-3/start"): {"status": 500, "body": {"error": "internal"}},
}
```

The path used by the bulk handler is the existing per-VDB endpoint `/vdbs/{vdbId}/start`. The bulk wrapper does NOT call `/vdbs/bulk_start` — that path is sentinel-only in the toolset `.txt` file (see design's "Generator-vs-pre-built decision").

### All failed (test 3)

All three vdb paths return status 500.

### Concurrency cap (test 6)

`DCT_BULK_CONCURRENCY=3`. `mock_dct.delay = 0.05`. 20 vdbIds. After `gather` returns, assert `mock_dct.max_in_flight <= 3` and `mock_dct.call_count == 20`. The `delay` ensures tasks overlap; without it the test would be racy.

### Confirmation envelope (tests 7, 8, 10)

For test 7 (no `confirmed`): expect the response dict to have key `status="confirmation_required"`. No mock setup needed beyond default — the gate fires before any DCT call. Assert `mock_dct.call_count == 0` after the call returns.

For test 8 (with `confirmed=True`): pass `confirmed=True` in the tool call kwargs. Mock returns 200 for all 6 paths. Assert `mock_dct.call_count == 6`.

## Toolset visibility tests (17, 18, 19)

These require a fresh server subprocess per test, because `DCT_TOOLSET` is read at server startup. Implementation pattern:

```python
@pytest.mark.asyncio
async def test_self_service_exposes_vdb_bulk_tool():
    async with _spawn_server({"DCT_TOOLSET": "self_service"}) as client:
        tools = await client.list_tools()
        bulk_tool = next((t for t in tools if t.name == "vdb_bulk_tool"), None)
        assert bulk_tool is not None, "vdb_bulk_tool missing from self_service"
        for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
            assert action in bulk_tool.description, f"{action} missing from vdb_bulk_tool docstring"

@pytest.mark.asyncio
async def test_reporting_insights_has_no_vdb_bulk_tool():
    async with _spawn_server({"DCT_TOOLSET": "reporting_insights"}) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "vdb_bulk_tool" not in names
```

The action names appear in the tool's docstring (the new module's `vdb_bulk_tool` function's docstring lists "Available actions: bulk_start, bulk_stop, bulk_enable, bulk_disable" in the same format as other pre-built tools). Asserting on the docstring is the stable way to discover available actions from outside the server.

## Logging assertions (test 15)

```python
@pytest.mark.asyncio
async def test_logging_one_info_n_debug(caplog, mcp_client, mock_dct):
    caplog.set_level(logging.DEBUG, logger="dct_mcp_server.tools.vdb_bulk_endpoints_tool")
    await mcp_client.call_tool("vdb_bulk_tool", {"action": "bulk_start", "vdbIds": ["vdb-1", "vdb-2", "vdb-3"]})
    info_records = [r for r in caplog.records if r.levelname == "INFO" and r.message.startswith("bulk_start completed")]
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG" and "bulk_start vdb=" in r.message]
    assert len(info_records) == 1
    assert len(debug_records) == 3
    # No raw API key in any record
    for r in caplog.records:
        assert "test-key-not-real" not in r.getMessage(), "API key leaked into logs"
```

Note: because the server runs in a subprocess, `caplog` cannot capture its logs directly. In practice the test will either:
(a) Run the bulk action handler in-process by importing `vdb_bulk_endpoints_tool` and calling its function with a mock client; or
(b) Tail the server's log file (`logs/dct_mcp_server.log`) after the call returns.

Option (a) is preferred because it is faster and more deterministic; option (b) is the fallback if FastMCP's plumbing prevents direct invocation of decorated tools. Implementation phase picks the path; both are acceptable for AC-15.

## Edge case tests (beyond the AC table)

These supplement the ACs and are tracked separately so they can be expanded post-merge without breaking the AC traceability:

- `test_bulk_stop_exactly_5_executes_no_confirmation` — boundary check on `> 5` vs `>= 5` (vision EC-6).
- `test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5` — invalid env var handling (ERR-5).
- `test_async_timeout_on_one_vdb_does_not_abort_batch` — `asyncio.TimeoutError` injected via `mock_dct` for one vdbId; other VDBs still complete (EC-12).

## Versions covered

| Toolset | Tested via | DCT version |
|---|---|---|
| `self_service` | Server subprocess in test 17 + in-process for tests 1–16 | Mocked — no live DCT |
| `continuous_data_admin` | Server subprocess in test 18 | Mocked — no live DCT |
| `reporting_insights` | Server subprocess in test 19 | Mocked — no live DCT |
| `self_service_provision` | Implicit via inheritance from `self_service` (not separately tested in this ticket — follow-up if FR-006 expands) | Mocked |
| `platform_admin` | Not tested (no VDB tool in this toolset) | n/a |
| `auto` | Not tested (out of scope per design Open Question #1) | n/a |

## Coverage gate

After the suite runs, `pytest --cov=src/dct_mcp_server/tools/vdb_bulk_endpoints_tool --cov-report=term-missing` must show coverage of the new module (the `_bulk_fanout` helper, the validation helpers, and the four `bulk_*` dispatch branches) at ≥ 90%. Existing files (`dataset_endpoints_tool.py`, `tools/__init__.py`, etc.) are not modified by this ticket; their coverage is unchanged.

## Test commands

```bash
# Install (one-time, on a fresh checkout)
pip install -r requirements.txt
pip install -e .
pip install pytest pytest-asyncio

# Full run
pytest tests/dlpxeco-13965-test.py -v

# Single AC during implementation
pytest tests/dlpxeco-13965-test.py::test_bulk_start_all_success -v

# With coverage on the new module
pytest tests/dlpxeco-13965-test.py --cov=src/dct_mcp_server/tools/vdb_bulk_endpoints_tool --cov-report=term-missing
```

---

## Live-DCT smoke test (validate phase)

The pytest suite above is mock-only and runs during the `test` phase. To satisfy `.claude/rules/testing.md` ("Test by running the server locally and connecting a real MCP client … against a live DCT instance") and to populate the PR description's required "MCP client / toolset / DCT version" evidence, the `validate` phase runs a live-DCT smoke test against a real Delphix DCT instance using credentials from `.claude/settings.local.json` (`mcpServers.dct.env.DCT_API_KEY` and `DCT_BASE_URL`).

### Approach

Spawn the **feature-branch** MCP server (from the worktree at `/Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965`) as a subprocess with real credentials, then drive it from a small script that mirrors the pytest fixture pattern but with no `MockDCT` patch. Do not rely on the already-loaded `mcp__delphix-dct__*` tools in the parent Claude session — those point to whatever pre-feature build is currently registered with the harness and do NOT have `vdb_bulk_tool`.

### Pre-flight checks

1. Read `DCT_API_KEY` and `DCT_BASE_URL` from `.claude/settings.local.json` — abort with a clear error if either is missing.
2. Confirm `start_mcp_server_uv.sh` is executable in the worktree.
3. Run a read-only sanity call first (`vdb_tool(action="search", limit=1)`) and confirm the server returns a non-error response before any write operation.

### Smoke scenarios

Each scenario picks **at most 2 real VDBs** from the live DCT and exercises one bulk action. Test VDBs are discovered dynamically — no hardcoded IDs. After each destructive action, the script restores state (e.g. `bulk_disable` → `bulk_enable`) so the smoke is idempotent.

| # | Scenario | What it proves |
|---|----------|----------------|
| S1 | `vdb_bulk_tool(action="bulk_start", vdbIds=[2 real ids])` against `DCT_TOOLSET=self_service` | Real DCT accepts the per-VDB `/vdbs/{id}/start` shape the bulk handler emits; jobs return real `jobId` values. |
| S2 | `vdb_bulk_tool(action="bulk_stop", vdbIds=[2 real ids])` (no `confirmed`) → expect confirmation envelope | Confirmation rule fires against live DCT path resolution. Re-call with `confirmed=True` to actually stop. |
| S3 | `vdb_bulk_tool(action="bulk_enable", vdbIds=[2 real ids])` against `DCT_TOOLSET=continuous_data_admin` | Tool is exposed under CDA, real DCT enable endpoint accepts the fan-out, AC-18 cross-toolset symmetry holds in production. |
| S4 | `vdb_bulk_tool(action="bulk_disable", vdbIds=[6 real ids])` (no `confirmed`) — only if 6+ test VDBs are available | Confirmation threshold check fires under realistic VDB counts. Skip with a logged note if the live DCT has fewer than 6 test VDBs. |
| S5 | `vdb_bulk_tool(action="bulk_start", vdbIds=[1 already-running id, 1 stopped id])` | Partial-success path with real DCT — running VDB returns a known error code; stopped VDB starts. Asserts `status="partial_success"` and that the error message from DCT is preserved in the `failed[].error` field. |

### Evidence captured for the PR

The script writes to `docs/DLPXECO-13965-smoke-results.md` (gitignored by default — explicit copy into the PR description by hand). Each scenario block records:
- Timestamp, DCT base URL (redacted to host only), toolset, VDB IDs used (anonymized as `vdb-A`, `vdb-B`)
- Raw JSON request and response
- Pass/fail verdict against the design's success criteria
- DCT version (from `GET /management/license` or `/about` — whichever the live build exposes)

These four pieces are exactly what `.claude/rules/testing.md` requires PR descriptions to include.

### Out of scope for smoke

- The pytest concurrency-cap test (AC-6) does NOT need a live counterpart — proving `asyncio.Semaphore` works once in mocks is sufficient; doing it against real DCT just wastes job slots.
- Auto-mode (`tool_factory.py`) bulk support remains descoped (design Open Question #1) — no live smoke for auto.
- `reporting_insights` exclusion (AC-19) is already proven by the pytest startup check; no live smoke needed.

---

<!-- Coverage matrix: each AC has exactly one row in the Test Scenarios table.
     Additional edge case tests are listed separately and do not back AC closure.
     All bulk-action tests target the NEW vdb_bulk_tool MCP tool. Single-VDB regression (test 16)
     uses the existing vdb_tool / data_tool to prove the existing tools are untouched.
     Live-DCT smoke runs in the `validate` phase against the feature-branch server with real credentials
     from .claude/settings.local.json — see "Live-DCT smoke test (validate phase)" above. -->


## Driver fix validation (bundled out-of-scope fix; see design doc)

The bundled fix to `src/dct_mcp_server/toolsgenerator/driver.py` (smart-deletion cleanup sweep, Option D) is validated by three independent checks:

1. **Syntax / import check.** `python -c "import py_compile; py_compile.compile('src/dct_mcp_server/toolsgenerator/driver.py', doraise=True)"` returns 0 with no output. Confirms the modified module is importable; catches any obvious refactor mistakes (typos, broken indentation, missing imports).

2. **Mock pytest suite re-run.** `uv run pytest tests/dlpxeco-13965-test.py -v` produces 22 PASS / 0 FAIL — identical to the outcome of the prior `test` phase (the mock suite is independent of the live filesystem cleanup behaviour; this is a regression check against the rest of the bulk-tool implementation, confirming the driver fix did not perturb any in-process module-loading path).

3. **Live-DCT smoke harness (this validate phase re-run).** The S1–S5 scenarios in "Live-DCT smoke test (validate phase)" above now exercise the corrected startup behaviour end-to-end. Each scenario starts the server via `bash start_mcp_server_uv.sh` from the worktree, which invokes `generate_tools_from_openapi()` against the live spec; with the fix in place, `vdb_bulk_endpoints_tool.py` is preserved on disk and `register_all_tools()` finds it. Confirmation that `tools/list` contains `vdb_bulk_tool` is the necessary pre-condition for any S1–S5 scenario to pass; this is captured implicitly by the pre-flight phase of every scenario.

No mocked "preserved file" assertion is added to the unit suite (`tests/dlpxeco-13965-test.py`) because the cleanup sweep runs at server-process startup before the in-process pytest fixture sees anything — a process-boundary test (which is what the live-smoke harness is) is the natural place to verify this behaviour. A future unit test could mock `glob.glob` + `os.remove` and call `generate_tools_from_openapi()` directly, but that level of coverage is overkill for a defect whose end-to-end signal is already strong.
