"""
Shared pytest fixtures for the dct-mcp-server test suite.

Three fixtures are registered here as autouse:

1. ``pytest_configure``: loads DCT credentials from .claude/settings.local.json
   so L4/L5 tests find real credentials when pytest is run directly.

2. ``_set_test_env`` (function scope): sets test env vars via monkeypatch; skips
   for @pytest.mark.real_dct tests so real credentials flow through unchanged.

3. ``reset_cache`` (function scope): calls ``clear_cache()`` before every test.
   ``config/loader.py`` uses ``@lru_cache``; without this, state bleeds between tests.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pydantic import RootModel  # noqa: F401  — ensures pydantic registers before mcp imports

import pytest

from dct_mcp_server.config.loader import clear_cache


def pytest_configure(config):
    """Load DCT credentials from .claude/settings.local.json into os.environ.

    Lets L4/L5 tests find real credentials when pytest is run directly
    (outside a Claude Code session). No-op if vars are already set.
    """
    if os.environ.get("DCT_API_KEY") and os.environ.get("DCT_BASE_URL"):
        return
    settings = Path(__file__).resolve().parents[1] / ".claude" / "settings.local.json"
    if not settings.exists():
        return
    try:
        data = json.loads(settings.read_text())
        env = data.get("env", {})
        for key in ("DCT_API_KEY", "DCT_BASE_URL"):
            if key not in os.environ and env.get(key):
                os.environ[key] = env[key]
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch, request):
    """Set env vars for unit/integration/functional tests; skip for real_dct tests."""
    if request.node.get_closest_marker("real_dct"):
        return
    monkeypatch.setenv("DCT_API_KEY", "test-api-key")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.test")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")
    monkeypatch.setenv("DCT_TIMEOUT", "30")
    monkeypatch.setenv("DCT_MAX_RETRIES", "3")
    monkeypatch.setenv("DCT_LOG_LEVEL", "ERROR")


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the loader lru_cache before each test to prevent state leakage."""
    clear_cache()
    yield


@pytest.fixture
def mock_dct_client():
    """A MagicMock for DCTAPIClient; make_request is an AsyncMock."""
    client = MagicMock()
    client.make_request = AsyncMock(return_value={"items": []})
    return client
