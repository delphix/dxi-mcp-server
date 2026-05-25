"""
Layer 4 cleanup pass — invoked by `dct-mcp-test` after every --layer e2e run,
even on test failure. Uses E2E_RUN_TAG to find and delete any resources the
e2e tests created during this run.

PoC stage: the smoke tests in tests/e2e/test_vdb_smoke.py are read-only, so
cleanup is a no-op. This file exists as the scaffold for when destructive
e2e workflows are added (delete created VDBs, bookmarks, tags, etc.).

When destructive tests are added:
  - Every created resource must be tagged with f"{E2E_RUN_TAG}-<purpose>"
    (e.g. in the resource name or via tags)
  - This module searches for everything tagged with the current run id and
    deletes it
  - Forced to run via `if: always()` in CI so crashed runs still clean up
"""

import os

import pytest


@pytest.mark.real_dct
@pytest.mark.asyncio
async def test_cleanup_is_a_noop_in_poc_phase(real_mcp_client):
    """
    Placeholder cleanup test. Confirms that we have an E2E_RUN_TAG and the
    real MCP client is reachable. Will grow into actual purge logic when
    destructive e2e workflows are introduced.
    """
    run_tag = os.environ.get("E2E_RUN_TAG")
    assert run_tag, "E2E_RUN_TAG must be set by the CLI before cleanup runs"
    assert run_tag.startswith("e2e-"), f"unexpected E2E_RUN_TAG format: {run_tag}"

    # Sanity check: client is still alive after the test pass — proves the
    # cleanup step has a live connection to DCT for future delete calls.
    tools = await real_mcp_client.list_tools()
    assert tools, "real_mcp_client lost its connection before cleanup ran"
