"""
Tools package for DCT API categories
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List

from .dsources import register_dsource_tools
from .vdb import register_vdb_tools
from .environments import register_environment_tools
from .engines import register_engine_tools
from .bookmarks import register_bookmark_tools
from .snapshots import register_snapshot_tools
from .continuous_compliance import (
    register_ruleset_tools,
    register_connector_tools,
    register_jobs_tools,
    register_executions_tools,
    register_logs_tools,
    register_log_explanation_tools,
)

logger = logging.getLogger("dct-tools")

# Registry for cleanup handlers
_cleanup_handlers: List[Callable[[], Awaitable[None]]] = []


def register_cleanup_handler(handler: Callable[[], Awaitable[None]]) -> None:
    """Register a cleanup handler to be called on shutdown"""
    _cleanup_handlers.append(handler)


async def run_cleanup() -> None:
    """Run all registered cleanup handlers"""
    if not _cleanup_handlers:
        return

    logger.info(f"Running {len(_cleanup_handlers)} cleanup handlers")
    for handler in _cleanup_handlers:
        try:
            await handler()
        except Exception as e:
            logger.error(f"Error in cleanup handler: {str(e)}")


__all__ = [
    "register_dsource_tools",
    "register_vdb_tools",
    "register_environment_tools",
    "register_engine_tools",
    "register_bookmark_tools",
    "register_snapshot_tools",
    "register_ruleset_tools",
    "register_connector_tools",
    "register_jobs_tools",
    "register_executions_tools",
    "register_logs_tools",
    "register_log_explanation_tools",
    "register_cleanup_handler",
    "run_cleanup",
]
