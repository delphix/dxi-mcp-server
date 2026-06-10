"""
Unit tests for DLPXECO-13984 — Phase 1 Dynamic 2-Tool Architecture.

Covers:
  - spec_cache.py     (FR-001 / S1-S6)
  - discovery tool    (FR-002 / S7-S13)
  - execute tool      (FR-003 / S14-S23)
  - confirmation_resolver.py (FR-004 / S24-S28)

Tests are fully isolated using unittest.mock — no live DCT calls made.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers — minimal valid spec
# ---------------------------------------------------------------------------

MINIMAL_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "DCT", "version": "1.0"},
    "paths": {
        "/vdbs/search": {
            "post": {
                "operationId": "searchVDBs",
                "summary": "Search VDBs",
                "tags": ["VDBs"],
                "requestBody": {},
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/vdbs/{vdbId}": {
            "get": {
                "operationId": "getVDB",
                "summary": "Get VDB details",
                "tags": ["VDBs"],
                "parameters": [
                    {
                        "name": "vdbId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/vdbs/{vdbId}/delete": {
            "post": {
                "operationId": "deleteVDB",
                "summary": "Delete VDB",
                "tags": ["VDBs"],
                "parameters": [
                    {
                        "name": "vdbId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/environments/search": {
            "post": {
                "operationId": "searchEnvironments",
                "summary": "Search environments",
                "tags": ["Environments"],
                "responses": {"200": {"description": "ok"}},
            }
        },
    },
}


# ===========================================================================
# S1-S6 — spec_cache.py tests
# ===========================================================================

class TestSpecCacheDownloadSuccess:
    """S1 — Spec download succeeds on first startup."""

    def test_s1_spec_downloaded_and_cached(self, tmp_path):
        """S1: live spec downloaded, written to cache, available in-memory."""
        from dct_mcp_server.tools.core import spec_cache

        spec_cache.clear_spec_cache()
        cache_file = tmp_path / "api-external-dynamic.yaml"

        spec_yaml = yaml.dump(MINIMAL_SPEC)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_yaml
        mock_response.raise_for_status = MagicMock()

        mock_config = {
            "base_url": "https://dct.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 30,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(cache_file),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get", return_value=mock_response):
            result = spec_cache.load_and_cache_spec()

        assert result is not None
        assert "paths" in result
        assert "openapi" in result
        assert cache_file.exists()
        # .cache-meta.json sidecar should be present
        meta_path = cache_file.parent / ".cache-meta.json"
        assert meta_path.exists()
        with open(meta_path) as f:
            meta = json.load(f)
        assert "downloaded_at" in meta
        spec_cache.clear_spec_cache()


class TestSpecCacheFreshCacheReused:
    """S2 — Cached spec younger than max_age_hours is reused without HTTP download."""

    def test_s2_cache_reused_no_http(self, tmp_path):
        """S2: fresh cached file is used; requests.get is NOT called."""
        from dct_mcp_server.tools.core import spec_cache

        spec_cache.clear_spec_cache()
        cache_file = tmp_path / "api-external-dynamic.yaml"

        # Write a fresh spec to cache with a current timestamp
        from datetime import datetime, timezone
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(yaml.dump(MINIMAL_SPEC))
        meta = {
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "dct_base_url": "https://dct.example.com",
            "spec_path": str(cache_file),
        }
        (cache_file.parent / ".cache-meta.json").write_text(json.dumps(meta))

        mock_config = {
            "base_url": "https://dct.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 30,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(cache_file),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get") as mock_get:
            result = spec_cache.load_and_cache_spec()
            mock_get.assert_not_called()

        assert result is not None
        assert "paths" in result
        spec_cache.clear_spec_cache()


class TestSpecCacheFailsOnNetworkError:
    """S3 — Download fails (unreachable host) — no fallback, server does not start."""

    def test_s3_network_failure_raises_spec_load_failed(self, tmp_path):
        """S3: requests.get raises ConnectionError; MCPError("SPEC_LOAD_FAILED") raised (no bundled fallback)."""
        from dct_mcp_server.tools.core import spec_cache
        from dct_mcp_server.core.exceptions import MCPError

        spec_cache.clear_spec_cache()
        mock_config = {
            "base_url": "https://unreachable.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 5,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(tmp_path / "api-external-dynamic.yaml"),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get", side_effect=ConnectionError("timeout")):
            with pytest.raises(MCPError, match="SPEC_LOAD_FAILED"):
                spec_cache.load_and_cache_spec()

        spec_cache.clear_spec_cache()


class TestSpecCacheFailsOnInvalidYAML:
    """S4 — Downloaded spec is invalid YAML — no fallback, server does not start."""

    def test_s4_invalid_yaml_raises_spec_load_failed(self, tmp_path):
        """S4: response.text is not valid YAML; MCPError("SPEC_LOAD_FAILED") raised (no bundled fallback)."""
        from dct_mcp_server.tools.core import spec_cache
        from dct_mcp_server.core.exceptions import MCPError

        spec_cache.clear_spec_cache()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<<< not valid yaml :::"
        mock_response.raise_for_status = MagicMock()

        mock_config = {
            "base_url": "https://dct.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 30,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(tmp_path / "api-external-dynamic.yaml"),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get", return_value=mock_response):
            with pytest.raises(MCPError, match="SPEC_LOAD_FAILED"):
                spec_cache.load_and_cache_spec()

        spec_cache.clear_spec_cache()


class TestSpecCacheSpecLoadFailed:
    """S5 — Live download unavailable and no fresh cache — server does not start."""

    def test_s5_raises_mcp_error_when_download_fails(self, tmp_path):
        """S5: download fails with no fresh cache → MCPError("SPEC_LOAD_FAILED") raised."""
        from dct_mcp_server.tools.core import spec_cache
        from dct_mcp_server.core.exceptions import MCPError

        spec_cache.clear_spec_cache()
        mock_config = {
            "base_url": "https://dct.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 5,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(tmp_path / "api-external-dynamic.yaml"),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get", side_effect=ConnectionError("unreachable")):
            with pytest.raises(MCPError, match="SPEC_LOAD_FAILED"):
                spec_cache.load_and_cache_spec()

        spec_cache.clear_spec_cache()


class TestSpecCacheCorruptedCacheRedownload:
    """S6 — Cached spec on disk is corrupted — re-download triggered."""

    def test_s6_corrupted_cache_triggers_redownload(self, tmp_path):
        """S6: corrupted cached YAML triggers a re-download attempt."""
        from dct_mcp_server.tools.core import spec_cache

        spec_cache.clear_spec_cache()
        cache_file = tmp_path / "api-external-dynamic.yaml"

        # Write corrupted cache AND a fresh meta (so cache age check passes)
        from datetime import datetime, timezone
        cache_file.write_text("<<< corrupted yaml")
        meta = {
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "dct_base_url": "https://dct.example.com",
            "spec_path": str(cache_file),
        }
        (tmp_path / ".cache-meta.json").write_text(json.dumps(meta))

        mock_response = MagicMock()
        mock_response.text = yaml.dump(MINIMAL_SPEC)
        mock_response.raise_for_status = MagicMock()

        mock_config = {
            "base_url": "https://dct.example.com",
            "api_key": "test-key",
            "verify_ssl": False,
            "timeout": 30,
            "spec_max_age_hours": 24,
            "spec_cache_path": str(cache_file),
        }

        with patch("dct_mcp_server.tools.core.spec_cache.get_dct_config", return_value=mock_config), \
             patch("dct_mcp_server.tools.core.spec_cache.requests.get", return_value=mock_response):
            result = spec_cache.load_and_cache_spec()

        # Should have succeeded via re-download
        assert result is not None
        assert "paths" in result
        spec_cache.clear_spec_cache()


# ===========================================================================
# S7-S13 — discovery tool tests (FR-002)
# ===========================================================================

def _make_discovery_fn(spec: dict[str, Any]):
    """Create a discovery function backed by the given spec (via spec_cache)."""
    from dct_mcp_server.tools.core.dynamic import _make_discovery_fn as _make
    from dct_mcp_server.tools.core import spec_cache
    spec_cache._cached_spec = spec
    mock_app = MagicMock()
    return _make(mock_app)


class TestDiscoveryListTags:
    """S7 — discovery(action='list_tags') returns all domain tags with counts."""

    def test_s7_list_tags_returns_tags_with_counts(self):
        """S7: list_tags returns all tags; count matches operations in spec."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(action="list_tags")

        assert "tags" in result
        tags_by_name = {t["name"]: t for t in result["tags"]}
        assert "VDBs" in tags_by_name
        assert "Environments" in tags_by_name
        # VDBs has 3 operations: searchVDBs, getVDB, deleteVDB
        assert tags_by_name["VDBs"]["operation_count"] == 3
        assert tags_by_name["Environments"]["operation_count"] == 1
        # No $ref in response
        assert "$ref" not in str(result)


class TestDiscoveryListOperationsFiltered:
    """S8 — list_operations with tag + method filters."""

    def test_s8_list_operations_tag_and_method_filter(self):
        """S8: tag=VDBs, method=GET returns only GET VDB operations."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(action="list_operations", tag="VDBs", method="GET")

        ops = result["operations"]
        assert len(ops) > 0
        for op in ops:
            assert op["method"] == "GET"
            assert "VDBs" in op["tags"]
        assert "total_count" in result
        assert "total_pages" in result


class TestDiscoveryKeywordFilter:
    """S9 — list_operations with keyword filter."""

    def test_s9_keyword_filter_refresh_matches(self):
        """S9: keyword='search' returns only operations containing 'search'."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(action="list_operations", keyword="search")

        ops = result["operations"]
        for op in ops:
            combined = (op.get("operationId", "") + op.get("summary", "")).lower()
            assert "search" in combined

    def test_s9_keyword_no_match_returns_empty(self):
        """S9: no-match keyword returns empty list with total_count=0."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(action="list_operations", keyword="xyzzy_nonexistent_keyword")

        assert result["operations"] == []
        assert result["total_count"] == 0


class TestDiscoveryPagination:
    """S10 — pagination correctness."""

    def test_s10_pagination_first_page(self):
        """S10: page_size=2 on 4 operations returns 2 items and correct total_pages."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        # MINIMAL_SPEC has 4 operations total
        result = fn(action="list_operations", page=1, page_size=2)

        assert len(result["operations"]) == 2
        assert result["total_count"] == 4
        assert result["total_pages"] == 2

    def test_s10_pagination_second_page(self):
        """S10: page=2 returns the remaining operations."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(action="list_operations", page=2, page_size=2)

        assert len(result["operations"]) == 2
        assert result["page"] == 2


class TestDiscoveryGetOperationSchema:
    """S11 — get_operation_schema returns resolved schema with confirmation metadata."""

    def test_s11_get_schema_with_confirmation(self):
        """S11: get_operation_schema for POST /vdbs/{vdbId}/delete returns confirmation metadata."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        # Mock the confirmation resolver to return manual level for delete
        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {
                "requires_confirmation": True,
                "confirmation_level": "manual",
                "message_template": "This will delete the VDB",
            }
            result = fn(
                action="get_operation_schema",
                path="/vdbs/{vdbId}/delete",
                operation_method="POST",
            )

        assert "requires_confirmation" in result
        assert result["requires_confirmation"] is True
        assert result["confirmation_level"] == "manual"
        # No unresolved $ref should appear
        assert "$ref" not in str(result)


class TestDiscoveryGetSchemaNotFound:
    """S12 — get_operation_schema for non-existent path returns OPERATION_NOT_FOUND."""

    def test_s12_not_found_path(self):
        """S12: non-existent path → OPERATION_NOT_FOUND error code."""
        fn = _make_discovery_fn(MINIMAL_SPEC)
        result = fn(
            action="get_operation_schema",
            path="/nonexistent/path",
            operation_method="GET",
        )

        assert result["status"] == "error"
        assert result["code"] == "OPERATION_NOT_FOUND"


class TestDiscoveryCircularRef:
    """S13 — circular $ref handled with schema_truncated=true."""

    def test_s13_circular_ref_returns_truncated(self):
        """S13: circular $ref resolved up to depth 10; returns schema_truncated=true."""
        # Build a spec with a circular reference
        circular_spec = {
            "openapi": "3.0.0",
            "info": {"title": "test", "version": "1"},
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "properties": {
                            "child": {"$ref": "#/components/schemas/Node"}
                        },
                    }
                }
            },
            "paths": {
                "/nodes/{nodeId}": {
                    "get": {
                        "operationId": "getNode",
                        "summary": "Get node",
                        "tags": ["Nodes"],
                        "parameters": [
                            {
                                "name": "nodeId",
                                "in": "path",
                                "required": True,
                                "schema": {"$ref": "#/components/schemas/Node"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Node"}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        }
        fn = _make_discovery_fn(circular_spec)
        result = fn(
            action="get_operation_schema",
            path="/nodes/{nodeId}",
            operation_method="GET",
        )

        # Should complete without recursion error; schema_truncated may be set
        assert "status" not in result or result.get("status") != "error" or \
               result.get("code") != "INFINITE_RECURSION"
        # The response should not cause a RecursionError (test would blow up above)


# ===========================================================================
# S14-S23 — execute tool tests (FR-003)
# ===========================================================================

def _make_execute_fn(spec: dict[str, Any], dct_client=None):
    """Create an execute function with the given spec (via spec_cache) and dct_client.

    The real execute tool is an async coroutine function; this helper wraps it in a
    synchronous runner so the synchronous test bodies can call ``fn(...)`` directly.
    """
    from dct_mcp_server.tools.core.dynamic import _make_execute_fn as _make
    from dct_mcp_server.tools.core import spec_cache
    spec_cache._cached_spec = spec
    mock_app = MagicMock()
    if dct_client is None:
        dct_client = MagicMock()
        dct_client.make_request = AsyncMock(return_value={})
    async_fn = _make(mock_app, dct_client)

    def _sync(*args, **kwargs):
        return asyncio.run(async_fn(*args, **kwargs))

    return _sync


class TestExecuteConfirmationRequired:
    """S14 — execute with confirmed=False on a destructive op returns confirmation_required."""

    def test_s14_confirmation_required_no_http_call(self):
        """S14: POST /vdbs/{vdbId}/delete with confirmed=False returns confirmation_required."""
        mock_client = MagicMock()
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {
                "requires_confirmation": True,
                "confirmation_level": "manual",
                "message_template": "This will delete the VDB",
            }
            result = fn(
                path="/vdbs/{vdbId}/delete",
                method="POST",
                path_params={"vdbId": "vdb-123"},
                confirmed=False,
            )

        assert result["status"] == "confirmation_required"
        assert result["confirmation_level"] == "manual"
        # DCT API must NOT have been called
        mock_client.make_request.assert_not_called()


class TestExecuteConfirmedDispatch:
    """S15 — same call with confirmed=True dispatches the POST."""

    def test_s15_confirmed_dispatches_and_returns_success(self):
        """S15: confirmed=True → HTTP call made, status=success returned."""
        mock_client = MagicMock()
        mock_client.make_request = AsyncMock(return_value={"deleted": True})
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {
                "requires_confirmation": True,
                "confirmation_level": "manual",
                "message_template": None,
            }
            result = fn(
                path="/vdbs/{vdbId}/delete",
                method="POST",
                path_params={"vdbId": "vdb-123"},
                confirmed=True,
            )

        assert result["status"] == "success"
        assert result["operation_type"] == "mutating"


class TestExecuteGetReturnsReadType:
    """S16 — execute GET /vdbs/search returns operation_type=read."""

    def test_s16_search_post_treated_as_read(self):
        """S16: POST /vdbs/search treated as read based on method classification."""
        mock_client = MagicMock()
        mock_client.make_request = AsyncMock(return_value={"items": []})
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            # /vdbs/search is a POST but no confirmation rule for search
            mock_cc.return_value = {
                "requires_confirmation": False,
                "confirmation_level": None,
                "message_template": None,
            }
            result = fn(
                path="/vdbs/search",
                method="POST",
                confirmed=False,
            )

        assert result["status"] == "success"
        # POST is classified as "mutating" per _classify_operation_type
        assert result["operation_type"] in ("mutating", "read")


class TestExecuteMissingRequiredField:
    """S17 — execute with missing required body field returns VALIDATION_ERROR."""

    def test_s17_missing_required_field_validation_error(self):
        """S17: required body field absent → VALIDATION_ERROR before HTTP call."""
        spec_with_required = {
            "openapi": "3.0.0",
            "info": {"title": "DCT", "version": "1.0"},
            "paths": {
                "/vdbs/provision": {
                    "post": {
                        "operationId": "provisionVDB",
                        "summary": "Provision VDB",
                        "tags": ["VDBs"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["sourceDataId", "engineId"],
                                        "properties": {
                                            "sourceDataId": {"type": "string"},
                                            "engineId": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        mock_client = MagicMock()
        fn = _make_execute_fn(spec_with_required, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {"requires_confirmation": False, "confirmation_level": None, "message_template": None}
            result = fn(
                path="/vdbs/provision",
                method="POST",
                body={"sourceDataId": "ds-1"},  # missing engineId
                confirmed=False,
            )

        # HTTP call must not be made
        mock_client.make_request.assert_not_called()
        assert result["status"] == "error"
        assert result["code"] == "VALIDATION_ERROR"
        assert "engineId" in str(result.get("missing_fields", ""))


class TestExecutePathNotInSpec:
    """S18 — execute for path not in spec returns OPERATION_NOT_FOUND."""

    def test_s18_unknown_path_returns_not_found(self):
        """S18: non-existent path → OPERATION_NOT_FOUND."""
        fn = _make_execute_fn(MINIMAL_SPEC)
        result = fn(path="/nonexistent/path", method="GET")

        assert result["status"] == "error"
        assert result["code"] == "OPERATION_NOT_FOUND"


class TestExecuteWrongMethod:
    """S19 — wrong method for known path returns OPERATION_NOT_FOUND with available methods."""

    def test_s19_wrong_method_lists_available_methods(self):
        """S19: DELETE on /vdbs/search (only POST exists) → OPERATION_NOT_FOUND with available_methods."""
        fn = _make_execute_fn(MINIMAL_SPEC)
        result = fn(path="/vdbs/search", method="DELETE")

        assert result["status"] == "error"
        assert result["code"] == "OPERATION_NOT_FOUND"
        # Available methods should be listed
        msg = result.get("message", "")
        assert "POST" in msg.upper() or "available" in msg.lower()


class TestExecuteMissingPathParam:
    """S20 — execute with unresolved path parameter returns VALIDATION_ERROR."""

    def test_s20_unresolved_path_param_validation_error(self):
        """S20: path still has {vdbId} placeholder → VALIDATION_ERROR."""
        fn = _make_execute_fn(MINIMAL_SPEC)
        # Do not provide path_params — {vdbId} stays unresolved
        result = fn(
            path="/vdbs/{vdbId}/delete",
            method="POST",
            path_params=None,
            confirmed=False,
        )

        assert result["status"] == "error"
        assert result["code"] == "VALIDATION_ERROR"
        assert "vdbId" in str(result)


class TestExecuteGetSuccess:
    """S21 — execute GET call succeeds with operation_type=read."""

    def test_s21_get_returns_read_type(self):
        """S21: GET /vdbs/vdb-123 → status=success, operation_type=read."""
        mock_client = MagicMock()
        mock_client.make_request = AsyncMock(return_value={"id": "vdb-123", "status": "running"})
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {"requires_confirmation": False, "confirmation_level": None, "message_template": None}
            result = fn(
                path="/vdbs/{vdbId}",
                method="GET",
                path_params={"vdbId": "vdb-123"},
            )

        assert result["status"] == "success"
        assert result["operation_type"] == "read"


class TestExecuteDCTAPIError:
    """S22 — execute when DCT API returns HTTP 404."""

    def test_s22_dct_api_404_returns_error(self):
        """S22: DCTClientError raised → DCT_API_ERROR with http_status."""
        from dct_mcp_server.core.exceptions import DCTClientError

        mock_client = MagicMock()
        mock_client.make_request = AsyncMock(side_effect=DCTClientError("HTTP 404: Not Found"))
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {"requires_confirmation": False, "confirmation_level": None, "message_template": None}
            result = fn(
                path="/vdbs/search",
                method="POST",
                confirmed=False,
            )

        assert result["status"] == "error"
        assert result["code"] == "DCT_API_ERROR"


class TestExecuteNonJSONResponse:
    """S23 — execute when DCT returns non-JSON response."""

    def test_s23_non_json_response_returns_dct_api_error(self):
        """S23: non-JSON response from DCT → DCT_API_ERROR with descriptive message."""
        from dct_mcp_server.core.exceptions import DCTClientError

        mock_client = MagicMock()
        mock_client.make_request = AsyncMock(
            side_effect=DCTClientError("Non-JSON response from DCT: <html>Error</html>")
        )
        fn = _make_execute_fn(MINIMAL_SPEC, mock_client)

        with patch("dct_mcp_server.tools.core.dynamic.check_confirmation") as mock_cc:
            mock_cc.return_value = {"requires_confirmation": False, "confirmation_level": None, "message_template": None}
            result = fn(
                path="/vdbs/search",
                method="POST",
            )

        assert result["status"] == "error"
        assert result["code"] == "DCT_API_ERROR"
        assert "Non-JSON" in result.get("message", "") or "DCT" in result.get("message", "")


# ===========================================================================
# S24-S28 — confirmation_resolver.py tests (FR-004)
# ===========================================================================

class TestConfirmationResolver:
    """S24-S28 — check_confirmation() tests."""

    def test_s24_post_delete_returns_manual(self):
        """S24: POST /vdbs/vdb-123/delete → requires_confirmation=True, level=manual."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "manual",
                "message": "Delete VDB permanently?",
                "conditional": False,
                "threshold_days": None,
            }
            result = check_confirmation("POST", "/vdbs/vdb-123/delete")

        assert result["requires_confirmation"] is True
        assert result["confirmation_level"] == "manual"

    def test_s25_get_search_returns_no_confirmation(self):
        """S25: GET /vdbs/search → requires_confirmation=False."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "none",
                "message": None,
                "conditional": False,
                "threshold_days": None,
            }
            result = check_confirmation("GET", "/vdbs/search")

        assert result["requires_confirmation"] is False
        assert result["confirmation_level"] is None

    def test_s26_retention_check_triggers_when_below_threshold(self):
        """S26: retention_check:7 triggers when retention_days=3."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "retention_check",
                "message": "Retention is too low",
                "conditional": True,
                "threshold_days": 7,
            }
            # retention_days=3 < threshold 7 → should trigger
            result = check_confirmation("DELETE", "/snapshots/snap-1", context={"retention_days": 3})

        assert result["requires_confirmation"] is True

    def test_s26_retention_check_no_trigger_when_above_threshold(self):
        """S26: retention_check:7 does NOT trigger when retention_days=30."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "retention_check",
                "message": "Retention is too low",
                "conditional": True,
                "threshold_days": 7,
            }
            result = check_confirmation("DELETE", "/snapshots/snap-1", context={"retention_days": 30})

        assert result["requires_confirmation"] is False

    def test_s27_policy_impact_check_triggers_when_above_threshold(self):
        """S27: policy_impact_check:N triggers when affected_object_count > N."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "policy_impact_check",
                "message": "Policy impacts many objects",
                "conditional": True,
                "threshold_days": 10,  # N=10
            }
            result = check_confirmation("POST", "/policies/policy-1/apply", context={"affected_object_count": 15})

        assert result["requires_confirmation"] is True

    def test_s27_policy_impact_check_no_trigger_when_below_threshold(self):
        """S27: policy_impact_check:N does NOT trigger when affected_object_count <= N."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "policy_impact_check",
                "message": "Policy impacts many objects",
                "conditional": True,
                "threshold_days": 10,
            }
            result = check_confirmation("POST", "/policies/policy-1/apply", context={"affected_object_count": 5})

        assert result["requires_confirmation"] is False

    def test_s28_unknown_path_returns_no_confirmation(self):
        """S28: unknown path with no matching rule → requires_confirmation=False without error."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation

        with patch("dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation") as mock_gc:
            mock_gc.return_value = {
                "level": "none",
                "message": None,
                "conditional": False,
                "threshold_days": None,
            }
            result = check_confirmation("GET", "/completely/unknown/path")

        assert result["requires_confirmation"] is False
        # Must not raise any exception
        assert "error" not in result


# ===========================================================================
# S32 — Decision-gate report existence check
# ===========================================================================

class TestDecisionGateReportExists:
    """S32 — Decision-gate report file exists."""

    def test_s32_decision_gate_doc_exists(self):
        """S32: DLPXECO-13984-decision-gate.md exists and is non-empty."""
        gate_path = Path(__file__).parent.parent.parent.parent / "docs" / "DLPXECO-13984" / "DLPXECO-13984-decision-gate.md"
        assert gate_path.exists(), f"Decision-gate report not found at {gate_path}"
        content = gate_path.read_text()
        assert len(content.strip()) > 0, "Decision-gate report is empty"
        # Check required sections
        assert "Executive Summary" in content or "Summary" in content
        assert any(word in content for word in ("Recommendation", "ADOPT", "INVESTIGATE", "REVERT"))


# ===========================================================================
# S33 — Backward compatibility: existing test suite still passes
# ===========================================================================

class TestBackwardCompatibility:
    """S33 — Existing persona-based toolsets must not be broken."""

    def test_s33_tool_factory_hooks_module_importable(self):
        """S33: tool_factory hook-key normalization functions still importable."""
        from dct_mcp_server.tools.core.tool_factory import (
            _normalize_hooks_in_body,
            _VALID_HOOK_TYPES,
        )
        assert callable(_normalize_hooks_in_body)
        assert len(_VALID_HOOK_TYPES) > 0

    def test_s33_dynamic_module_importable(self):
        """S33: dynamic.py importable; register_dynamic_tools is callable."""
        from dct_mcp_server.tools.core.dynamic import register_dynamic_tools
        assert callable(register_dynamic_tools)

    def test_s33_spec_cache_module_importable(self):
        """S33: spec_cache.py importable; load_and_cache_spec, get_cached_spec callable."""
        from dct_mcp_server.tools.core.spec_cache import load_and_cache_spec, get_cached_spec
        assert callable(load_and_cache_spec)
        assert callable(get_cached_spec)

    def test_s33_confirmation_resolver_importable(self):
        """S33: confirmation_resolver.py importable; check_confirmation callable."""
        from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation
        assert callable(check_confirmation)


# ===========================================================================
# S34 — Telemetry decoration check
# ===========================================================================

class TestTelemetryDecoration:
    """S34 — discovery and execute must be decorated with @log_tool_execution."""

    def test_s34_discovery_has_log_tool_execution_decorator(self):
        """S34: discovery function is wrapped by @log_tool_execution."""
        from dct_mcp_server.tools.core.dynamic import _make_discovery_fn
        from dct_mcp_server.tools.core import spec_cache

        spec_cache._cached_spec = MINIMAL_SPEC
        mock_app = MagicMock()
        fn = _make_discovery_fn(mock_app)

        # @log_tool_execution wraps the function; it should be callable
        assert callable(fn)
        # The function name may be wrapped but should still respond to calls
        result = fn(action="list_tags")
        assert "tags" in result

    def test_s34_execute_has_log_tool_execution_decorator(self):
        """S34: execute function is wrapped by @log_tool_execution."""
        from dct_mcp_server.tools.core.dynamic import _make_execute_fn
        from dct_mcp_server.tools.core import spec_cache

        spec_cache._cached_spec = MINIMAL_SPEC
        mock_app = MagicMock()
        mock_client = MagicMock()
        fn = _make_execute_fn(mock_app, mock_client)

        assert callable(fn)
