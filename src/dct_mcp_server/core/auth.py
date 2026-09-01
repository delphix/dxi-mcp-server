"""
Authentication and per-process identity resolution for the DCT MCP Server.

The server runs over stdio only. A stdio pipe is 1:1 and carries no request
headers, so an embedded host spawns one server process per caller and supplies
the caller's DCT account id in the child process environment as
``DCT_CLIENT_ID``. Identity is therefore fixed for the life of the process.

Provides:
- AuthContext: dataclass returned by resolve_auth() describing the caller's identity.
- resolve_auth(): returns an AuthContext appropriate for the configured auth_mode.
"""

from dataclasses import dataclass
from typing import Optional

from dct_mcp_server.core.exceptions import AuthError
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask(v: str) -> str:
    """Return a masked version of a sensitive string for safe logging."""
    return v[:2] + "***" + v[-2:] if len(v) > 4 else "***"


# ---------------------------------------------------------------------------
# AuthContext
# ---------------------------------------------------------------------------


@dataclass
class AuthContext:
    """Identity information resolved for the current request."""

    account_id: str
    api_key: Optional[str]
    auth_mode: str


# ---------------------------------------------------------------------------
# resolve_auth
# ---------------------------------------------------------------------------


def resolve_auth() -> AuthContext:
    """Return an :class:`AuthContext` for the current process.

    In ``embedded`` auth mode the caller identity comes from the
    ``DCT_CLIENT_ID`` environment variable, supplied by the host when it
    spawned this process. The server runs over stdio, whose pipe is 1:1 and
    carries no headers, so the host runs one process per caller and the
    identity is fixed for the life of the process. A missing identity raises
    :class:`AuthError`.

    In ``standalone`` mode (the default) the identity is fixed as
    ``"standalone"`` and the API key is read from config.

    Import of :func:`get_dct_config` is deferred to avoid circular imports.
    """
    # Deferred import to avoid circular dependency between config and core
    from dct_mcp_server.config.config import get_dct_config  # noqa: PLC0415

    config = get_dct_config(require_key=False)
    auth_mode: str = config.get("auth_mode", "standalone")

    if auth_mode == "embedded":
        # Identity is the per-process value the host set at spawn time.
        caller_id = config.get("client_id")
        if not caller_id:
            raise AuthError(
                "No caller identity in embedded auth mode. Supply the "
                "DCT_CLIENT_ID environment variable when spawning the "
                "server process."
            )
        logger.debug("Resolved embedded auth for caller %s", _mask(caller_id))
        return AuthContext(account_id=caller_id, api_key=None, auth_mode="embedded")

    # Standalone mode
    api_key: Optional[str] = config.get("api_key")
    logger.debug("Resolved standalone auth")
    return AuthContext(account_id="standalone", api_key=api_key, auth_mode="standalone")
