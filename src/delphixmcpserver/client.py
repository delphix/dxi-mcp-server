"""
DCT API Client module
"""

import asyncio
import contextlib
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

from .config import get_dct_config

logger = logging.getLogger("dct-api-client")


class DCTAPIClient:
    """Client for interacting with Delphix DCT API"""

    def __init__(self):
        self.config = get_dct_config()
        self.base_url = self.config["base_url"].rstrip("/")
        self.api_key = self.config["api_key"]
        self.verify_ssl = self.config["verify_ssl"]
        self.timeout = self.config["timeout"]
        self.max_retries = self.config["max_retries"]

        # Default headers
        self.headers = {
            "Authorization": f"apk {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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

    @contextlib.asynccontextmanager
    async def _session(self):
        """Context manager for HTTP client session"""
        client = await self._get_client()
        try:
            yield client
        except Exception as e:
            # If there's a connection error, close and create a new client next time
            logger.warning(f"Connection error: {str(e)}")
            await self.close()
            raise

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to DCT API with retry logic"""

        url = urljoin(f"{self.base_url}/dct/v3/", endpoint.lstrip("/"))

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
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"API request failed after {self.max_retries} attempts: {error_msg}"
                    )
                    raise Exception(error_msg)
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
                    raise
                else:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        # If we get here, all attempts failed
        raise Exception("All retry attempts failed")
