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
_CONFIRMATION_REQUIRED_ACTIONS = frozenset({"bulk_stop", "bulk_disable"})


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


def register_tools(app, dct_client) -> None:
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
