"""
DCT API Client module
"""

import asyncio
import contextlib
import importlib.metadata
import os
import re as _re
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

from dct_mcp_server.config import get_dct_config
from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)


def _mask_secret(value: str) -> str:
    """Return a masked version of a secret string safe for logging."""
    if not value:
        return "***"
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]


class SecretGuard:
    """Prevents raw secrets from appearing in tool arguments."""

    # Pattern 1: DCT API key prefix
    _APK_PATTERN = _re.compile(r"^apk\s+", _re.IGNORECASE)
    # Pattern 2: base64-like token longer than 32 chars
    _B64_PATTERN = _re.compile(r"^[A-Za-z0-9+/=]{33,}$")

    @staticmethod
    def check(kwargs: dict) -> None:
        """Raise DCTClientError if any kwarg value looks like a raw secret."""
        for key, value in kwargs.items():
            if not isinstance(value, str):
                continue
            if SecretGuard._APK_PATTERN.match(value):
                raise DCTClientError(
                    f"Tool argument '{key}' appears to contain a raw DCT API key "
                    f"(matched 'apk ' prefix). Use a credential alias instead."
                )
            if SecretGuard._B64_PATTERN.match(value):
                raise DCTClientError(
                    f"Tool argument '{key}' appears to contain a raw secret token "
                    f"(base64-like string > 32 chars). Use a credential alias instead."
                )


class DCTAPIClient:
    """Client for interacting with Delphix DCT API"""

    def __init__(self):
        self.config = get_dct_config()
        self.base_url = self.config["base_url"].rstrip("/")
        self.api_key = self.config["api_key"]
        self.verify_ssl = self.config["verify_ssl"]
        self.timeout = self.config["timeout"]
        self.max_retries = self.config["max_retries"]

        # Get project version for User-Agent
        try:
            version = importlib.metadata.version("dct-mcp-server")
        except importlib.metadata.PackageNotFoundError:
            version = "2026.0.1.0-preview"

        # Default headers
        self.headers = {
            "Authorization": f"apk {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"dct-mcp-server/{version}",
        }

        # Create a client that can be reused
        self._client = None

    async def _get_client(self):
        """Get or create the HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(verify=self.verify_ssl)
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @classmethod
    def for_identity(
        cls, account_id: str, api_key: Optional[str] = None
    ) -> "DCTAPIClient":
        """Create a DCTAPIClient instance for a specific embedded-mode identity.

        The account_id is used as the X-CLIENT-ID internal trust header value.
        The 'apk ' prefix is NOT prepended — account IDs are not API keys.
        Never log the raw account_id.
        """
        from dct_mcp_server.config.config import get_dct_config

        config = get_dct_config(require_key=False)
        instance = cls.__new__(cls)
        instance.config = config
        instance.base_url = config["base_url"].rstrip("/")
        instance.api_key = api_key  # may be None in embedded mode
        instance.verify_ssl = config["verify_ssl"]
        instance.timeout = config["timeout"]
        instance.max_retries = config["max_retries"]
        try:
            import importlib.metadata

            version = importlib.metadata.version("dct-mcp-server")
        except Exception:
            version = "2026.0.1.0-preview"
        # Use X-CLIENT-ID header for embedded-mode identity; no Authorization header.
        # Embedded mode == the DCT AI Assistant driving the server, so tag every
        # DCT API call for source attribution (PPM-1727). Standalone/local clients
        # (DCTAPIClient.__init__) are deliberately left unattributed.
        instance.headers = {
            "X-CLIENT-ID": account_id,  # Internal DCT trust header; not Authorization
            "X-Dct-Client-Name": "Delphix AI Assistant",  # PPM-1727 source attribution
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"Delphix-AI-Assistant/{version}",
        }
        instance._client = None
        logger.debug("Created per-identity client for %s", _mask_secret(account_id))
        return instance

    @contextlib.asynccontextmanager
    async def _session(self):
        """Context manager for HTTP client session"""
        client = await self._get_client()
        try:
            yield client
        except httpx.HTTPStatusError:
            # Let HTTP status errors (4xx/5xx) propagate to the retry handler
            # in make_request, which extracts the response body for diagnostics.
            raise
        except Exception as e:
            # Actual connection/transport errors — close and recreate client
            logger.warning(f"Connection error: {str(e)}")
            await self.close()
            raise DCTClientError(f"A connection error occurred: {e}") from e

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to DCT API with retry logic"""

        # The API path prefix is configurable so the client can target either the
        # external proxy path ("dct/v3", the default) or an internal DCT gateway
        # that serves "/v3" directly. Set DCT_API_PATH_PREFIX="v3" for the latter.
        _prefix = os.getenv("DCT_API_PATH_PREFIX", "dct/v3").strip("/")
        url = urljoin(
            f"{self.base_url}/" + (f"{_prefix}/" if _prefix else ""),
            endpoint.lstrip("/"),
        )

        # Use json parameter if provided, otherwise use data
        json_data = json if json is not None else data

        for attempt in range(self.max_retries):
            try:
                async with self._session() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        json=json_data,
                        params=params,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()

                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    ):
                        return response.json()
                    else:
                        return {"response": response.text}

            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
                # Don't retry client errors (4xx) — the request itself is wrong
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error (not retrying): {error_msg}")
                    raise DCTClientError(error_msg) from e
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"API request failed after {self.max_retries} attempts: {error_msg}"
                    )
                    raise DCTClientError(error_msg) from e
                else:
                    logger.warning(
                        f"API request failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Request failed after {self.max_retries} attempts: {str(e)}"
                    )
                    raise DCTClientError(
                        f"Request failed after {self.max_retries} attempts"
                    ) from e
                else:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        # If we get here, all attempts failed
        raise DCTClientError("All retry attempts failed")
