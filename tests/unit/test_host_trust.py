"""Unit tests for dct_mcp_server.tools.core.host_trust."""
import os
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV, host_nonce_ok


def test_host_nonce_ok_env_match(monkeypatch):
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, "test-nonce")
    assert host_nonce_ok({"nonce": "test-nonce"}) is True


def test_host_nonce_ok_mismatch(monkeypatch):
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, "test-nonce")
    assert host_nonce_ok({"nonce": "wrong"}) is False


def test_host_nonce_ok_no_env(monkeypatch):
    monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    assert host_nonce_ok({"nonce": "anything"}) is False
