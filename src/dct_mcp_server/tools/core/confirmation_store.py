"""
In-memory stores for single-use confirmation tokens and scoped batch grants.

Both stores are module-level singletons reset on server restart.
Thread-safe via threading.Lock. TTL sweep occurs on every lookup.

FR-001: ConsumedTokenStore — single-use body-bound token enforcement
FR-004: GrantStore — scoped batch grant lifecycle
"""

import threading
import time
from dataclasses import dataclass

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _TokenEntry:
    expiry: float  # wall-clock time.time() value


@dataclass
class GrantEntry:
    grant_id: str
    operation: str
    targets: list  # list of canonical target bodies
    remaining: int
    expiry: float  # wall-clock time.time() value


class ConsumedTokenStore:
    """Thread-safe in-memory store for single-use confirmation tokens with TTL.

    Tokens are added with a TTL and can only be consumed once. Replaying a
    token after consumption returns False. Expired tokens are swept on every
    lookup.

    FR-001: single-use body-bound token enforcement.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps token -> _TokenEntry (present == pending, absent == consumed or never added)
        self._pending: dict[str, _TokenEntry] = {}

    def _sweep_expired(self) -> None:
        """Remove all entries where now >= expiry. Must be called with lock held."""
        now = time.time()
        expired = [tok for tok, entry in self._pending.items() if now >= entry.expiry]
        for tok in expired:
            del self._pending[tok]
            logger.debug("ConsumedTokenStore: swept expired token %s", tok[:8])

    def add(self, token: str, ttl_seconds: int) -> None:
        """Register *token* as a pending single-use token that expires after *ttl_seconds*."""
        expiry = time.time() + ttl_seconds
        with self._lock:
            self._pending[token] = _TokenEntry(expiry=expiry)
            logger.debug(
                "ConsumedTokenStore: added token %s ttl=%s", token[:8], ttl_seconds
            )

    def consume(self, token: str) -> bool:
        """Consume *token*, returning True iff it was present, not expired, and not already consumed.

        Removes the token atomically so a second call with the same token always
        returns False (replay protection).
        """
        with self._lock:
            self._sweep_expired()
            entry = self._pending.pop(token, None)
            if entry is None:
                logger.debug(
                    "ConsumedTokenStore: consume miss (absent/consumed/expired) for %s",
                    token[:8],
                )
                return False
            logger.debug("ConsumedTokenStore: consumed token %s", token[:8])
            return True

    def is_pending(self, token: str) -> bool:
        """Return True if *token* exists and has not expired. Does NOT consume the token."""
        with self._lock:
            self._sweep_expired()
            return token in self._pending


class GrantStore:
    """Thread-safe in-memory store for scoped batch grants with TTL.

    A grant authorises a caller to execute a specific operation against a
    bounded list of target canonical bodies. Each target may be consumed at
    most once. The grant expires after *ttl_seconds* regardless of remaining
    uses.

    FR-004: scoped batch grant lifecycle.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._grants: dict[str, GrantEntry] = {}

    def _is_expired(self, entry: GrantEntry) -> bool:
        return time.time() >= entry.expiry

    def create_grant(
        self,
        grant_id: str,
        operation: str,
        targets: list[str],
        ttl_seconds: int,
    ) -> None:
        """Create a new grant identified by *grant_id*.

        *targets* is the list of canonical request bodies authorised for this
        grant. *remaining* starts at len(targets).
        """
        expiry = time.time() + ttl_seconds
        entry = GrantEntry(
            grant_id=grant_id,
            operation=operation,
            targets=list(targets),
            remaining=len(targets),
            expiry=expiry,
        )
        with self._lock:
            self._grants[grant_id] = entry
            logger.debug(
                "GrantStore: created grant %s op=%s targets=%d ttl=%s",
                grant_id,
                operation,
                len(targets),
                ttl_seconds,
            )

    def consume_target(self, grant_id: str, target_canonical: str) -> str:
        """Attempt to consume *target_canonical* from grant *grant_id*.

        Returns one of:
        - ``"ok"``             — target was present, consumed successfully
        - ``"not_found"``      — target not in grant's target list (or already consumed)
        - ``"exhausted"``      — remaining count is 0 (all targets already consumed)
        - ``"expired"``        — grant TTL has elapsed
        - ``"grant_missing"``  — no grant with this ID exists
        """
        with self._lock:
            entry = self._grants.get(grant_id)
            if entry is None:
                logger.debug("GrantStore: consume_target grant_missing id=%s", grant_id)
                return "grant_missing"

            if self._is_expired(entry):
                del self._grants[grant_id]
                logger.debug("GrantStore: consume_target expired id=%s", grant_id)
                return "expired"

            if entry.remaining <= 0:
                logger.debug("GrantStore: consume_target exhausted id=%s", grant_id)
                return "exhausted"

            if target_canonical not in entry.targets:
                logger.debug(
                    "GrantStore: consume_target not_found id=%s target=%s",
                    grant_id,
                    target_canonical[:32],
                )
                return "not_found"

            entry.targets.remove(target_canonical)
            entry.remaining -= 1
            logger.debug(
                "GrantStore: consume_target ok id=%s remaining=%d",
                grant_id,
                entry.remaining,
            )
            return "ok"

    def get_grant(self, grant_id: str) -> GrantEntry | None:
        """Return the GrantEntry for *grant_id*, or None if missing or expired."""
        with self._lock:
            entry = self._grants.get(grant_id)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._grants[grant_id]
                return None
            return entry

    def get_remaining(self, grant_id: str) -> int | None:
        """Return remaining target count for *grant_id*, or None if missing or expired."""
        entry = self.get_grant(grant_id)
        if entry is None:
            return None
        return entry.remaining


# Module-level singletons — reset on server restart.
_consumed_token_store = ConsumedTokenStore()
_grant_store = GrantStore()
