"""
Unit tests for dct_mcp_server.tools.core.spec_cache.

Covers: get_cached_spec, clear_spec_cache, _validate_spec, _should_use_cache,
        _load_from_disk, load_and_cache_spec (success + cache hit + failure),
        _write_cache, _download_spec (4xx + network error).

Uses tmp_path for file-based tests and patch("requests.get") for HTTP.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

import dct_mcp_server.tools.core.spec_cache as spec_cache_mod
from dct_mcp_server.core.exceptions import MCPError
from dct_mcp_server.tools.core.spec_cache import (
    _load_from_disk,
    _should_use_cache,
    _validate_spec,
    _write_cache,
    _download_spec,
    clear_spec_cache,
    get_cached_spec,
    load_and_cache_spec,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "DCT API", "version": "1.0.0"},
    "paths": {"/vdbs": {"get": {"operationId": "listVdbs", "summary": "List VDBs"}}},
}


def _write_valid_spec_file(path: Path, spec: dict = None) -> None:
    if spec is None:
        spec = _VALID_SPEC
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(spec, f)


def _write_cache_meta(cache_path: Path, age_hours: float = 0.0) -> None:
    """Write a .cache-meta.json sidecar with a timestamp *age_hours* old."""
    downloaded_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    meta = {
        "downloaded_at": downloaded_at.isoformat(),
        "dct_base_url": "https://dct.test",
        "spec_path": str(cache_path),
    }
    meta_path = cache_path.parent / ".cache-meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f)


@pytest.fixture(autouse=True)
def _clear_in_memory_cache():
    """Reset the module-level _cached_spec before and after each test."""
    clear_spec_cache()
    yield
    clear_spec_cache()


# ---------------------------------------------------------------------------
# get_cached_spec / clear_spec_cache
# ---------------------------------------------------------------------------


def test_get_cached_spec_initially_none():
    assert get_cached_spec() is None


def test_clear_spec_cache_resets_to_none():
    spec_cache_mod._cached_spec = {"openapi": "3.0.0", "paths": {}}
    clear_spec_cache()
    assert get_cached_spec() is None


# ---------------------------------------------------------------------------
# _validate_spec
# ---------------------------------------------------------------------------


def test_validate_spec_valid_dict():
    assert _validate_spec({"openapi": "3.0.0", "paths": {}}) is True


def test_validate_spec_missing_openapi():
    assert _validate_spec({"paths": {}}) is False


def test_validate_spec_missing_paths():
    assert _validate_spec({"openapi": "3.0.0"}) is False


def test_validate_spec_paths_not_dict():
    assert _validate_spec({"openapi": "3.0.0", "paths": []}) is False


def test_validate_spec_non_dict_input():
    assert _validate_spec("not a dict") is False


def test_validate_spec_none_input():
    assert _validate_spec(None) is False


# ---------------------------------------------------------------------------
# _should_use_cache
# ---------------------------------------------------------------------------


def test_should_use_cache_nonexistent_file_returns_false(tmp_path):
    cache_path = tmp_path / "missing.yaml"
    assert _should_use_cache(cache_path, 24) is False


def test_should_use_cache_no_meta_returns_false(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    # No meta file → False
    assert _should_use_cache(cache_path, 24) is False


def test_should_use_cache_fresh_meta_returns_true(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    _write_cache_meta(cache_path, age_hours=0.5)
    assert _should_use_cache(cache_path, 24) is True


def test_should_use_cache_stale_meta_returns_false(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    _write_cache_meta(cache_path, age_hours=25)  # older than 24h max
    assert _should_use_cache(cache_path, 24) is False


def test_should_use_cache_exactly_at_max_age_returns_false(tmp_path):
    """Age == max_age_hours is NOT fresh (strict <)."""
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    _write_cache_meta(cache_path, age_hours=24.0)
    assert _should_use_cache(cache_path, 24) is False


# ---------------------------------------------------------------------------
# _load_from_disk
# ---------------------------------------------------------------------------


def test_load_from_disk_valid_yaml(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    result = _load_from_disk(cache_path)
    assert result is not None
    assert "openapi" in result
    assert "paths" in result


def test_load_from_disk_nonexistent_file_returns_none(tmp_path):
    result = _load_from_disk(tmp_path / "missing.yaml")
    assert result is None


def test_load_from_disk_invalid_yaml_returns_none(tmp_path):
    cache_path = tmp_path / "bad.yaml"
    cache_path.write_text(": invalid: yaml: ][")
    result = _load_from_disk(cache_path)
    assert result is None


def test_load_from_disk_valid_yaml_but_invalid_spec_returns_none(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    cache_path.write_text("key: value\n")  # valid YAML, but not an OpenAPI spec
    result = _load_from_disk(cache_path)
    assert result is None


# ---------------------------------------------------------------------------
# _write_cache
# ---------------------------------------------------------------------------


def test_write_cache_creates_yaml_file(tmp_path):
    cache_path = tmp_path / "subdir" / "spec.yaml"
    _write_cache(cache_path, _VALID_SPEC, "https://dct.test")
    assert cache_path.exists()
    with open(cache_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded["openapi"] == "3.0.0"


def test_write_cache_creates_meta_sidecar(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_cache(cache_path, _VALID_SPEC, "https://dct.test")
    meta_path = tmp_path / ".cache-meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert "downloaded_at" in meta
    assert meta["dct_base_url"] == "https://dct.test"


# ---------------------------------------------------------------------------
# _download_spec
# ---------------------------------------------------------------------------


def test_download_spec_returns_none_on_401():
    """HTTP 4xx errors are not retried; returns None immediately."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = __import__("requests").HTTPError(
        response=MagicMock(status_code=401)
    )
    with patch("requests.get", return_value=mock_response):
        result = _download_spec("https://dct.test", "bad-key", False, 5)
    assert result is None


def test_download_spec_returns_none_after_two_network_errors():
    """Two consecutive network errors → returns None after 2 attempts."""
    with patch("requests.get", side_effect=ConnectionError("timeout")):
        result = _download_spec("https://dct.test", "api-key", False, 5)
    assert result is None


def test_download_spec_returns_none_when_base_url_empty():
    result = _download_spec("", "api-key", False, 5)
    assert result is None


def test_download_spec_returns_spec_on_success():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = yaml.dump(_VALID_SPEC)
    with patch("requests.get", return_value=mock_response):
        result = _download_spec("https://dct.test", "api-key", False, 5)
    assert result is not None
    assert result["openapi"] == "3.0.0"


def test_download_spec_returns_none_on_invalid_yaml_response():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = ": invalid: yaml: ]["
    with patch("requests.get", return_value=mock_response):
        result = _download_spec("https://dct.test", "api-key", False, 5)
    assert result is None


# ---------------------------------------------------------------------------
# load_and_cache_spec — success path (download)
# ---------------------------------------------------------------------------


def test_load_and_cache_spec_success_sets_cached_spec(tmp_path, monkeypatch):
    cache_path = tmp_path / "spec.yaml"
    monkeypatch.setenv("DCT_SPEC_CACHE_PATH", str(cache_path))

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = yaml.dump(_VALID_SPEC)

    with patch("requests.get", return_value=mock_response):
        with patch(
            "dct_mcp_server.tools.core.spec_cache.get_dct_config",
            return_value={
                "base_url": "https://dct.test",
                "api_key": "test-api-key",
                "verify_ssl": False,
                "timeout": 5,
                "spec_max_age_hours": 24,
                "spec_cache_path": str(cache_path),
            },
        ):
            result = load_and_cache_spec()

    assert result is not None
    assert result["openapi"] == "3.0.0"
    assert get_cached_spec() is not None


# ---------------------------------------------------------------------------
# load_and_cache_spec — uses on-disk cache when fresh
# ---------------------------------------------------------------------------


def test_load_and_cache_spec_uses_fresh_cache(tmp_path):
    cache_path = tmp_path / "spec.yaml"
    _write_valid_spec_file(cache_path)
    _write_cache_meta(cache_path, age_hours=1)  # 1h old → fresh

    with patch(
        "dct_mcp_server.tools.core.spec_cache.get_dct_config",
        return_value={
            "base_url": "https://dct.test",
            "api_key": "test-api-key",
            "verify_ssl": False,
            "timeout": 5,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(cache_path),
        },
    ):
        with patch("requests.get") as mock_get:
            result = load_and_cache_spec()

    # Should have used cache, not called requests.get
    mock_get.assert_not_called()
    assert result is not None
    assert result["openapi"] == "3.0.0"


# ---------------------------------------------------------------------------
# load_and_cache_spec — raises MCPError when download fails and no cache
# ---------------------------------------------------------------------------


def test_load_and_cache_spec_raises_mcp_error_when_no_cache_and_download_fails(
    tmp_path,
):
    cache_path = tmp_path / "nonexistent.yaml"  # does not exist

    with patch(
        "dct_mcp_server.tools.core.spec_cache.get_dct_config",
        return_value={
            "base_url": "https://dct.test",
            "api_key": "test-api-key",
            "verify_ssl": False,
            "timeout": 5,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(cache_path),
        },
    ):
        with patch("requests.get", side_effect=ConnectionError("unreachable")):
            with pytest.raises(MCPError, match="SPEC_LOAD_FAILED"):
                load_and_cache_spec()
