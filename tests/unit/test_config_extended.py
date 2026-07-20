"""
Extended unit tests for config/config.py.

Covers:
- print_config_help()
- get_dct_config() with various env-var combinations
- invalid DCT_TOOLSET raises ValueError
"""

from __future__ import annotations


import pytest

from dct_mcp_server.config.config import get_dct_config, print_config_help


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


# ---------------------------------------------------------------------------
# print_config_help
# ---------------------------------------------------------------------------


def test_print_config_help_no_exception(monkeypatch, capsys):
    print_config_help()
    captured = capsys.readouterr()
    assert "DCT_API_KEY" in captured.out


def test_print_config_help_lists_toolsets(monkeypatch, capsys):
    print_config_help()
    captured = capsys.readouterr()
    assert "self_service" in captured.out
    assert "dynamic" in captured.out


# ---------------------------------------------------------------------------
# get_dct_config — various env combos
# ---------------------------------------------------------------------------


def test_get_dct_config_auto_toolset(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    cfg = get_dct_config()
    assert cfg["toolset"] == "auto"


def test_get_dct_config_verify_ssl_true(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_VERIFY_SSL", "true")
    cfg = get_dct_config()
    assert cfg["verify_ssl"] is True


def test_get_dct_config_verify_ssl_false(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")
    cfg = get_dct_config()
    assert cfg["verify_ssl"] is False


def test_get_dct_config_log_level_debug(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_LOG_LEVEL", "debug")
    cfg = get_dct_config()
    assert cfg["log_level"] == "DEBUG"


def test_get_dct_config_log_level_warning(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_LOG_LEVEL", "WARNING")
    cfg = get_dct_config()
    assert cfg["log_level"] == "WARNING"


def test_get_dct_config_telemetry_enabled(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("IS_LOCAL_TELEMETRY_ENABLED", "true")
    cfg = get_dct_config()
    assert cfg["is_local_telemetry_enabled"] is True


def test_get_dct_config_telemetry_disabled(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("IS_LOCAL_TELEMETRY_ENABLED", "false")
    cfg = get_dct_config()
    assert cfg["is_local_telemetry_enabled"] is False


def test_get_dct_config_all_toolsets_valid(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    valid_toolsets = [
        "self_service",
        "self_service_provision",
        "continuous_data_admin",
        "platform_admin",
        "reporting_insights",
        "auto",
    ]
    for ts in valid_toolsets:
        monkeypatch.setenv("DCT_TOOLSET", ts)
        cfg = get_dct_config()
        assert cfg["toolset"] == ts.lower()


def test_get_dct_config_custom_base_url(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_BASE_URL", "https://custom.host:9090")
    cfg = get_dct_config()
    assert cfg["base_url"] == "https://custom.host:9090"


def test_get_dct_config_custom_timeout_and_retries(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_TIMEOUT", "60")
    monkeypatch.setenv("DCT_MAX_RETRIES", "5")
    cfg = get_dct_config()
    assert cfg["timeout"] == 60
    assert cfg["max_retries"] == 5


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_get_dct_config_missing_api_key_raises(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.delenv("DCT_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DCT_API_KEY"):
        get_dct_config()


def test_get_dct_config_invalid_log_level_raises(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_LOG_LEVEL", "SUPERVERBOSE")
    with pytest.raises(ValueError, match="Invalid log level"):
        get_dct_config()


def test_get_dct_config_contains_required_keys(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "k")
    cfg = get_dct_config()
    required_keys = {
        "api_key",
        "base_url",
        "verify_ssl",
        "timeout",
        "max_retries",
        "log_level",
        "is_local_telemetry_enabled",
        "toolset",
    }
    assert required_keys.issubset(set(cfg.keys()))


def test_get_dct_config_api_key_stored(monkeypatch):
    _clear_optionals(monkeypatch)
    monkeypatch.setenv("DCT_API_KEY", "my-secret-key")
    cfg = get_dct_config()
    assert cfg["api_key"] == "my-secret-key"
