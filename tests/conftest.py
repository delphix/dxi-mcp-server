"""
Shared pytest fixtures for the dct-mcp-server test suite.

Two fixtures are registered here as autouse to prevent two common failure modes:

1. ``set_env_vars`` (session scope): sets DCT_API_KEY and DCT_BASE_URL in the
   process environment before any test module is imported.  Without these,
   ``DCTAPIClient.__init__`` calls ``get_dct_config()`` which raises ValueError
   on the missing API key — causing collection-time ImportErrors.

2. ``reset_cache`` (function scope): calls ``clear_cache()`` before every test.
   ``config/loader.py`` uses ``@lru_cache`` on several loader functions; without
   this fixture, state from one test bleeds into the next, making test-order
   dependencies possible.

   IMPORTANT: the fixture must call ``clear_cache()`` at the *start* of each
   test (not teardown), because the cache may already be warm when the test
   body begins executing.
"""

import os

import pytest

from dct_mcp_server.config.loader import clear_cache


@pytest.fixture(scope="session", autouse=True)
def set_env_vars():
    """Set required environment variables for the entire test session.

    Uses ``os.environ`` directly (rather than monkeypatch) because pytest's
    ``monkeypatch`` fixture is function-scoped by default; a session-scoped
    fixture cannot accept a function-scoped fixture as a parameter.
    """
    os.environ.setdefault("DCT_API_KEY", "test-key")
    os.environ.setdefault("DCT_BASE_URL", "http://localhost:9999")
    yield
    # Leave env vars in place — removing them during teardown can cause
    # issues if the test session is used in a long-running process.


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the loader lru_cache before each test to prevent state leakage."""
    clear_cache()
    yield
