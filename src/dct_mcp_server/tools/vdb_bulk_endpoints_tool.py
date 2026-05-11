"""
VDB Bulk Lifecycle Tool — DLPXECO-13965.

Implements a new MCP tool, ``vdb_bulk_tool``, that fans out lifecycle
operations (start / stop / enable / disable) across multiple VDB IDs in a
single call. Each per-VDB request is dispatched against the existing DCT
endpoint family (``POST /vdbs/{vdbId}/start`` and friends) under an
``asyncio.Semaphore``-bounded concurrency cap (default 5, override via
``DCT_BULK_CONCURRENCY``).

This module is intentionally separate from ``dataset_endpoints_tool.py``:
the OpenAPI generator may emit a shadowing copy of that module at startup
on ``pip`` / ``uvx`` installs, which would mask any in-place edits. The
generator never produces ``vdb_bulk_endpoints_tool``, so the standard
pre-built fallback path always loads this module unchanged.

Design reference: docs/DLPXECO-13965-design.md (Option B, "Generator-vs-pre-built
decision"). Functional spec: docs/DLPXECO-13965-functional.md FR-001..FR-010.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from dct_mcp_server.config import get_confirmation_for_operation
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.core.exceptions import DCTClientError, MCPError
from dct_mcp_server.core.logging import get_logger

client = None
logger = get_logger(__name__)

_DEFAULT_CONCURRENCY = 5
_CONFIRMATION_THRESHOLD = 5

# Maps action name -> per-VDB DCT path template. The {vdbId} placeholder is
# substituted per task inside _bulk_fanout.
_ACTION_TO_PATH_TEMPLATE: Dict[str, str] = {
    "bulk_start": "/vdbs/{vdbId}/start",
    "bulk_stop": "/vdbs/{vdbId}/stop",
    "bulk_enable": "/vdbs/{vdbId}/enable",
    "bulk_disable": "/vdbs/{vdbId}/disable",
}

# Actions that consult the manual-confirmation table when len(vdbIds) > N.
# Sentinel paths are declared in config/mappings/manual_confirmation.txt so
# the confirmation rule lookup can locate them.
_ACTIONS_REQUIRING_CONFIRMATION = ("bulk_stop", "bulk_disable")

_ACTION_TO_CONFIRMATION_PATH: Dict[str, str] = {
    "bulk_stop": "/vdbs/bulk_stop",
    "bulk_disable": "/vdbs/bulk_disable",
}


def _resolve_concurrency_cap() -> int:
    """
    Read DCT_BULK_CONCURRENCY and return a positive integer cap.

    Per design Open Questions #5 / spec FR-005 AC-2: invalid values
    (non-integer, zero, negative) fall back silently to the default with
    a single WARNING log. The env var is read per-invocation so tests can
    rebind it between calls.
    """
    raw = os.environ.get("DCT_BULK_CONCURRENCY")
    if raw is None or raw == "":
        return _DEFAULT_CONCURRENCY
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid DCT_BULK_CONCURRENCY=%r — falling back to default %d",
            raw,
            _DEFAULT_CONCURRENCY,
        )
        return _DEFAULT_CONCURRENCY
    if value <= 0:
        logger.warning(
            "Non-positive DCT_BULK_CONCURRENCY=%d — falling back to default %d",
            value,
            _DEFAULT_CONCURRENCY,
        )
        return _DEFAULT_CONCURRENCY
    return value


def _validate_vdb_ids(action: str, vdb_ids: Any) -> List[str]:
    """
    Validate the ``vdbIds`` argument. Raises MCPError on any violation.

    FR-009 AC-2: ``vdbIds`` must be a list. FR-001 AC-4: empty list is
    rejected before any DCT call is made.
    """
    if not isinstance(vdb_ids, list):
        raise MCPError(
            f"vdb_bulk_tool action='{action}': vdbIds must be a list of strings, got "
            f"{type(vdb_ids).__name__}"
        )
    if len(vdb_ids) == 0:
        raise MCPError(
            f"vdb_bulk_tool action='{action}': vdbIds must contain at least one ID"
        )
    for idx, vid in enumerate(vdb_ids):
        if not isinstance(vid, str) or not vid:
            raise MCPError(
                f"vdb_bulk_tool action='{action}': vdbIds[{idx}] must be a non-empty string, got "
                f"{type(vid).__name__}"
            )
    return vdb_ids


def _build_confirmation_envelope(
    action: str, vdb_ids: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Build the confirmation_required response envelope for actions that
    cross the threshold without ``confirmed=True``. Returns None if no
    confirmation is needed.

    Confirmation rule lookup uses the sentinel path declared in
    manual_confirmation.txt (e.g. ``POST /vdbs/bulk_stop``). The ``{count}``
    placeholder in the rule message template is filled in here.
    """
    if action not in _ACTIONS_REQUIRING_CONFIRMATION:
        return None
    if len(vdb_ids) <= _CONFIRMATION_THRESHOLD:
        return None

    confirmation_path = _ACTION_TO_CONFIRMATION_PATH[action]
    rule = get_confirmation_for_operation("POST", confirmation_path)
    count = len(vdb_ids)
    level = rule.get("level") if rule.get("level") and rule["level"] != "none" else "manual"
    raw_message = rule.get("message") or (
        f"You are about to {action.replace('bulk_', '')} {count} VDBs. "
        "Re-call with confirmed=True to proceed."
    )
    try:
        message = raw_message.format(count=count)
    except (KeyError, IndexError):
        message = raw_message
    return {
        "status": "confirmation_required",
        "confirmation_level": level,
        "confirmation_message": message,
        "action": action,
        "tool": "vdb_bulk_tool",
        "message": (
            "STOP: You MUST display the confirmation_message to the user and wait "
            "for their EXPLICIT approval before re-calling with confirmed=True. "
            "Do NOT proceed without user consent."
        ),
    }


def _extract_job_id(body: Optional[Dict[str, Any]]) -> Optional[str]:
    """Best-effort jobId extraction from a DCT response body."""
    if not isinstance(body, dict):
        return None
    for key in ("jobId", "job_id", "id"):
        val = body.get(key)
        if isinstance(val, str) and val:
            return val
    job = body.get("job")
    if isinstance(job, dict):
        for key in ("jobId", "job_id", "id"):
            val = job.get(key)
            if isinstance(val, str) and val:
                return val
    return None


async def _bulk_fanout(
    path_template: str,
    vdb_ids: List[str],
    dct_client: Any,
    *,
    concurrency: Optional[int] = None,
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Fan out one POST request per vdbId under a Semaphore-bounded cap and
    return ``(succeeded, failed, jobs)``.

    - ``succeeded``: vdbIds that returned a 2xx response.
    - ``failed``:    [{"vdbId": ..., "error": ...}] for any per-VDB error.
    - ``jobs``:      [{"vdbId": ..., "jobId": ...}] for any successful call
                     that carried a jobId in the response body.

    A single per-VDB exception does NOT abort the batch — we use
    ``return_exceptions=True`` on the gather so every task's outcome is
    captured.
    """
    cap = concurrency if concurrency and concurrency > 0 else _resolve_concurrency_cap()
    sem = asyncio.Semaphore(cap)

    async def _one(
        vdb_id: str,
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[BaseException]]:
        path = path_template.replace("{vdbId}", vdb_id)
        async with sem:
            try:
                response = await dct_client.make_request("POST", path)
                return vdb_id, response, None
            except BaseException as exc:  # capture EVERY exception — see docstring
                return vdb_id, None, exc

    tasks = [_one(vid) for vid in vdb_ids]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    succeeded: List[str] = []
    failed: List[Dict[str, Any]] = []
    jobs: List[Dict[str, str]] = []

    for item in raw_results:
        # gather(return_exceptions=True) will return an Exception object
        # if a task raised before its own try/except caught it. In our
        # case _one swallows everything, but we guard anyway.
        if isinstance(item, BaseException):
            failed.append({"vdbId": "<unknown>", "error": _format_exception(item)})
            continue
        vdb_id, body, exc = item
        if exc is not None:
            failed.append({"vdbId": vdb_id, "error": _format_exception(exc)})
            continue
        succeeded.append(vdb_id)
        job_id = _extract_job_id(body)
        if job_id:
            jobs.append({"vdbId": vdb_id, "jobId": job_id})

    return succeeded, failed, jobs


def _format_exception(exc: BaseException) -> str:
    """Render an exception in a stable form for the response/log."""
    if isinstance(exc, asyncio.TimeoutError):
        return f"timeout: {exc!s}" if str(exc) else "timeout"
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


def _classify_status(succeeded: List[str], failed: List[Dict[str, Any]]) -> str:
    if not failed:
        return "success"
    if not succeeded:
        return "failed"
    return "partial_success"


def _log_outcome(
    action: str,
    total: int,
    succeeded: List[str],
    failed: List[Dict[str, Any]],
) -> None:
    """Emit FR-008-mandated logs: one INFO summary + one DEBUG per VDB."""
    logger.info(
        "%s completed: succeeded=%d failed=%d total=%d",
        action,
        len(succeeded),
        len(failed),
        total,
    )
    for vid in succeeded:
        logger.debug("%s vdb=%s status=success", action, vid)
    for entry in failed:
        logger.debug(
            "%s vdb=%s status=error error=%s",
            action,
            entry.get("vdbId", "<unknown>"),
            entry.get("error", ""),
        )


async def _vdb_bulk_tool_async(
    action: str,
    vdbIds: Any,
    confirmed: bool = False,
    *,
    _client_override: Any = None,
) -> Dict[str, Any]:
    """
    Async core for ``vdb_bulk_tool``. See the public wrapper for arg docs.

    ``_client_override`` lets tests inject a fake DCT client without
    monkey-patching the module-level ``client`` global.
    """
    if action not in _ACTION_TO_PATH_TEMPLATE:
        raise MCPError(
            f"vdb_bulk_tool: unknown action '{action}'. Available actions: "
            f"{', '.join(sorted(_ACTION_TO_PATH_TEMPLATE.keys()))}"
        )

    validated = _validate_vdb_ids(action, vdbIds)

    if not confirmed:
        envelope = _build_confirmation_envelope(action, validated)
        if envelope is not None:
            return envelope

    dct_client = _client_override if _client_override is not None else client
    if dct_client is None:
        raise MCPError(
            "vdb_bulk_tool: DCT client is not initialised — register_tools() "
            "must run at server startup before any bulk action is invoked."
        )

    path_template = _ACTION_TO_PATH_TEMPLATE[action]
    succeeded, failed, jobs = await _bulk_fanout(path_template, validated, dct_client)
    total = len(validated)
    status = _classify_status(succeeded, failed)
    _log_outcome(action, total, succeeded, failed)

    return {
        "status": status,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "jobs": jobs,
    }


def vdb_bulk_tool(
    action: str,
    vdbIds: List[str],
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Bulk VDB lifecycle operations — start / stop / enable / disable many VDBs in one call.

    Available actions: bulk_start, bulk_stop, bulk_enable, bulk_disable

    Each action fans out one HTTP POST per ``vdbId`` against the existing
    DCT per-VDB endpoint (``/vdbs/{vdbId}/start`` etc.) under an
    ``asyncio.Semaphore`` cap of ``DCT_BULK_CONCURRENCY`` (default 5,
    minimum 1). Outcomes are aggregated and returned as a single dict:

    .. code-block:: python

        {
            "status": "success" | "partial_success" | "failed",
            "total": int,
            "succeeded": [vdbId, ...],
            "failed":    [{"vdbId": ..., "error": ...}, ...],
            "jobs":      [{"vdbId": ..., "jobId": ...}, ...],
        }

    ``bulk_stop`` and ``bulk_disable`` are gated by the manual-confirmation
    pipeline when more than 5 VDBs are targeted: the first call returns a
    ``confirmation_required`` envelope without any DCT call; re-call with
    ``confirmed=True`` to actually execute. ``bulk_start`` and
    ``bulk_enable`` execute immediately regardless of list size.

    Args:
        action: One of ``bulk_start``, ``bulk_stop``, ``bulk_enable``,
            ``bulk_disable``.
        vdbIds: Non-empty list of VDB IDs.
        confirmed: When True, skips the confirmation gate for stop/disable.

    Returns:
        Aggregate dict described above, or a ``confirmation_required``
        envelope when gating fires.

    Raises:
        MCPError: For unknown actions, non-list ``vdbIds``, empty list, or
            non-string IDs.
    """
    # The synchronous wrapper lets FastMCP register us as a regular tool
    # while the work itself remains async. If we're already inside a
    # running loop (e.g. when called from another async tool) we offload
    # to a worker thread to avoid nested-loop deadlocks; otherwise we run
    # the coroutine on a fresh loop.
    try:
        loop = asyncio.get_event_loop()
        running = loop.is_running()
    except RuntimeError:
        loop = None
        running = False

    if not running:
        return asyncio.run(_vdb_bulk_tool_async(action, vdbIds, confirmed=confirmed))

    import threading

    container: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            container["result"] = asyncio.run(
                _vdb_bulk_tool_async(action, vdbIds, confirmed=confirmed)
            )
        except BaseException as exc:
            container["exc"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "exc" in container:
        raise container["exc"]
    return container["result"]


def register_tools(app, dct_client):
    """
    Standard pre-built module entry point — called by
    ``tools/__init__.py:register_all_tools`` at server startup.
    """
    global client
    client = dct_client
    logger.info("Registering tools for vdb_bulk_endpoints...")
    try:
        logger.info("  Registering tool function: vdb_bulk_tool")
        app.tool(name="vdb_bulk_tool")(log_tool_execution(vdb_bulk_tool))
    except Exception as exc:
        logger.error("Error registering tools for vdb_bulk_endpoints: %s", exc)
        raise
    logger.info("Tools registration finished for vdb_bulk_endpoints.")
