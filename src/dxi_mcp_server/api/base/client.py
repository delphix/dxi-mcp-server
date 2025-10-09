from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseHttpClient(ABC):
    """
    Abstract base class for an HTTP client.
    This class defines the interface for making HTTP requests.
    """

    @abstractmethod
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a GET request to the specified path.
        """
        pass

    @abstractmethod
    async def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a POST request to the specified path.
        """
        pass

    @abstractmethod
    async def put(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a PUT request to the specified path.
        """
        pass

    @abstractmethod
    async def patch(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Sends a PATCH request to the specified path.
        """
        pass

    @abstractmethod
    async def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Sends a DELETE request to the specified path.
        """
        pass
