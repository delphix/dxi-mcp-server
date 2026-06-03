"""
Layer 1 unit tests for config.py env-var parsing/validation.

These manage their own env explicitly via monkeypatch (clearing optional vars)
so they assert true defaults rather than the placeholder values set by the
autouse _set_test_env fixture.
"""

import pytest

from dct_mcp_server.config.config import get_dct_config

_OPTIONAL_VARS = [
    "DCT_BASE_URL",
    "DCT_VERIFY_SSL",
    "DCT_TIMEOUT",
    "DCT_MAX_RETRIES",
    "DCT_LOG_LEVEL",
    "DCT_TOOLSET",
    "IS_LOCAL_TELEMETRY_ENABLED",
]


def _clear_optionals(monkeypatch):
    for var in _OPTIONAL_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")

    cfg = get_dct_config()
    assert cfg["base_url"] == "https://localhost:8083"
    assert cfg["verify_ssl"] is False
    assert cfg["timeout"] == 30
    assert cfg["max_retries"] == 3
    assert cfg["log_level"] == "INFO"
    assert cfg["toolset"] == "self_service"
    assert cfg["is_local_telemetry_enabled"] is False


def test_verify_ssl_true_parsing(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_VERIFY_SSL", "true")
    assert get_dct_config()["verify_ssl"] is True


def test_verify_ssl_false_parsing(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")
    assert get_dct_config()["verify_ssl"] is False


def test_int_coercion(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_TIMEOUT", "45")
    monkeypatch.setenv("DCT_MAX_RETRIES", "7")
    cfg = get_dct_config()
    assert cfg["timeout"] == 45
    assert cfg["max_retries"] == 7


def test_toolset_lowercased(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_TOOLSET", "Self_Service")
    assert get_dct_config()["toolset"] == "self_service"


def test_log_level_uppercased(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_LOG_LEVEL", "debug")
    assert get_dct_config()["log_level"] == "DEBUG"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("DCT_API_KEY", raising=False)
    with pytest.raises(ValueError):
        get_dct_config()
