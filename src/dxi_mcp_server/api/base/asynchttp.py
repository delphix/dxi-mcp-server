from typing import Any, Dict, Optional
import aiohttp
from .client import BaseHttpClient


class AsyncHttp(BaseHttpClient):
    """
    An asynchronous HTTP client using aiohttp.
    This class is designed to be used as an async context manager.
    """

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.headers = headers or {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """
        Initializes the aiohttp ClientSession.
        """
        self._session = aiohttp.ClientSession(
            base_url=self.base_url, headers=self.headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the aiohttp ClientSession.
        """
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        """
        Returns the aiohttp ClientSession, raising an error if it's not initialized.
        """
        if self._session is None or self._session.closed:
            raise RuntimeError(
                "Session is not active. Use 'async with' context manager."
            )
        return self._session

    def _get_request_headers(
        self, headers: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Merges session headers with request-specific headers.
        """
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        return request_headers

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a GET request to the specified path.
        """
        request_headers = self._get_request_headers(headers)
        async with self.session.get(path, params=params, headers=request_headers) as response:
            response.raise_for_status()
            return await response.json()

    async def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a POST request to the specified path.
        """
        request_headers = self._get_request_headers(headers)
        async with self.session.post(path, json=data, headers=request_headers) as response:
            response.raise_for_status()
            return await response.json()

    async def put(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a PUT request to the specified path.
        """
        request_headers = self._get_request_headers(headers)
        async with self.session.put(path, json=data, headers=request_headers) as response:
            response.raise_for_status()
            return await response.json()

    async def patch(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a PATCH request to the specified path.
        """
        request_headers = self._get_request_headers(headers)
        async with self.session.patch(path, json=data, headers=request_headers) as response:
            response.raise_for_status()
            return await response.json()

    async def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Sends a DELETE request to the specified path.
        """
        request_headers = self._get_request_headers(headers)
        async with self.session.delete(path, headers=request_headers) as response:
            response.raise_for_status()
            return await response.json()
