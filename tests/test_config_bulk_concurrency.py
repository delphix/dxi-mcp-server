"""Tests for DCT_BULK_CONCURRENCY config parsing."""
import os
import importlib
import pytest


def reload_config():
    """Re-import config to pick up env var changes."""
    import dct_mcp_server.config.config as cfg_mod
    importlib.reload(cfg_mod)
    return cfg_mod


def test_bulk_concurrency_default(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
    monkeypatch.delenv("DCT_BULK_CONCURRENCY", raising=False)
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 5


def test_bulk_concurrency_custom(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "3")
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 3


def test_bulk_concurrency_clamped_to_1(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "0")
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 1


def test_bulk_concurrency_clamped_to_50(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "100")
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 50


def test_bulk_concurrency_invalid_string(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "test-key")
    monkeypatch.setenv("DCT_BASE_URL", "http://fake.test")
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "abc")
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 5  # falls back to default
