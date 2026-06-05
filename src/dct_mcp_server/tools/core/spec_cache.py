"""
OpenAPI Spec Cache Subsystem for DCT MCP Server — Dynamic Mode.

This module is INDEPENDENT of the existing tool_factory.py spec cache.  It
is only activated when DCT_TOOLSET=dynamic and is responsible for:

1. Downloading the DCT OpenAPI spec from {DCT_BASE_URL}/dct/static/api-external.yaml
2. Validating the spec (must be parseable YAML with top-level `openapi` and `paths`)
3. Persisting the spec to disk at DCT_SPEC_CACHE_PATH
4. Writing a .cache-meta.json sidecar with download timestamp and source URL
5. Respecting DCT_SPEC_MAX_AGE_HOURS — re-download only when the cached file is stale
6. Raising MCPError("SPEC_LOAD_FAILED") if the spec cannot be downloaded from DCT
   (and no fresh on-disk cache is available). There is no bundled-spec fallback:
   a failed download means DCT is unreachable, in which case the server cannot
   function anyway.

Hot path notes:
- load_and_cache_spec() is called once at server startup in async_main() via asyncio.to_thread()
- get_cached_spec() returns the in-memory dict that was set by load_and_cache_spec()
- A single retry is attempted on download failure; it does NOT use DCT_MAX_RETRIES (too slow
  for startup).
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

from dct_mcp_server.config.config import get_dct_config
from dct_mcp_server.core.exceptions import MCPError
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

# In-memory cache — set once by load_and_cache_spec(), read by get_cached_spec()
_cached_spec: dict[str, Any] | None = None

# Default cache path (mirrors tool_factory.py temp dir convention)
_DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "dct_mcp_tools")
_DEFAULT_CACHE_FILENAME = "api-external-dynamic.yaml"
_CACHE_META_FILENAME = ".cache-meta.json"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def load_and_cache_spec() -> dict[str, Any]:
    """
    Download, validate, and cache the DCT OpenAPI spec.

    Called once at server startup (from async_main() via asyncio.to_thread).
    Stores the parsed spec in the module-level _cached_spec variable.

    Returns:
        Parsed spec dict.

    Raises:
        MCPError: with code "SPEC_LOAD_FAILED" if the spec cannot be downloaded
                  from DCT and no fresh on-disk cache is available.
    """
    global _cached_spec

    dct_config = get_dct_config()
    base_url: str = dct_config.get("base_url", "")
    api_key: str = dct_config.get("api_key", "")
    verify_ssl: bool = dct_config.get("verify_ssl", False)
    timeout: int = dct_config.get("timeout", 30)
    max_age_hours: int = int(dct_config.get("spec_max_age_hours", 24))
    cache_path_str: str = dct_config.get(
        "spec_cache_path",
        os.path.join(_DEFAULT_CACHE_DIR, _DEFAULT_CACHE_FILENAME),
    )
    cache_path = Path(cache_path_str)

    # ------------------------------------------------------------------ #
    # Step 1 — Check if cached file is still fresh
    # ------------------------------------------------------------------ #
    if _should_use_cache(cache_path, max_age_hours):
        spec = _load_from_disk(cache_path)
        if spec is not None:
            logger.info("Using cached OpenAPI spec from %s (within max age)", cache_path)
            _cached_spec = spec
            return _cached_spec

    # ------------------------------------------------------------------ #
    # Step 2 — Attempt live download
    # ------------------------------------------------------------------ #
    spec = _download_spec(base_url, api_key, verify_ssl, timeout)
    if spec is not None:
        _write_cache(cache_path, spec, base_url)
        _cached_spec = spec
        return _cached_spec

    # ------------------------------------------------------------------ #
    # Step 3 — Download failed and no fresh cache — fatal
    # ------------------------------------------------------------------ #
    # There is no bundled-spec fallback: a failed download means DCT is
    # unreachable, in which case the server cannot serve any DCT API call.
    raise MCPError(
        f"SPEC_LOAD_FAILED: Could not download the DCT OpenAPI spec from "
        f"{base_url.rstrip('/')}/dct/static/api-external.yaml. "
        "Check DCT_BASE_URL / DCT_API_KEY and connectivity to the DCT instance."
    )


def get_cached_spec() -> dict[str, Any] | None:
    """Return the in-memory cached spec, or None if not yet loaded."""
    return _cached_spec


def clear_spec_cache() -> None:
    """Clear the in-memory spec cache (mainly used for testing)."""
    global _cached_spec
    _cached_spec = None


# --------------------------------------------------------------------------- #
# Private helpers
# --------------------------------------------------------------------------- #

def _should_use_cache(cache_path: Path, max_age_hours: int) -> bool:
    """Return True if the cache file exists and is younger than max_age_hours."""
    if not cache_path.exists():
        return False
    meta = _read_cache_meta(cache_path)
    if meta is None:
        # No meta file — treat as stale so we attempt a fresh download
        return False
    downloaded_at_str = meta.get("downloaded_at")
    if not downloaded_at_str:
        return False
    try:
        downloaded_at = datetime.fromisoformat(downloaded_at_str)
        age_hours = (datetime.now(timezone.utc) - downloaded_at).total_seconds() / 3600
        return age_hours < max_age_hours
    except (ValueError, TypeError):
        return False


def _read_cache_meta(cache_path: Path) -> dict | None:
    """Read the .cache-meta.json sidecar adjacent to cache_path."""
    meta_path = cache_path.parent / _CACHE_META_FILENAME
    if not meta_path.exists():
        return None
    try:
        with open(meta_path) as f:
            return json.load(f)
    except Exception as exc:
        logger.debug("Could not read cache meta from %s: %s", meta_path, exc)
        return None


def _write_cache_meta(cache_path: Path, dct_base_url: str) -> None:
    """Write/update the .cache-meta.json sidecar adjacent to cache_path."""
    meta_path = cache_path.parent / _CACHE_META_FILENAME
    meta = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "dct_base_url": dct_base_url,
        "spec_path": str(cache_path),
    }
    try:
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        logger.debug("Cache meta written to %s", meta_path)
    except Exception as exc:
        logger.warning("Could not write cache meta to %s: %s", meta_path, exc)


def _load_from_disk(cache_path: Path) -> dict | None:
    """Parse the cached YAML spec from disk; return None if missing/invalid."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            spec = yaml.safe_load(f)
        if _validate_spec(spec):
            return spec
        logger.warning("Cached spec at %s failed validation — will re-download", cache_path)
        return None
    except Exception as exc:
        logger.warning("Could not load cached spec from %s: %s", cache_path, exc)
        return None


def _download_spec(
    base_url: str, api_key: str, verify_ssl: bool, timeout: int
) -> dict | None:
    """
    Download the DCT OpenAPI spec via HTTP GET.

    Attempts one retry on transient failures.  Returns None (non-fatal) on any
    error so the caller can fall through to the bundled spec.
    """
    if not base_url:
        logger.warning("DCT_BASE_URL not set — cannot download OpenAPI spec")
        return None

    spec_url = f"{base_url.rstrip('/')}/dct/static/api-external.yaml"
    headers: dict[str, str] = {
        "Accept": "application/x-yaml, text/yaml, application/json",
        "User-Agent": "dct-mcp-server/dynamic-mode",
    }
    if api_key:
        headers["Authorization"] = f"apk {api_key}"

    for attempt in (1, 2):
        try:
            logger.info(
                "Downloading OpenAPI spec from %s (attempt %d)…", spec_url, attempt
            )
            response = requests.get(
                spec_url,
                headers=headers,
                timeout=timeout,
                verify=verify_ssl,
            )
            response.raise_for_status()
            spec = yaml.safe_load(response.text)
            if not _validate_spec(spec):
                logger.warning(
                    "Downloaded spec from %s failed structural validation — "
                    "missing 'openapi' or 'paths' key",
                    spec_url,
                )
                return None
            logger.info(
                "OpenAPI spec downloaded: %d paths", len(spec.get("paths", {}))
            )
            return spec
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            # Do not log the API key
            logger.warning(
                "Spec download failed: HTTP %s from %s",
                status,
                spec_url,
            )
            return None  # HTTP errors (e.g. 401) won't be fixed by a retry
        except Exception as exc:
            logger.warning("Spec download attempt %d failed: %s", attempt, exc)
            if attempt == 2:
                return None
    return None


def _write_cache(cache_path: Path, spec: dict, dct_base_url: str) -> None:
    """Persist the downloaded spec to disk and write the sidecar meta file."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            yaml.dump(spec, f, allow_unicode=True, default_flow_style=False)
        _write_cache_meta(cache_path, dct_base_url)
        logger.info("OpenAPI spec cached to %s", cache_path)
    except OSError as exc:
        # Read-only filesystem or permission error — non-fatal, use in-memory only
        logger.warning(
            "Could not write spec cache to %s (non-fatal): %s", cache_path, exc
        )


def _validate_spec(spec: Any) -> bool:
    """Return True if spec is a dict with both 'openapi' and 'paths' keys."""
    return (
        isinstance(spec, dict)
        and "openapi" in spec
        and "paths" in spec
        and isinstance(spec["paths"], dict)
    )
