"""
Shared pytest fixtures for generated tests in .claude/test/generated-test/.

Sets test env vars so unit-style tests can call get_dct_config() and
DCTAPIClient() without real credentials. Mirrors the _set_test_env fixture
in tests/conftest.py.
"""

import pytest


@pytest.fixture(autouse=True)
def _set_generated_test_env(monkeypatch):
    """Set required env vars for generated unit tests that call get_dct_config()."""
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.test")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")
    monkeypatch.setenv("DCT_TIMEOUT", "30")
    monkeypatch.setenv("DCT_MAX_RETRIES", "3")
    monkeypatch.setenv("DCT_LOG_LEVEL", "ERROR")
