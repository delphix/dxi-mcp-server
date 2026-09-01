"""
Sliding-window per-identity velocity counter.

Detects when a single caller makes N or more calls to the same operation
within a sliding time window of T seconds, triggering a batch confirmation.

FR-006: Per-Identity Velocity Detection

Key: (caller_identity, method, path_template)
Value: deque of timestamps (float, seconds since epoch)

The counter is NOT reset after a user declines the batch confirmation —
there is no retry amnesty (ERR-7 from the functional spec).
"""

import collections
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# Persistence mode: set DCT_BATCH_COUNTER_PERSISTENCE=file to enable file persistence
_PERSISTENCE_MODE = os.environ.get("DCT_BATCH_COUNTER_PERSISTENCE", "memory").lower()

# Path for file-based persistence
_COUNTER_FILE_DIR = (
    Path(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp"))) / "dct_mcp_tools"
)
_COUNTER_FILE_PATH = _COUNTER_FILE_DIR / "velocity_counters.json"


class VelocityCounter:
    """Thread-safe sliding-window per-identity velocity counter.

    Stores a deque of timestamps for each (identity, method, path_template) key.
    Only timestamps within the last T seconds count toward the threshold.
    """

    def __init__(self) -> None:
        # Maps (identity, method, path_template) -> deque of float timestamps
        self._counters: dict[tuple[str, str, str], collections.deque] = {}
        self._lock = threading.Lock()

        if _PERSISTENCE_MODE == "file":
            self._load_from_file()

    def _load_from_file(self) -> None:
        """Load persisted counters from disk (best-effort).

        If the file is corrupted or unreadable, reset to empty state and log
        a warning (ERR-6).
        """
        if not _COUNTER_FILE_PATH.exists():
            return

        try:
            raw = _COUNTER_FILE_PATH.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)

            for key_str, timestamps in data.items():
                # key_str is serialized as "identity|method|path_template"
                parts = key_str.split("|", 2)
                if len(parts) != 3:
                    logger.warning(
                        "velocity_counter: skipping malformed key in persistence file: %s",
                        key_str,
                    )
                    continue
                identity, method, path_template = parts
                key = (identity, method, path_template)

                if not isinstance(timestamps, list):
                    logger.warning(
                        "velocity_counter: unexpected timestamp format for key %s; skipping",
                        key_str,
                    )
                    continue

                # We don't know T at load time, so we keep all timestamps and
                # let increment_and_check prune them lazily based on the caller's T.
                deque: collections.deque = collections.deque(
                    ts for ts in timestamps if isinstance(ts, (int, float))
                )
                if deque:
                    self._counters[key] = deque

            logger.debug(
                "velocity_counter: loaded %d counter(s) from %s",
                len(self._counters),
                _COUNTER_FILE_PATH,
            )

        except (json.JSONDecodeError, OSError, ValueError, TypeError) as exc:
            # ERR-6: corrupted file — reset to empty and continue
            logger.warning(
                "velocity_counter: persistence file is corrupted (%s); resetting to empty state. "
                "File: %s",
                exc,
                _COUNTER_FILE_PATH,
            )
            self._counters = {}

    def _save_to_file(self) -> None:
        """Persist current counter state to disk (best-effort).

        Failures are logged as warnings but do not raise.
        """
        try:
            _COUNTER_FILE_DIR.mkdir(parents=True, exist_ok=True)

            data: dict[str, list[float]] = {}
            for (identity, method, path_template), timestamps in self._counters.items():
                key_str = f"{identity}|{method}|{path_template}"
                data[key_str] = list(timestamps)

            _COUNTER_FILE_PATH.write_text(json.dumps(data), encoding="utf-8")

        except OSError as exc:
            logger.warning(
                "velocity_counter: failed to persist counters to file: %s", exc
            )

    def increment_and_check(
        self,
        identity: str,
        method: str,
        path_template: str,
        N: int,
        T: int,
    ) -> tuple[bool, int]:
        """Increment the counter for (identity, method, path_template) and check threshold.

        Uses a sliding window of T seconds. Only calls within the last T seconds count.

        Args:
            identity: Caller identity (process UUID or X-CLIENT-ID header value)
            method: HTTP method (POST, DELETE, etc.)
            path_template: URL path template (not the resolved path)
            N: Threshold count (trigger when count >= N)
            T: Window in seconds

        Returns:
            (triggered: bool, count: int)
            triggered is True when count >= N after this increment.
            count is the number of calls within the window after this increment.
        """
        key = (identity, method, path_template)
        now = time.time()
        cutoff = now - T

        with self._lock:
            if key not in self._counters:
                self._counters[key] = collections.deque()

            dq = self._counters[key]

            # Prune entries outside the sliding window
            while dq and dq[0] < cutoff:
                dq.popleft()

            # Add current timestamp
            dq.append(now)

            count = len(dq)
            triggered = count >= N

            if _PERSISTENCE_MODE == "file":
                self._save_to_file()

        return triggered, count

    def reset_counter(self, identity: str, method: str, path_template: str) -> None:
        """Reset the counter for a specific (identity, method, path_template) key.

        NOTE: This should NOT be called when a user declines a batch confirmation.
        There is no retry amnesty (ERR-7). Only reset for testing or explicit expiry.
        """
        key = (identity, method, path_template)
        with self._lock:
            self._counters.pop(key, None)

            if _PERSISTENCE_MODE == "file":
                self._save_to_file()


# Module-level singleton
_velocity_counter = VelocityCounter()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def increment_and_check(
    identity: str,
    method: str,
    path_template: str,
    N: int,
    T: int,
) -> tuple[bool, int]:
    """Increment the counter for (identity, method, path_template) and check threshold.

    Uses a sliding window of T seconds. Only calls within the last T seconds count.

    Args:
        identity: Caller identity (process UUID or X-CLIENT-ID header value)
        method: HTTP method (POST, DELETE, etc.)
        path_template: URL path template (not the resolved path)
        N: Threshold count (trigger when count >= N)
        T: Window in seconds

    Returns:
        (triggered: bool, count: int)
        triggered is True when count >= N after this increment.
        count is the number of calls within the window after this increment.
    """
    return _velocity_counter.increment_and_check(identity, method, path_template, N, T)


def reset_counter(identity: str, method: str, path_template: str) -> None:
    """Reset the counter for a specific (identity, method, path_template) key.

    NOTE: This should NOT be called when a user declines a batch confirmation.
    There is no retry amnesty (ERR-7). Only reset for testing or explicit expiry.
    """
    _velocity_counter.reset_counter(identity, method, path_template)
