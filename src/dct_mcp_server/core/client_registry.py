"""
Thread-safe LRU-bounded registry of DCTAPIClient instances keyed by identity hash.
"""

import hashlib
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dct_mcp_server.core.logging import get_logger

if TYPE_CHECKING:
    from dct_mcp_server.core.auth import AuthContext

logger = get_logger(__name__)


class ClientRegistry:
    """Thread-safe LRU-bounded registry of DCTAPIClient instances keyed by identity hash."""

    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max_size
        self._cache: OrderedDict = OrderedDict()  # key=identity_hash, value=DCTAPIClient
        self._lock = threading.Lock()
        self._evicted: List = []  # Clients evicted from LRU; closed in close_all()

    def _identity_hash(self, auth_ctx) -> str:
        """Stable hash of the caller's identity — never logs raw values."""
        raw = f"{auth_ctx.account_id}:{auth_ctx.auth_mode}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_client(self, auth_ctx) -> "DCTAPIClient":
        """Return cached or new DCTAPIClient for the given AuthContext."""
        key = self._identity_hash(auth_ctx)
        with self._lock:
            if key in self._cache:
                # LRU: move to end
                self._cache.move_to_end(key)
                return self._cache[key]
            # Create new client
            from dct_mcp_server.dct_client.client import DCTAPIClient
            client = DCTAPIClient.for_identity(auth_ctx.account_id, auth_ctx.api_key)
            self._cache[key] = client
            self._cache.move_to_end(key)
            # Evict oldest if over limit; track for async close in close_all()
            if len(self._cache) > self._max_size:
                _oldest_key, oldest_client = self._cache.popitem(last=False)
                self._evicted.append(oldest_client)
                logger.debug("ClientRegistry: evicted entry (LRU limit=%d)", self._max_size)
            return client

    async def close_all(self) -> None:
        """Close all managed HTTP clients, including any LRU-evicted ones."""
        with self._lock:
            clients = list(self._cache.values()) + list(self._evicted)
            self._cache.clear()
            self._evicted.clear()
        for client in clients:
            try:
                await client.close()
            except Exception:
                pass
