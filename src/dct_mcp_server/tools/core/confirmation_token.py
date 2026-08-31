"""
Server-issued confirmation tokens for the execute() destructive-operation gate.

A bare ``confirmed=true`` on the first call must not be able to bypass a
destructive operation. The caller has to echo a ``confirmation_token`` that the
server only reveals inside the ``confirmation_required`` response. The token is
an HMAC of the operation identity (method, path, canonical request body) keyed
by a per-process secret, so it cannot be precomputed — possessing the correct
token proves the caller actually received the ``confirmation_required`` response
(and its STOP-and-ask instructions) before re-calling.

Tokens are body-bound (FR-001): the HMAC input includes a deterministic
serialisation of the request body, so a token issued for one set of parameters
does not authorise a different set.  Tokens are also single-use: ``issue_token``
registers them in ``ConsumedTokenStore`` and ``verify_and_consume_token`` removes
them atomically on first successful verification.

The secret is regenerated on every server start. Tokens are therefore stable
within a single server session (an echoed token verifies) but are not guessable
by a client and do not persist across restarts.
"""

import hashlib
import hmac
import json
import os

# Per-process secret. Regenerated each start; never logged or returned to clients.
_SECRET = os.urandom(32)


def canonical_json(body: dict | None) -> str:
    """Deterministic JSON serialization for body-bound token generation.

    Keys are sorted lexicographically at every nesting level (recursively).
    No insignificant whitespace. Empty or None body serializes to "{}".

    EC-1: canonical_json(None) == canonical_json({}) == "{}"
    EC-2: Nested objects and lists have all dict keys sorted recursively.
    AC-3: Different key order on two calls produces identical output.
    """
    if not body:
        return "{}"
    # json.dumps with sort_keys=True handles nested sorting recursively
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def make_confirmation_token(method: str, path: str, body: dict | None = None) -> str:
    """Return the body-bound confirmation token for (method, resolved-path, body).

    The body is canonicalized before hashing so key-order variations between
    the two calls produce the same token (AC-3 from FR-001).
    """
    body_canonical = canonical_json(body)
    msg = f"{(method or '').upper()} {path} {body_canonical}".encode()
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:32]


def issue_token(
    method: str,
    path: str,
    body: dict | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Issue a new body-bound single-use confirmation token.

    Computes the HMAC token and registers it in the pending-token store with TTL.
    The caller must use verify_and_consume_token() on the second call — not
    make_confirmation_token() directly.

    FR-001 processing step 1c: stores (token, timestamp) in pending-token set.
    """
    token = make_confirmation_token(method, path, body)
    from dct_mcp_server.tools.core.confirmation_store import _consumed_token_store

    _consumed_token_store.add(token, ttl_seconds)
    return token


def verify_and_consume_token(
    token: str | None,
    method: str,
    path: str,
    body: dict | None = None,
    ttl_seconds: int = 3600,
) -> bool:
    """Verify a body-bound single-use token and consume it atomically.

    Returns True only if:
      1. token is not None/empty
      2. token matches HMAC(method, path, canonical_json(body))
      3. token is in the pending-token store (was issued and not yet consumed)
      4. token has not expired (TTL check on lookup)

    Side effect: removes the token from the pending store on success.

    FR-001 AC-1: Token for body A does not verify with body B.
    FR-001 AC-2: Consumed token cannot be reused.
    FR-001 AC-3: Key order does not matter (canonicalization is stable).
    EC-3: Thread-safe — only one concurrent consumer proceeds.
    """
    if not token:
        return False
    expected = make_confirmation_token(method, path, body)
    if not hmac.compare_digest(token, expected):
        return False
    # Consume from the pending store — returns True only if it was pending and not expired
    from dct_mcp_server.tools.core.confirmation_store import _consumed_token_store

    return _consumed_token_store.consume(token)


def verify_confirmation_token(token: str | None, method: str, path: str) -> bool:
    """Constant-time check that *token* matches the token for this operation.

    .. deprecated::
        Use ``verify_and_consume_token()`` for new call sites.  This function
        does not enforce single-use semantics or body binding; it exists only
        for backward compatibility with callers that have not yet been migrated.
    """
    if not token:
        return False
    return hmac.compare_digest(token, make_confirmation_token(method, path))
