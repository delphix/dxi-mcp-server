"""
Server-issued confirmation tokens for the execute() destructive-operation gate.

A bare ``confirmed=true`` on the first call must not be able to bypass a
destructive operation. The caller has to echo a ``confirmation_token`` that the
server only reveals inside the ``confirmation_required`` response. The token is
an HMAC of the operation identity keyed by a per-process secret, so it cannot be
precomputed — possessing the correct token proves the caller actually received
the ``confirmation_required`` response (and its STOP-and-ask instructions) before
re-calling.

The secret is regenerated on every server start. Tokens are therefore stable
within a single server session (an echoed token verifies) but are not guessable
by a client and do not persist across restarts.
"""

import hashlib
import hmac
import os

# Per-process secret. Regenerated each start; never logged or returned to clients.
_SECRET = os.urandom(32)


def make_confirmation_token(method: str, path: str) -> str:
    """Return the confirmation token for a (method, resolved-path) operation."""
    msg = f"{(method or '').upper()} {path}".encode()
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:32]


def verify_confirmation_token(token: str | None, method: str, path: str) -> bool:
    """Constant-time check that *token* matches the token for this operation."""
    if not token:
        return False
    return hmac.compare_digest(token, make_confirmation_token(method, path))
