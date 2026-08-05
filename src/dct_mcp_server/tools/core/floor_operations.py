"""
Floor operation guard for the DCT MCP Server confirmation system.

Floor operations require individual single-use confirmation and cannot be
authorized by batch grant, standing approval, or any configuration value.

FR-007: Non-Relaxable Floor Operations
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

_MAPPINGS_DIR = Path(__file__).parent.parent.parent / "config" / "mappings"
_FLOOR_FILE = _MAPPINGS_DIR / "floor_operations.txt"


@lru_cache(maxsize=1)
def get_floor_patterns() -> Tuple[Tuple[str, str], ...]:
    """
    Load and return floor operation patterns from floor_operations.txt.

    Results are cached after the first call.

    Returns:
        Tuple of (method, pattern) tuples, e.g.
        (("DELETE", "*"), ("POST", "*/delete"), ("POST", "/dsources/delete"), ...)
    """
    patterns: List[Tuple[str, str]] = []

    if not _FLOOR_FILE.exists():
        logger.warning("floor_operations.txt not found: %s", _FLOOR_FILE)
        return tuple(patterns)

    with open(_FLOOR_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 1)
            if len(parts) == 2:
                method = parts[0].strip().upper()
                pattern = parts[1].strip()
                patterns.append((method, pattern))
                logger.debug("Loaded floor pattern: %s|%s", method, pattern)

    logger.info("Loaded %d floor operation patterns", len(patterns))
    return tuple(patterns)


def _floor_pattern_matches(pattern: str, path: str) -> bool:
    """
    Check if a path matches a floor operations path pattern.

    Supports:
      - ``*``           — matches any path
      - ``*/delete``    — glob-style wildcard; matches any path ending in ``/delete``
      - ``/foo/{id}``   — path parameter placeholders matched as ``[^/]+``

    Args:
        pattern: Path pattern from floor_operations.txt
        path:    Actual API path to test

    Returns:
        True if the path matches the pattern
    """
    if pattern == "*":
        return True

    if "*" in pattern:
        # Convert glob-style wildcard to a regex:  * → .*
        regex = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.fullmatch(regex, path))

    # Replace path-parameter placeholders {paramName} with [^/]+
    regex = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
    return bool(re.fullmatch(regex, path))


def is_floor_operation(method: str, path: str) -> bool:
    """
    Return True if the given HTTP operation is a non-relaxable floor operation.

    Floor operations require individual single-use confirmation and cannot be
    authorized by batch grant, standing approval, or any configuration value.

    Checks (in order, fastest first):
      1. Any HTTP DELETE          → True  (``DELETE|*`` wildcard)
      2. POST ending in ``/delete`` → True  (``POST|*/delete`` wildcard)
      3. Named explicit patterns from floor_operations.txt → True if matched

    Args:
        method: HTTP method string (e.g. ``"GET"``, ``"POST"``, ``"DELETE"``)
        path:   API endpoint path  (e.g. ``"/vdbs/vdb-123/delete"``)

    Returns:
        True if this is a floor operation, False otherwise
    """
    m = (method or "").upper()

    # Fast-path 1: any HTTP DELETE is a floor operation (DELETE|* wildcard)
    if m == "DELETE":
        return True

    # Fast-path 2: POST to a path ending in /delete (POST|*/delete wildcard)
    if m == "POST" and path.rstrip("/").endswith("/delete"):
        return True

    # Check remaining named explicit patterns from the file.
    # The two wildcard entries above are already handled, so we skip them here
    # to avoid redundant regex work.
    for pattern_method, pattern_path in get_floor_patterns():
        if pattern_method == "DELETE" and pattern_path == "*":
            continue
        if pattern_method == "POST" and pattern_path == "*/delete":
            continue

        if pattern_method != m:
            continue

        if _floor_pattern_matches(pattern_path, path):
            return True

    return False
