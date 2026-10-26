"""
host_trust.py — shared nonce trust check for the sensitive-input gate.

Moved from tools/core/dynamic.py so that connector_secrets.py can import it
without creating a circular dependency.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# Name of the env var the embedding host injects at startup.
# Shared secret proving a `sensitive_applied` marker came from the embedding
# host and not from the model. The host generates it and passes it in this
# server's environment when it spawns the process (stdio embedded mode), so it
# never appears in a tool result, a prompt or the conversation. Unset
# (non-embedded deployments) => no marker is honoured and nothing changes.
_SENSITIVE_NONCE_ENV = "DCT_MCP_SENSITIVE_NONCE"


def host_nonce_ok(marker: Any) -> bool:
    """Return True if *marker* matches the process-startup nonce.

    The host (DCT AI Assistant) injects the nonce via ``_SENSITIVE_NONCE_ENV``
    at process startup and passes it back in ``sensitive_applied.marker``.
    A wrong or missing nonce means the ``sensitive_applied`` payload was not
    injected by the trusted host, so applied fields are not trusted.

    The marker must be a dict with a ``nonce`` key whose value matches the env
    var exactly. Unset (non-embedded deployments) => no marker is ever honoured.
    """
    expected = os.environ.get(_SENSITIVE_NONCE_ENV) or ""
    if not expected or not isinstance(marker, dict):
        return False
    return hmac.compare_digest(str(marker.get("nonce") or ""), expected)
