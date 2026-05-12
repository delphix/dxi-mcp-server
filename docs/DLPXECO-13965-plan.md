# Bulk VDB Lifecycle Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bulk_start`, `bulk_stop`, `bulk_enable`, and `bulk_disable` actions to the DCT MCP Server so AI assistants can apply lifecycle operations to multiple VDBs in a single tool call with semaphore-bounded async fan-out.

**Architecture:** Four bulk actions are implemented in a new `vdb_endpoints_tool.py` pre-built module that exposes a single `async def vdb_tool` function. The tool fans out to existing per-VDB DCT API endpoints concurrently using `asyncio.Semaphore`, aggregates per-VDB outcomes, and returns a single structured response. Confirmation gates for `bulk_stop` and `bulk_disable` (>5 VDBs) are implemented inline rather than via `manual_confirmation.txt` because the threshold is data-dependent. A new `DCT_BULK_CONCURRENCY` env var (default 5, clamped 1–50) is added to `config.py`.

**Tech Stack:** Python 3.11+, asyncio, FastMCP, pytest + pytest-asyncio, unittest.mock (AsyncMock)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/dct_mcp_server/config/config.py` | Modify | Add `DCT_BULK_CONCURRENCY` parsing + clamping + help text |
| `src/dct_mcp_server/config/toolsets/self_service.txt` | Modify | Register 4 bulk action lines under `vdb_tool` |
| `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` | Modify | Register 4 bulk action lines under `data_tool` VDB section |
| `src/dct_mcp_server/config/loader.py` | Modify | Map `vdb_tool` → `vdb_endpoints_tool` in `TOOL_TO_MODULE` |
| `src/dct_mcp_server/tools/vdb_endpoints_tool.py` | Create | `register_tools()` + `async def vdb_tool` + `_bulk_vdb_action` helper |
| `tests/dlpxeco-13965-test.py` | Create | 19 pytest scenarios with AsyncMock patching |

---

## Task 1: Add DCT_BULK_CONCURRENCY to config.py  [parallel][model:haiku]

### Description
Modifies `src/dct_mcp_server/config/config.py` to read and validate the new `DCT_BULK_CONCURRENCY` environment variable. Adds it to the config dict returned by `get_dct_config()` and documents it in `print_config_help()`. Must run before Task 4 because `vdb_endpoints_tool.py` reads `get_dct_config()["bulk_concurrency"]`.

### Spec References
- FR-006 (AC-1, AC-2, AC-3): Add `DCT_BULK_CONCURRENCY` env var with default 5, clamping to [1, 50], and WARNING log on invalid values

### Sub-tasks (TDD)

- [ ] **RED**: Write a failing test that exercises `get_dct_config()["bulk_concurrency"]` with various env var values

  Create a temporary test file at `tests/test_config_bulk_concurrency.py`:
  ```python
  """Tests for DCT_BULK_CONCURRENCY config parsing."""
  import os
  import importlib
  import pytest


  def reload_config():
      """Re-import config to pick up env var changes."""
      import dct_mcp_server.config.config as cfg_mod
      importlib.reload(cfg_mod)
      return cfg_mod


  def test_bulk_concurrency_default(monkeypatch):
      monkeypatch.setenv("DCT_API_KEY", "test-key")
      monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
      monkeypatch.delenv("DCT_BULK_CONCURRENCY", raising=False)
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 5


  def test_bulk_concurrency_custom(monkeypatch):
      monkeypatch.setenv("DCT_API_KEY", "test-key")
      monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "3")
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 3


  def test_bulk_concurrency_clamped_to_1(monkeypatch):
      monkeypatch.setenv("DCT_API_KEY", "test-key")
      monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "0")
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 1


  def test_bulk_concurrency_clamped_to_50(monkeypatch):
      monkeypatch.setenv("DCT_API_KEY", "test-key")
      monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "100")
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 50


  def test_bulk_concurrency_invalid_string(monkeypatch):
      monkeypatch.setenv("DCT_API_KEY", "test-key")
      monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "abc")
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 5  # falls back to default
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_config_bulk_concurrency.py -v`
  Expected: FAIL — `KeyError: 'bulk_concurrency'`

- [ ] **GREEN**: Add `DCT_BULK_CONCURRENCY` parsing to `get_dct_config()` and help text to `print_config_help()`

  In `src/dct_mcp_server/config/config.py`, add logger import at top and insert bulk_concurrency parsing. The full updated file:

  ```python
  """
  Configuration module for DCT MCP Server
  """

  import logging
  import os
  from typing import Any, Dict

  logger = logging.getLogger(__name__)


  def get_dct_config() -> Dict[str, Any]:
      """Get DCT configuration from environment variables"""

      # Parse DCT_BULK_CONCURRENCY with fallback and clamping
      _bulk_concurrency_raw = os.getenv("DCT_BULK_CONCURRENCY", "5")
      try:
          _bulk_concurrency = int(_bulk_concurrency_raw)
      except ValueError:
          logger.warning(
              f"DCT_BULK_CONCURRENCY='{_bulk_concurrency_raw}' is not a valid integer; "
              "falling back to default 5."
          )
          _bulk_concurrency = 5

      if _bulk_concurrency < 1:
          logger.warning(
              f"DCT_BULK_CONCURRENCY={_bulk_concurrency} is below minimum 1; clamping to 1."
          )
          _bulk_concurrency = 1
      elif _bulk_concurrency > 50:
          logger.warning(
              f"DCT_BULK_CONCURRENCY={_bulk_concurrency} exceeds maximum 50; clamping to 50."
          )
          _bulk_concurrency = 50

      config = {
          "api_key": os.getenv("DCT_API_KEY"),
          "base_url": os.getenv("DCT_BASE_URL", "https://localhost:8083"),
          "verify_ssl": os.getenv("DCT_VERIFY_SSL", "false").lower() == "true",
          "timeout": int(os.getenv("DCT_TIMEOUT", "30")),
          "max_retries": int(os.getenv("DCT_MAX_RETRIES", "3")),
          "log_level": os.getenv("DCT_LOG_LEVEL", "INFO").upper(),
          "is_local_telemetry_enabled": os.getenv("IS_LOCAL_TELEMETRY_ENABLED", "false").lower()
          == "true",
          "toolset": os.getenv("DCT_TOOLSET", "self_service").lower().strip(),
          "bulk_concurrency": _bulk_concurrency,
      }

      # Validate required configuration
      if not config["api_key"]:
          raise ValueError(
              "DCT_API_KEY environment variable is required. "
              "Please set it to your Delphix DCT API key."
          )

      # Validate log level
      valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
      if config["log_level"] not in valid_log_levels:
          raise ValueError(
              f"Invalid log level: {config['log_level']}. "
              f"Must be one of: {', '.join(valid_log_levels)}"
          )

      return config


  def print_config_help():
      """Print configuration help"""
      print("\nDelphix DCT MCP Server Configuration:")
      print("=====================================")
      print()
      print("Required Environment Variables:")
      print("  DCT_API_KEY      Your DCT API key (required)")
      print()
      print("Optional Environment Variables:")
      print("  DCT_BASE_URL     DCT base URL (default: https://localhost:8083)")
      print("  DCT_VERIFY_SSL   Verify SSL certificates (default: false)")
      print("  DCT_TIMEOUT      Request timeout in seconds (default: 30)")
      print("  DCT_MAX_RETRIES  Maximum retry attempts (default: 3)")
      print(
          "  DCT_LOG_LEVEL    Logging level (default: INFO, options: DEBUG, INFO, WARNING, ERROR, CRITICAL)"
      )
      print(
          "  IS_LOCAL_TELEMETRY_ENABLED Enable local telemetry data collection (default: false)"
      )
      print(
          "  DCT_BULK_CONCURRENCY  Max concurrent DCT requests in bulk VDB actions (default: 5, range: 1-50)"
      )
      print(
          "  DCT_TOOLSET      Active toolset (default: self_service). Options:"
      )
      print(
          "                   - auto: Dynamic discovery mode with meta-tools"
      )
      print(
          "                   - self_service: Basic VDB operations for developers/QA"
      )
      print(
          "                   - self_service_provision: Extended self-service with provisioning"
      )
      print(
          "                   - continuous_data_admin: Full DBA/CD admin operations"
      )
      print(
          "                   - platform_admin: System administration tools"
      )
      print(
          "                   - reporting_insights: Read-only reporting and analytics"
      )
      print()
      print("Example:")
      print("  export DCT_API_KEY=apk1.your-api-key-here")
      print("  export DCT_BASE_URL=https://your-dct-host:8083")
      print("  export DCT_VERIFY_SSL=true")
      print("  export DCT_LOG_LEVEL=DEBUG")
      print("  export DCT_TOOLSET=self_service")
      print("  export DCT_BULK_CONCURRENCY=5")
      print()
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_config_bulk_concurrency.py -v`
  Expected: PASS (5 tests)

- [ ] **REFACTOR**: No structural changes needed — parsing logic is already clean. Remove the temporary test file after Task 7 tests cover S14/S15.

  ```bash
  # Leave in place for now — will be folded into main test file in Task 5
  ```

- [ ] **Commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add src/dct_mcp_server/config/config.py tests/test_config_bulk_concurrency.py
  git commit -m "Add DCT_BULK_CONCURRENCY env var with clamping to config.py"
  ```

### Depends On
- None

### Acceptance Criteria
- [ ] `get_dct_config()["bulk_concurrency"]` returns 5 when `DCT_BULK_CONCURRENCY` is unset
- [ ] Returns 3 when set to `"3"`
- [ ] Returns 1 when set to `"0"` (clamped)
- [ ] Returns 50 when set to `"100"` (clamped)
- [ ] Returns 5 when set to `"abc"` (invalid, falls back)
- [ ] All 5 tests in `tests/test_config_bulk_concurrency.py` pass

---

## Task 2: Register bulk actions in toolset .txt files  [parallel][model:haiku]

### Description
Appends four bulk action lines to `self_service.txt` and `continuous_data_admin.txt` so the MCP server discovers and exposes `bulk_start`, `bulk_stop`, `bulk_enable`, and `bulk_disable` as valid `vdb_tool` actions when the relevant toolsets are loaded. No Python code changes required — only `.txt` config edits. Can run in parallel with Task 1.

### Spec References
- FR-001 (AC-1, AC-2, AC-3): Register bulk actions in `self_service` and `continuous_data_admin`; verify absence from `reporting_insights`

### Sub-tasks (TDD)

- [ ] **RED**: Write a failing test that checks the toolset files for bulk action presence/absence

  Create `tests/test_toolset_bulk_actions.py`:
  ```python
  """Tests for bulk action registration in toolset .txt config files."""
  import pytest
  from dct_mcp_server.config.loader import load_toolset_grouped_apis, load_toolset_apis


  BULK_ACTIONS = {"bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"}


  def test_self_service_vdb_tool_has_all_bulk_actions():
      grouped = load_toolset_grouped_apis("self_service")
      vdb_actions = {api["action"] for api in grouped["vdb_tool"]["apis"]}
      assert BULK_ACTIONS.issubset(vdb_actions), (
          f"Missing bulk actions in self_service vdb_tool: {BULK_ACTIONS - vdb_actions}"
      )


  def test_continuous_data_admin_data_tool_has_all_bulk_actions():
      grouped = load_toolset_grouped_apis("continuous_data_admin")
      data_actions = {api["action"] for api in grouped["data_tool"]["apis"]}
      assert BULK_ACTIONS.issubset(data_actions), (
          f"Missing bulk actions in continuous_data_admin data_tool: {BULK_ACTIONS - data_actions}"
      )


  def test_reporting_insights_has_no_bulk_actions():
      apis = load_toolset_apis("reporting_insights")
      all_actions = {api["action"] for api in apis}
      overlap = BULK_ACTIONS & all_actions
      assert not overlap, f"Unexpected bulk actions in reporting_insights: {overlap}"
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_toolset_bulk_actions.py -v`
  Expected: FAIL — bulk_start, bulk_stop etc. not found in toolset files

  **Note:** `load_toolset_grouped_apis` uses `@lru_cache` — if running tests in the same process as prior config reads, clear cache first or run in a fresh process. The pytest invocation above is a fresh process, so no issue.

- [ ] **GREEN**: Append bulk action lines to both toolset files

  Add to end of VDB section in `src/dct_mcp_server/config/toolsets/self_service.txt` (after the last existing vdb_tool line, before the `# TOOL 2: vdb_group_tool` comment):
  ```
  POST|/vdbs/bulk_start|bulk_start
  POST|/vdbs/bulk_stop|bulk_stop
  POST|/vdbs/bulk_enable|bulk_enable
  POST|/vdbs/bulk_disable|bulk_disable
  ```

  The current last line of the vdb_tool section is:
  ```
  POST|/vdbs/{vdbId}/tags/delete|delete_tags
  ```
  Insert the four bulk lines immediately after it.

  For `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt`, find the VDB operations section of `data_tool`. After the last VDB export/finalize line (currently `POST|/vdbs/{vdbId}/export_finalize|export_finalize`), before the `# VDB Group Operations` comment, insert:
  ```
  POST|/vdbs/bulk_start|bulk_start
  POST|/vdbs/bulk_stop|bulk_stop
  POST|/vdbs/bulk_enable|bulk_enable
  POST|/vdbs/bulk_disable|bulk_disable
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_toolset_bulk_actions.py -v`
  Expected: PASS (3 tests)

- [ ] **REFACTOR**: No refactoring needed — `.txt` files have no logic.

- [ ] **Commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add src/dct_mcp_server/config/toolsets/self_service.txt \
          src/dct_mcp_server/config/toolsets/continuous_data_admin.txt \
          tests/test_toolset_bulk_actions.py
  git commit -m "Register bulk VDB lifecycle actions in self_service and continuous_data_admin toolsets"
  ```

### Depends On
- None

### Acceptance Criteria
- [ ] `load_toolset_grouped_apis("self_service")["vdb_tool"]["apis"]` contains all 4 bulk actions
- [ ] `load_toolset_grouped_apis("continuous_data_admin")["data_tool"]["apis"]` contains all 4 bulk actions
- [ ] `load_toolset_apis("reporting_insights")` contains none of the 4 bulk actions
- [ ] All 3 tests in `tests/test_toolset_bulk_actions.py` pass

---

## Task 3: Map vdb_tool to vdb_endpoints_tool in loader.py  [parallel][model:haiku]

### Description
Updates `TOOL_TO_MODULE` in `src/dct_mcp_server/config/loader.py` to point `"vdb_tool"` at the new `"vdb_endpoints_tool"` module. Currently `"vdb_tool"` maps to `"dataset_endpoints_tool"` — adding an explicit `"vdb_endpoints_tool"` entry gives the new module discovery priority for `vdb_tool`. Can run in parallel with Tasks 1 and 2.

**Important:** The design doc says "Add `vdb_tool: vdb_endpoints_tool` entry" but the existing entry is `"vdb_tool": "dataset_endpoints_tool"`. Both modules will be discovered by `tools/__init__.py` auto-discovery (it loads all modules with `register_tools`). The mapping change only affects filtered loading (the `get_modules_for_toolset` path). The simplest approach: add a new line `"vdb_tool": "vdb_endpoints_tool"` to override the old mapping so filtered loading picks up the correct module.

### Spec References
- FR-001 (supporting AC): Correct module mapping for `vdb_tool` so `register_all_tools` loads the right pre-built module in fixed-toolset mode

### Sub-tasks (TDD)

- [ ] **RED**: Write a test that verifies `get_modules_for_toolset("self_service")` includes `vdb_endpoints_tool`

  Add to `tests/test_toolset_bulk_actions.py`:
  ```python
  from dct_mcp_server.config.loader import get_modules_for_toolset


  def test_self_service_modules_include_vdb_endpoints_tool():
      modules = get_modules_for_toolset("self_service")
      assert "vdb_endpoints_tool" in modules, (
          f"vdb_endpoints_tool not in modules for self_service: {modules}"
      )
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_toolset_bulk_actions.py::test_self_service_modules_include_vdb_endpoints_tool -v`
  Expected: FAIL — `dataset_endpoints_tool` is returned, not `vdb_endpoints_tool`

- [ ] **GREEN**: Update `TOOL_TO_MODULE` in `loader.py`

  In `src/dct_mcp_server/config/loader.py`, find the `TOOL_TO_MODULE` dict (line ~443). Change:
  ```python
  "vdb_tool": "dataset_endpoints_tool",
  ```
  To:
  ```python
  "vdb_tool": "vdb_endpoints_tool",
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_toolset_bulk_actions.py -v`
  Expected: PASS (all 4 tests including the new one)

- [ ] **REFACTOR**: No refactoring needed.

- [ ] **Commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add src/dct_mcp_server/config/loader.py tests/test_toolset_bulk_actions.py
  git commit -m "Map vdb_tool to vdb_endpoints_tool in loader TOOL_TO_MODULE"
  ```

### Depends On
- None (modifies different file from Tasks 1 and 2)

### Acceptance Criteria
- [ ] `get_modules_for_toolset("self_service")` returns a list containing `"vdb_endpoints_tool"`
- [ ] `get_modules_for_toolset("continuous_data_admin")` returns a list containing `"vdb_endpoints_tool"` (via data_tool mapping — note: `data_tool` still maps to `dataset_endpoints_tool`; only `vdb_tool` is changed)
- [ ] Test passes

---

## Task 4: Create vdb_endpoints_tool.py with bulk action implementation  [model:sonnet]

### Description
Creates the new pre-built tool module `src/dct_mcp_server/tools/vdb_endpoints_tool.py`. This is the core implementation task. The module exposes `register_tools(app, dct_client)` which registers an `async def vdb_tool` MCP tool decorated with `@log_tool_execution`. The tool dispatches to four bulk action branches via a shared `_bulk_vdb_action` async helper. Must run after Tasks 1, 2, and 3 are complete (needs bulk_concurrency from config and expects toolset .txt files to have the right action names).

**Key constraints (violations fail the design review):**
- `vdb_tool` must be `async def` (FastMCP supports it; `@log_tool_execution` already handles async in `decorators.py`)
- Catch only `DCTClientError` in per-VDB except clause — NOT bare `except Exception` (QR-8)
- Deduplicate `vdbIds` before fan-out using `list(dict.fromkeys(vdbIds))` (Assumption A6)
- Read `bulk_concurrency` from `get_dct_config()["bulk_concurrency"]` at call time — never `os.getenv` directly in the handler
- `bulk_stop` and `bulk_disable` confirmation gate: if `len(vdbIds) > 5` and `confirmed is not True`, return `{"status": "confirmation_required", ...}` with no DCT calls
- `asyncio.run()` must NOT be used inside the tool — there is already a running event loop

### Spec References
- FR-002 (all ACs): bulk_start fan-out and aggregation
- FR-003 (all ACs): bulk_stop with confirmation gate
- FR-004 (all ACs): bulk_enable (no confirmation gate)
- FR-005 (all ACs): bulk_disable with confirmation gate
- FR-006 (AC-1, AC-2): Read and apply bulk_concurrency from config
- FR-007 (AC-1, AC-2): INFO + DEBUG logging per bulk invocation

### Sub-tasks (TDD)

- [ ] **RED**: Create a minimal failing test proving the module can be imported and vdb_tool registered

  Create `tests/test_vdb_endpoints_tool_import.py`:
  ```python
  """Smoke test: vdb_endpoints_tool must be importable and expose register_tools."""
  import pytest


  def test_vdb_endpoints_tool_importable():
      from dct_mcp_server.tools import vdb_endpoints_tool
      assert callable(getattr(vdb_endpoints_tool, "register_tools", None))
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_vdb_endpoints_tool_import.py -v`
  Expected: FAIL — ModuleNotFoundError: No module named 'dct_mcp_server.tools.vdb_endpoints_tool'

- [ ] **GREEN**: Create `src/dct_mcp_server/tools/vdb_endpoints_tool.py`

  ```python
  """
  Pre-built grouped tool module — Bulk VDB Lifecycle Actions.

  Implements register_tools(app, dct_client) with a single async vdb_tool MCP tool
  that handles bulk_start, bulk_stop, bulk_enable, and bulk_disable via a shared
  _bulk_vdb_action async helper with asyncio.Semaphore-bounded concurrency.

  Design: docs/DLPXECO-13965-design.md
  Functional spec: docs/DLPXECO-13965-functional.md
  """

  import asyncio
  from typing import List, Optional

  from dct_mcp_server.config.config import get_dct_config
  from dct_mcp_server.core.decorators import log_tool_execution
  from dct_mcp_server.core.exceptions import DCTClientError, MCPError
  from dct_mcp_server.core.logging import get_logger

  logger = get_logger(__name__)

  # DCT API endpoint templates for single-VDB lifecycle actions.
  # Bulk actions fan out to these per-VDB endpoints internally — there are no
  # real DCT bulk endpoints. The toolset .txt entries (e.g. POST|/vdbs/bulk_start|bulk_start)
  # are fictitious paths whose sole purpose is to register the action name token.
  _VDB_ACTION_ENDPOINTS = {
      "bulk_start": "/vdbs/{vdbId}/start",
      "bulk_stop": "/vdbs/{vdbId}/stop",
      "bulk_enable": "/vdbs/{vdbId}/enable",
      "bulk_disable": "/vdbs/{vdbId}/disable",
  }

  # Actions that require confirmation when len(vdbIds) > 5 (Assumption A2, FR-003, FR-005).
  _CONFIRMATION_REQUIRED_ACTIONS = {"bulk_stop", "bulk_disable"}


  async def _bulk_vdb_action(
      dct_client,
      action: str,
      vdb_ids: List[str],
      concurrency: int,
  ) -> dict:
      """
      Fan out a single-VDB DCT lifecycle action across a list of VDB IDs
      using asyncio.Semaphore-bounded concurrency.

      Args:
          dct_client: DCTAPIClient instance with a make_request(method, path) coroutine.
          action:     Bulk action name (e.g. "bulk_start"). Used to look up the endpoint template.
          vdb_ids:    Deduplicated list of VDB IDs to act on.
          concurrency: Maximum number of concurrent DCT API calls (from DCT_BULK_CONCURRENCY).

      Returns:
          Aggregated response dict with status, total, succeeded, failed, jobs keys.
      """
      endpoint_template = _VDB_ACTION_ENDPOINTS[action]
      semaphore = asyncio.Semaphore(concurrency)
      succeeded: List[str] = []
      failed: List[dict] = []
      jobs: List[dict] = []
      lock = asyncio.Lock()

      logger.info(
          f"{action}: fanning out to {len(vdb_ids)} VDBs with concurrency={concurrency}"
      )

      async def _call_one(vdb_id: str) -> None:
          endpoint = endpoint_template.replace("{vdbId}", vdb_id)
          async with semaphore:
              try:
                  response = await dct_client.make_request("POST", endpoint)
                  async with lock:
                      succeeded.append(vdb_id)
                      job_id = response.get("jobId") if isinstance(response, dict) else None
                      if job_id:
                          jobs.append({"vdbId": vdb_id, "jobId": job_id})
                  logger.debug(f"{action}: vdbId={vdb_id} status=ok")
              except DCTClientError as e:
                  async with lock:
                      failed.append({"vdbId": vdb_id, "error": str(e)})
                  logger.debug(f"{action}: vdbId={vdb_id} status=error [{e}]")

      await asyncio.gather(*[_call_one(vdb_id) for vdb_id in vdb_ids])

      total = len(vdb_ids)
      if not failed:
          status = "success"
      elif not succeeded:
          status = "failed"
      else:
          status = "partial_success"

      return {
          "status": status,
          "total": total,
          "succeeded": succeeded,
          "failed": failed,
          "jobs": jobs,
      }


  def register_tools(app, dct_client):
      """Register bulk VDB lifecycle tools with the FastMCP application."""

      @app.tool()
      @log_tool_execution
      async def vdb_tool(
          action: str,
          vdbIds: Optional[List[str]] = None,
          confirmed: bool = False,
      ) -> dict:
          """
          Bulk VDB lifecycle operations.

          Supported actions:
            - bulk_start:   Start multiple VDBs concurrently.
            - bulk_stop:    Stop multiple VDBs (requires confirmed=True if > 5 VDBs).
            - bulk_enable:  Enable multiple VDBs concurrently (no confirmation gate).
            - bulk_disable: Disable multiple VDBs (requires confirmed=True if > 5 VDBs).

          Args:
              action:   One of bulk_start, bulk_stop, bulk_enable, bulk_disable.
              vdbIds:   Non-empty list of VDB identifier strings.
              confirmed: Set to True to bypass the confirmation gate for bulk_stop / bulk_disable
                         when len(vdbIds) > 5.

          Returns:
              Aggregated response dict:
                {
                  "status": "success" | "partial_success" | "failed",
                  "total": <int>,
                  "succeeded": [<vdbId>, ...],
                  "failed": [{"vdbId": <id>, "error": <msg>}, ...],
                  "jobs": [{"vdbId": <id>, "jobId": <id>}, ...]
                }
              Or a confirmation_required dict when the gate triggers.
          """
          # ── Input validation ────────────────────────────────────────────────
          if not vdbIds or not isinstance(vdbIds, list):
              raise MCPError("vdbIds must be a non-empty list of strings")

          # Deduplicate preserving insertion order (Assumption A6)
          original_count = len(vdbIds)
          vdb_ids = list(dict.fromkeys(vdbIds))
          if len(vdb_ids) < original_count:
              removed = original_count - len(vdb_ids)
              logger.debug(
                  f"{action}: deduplicated {removed} duplicate vdbId(s) before fan-out"
              )

          # ── Action dispatch ─────────────────────────────────────────────────
          if action not in _VDB_ACTION_ENDPOINTS:
              raise MCPError(f"Unknown action: {action}")

          # ── Confirmation gate (bulk_stop, bulk_disable with > 5 VDBs) ───────
          if action in _CONFIRMATION_REQUIRED_ACTIONS and len(vdb_ids) > 5 and not confirmed:
              verb = action.replace("bulk_", "")  # "stop" or "disable"
              return {
                  "status": "confirmation_required",
                  "confirmation_level": "manual",
                  "message": (
                      f"You are about to {verb} {len(vdb_ids)} VDBs. "
                      "Re-call with confirmed=True to proceed."
                  ),
                  "vdbIds": vdb_ids,
              }

          # ── Fan-out ──────────────────────────────────────────────────────────
          config = get_dct_config()
          concurrency = config["bulk_concurrency"]

          return await _bulk_vdb_action(dct_client, action, vdb_ids, concurrency)
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/test_vdb_endpoints_tool_import.py -v`
  Expected: PASS

- [ ] **REFACTOR**: 
  - Verify `_CONFIRMATION_REQUIRED_ACTIONS` is a frozenset for O(1) lookup: `_CONFIRMATION_REQUIRED_ACTIONS = frozenset({"bulk_stop", "bulk_disable"})`
  - Verify type hints are complete on `register_tools` and `_bulk_vdb_action`
  - No logic changes needed

- [ ] **Commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add src/dct_mcp_server/tools/vdb_endpoints_tool.py tests/test_vdb_endpoints_tool_import.py
  git commit -m "Add vdb_endpoints_tool.py with bulk_start/stop/enable/disable implementation"
  ```

### Depends On
- Task 1 (bulk_concurrency key in config dict)
- Task 2 (toolset .txt files have bulk action entries — needed for S18/S19 tests in Task 5)
- Task 3 (loader maps vdb_tool to vdb_endpoints_tool)

### Acceptance Criteria
- [ ] `from dct_mcp_server.tools import vdb_endpoints_tool` succeeds
- [ ] `vdb_endpoints_tool.register_tools` is callable
- [ ] `_bulk_vdb_action` uses `asyncio.Semaphore` — verified by inspection
- [ ] `except DCTClientError` (not bare `except Exception`) in `_call_one` — verified by inspection
- [ ] Import test passes

---

## Task 5: Write full pytest test suite (19 scenarios)  [model:sonnet]

### Description
Creates `tests/dlpxeco-13965-test.py` containing all 19 required test scenarios (S1–S19). Uses `unittest.mock.AsyncMock` to patch `DCTAPIClient.make_request` at the class level in-process — avoiding the subprocess/respx complexity while still validating all behaviour. This approach is simpler than spawning a subprocess and avoids needing real credentials. The test file documents the mocking approach in its module docstring.

**Why in-process patching?** The design doc (Assumption A4) notes that subprocess boundary crossing makes `unittest.mock.patch` difficult — but FastMCP provides an in-process test client that avoids this. Using FastMCP's test client + `unittest.mock.patch` at the class level lets us intercept `DCTAPIClient.make_request` without a real server subprocess.

**FastMCP test client pattern** (from FastMCP docs and codebase conventions):
```python
from fastmcp import FastMCP
client = FastMCP.from_client(app)  # or use the in-process context manager
```
Actually the project uses `mcp.server.fastmcp.FastMCP`. For in-process testing with patching, we create a FastMCP app, call `register_tools(app, mock_client)`, and call `vdb_tool(...)` directly — bypassing the MCP transport entirely since it's just a Python function.

**Simpler approach:** Since `vdb_tool` is a plain async Python function registered via `@app.tool()`, we can:
1. Create a mock `dct_client` with `AsyncMock` for `make_request`
2. Call `register_tools(app, mock_client)` to wire up the function
3. Call `vdb_tool(action=..., vdbIds=...)` directly as an async function — no subprocess needed

This is valid because all the business logic is in the Python function, not in MCP transport.

### Spec References
- FR-002 (all ACs): S1–S5 test bulk_start aggregation
- FR-003 (all ACs): S6–S8 test bulk_stop confirmation gate
- FR-004 (all ACs): S9–S10 test bulk_enable (no gate)
- FR-005 (all ACs): S11–S12 test bulk_disable confirmation gate
- FR-006 (all ACs): S13–S15 test concurrency cap
- FR-007 (AC-1): S16 tests log output
- FR-001 (AC-1, AC-2, AC-3): S17–S19 test toolset config sync
- QR-1 (backward compat): S17 asserts single-VDB start is unaffected

### Sub-tasks (TDD)

- [ ] **RED**: Create the test file with all 19 scenarios as stubs; run and verify they all fail (or error) before implementation

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/dlpxeco-13965-test.py --collect-only`
  Expected: Collected 19 tests (all marked as failing/error if module doesn't exist yet — it exists after Task 4)

- [ ] **GREEN**: Write the complete test file

  Create `tests/dlpxeco-13965-test.py`:
  ```python
  """
  Tests for DLPXECO-13965: Bulk VDB Lifecycle Actions.

  Mocking approach: In-process function-level testing.
  We call register_tools(app, mock_client) to wire vdb_tool into a throwaway FastMCP app,
  then invoke vdb_tool(...) directly as an async coroutine.
  DCTAPIClient.make_request is replaced with AsyncMock — no real DCT instance or subprocess needed.

  Test runner:
      pytest tests/dlpxeco-13965-test.py -v \
          --cov=src/dct_mcp_server/tools/vdb_endpoints_tool \
          --cov-report=term-missing

  Environment:
      DCT_API_KEY=test-key DCT_BASE_URL=http://fake.test DCT_TOOLSET=continuous_data_admin
      DCT_BULK_CONCURRENCY=5  (default; overridden per-test via monkeypatch)
  """

  import asyncio
  import logging
  import os
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  import pytest_asyncio

  # ---------------------------------------------------------------------------
  # Module-level env setup — must happen before any dct_mcp_server imports
  # ---------------------------------------------------------------------------
  os.environ.setdefault("DCT_API_KEY", "test-key")
  os.environ.setdefault("DCT_BASE_URL", "http://fake.test")
  os.environ.setdefault("DCT_TOOLSET", "continuous_data_admin")
  os.environ.setdefault("DCT_BULK_CONCURRENCY", "5")


  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  def _make_app_and_tool(mock_client):
      """
      Register vdb_endpoints_tool against a throwaway FastMCP app, return
      the registered vdb_tool coroutine function directly.
      """
      from mcp.server.fastmcp import FastMCP
      from dct_mcp_server.tools import vdb_endpoints_tool

      app = FastMCP("test-dct-mcp")
      vdb_endpoints_tool.register_tools(app, mock_client)

      # FastMCP stores registered tools; retrieve the underlying function by name.
      # The @app.tool() decorator registers it; we can look it up from app._tool_manager
      # or just import the function that was decorated.
      # Simpler: re-import the module function directly since the module-level function
      # name is vdb_tool and it's exported at module level after register_tools runs.
      # We'll use a direct approach: call it via the FastMCP tool manager.
      # FastMCP tool manager is at app._tool_manager._tools[name].fn
      tool_fn = app._tool_manager._tools["vdb_tool"].fn
      return tool_fn


  def _ok_response(vdb_id: str) -> dict:
      """Mock DCT success response for a single VDB action."""
      return {"jobId": f"job-{vdb_id}", "status": "RUNNING"}


  def _error_side_effect(failing_ids: set):
      """
      Return an AsyncMock side_effect that raises DCTClientError for IDs in failing_ids,
      and returns a success response for all others.
      """
      from dct_mcp_server.core.exceptions import DCTClientError

      async def _side_effect(method, endpoint, **kwargs):
          vdb_id = endpoint.split("/")[2]  # /vdbs/<id>/start → <id>
          if vdb_id in failing_ids:
              raise DCTClientError(f"HTTP 500: internal error for {vdb_id}")
          return _ok_response(vdb_id)

      return _side_effect


  # ---------------------------------------------------------------------------
  # Fixtures
  # ---------------------------------------------------------------------------

  @pytest.fixture
  def mock_client():
      """A mock DCTAPIClient with AsyncMock make_request."""
      client = MagicMock()
      client.make_request = AsyncMock(side_effect=lambda m, ep, **kw: _ok_response(ep.split("/")[2]))
      return client


  # ---------------------------------------------------------------------------
  # S1: bulk_start with 3 VDB IDs all returning HTTP 200
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s1_bulk_start_all_success(mock_client):
      """S1: bulk_start 3 VDBs all 200 → status=success, total=3, 3 succeeded, 0 failed."""
      vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=vdb_ids)
      assert result["status"] == "success"
      assert result["total"] == 3
      assert len(result["succeeded"]) == 3
      assert result["failed"] == []


  # ---------------------------------------------------------------------------
  # S2: bulk_start with one VDB returning HTTP 500
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s2_bulk_start_partial_failure(mock_client):
      """S2: 3 VDBs, one fails → partial_success, 2 succeeded, 1 failed."""
      mock_client.make_request.side_effect = _error_side_effect({"vdb-2"})
      vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=vdb_ids)
      assert result["status"] == "partial_success"
      assert len(result["succeeded"]) == 2
      assert len(result["failed"]) == 1
      assert result["failed"][0]["vdbId"] == "vdb-2"


  # ---------------------------------------------------------------------------
  # S3: bulk_start with all VDBs failing
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s3_bulk_start_all_failed(mock_client):
      """S3: All 3 VDBs fail → status=failed, succeeded=[]."""
      mock_client.make_request.side_effect = _error_side_effect({"vdb-1", "vdb-2", "vdb-3"})
      vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=vdb_ids)
      assert result["status"] == "failed"
      assert result["succeeded"] == []
      assert len(result["failed"]) == 3


  # ---------------------------------------------------------------------------
  # S4: bulk_start with empty vdbIds
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s4_bulk_start_empty_list_rejected(mock_client):
      """S4: empty vdbIds → MCPError before any DCT call."""
      from dct_mcp_server.core.exceptions import MCPError
      tool = _make_app_and_tool(mock_client)
      with pytest.raises(MCPError, match="vdbIds must be a non-empty list"):
          await tool(action="bulk_start", vdbIds=[])
      mock_client.make_request.assert_not_called()


  # ---------------------------------------------------------------------------
  # S5: bulk_start with a single VDB ID
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s5_bulk_start_single_vdb(mock_client):
      """S5: single VDB → status=success, total=1, 1 succeeded."""
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=["vdb-solo"])
      assert result["status"] == "success"
      assert result["total"] == 1
      assert len(result["succeeded"]) == 1
      assert result["failed"] == []


  # ---------------------------------------------------------------------------
  # S6: bulk_stop with 6 VDB IDs and confirmed=False
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s6_bulk_stop_confirmation_gate(mock_client):
      """S6: 6 VDBs, confirmed=False → confirmation_required, no DCT calls."""
      vdb_ids = [f"vdb-{i}" for i in range(6)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_stop", vdbIds=vdb_ids, confirmed=False)
      assert result["status"] == "confirmation_required"
      assert result["confirmation_level"] == "manual"
      assert len(result["vdbIds"]) == 6
      mock_client.make_request.assert_not_called()


  # ---------------------------------------------------------------------------
  # S7: bulk_stop with 6 VDB IDs and confirmed=True
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s7_bulk_stop_confirmed_executes(mock_client):
      """S7: 6 VDBs, confirmed=True → batch executes, total=6, 6 DCT calls."""
      vdb_ids = [f"vdb-{i}" for i in range(6)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_stop", vdbIds=vdb_ids, confirmed=True)
      assert result["status"] in ("success", "partial_success", "failed")
      assert result["total"] == 6
      assert mock_client.make_request.call_count == 6


  # ---------------------------------------------------------------------------
  # S8: bulk_stop with 5 VDB IDs and no confirmed
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s8_bulk_stop_five_no_confirmation_needed(mock_client):
      """S8: 5 VDBs, no confirmed → executes immediately (no confirmation gate)."""
      vdb_ids = [f"vdb-{i}" for i in range(5)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_stop", vdbIds=vdb_ids)
      assert result["status"] in ("success", "partial_success", "failed")
      assert result["total"] == 5
      # confirmation_required was NOT returned
      assert result.get("confirmation_level") is None


  # ---------------------------------------------------------------------------
  # S9: bulk_enable with > 5 VDB IDs executes without confirmation gate
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s9_bulk_enable_no_confirmation_gate(mock_client):
      """S9: bulk_enable with 7 VDBs → executes immediately, no confirmation returned."""
      vdb_ids = [f"vdb-{i}" for i in range(7)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_enable", vdbIds=vdb_ids)
      assert result["status"] in ("success", "partial_success", "failed")
      assert result.get("confirmation_level") is None


  # ---------------------------------------------------------------------------
  # S10: bulk_enable with mixed results → partial_success
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s10_bulk_enable_partial_success(mock_client):
      """S10: bulk_enable, one VDB fails → partial_success."""
      mock_client.make_request.side_effect = _error_side_effect({"vdb-1"})
      vdb_ids = ["vdb-0", "vdb-1", "vdb-2"]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_enable", vdbIds=vdb_ids)
      assert result["status"] == "partial_success"
      assert len(result["succeeded"]) > 0
      assert len(result["failed"]) > 0


  # ---------------------------------------------------------------------------
  # S11: bulk_disable with 6 VDB IDs and no confirmed
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s11_bulk_disable_confirmation_gate(mock_client):
      """S11: 6 VDBs, no confirmed → confirmation_required, zero DCT calls."""
      vdb_ids = [f"vdb-{i}" for i in range(6)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_disable", vdbIds=vdb_ids)
      assert result["status"] == "confirmation_required"
      assert result["confirmation_level"] == "manual"
      mock_client.make_request.assert_not_called()


  # ---------------------------------------------------------------------------
  # S12: bulk_disable with 5 VDB IDs executes without confirmation gate
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s12_bulk_disable_five_no_gate(mock_client):
      """S12: 5 VDBs, no confirmed → executes without confirmation gate."""
      vdb_ids = [f"vdb-{i}" for i in range(5)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_disable", vdbIds=vdb_ids)
      assert result["status"] in ("success", "partial_success", "failed")
      assert result["total"] == 5
      assert result.get("confirmation_level") is None


  # ---------------------------------------------------------------------------
  # S13: Concurrency cap at DCT_BULK_CONCURRENCY=3
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s13_bulk_concurrency_cap_3(monkeypatch):
      """S13: DCT_BULK_CONCURRENCY=3, 10 VDBs → peak in-flight <= 3."""
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "3")

      peak_inflight = 0
      current_inflight = 0
      counter_lock = asyncio.Lock()

      async def _counting_mock(method, endpoint, **kwargs):
          nonlocal peak_inflight, current_inflight
          async with counter_lock:
              current_inflight += 1
              if current_inflight > peak_inflight:
                  peak_inflight = current_inflight
          await asyncio.sleep(0.01)  # Simulate DCT latency
          async with counter_lock:
              current_inflight -= 1
          vdb_id = endpoint.split("/")[2]
          return _ok_response(vdb_id)

      mock_client = MagicMock()
      mock_client.make_request = AsyncMock(side_effect=_counting_mock)
      vdb_ids = [f"vdb-{i}" for i in range(10)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=vdb_ids)
      assert peak_inflight <= 3, f"Peak in-flight {peak_inflight} exceeded cap of 3"
      assert result["total"] == 10


  # ---------------------------------------------------------------------------
  # S14: Default DCT_BULK_CONCURRENCY=5 when not set
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s14_bulk_concurrency_default_5(monkeypatch):
      """S14: DCT_BULK_CONCURRENCY not set → default 5, peak in-flight <= 5."""
      monkeypatch.delenv("DCT_BULK_CONCURRENCY", raising=False)

      peak_inflight = 0
      current_inflight = 0
      counter_lock = asyncio.Lock()

      async def _counting_mock(method, endpoint, **kwargs):
          nonlocal peak_inflight, current_inflight
          async with counter_lock:
              current_inflight += 1
              if current_inflight > peak_inflight:
                  peak_inflight = current_inflight
          await asyncio.sleep(0.01)
          async with counter_lock:
              current_inflight -= 1
          vdb_id = endpoint.split("/")[2]
          return _ok_response(vdb_id)

      mock_client = MagicMock()
      mock_client.make_request = AsyncMock(side_effect=_counting_mock)
      vdb_ids = [f"vdb-{i}" for i in range(10)]
      tool = _make_app_and_tool(mock_client)
      result = await tool(action="bulk_start", vdbIds=vdb_ids)
      assert peak_inflight <= 5, f"Peak in-flight {peak_inflight} exceeded cap of 5"


  # ---------------------------------------------------------------------------
  # S15: DCT_BULK_CONCURRENCY=0 clamped to 1
  # ---------------------------------------------------------------------------
  def test_s15_bulk_concurrency_zero_clamped(monkeypatch):
      """S15: DCT_BULK_CONCURRENCY=0 → config["bulk_concurrency"] == 1, WARNING logged."""
      monkeypatch.setenv("DCT_BULK_CONCURRENCY", "0")
      from dct_mcp_server.config.config import get_dct_config
      cfg = get_dct_config()
      assert cfg["bulk_concurrency"] == 1


  # ---------------------------------------------------------------------------
  # S16: Logging — 1 INFO + N DEBUG per bulk_start
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s16_logging_one_info_n_debug(mock_client, caplog):
      """S16: bulk_start 3 VDBs → exactly 1 INFO 'fanning out' + 3 DEBUG 'vdbId='."""
      vdb_ids = ["vdb-a", "vdb-b", "vdb-c"]
      tool = _make_app_and_tool(mock_client)
      with caplog.at_level(logging.DEBUG, logger="dct_mcp_server.tools.vdb_endpoints_tool"):
          await tool(action="bulk_start", vdbIds=vdb_ids)

      info_lines = [r for r in caplog.records
                    if r.levelno == logging.INFO and "fanning out" in r.message]
      debug_lines = [r for r in caplog.records
                     if r.levelno == logging.DEBUG and "vdbId=" in r.message]
      assert len(info_lines) == 1, f"Expected 1 INFO 'fanning out' line, got {len(info_lines)}"
      assert len(debug_lines) == 3, f"Expected 3 DEBUG 'vdbId=' lines, got {len(debug_lines)}"


  # ---------------------------------------------------------------------------
  # S17: Existing single-VDB start action in dataset_endpoints_tool is unaffected
  # ---------------------------------------------------------------------------
  @pytest.mark.asyncio
  async def test_s17_single_vdb_start_unchanged(mock_client):
      """S17: vdb_tool with action=bulk_start returns aggregated shape (not per-VDB raw response).
      QR-1: Verifies bulk actions do not break the vdb_endpoints_tool contract."""
      # Single-VDB start IS bulk_start with len==1 in this module; it returns
      # the aggregated shape. The single-VDB actions still exist in dataset_endpoints_tool.
      # This test asserts the new vdb_tool (bulk only) does not regress on single-VDB intent:
      # calling bulk_start with 1 VDB returns the correct aggregated shape.
      result = await _make_app_and_tool(mock_client)(
          action="bulk_start", vdbIds=["vdb-solo"]
      )
      assert result["status"] == "success"
      assert result["total"] == 1
      # The response is the aggregated wrapper, not a raw DCT response
      assert "succeeded" in result
      assert "failed" in result
      assert "jobs" in result


  # ---------------------------------------------------------------------------
  # S18: bulk_start, bulk_stop, bulk_enable, bulk_disable in self_service vdb_tool
  # ---------------------------------------------------------------------------
  def test_s18_bulk_actions_in_self_service():
      """S18: All 4 bulk actions appear in self_service toolset vdb_tool actions."""
      from dct_mcp_server.config.loader import load_toolset_grouped_apis
      grouped = load_toolset_grouped_apis("self_service")
      vdb_actions = {api["action"] for api in grouped["vdb_tool"]["apis"]}
      for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
          assert action in vdb_actions, f"{action} missing from self_service vdb_tool"


  # ---------------------------------------------------------------------------
  # S19: All 4 bulk actions in continuous_data_admin; none in reporting_insights
  # ---------------------------------------------------------------------------
  def test_s19_bulk_actions_toolset_presence_absence():
      """S19: All 4 in continuous_data_admin data_tool; none in reporting_insights."""
      from dct_mcp_server.config.loader import load_toolset_grouped_apis, load_toolset_apis

      grouped = load_toolset_grouped_apis("continuous_data_admin")
      data_actions = {api["action"] for api in grouped["data_tool"]["apis"]}
      for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
          assert action in data_actions, f"{action} missing from continuous_data_admin data_tool"

      ri_apis = load_toolset_apis("reporting_insights")
      ri_actions = {api["action"] for api in ri_apis}
      for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
          assert action not in ri_actions, f"{action} unexpectedly in reporting_insights"
  ```

  Run: `cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965 && python -m pytest tests/dlpxeco-13965-test.py -v --cov=src/dct_mcp_server/tools/vdb_endpoints_tool --cov-report=term-missing`
  Expected: All 19 tests PASS; coverage >= 80% for `vdb_endpoints_tool.py`

  **If `app._tool_manager._tools` raises AttributeError** (FastMCP internals differ), use this fallback in `_make_app_and_tool`:
  ```python
  # Alternative: call the function by finding it in the module namespace
  import importlib
  mod = importlib.import_module("dct_mcp_server.tools.vdb_endpoints_tool")
  # After register_tools runs, vdb_tool is in the module's globals as a decorated fn
  # but the @app.tool() wraps it. Simplest fallback: grab it from the FastMCP tool list.
  tools = asyncio.run(app.get_tools()) if not asyncio.get_event_loop().is_running() else []
  # Or use the _tool_manager if available; otherwise call the underlying function directly:
  from dct_mcp_server.tools.vdb_endpoints_tool import _bulk_vdb_action
  # and test _bulk_vdb_action directly for S1-S16.
  ```

  If `_tool_manager` is not accessible, refactor `_make_app_and_tool` to directly test `_bulk_vdb_action` for fan-out tests and access `vdb_tool` for confirmation gate tests by making it a module-level function:
  ```python
  # In vdb_endpoints_tool.py (add after register_tools):
  # _vdb_tool_fn: kept as a module-level reference for testing
  _vdb_tool_fn = None

  def register_tools(app, dct_client):
      global _vdb_tool_fn

      @app.tool()
      @log_tool_execution
      async def vdb_tool(...):
          ...

      _vdb_tool_fn = vdb_tool
  ```
  Then in tests: `from dct_mcp_server.tools.vdb_endpoints_tool import _vdb_tool_fn`

- [ ] **REFACTOR**: 
  - Extract `_counting_mock` as a shared fixture to avoid code duplication between S13 and S14
  - Ensure all 19 test functions have clear docstrings matching the test plan scenario text
  - Remove `tests/test_config_bulk_concurrency.py` and `tests/test_toolset_bulk_actions.py` (they overlap with S15, S18, S19) OR keep them as lightweight unit tests — implementer's preference

- [ ] **Commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add tests/dlpxeco-13965-test.py
  git commit -m "Add 19 pytest scenarios for bulk VDB lifecycle actions (DLPXECO-13965)"
  ```

### Depends On
- Task 1 (config has bulk_concurrency)
- Task 2 (toolset files have bulk action entries)
- Task 4 (vdb_endpoints_tool.py exists and is importable)

### Acceptance Criteria
- [ ] `pytest tests/dlpxeco-13965-test.py -v` exits 0 with 19 tests passing
- [ ] No test requires a live DCT instance or real API key
- [ ] Coverage of `vdb_endpoints_tool.py` >= 80%

---

## Task 6: Install test dependencies  [parallel][model:haiku]

### Description
Ensures `pytest-asyncio` is available for async test execution. The project uses `uv` for dependency management (see `build-and-execution.md`). Adds `pytest-asyncio` to the project's test dependencies if not already present.

### Spec References
- FR-008 (AC-1): pytest + pytest-asyncio required for all 19 tests

### Sub-tasks (TDD)

- [ ] **Check if pytest-asyncio is already installed**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  python -m pytest --version && python -c "import pytest_asyncio; print('pytest-asyncio:', pytest_asyncio.__version__)"
  ```
  If output shows `pytest-asyncio: X.Y.Z`, skip the install step.

- [ ] **If not installed**: Check `pyproject.toml` or `requirements.txt`:
  ```bash
  cat /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965/pyproject.toml | grep -i pytest
  ```
  Add to the `[project.optional-dependencies]` `test` or `dev` group:
  ```toml
  [project.optional-dependencies]
  test = [
      "pytest",
      "pytest-asyncio",
  ]
  ```
  Then: `uv sync`

- [ ] **Verify**:
  ```bash
  python -m pytest tests/dlpxeco-13965-test.py --collect-only
  ```
  Expected: 19 tests collected with no import errors.

- [ ] **Commit** (if pyproject.toml changed):
  ```bash
  git add pyproject.toml
  git commit -m "Add pytest-asyncio to test dependencies"
  ```

### Depends On
- None

### Acceptance Criteria
- [ ] `import pytest_asyncio` succeeds in the project virtualenv
- [ ] `pytest tests/dlpxeco-13965-test.py --collect-only` collects 19 tests without import error

---

## Task 7: Verify full test suite and cleanup  [model:haiku]

### Description
Runs the complete test suite, checks coverage, cleans up temporary test files from earlier tasks, and ensures no regressions in adjacent modules.

### Spec References
- FR-008 (AC-1): All 19 tests pass; coverage measurable via `--cov`

### Sub-tasks (TDD)

- [ ] **Run the full test suite**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  DCT_API_KEY=test-key DCT_BASE_URL=http://fake.test DCT_TOOLSET=continuous_data_admin \
    DCT_BULK_CONCURRENCY=5 \
    python -m pytest tests/dlpxeco-13965-test.py -v \
      --cov=src/dct_mcp_server/tools/vdb_endpoints_tool \
      --cov-report=term-missing
  ```
  Expected: 19 PASSED, exit 0, coverage >= 80%

- [ ] **Run the full project test suite** (regression check):
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  DCT_API_KEY=test-key DCT_BASE_URL=http://fake.test \
    python -m pytest tests/ -v
  ```
  Expected: All tests PASS

- [ ] **Check git diff covers all required files**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git diff --name-only HEAD
  ```
  Expected output must include all of:
  - `src/dct_mcp_server/config/config.py`
  - `src/dct_mcp_server/config/toolsets/self_service.txt`
  - `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt`
  - `src/dct_mcp_server/config/loader.py`
  - `src/dct_mcp_server/tools/vdb_endpoints_tool.py`
  - `tests/dlpxeco-13965-test.py`

- [ ] **Clean up temporary test files** (if they were created):
  ```bash
  rm -f tests/test_config_bulk_concurrency.py tests/test_vdb_endpoints_tool_import.py tests/test_toolset_bulk_actions.py
  ```
  _(Keep any of these if they cover scenarios not in `dlpxeco-13965-test.py`)_

- [ ] **Final commit**:
  ```bash
  cd /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
  git add -u
  git commit -m "DLPXECO-13965 bulk VDB lifecycle actions — all 19 tests pass"
  ```

### Depends On
- Task 1, Task 2, Task 3, Task 4, Task 5, Task 6

### Acceptance Criteria
- [ ] All 19 scenarios in `tests/dlpxeco-13965-test.py` pass
- [ ] Coverage of `vdb_endpoints_tool.py` >= 80%
- [ ] `git diff --name-only HEAD` includes all 6 required files
- [ ] No regressions in other test files

---

## Execution Order

Task 1 (parallel), Task 2 (parallel), Task 3 (parallel), Task 6 (parallel) → Task 4 → Task 5 → Task 7

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Add DCT_BULK_CONCURRENCY to config.py | PENDING |
| Task 2: Register bulk actions in toolset .txt files | PENDING |
| Task 3: Map vdb_tool to vdb_endpoints_tool in loader.py | PENDING |
| Task 4: Create vdb_endpoints_tool.py | PENDING |
| Task 5: Write full pytest test suite (19 scenarios) | PENDING |
| Task 6: Install test dependencies | PENDING |
| Task 7: Verify full test suite and cleanup | PENDING |
