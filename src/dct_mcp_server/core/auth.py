"""
Authentication and per-request identity resolution for the DCT MCP Server.

Provides:
- _CALLER_ID_VAR: ContextVar that holds the X-CLIENT-ID value for the current request.
- AuthContext: dataclass returned by resolve_auth() describing the caller's identity.
- ClientIDMiddleware: raw ASGI middleware that extracts and validates X-CLIENT-ID.
- resolve_auth(): returns an AuthContext appropriate for the configured auth_mode.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from dct_mcp_server.core.exceptions import AuthError
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# ContextVar — holds the caller ID for the lifetime of each HTTP request
# ---------------------------------------------------------------------------

_CALLER_ID_VAR: ContextVar[Optional[str]] = ContextVar("_caller_id", default=None)


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
# ClientIDMiddleware — raw ASGI middleware (no Starlette dependency)
# ---------------------------------------------------------------------------


class ClientIDMiddleware:
    """ASGI middleware that extracts and validates the X-CLIENT-ID request header.

    Non-HTTP scopes (e.g. lifespan, websocket) are passed through unchanged.
    For HTTP requests the middleware:
      1. Reads the ``x-client-id`` header.
      2. Raises :class:`AuthError` if the header is absent or blank.
      3. Stores the value in :data:`_CALLER_ID_VAR` for the duration of the
         request, then resets it in a ``finally`` block.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # headers is List[Tuple[bytes, bytes]] with lower-cased header names
        caller_id: Optional[str] = None
        for name, value in scope.get("headers", []):
            if name == b"x-client-id":
                decoded = value.decode("utf-8").strip()
                if decoded:
                    caller_id = decoded
                break

        if not caller_id:
            logger.debug("Request rejected: X-CLIENT-ID header missing or empty")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "X-CLIENT-ID header is missing or empty"}',
                "more_body": False,
            })
            return

        logger.debug("Request received for caller %s", _mask(caller_id))

        token = _CALLER_ID_VAR.set(caller_id)
        # Lazily create the per-caller telemetry session when telemetry is enabled.
        # This ensures log_tool_call() finds a session logger for this caller.
        try:
            from dct_mcp_server.config.config import get_dct_config  # noqa: PLC0415
            _cfg = get_dct_config(require_key=False)
            if _cfg.get("is_local_telemetry_enabled"):
                from dct_mcp_server.core.session import get_or_create_caller_session
                get_or_create_caller_session(caller_id)
        except Exception:
            pass  # Non-fatal — session creation failure must not block the request
        try:
            await self.app(scope, receive, send)
        finally:
            _CALLER_ID_VAR.reset(token)


# ---------------------------------------------------------------------------
# resolve_auth
# ---------------------------------------------------------------------------


def resolve_auth() -> AuthContext:
    """Return an :class:`AuthContext` for the current request or process.

    In ``embedded`` auth mode the caller identity comes from the
    ``X-CLIENT-ID`` header stored in :data:`_CALLER_ID_VAR`.  The header is
    mandatory in this mode; a missing value raises :class:`AuthError`.

    In ``standalone`` mode (the default) the identity is fixed as
    ``"standalone"`` and the API key is read from config.

    Import of :func:`get_dct_config` is deferred to avoid circular imports.
    """
    # Deferred import to avoid circular dependency between config and core
    from dct_mcp_server.config.config import get_dct_config  # noqa: PLC0415

    config = get_dct_config(require_key=False)
    auth_mode: str = config.get("auth_mode", "standalone")

    if auth_mode == "embedded":
        caller_id = _CALLER_ID_VAR.get(None)
        if not caller_id:
            raise AuthError("X-CLIENT-ID is required in embedded auth mode")
        logger.debug("Resolved embedded auth for caller %s", _mask(caller_id))
        return AuthContext(account_id=caller_id, api_key=None, auth_mode="embedded")

    # Standalone mode
    api_key: Optional[str] = config.get("api_key")
    logger.debug("Resolved standalone auth")
    return AuthContext(account_id="standalone", api_key=api_key, auth_mode="standalone")
