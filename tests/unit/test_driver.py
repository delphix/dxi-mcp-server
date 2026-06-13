"""
Unit tests for src/dct_mcp_server/toolsgenerator/driver.py

Pure unit tests — no network, no real DCT.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import requests
import yaml

import dct_mcp_server.toolsgenerator.driver as driver_mod


# ---------------------------------------------------------------------------
# MINIMAL_SPEC used across multiple tests
# ---------------------------------------------------------------------------

MINIMAL_SPEC = {
    "paths": {
        "/vdbs/search": {
            "post": {
                "summary": "Search VDBs",
                "operationId": "searchVdbs",
                "x-filterable": True,
                "parameters": [],
                "requestBody": {"content": {"application/json": {"schema": {
                    "properties": {"filter_expression": {"type": "string", "description": "Filter"}}
                }}}},
                "responses": {"200": {"content": {"application/json": {"schema": {
                    "properties": {"items": {"items": {"$ref": "#/components/schemas/VDB"}}}
                }}}}}
            }
        },
        "/vdbs/{vdbId}": {
            "get": {"summary": "Get VDB", "operationId": "getVdb",
                    "parameters": [{"name": "vdbId", "in": "path", "schema": {"type": "string"}, "description": "VDB ID"}],
                    "responses": {}},
            "delete": {"summary": "Delete VDB", "operationId": "deleteVdb",
                       "parameters": [{"name": "vdbId", "in": "path", "schema": {"type": "string"}, "description": "VDB ID"}],
                       "responses": {}}
        },
        "/vdbs": {
            "post": {"summary": "Provision VDB", "operationId": "provisionVdb",
                     "requestBody": {"content": {"application/json": {"schema": {
                         "properties": {
                             "name": {"type": "string", "description": "VDB name"},
                             "sourceId": {"type": "string", "description": "Source ID"},
                             "retainForever": {"type": "boolean", "description": "Retain forever"},
                             "tags": {"type": "array", "description": "Tags"},
                             "config": {"type": "object", "description": "Config"},
                             "environment_user_id": {"type": "string", "description": "Env user ID"},
                         },
                         "required": ["name"]
                     }}}},
                     "responses": {}}
        }
    },
    "components": {"schemas": {
        "VDB": {"properties": {
            "id": {"type": "string", "description": "ID"},
            "name": {"type": "string", "description": "Name"},
            "status": {"type": "string", "description": "Status"},
        }}
    }}
}


# ---------------------------------------------------------------------------
# Autouse fixture: reset module-level globals between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_globals():
    original_tools = dict(driver_mod.TOOLS_BY_NAME)
    original_skipped = list(driver_mod.SKIPPED_ENTRIES)
    driver_mod.TOOLS_BY_NAME.clear()
    driver_mod.SKIPPED_ENTRIES.clear()
    yield
    driver_mod.TOOLS_BY_NAME.clear()
    driver_mod.TOOLS_BY_NAME.update(original_tools)
    driver_mod.SKIPPED_ENTRIES.clear()
    driver_mod.SKIPPED_ENTRIES.extend(original_skipped)


# ===========================================================================
# _parse_toolset_file
# ===========================================================================

def test_parse_toolset_file_normal(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("# TOOL 1: vdb_tool - VDB tool\nPOST|/vdbs/search|search\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    assert "vdb_tool" in driver_mod.TOOLS_BY_NAME
    assert driver_mod.TOOLS_BY_NAME["vdb_tool"] == [{"method": "POST", "path": "/vdbs/search", "action": "search"}]


def test_parse_toolset_file_empty_lines_skipped(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("\n\n# TOOL 1: vdb_tool\n\nPOST|/vdbs/search|search\n\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    assert len(driver_mod.TOOLS_BY_NAME["vdb_tool"]) == 1


def test_parse_toolset_file_non_tool_comment_skipped(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("# This is a regular comment\n# TOOL 1: vdb_tool\nPOST|/vdbs|provision\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    assert "vdb_tool" in driver_mod.TOOLS_BY_NAME
    assert len(driver_mod.TOOLS_BY_NAME["vdb_tool"]) == 1


def test_parse_toolset_file_inherit_reads_parent(tmp_path):
    parent = tmp_path / "parent.txt"
    parent.write_text("# TOOL 1: parent_tool\nGET|/parent|list\n")
    child = tmp_path / "child.txt"
    child.write_text("@inherit:parent\n# TOOL 2: child_tool\nGET|/child|list\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(child)
    assert "parent_tool" in driver_mod.TOOLS_BY_NAME
    assert "child_tool" in driver_mod.TOOLS_BY_NAME


def test_parse_toolset_file_inherit_missing_parent_logs_warning(tmp_path, caplog):
    child = tmp_path / "child.txt"
    child.write_text("@inherit:nonexistent\n# TOOL 1: child_tool\nGET|/child|list\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        import logging
        with caplog.at_level(logging.WARNING):
            driver_mod._parse_toolset_file(child)
    assert "child_tool" in driver_mod.TOOLS_BY_NAME
    assert any("nonexistent" in r.message for r in caplog.records)


def test_parse_toolset_file_duplicate_not_added(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("# TOOL 1: vdb_tool\nPOST|/vdbs/search|search\nPOST|/vdbs/search|search\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    assert len(driver_mod.TOOLS_BY_NAME["vdb_tool"]) == 1


def test_parse_toolset_file_fewer_than_3_parts_skipped(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("# TOOL 1: vdb_tool\nPOST|/vdbs\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    assert driver_mod.TOOLS_BY_NAME["vdb_tool"] == []


def test_parse_toolset_file_tool_already_in_tools_by_name_not_reset(tmp_path):
    driver_mod.TOOLS_BY_NAME["vdb_tool"] = [{"method": "GET", "path": "/existing", "action": "existing"}]
    f = tmp_path / "test.txt"
    f.write_text("# TOOL 1: vdb_tool\nPOST|/vdbs/search|search\n")
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        driver_mod._parse_toolset_file(f)
    # existing entry is preserved because the tool was already in TOOLS_BY_NAME
    assert len(driver_mod.TOOLS_BY_NAME["vdb_tool"]) >= 1


# ===========================================================================
# load_api_endpoints_from_toolsets
# ===========================================================================

def test_load_api_endpoints_from_toolsets_normal(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    # Real TOOLSETS_DIR and real files should work
    driver_mod.load_api_endpoints_from_toolsets()
    assert len(driver_mod.TOOLS_BY_NAME) > 0


def test_load_api_endpoints_from_toolsets_missing_dir(monkeypatch, tmp_path, caplog):
    missing = tmp_path / "nonexistent"
    with patch.object(driver_mod, "TOOLSETS_DIR", missing):
        import logging
        with caplog.at_level(logging.ERROR):
            driver_mod.load_api_endpoints_from_toolsets()
    assert driver_mod.TOOLS_BY_NAME == {}
    assert any("not found" in r.message.lower() for r in caplog.records)


def test_load_api_endpoints_from_toolsets_missing_toolset_file(monkeypatch, tmp_path, caplog):
    # Directory exists but the toolset file doesn't
    with patch.object(driver_mod, "TOOLSETS_DIR", tmp_path):
        monkeypatch.setenv("DCT_TOOLSET", "self_service")
        import logging
        with caplog.at_level(logging.ERROR):
            driver_mod.load_api_endpoints_from_toolsets()
    assert driver_mod.TOOLS_BY_NAME == {}


def test_load_api_endpoints_from_toolsets_auto_defaults_to_self_service(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    # auto should fall back to self_service (which exists)
    driver_mod.load_api_endpoints_from_toolsets()
    assert len(driver_mod.TOOLS_BY_NAME) > 0


# ===========================================================================
# load_api_endpoints (legacy wrapper)
# ===========================================================================

def test_load_api_endpoints_delegates_to_from_toolsets(monkeypatch):
    called = []

    def fake_from_toolsets():
        called.append(True)

    with patch.object(driver_mod, "load_api_endpoints_from_toolsets", fake_from_toolsets):
        driver_mod.load_api_endpoints()
    assert called == [True]


# ===========================================================================
# download_open_api_yaml
# ===========================================================================

def test_download_open_api_yaml_success(tmp_path):
    save_path = str(tmp_path / "api.yaml")
    mock_response = MagicMock()
    mock_response.text = "openapi: '3.0.0'\n"
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response) as mock_get:
        driver_mod.download_open_api_yaml("https://dct.test/api.yaml", save_path)

    mock_get.assert_called_once()
    assert os.path.exists(save_path)
    with open(save_path) as f:
        assert "openapi" in f.read()


def test_download_open_api_yaml_request_exception_raises(tmp_path):
    save_path = str(tmp_path / "api.yaml")
    with patch("requests.get", side_effect=requests.exceptions.RequestException("timeout")):
        with pytest.raises(requests.exceptions.RequestException):
            driver_mod.download_open_api_yaml("https://dct.test/api.yaml", save_path)


# ===========================================================================
# create_register_tool_function
# ===========================================================================

def test_create_register_tool_function_contains_register_tools():
    result = driver_mod.create_register_tool_function("vdb_tool", ["vdb_tool"])
    assert "def register_tools" in result
    assert "app.add_tool" in result
    assert "vdb_tool" in result


def test_create_register_tool_function_multiple_functions():
    result = driver_mod.create_register_tool_function("my_module", ["tool_a", "tool_b"])
    assert 'app.add_tool(tool_a' in result
    assert 'app.add_tool(tool_b' in result


# ===========================================================================
# read_open_api_yaml
# ===========================================================================

def test_read_open_api_yaml_returns_parsed_dict(tmp_path):
    yaml_path = tmp_path / "spec.yaml"
    yaml_path.write_text("openapi: '3.0.0'\ninfo:\n  title: Test\n")
    result = driver_mod.read_open_api_yaml(str(yaml_path))
    assert isinstance(result, dict)
    assert result["openapi"] == "3.0.0"


# ===========================================================================
# resolve_ref
# ===========================================================================

def test_resolve_ref_simple_path():
    root = {"components": {"schemas": {"Foo": {"type": "object"}}}}
    result = driver_mod.resolve_ref("#/components/schemas/Foo", root)
    assert result == {"type": "object"}


def test_resolve_ref_nested_path():
    root = {"a": {"b": {"c": "value"}}}
    result = driver_mod.resolve_ref("#/a/b/c", root)
    assert result == "value"


def test_resolve_ref_non_hash_format_raises():
    with pytest.raises(ValueError, match="Unsupported ref format"):
        driver_mod.resolve_ref("components/schemas/Foo", {})


def test_resolve_ref_missing_key_raises():
    root = {"components": {}}
    with pytest.raises(KeyError):
        driver_mod.resolve_ref("#/components/schemas/Missing", root)


# ===========================================================================
# resolve_schema_properties
# ===========================================================================

def test_resolve_schema_properties_direct_properties():
    schema = {"properties": {"name": {"type": "string"}, "id": {"type": "string"}}}
    props, required, key_props = driver_mod.resolve_schema_properties(schema, {})
    assert "name" in props
    assert "id" in props
    assert key_props == {"name", "id"}


def test_resolve_schema_properties_top_level_ref():
    spec = {"components": {"schemas": {"Foo": {"properties": {"x": {"type": "integer"}}}}}}
    schema = {"$ref": "#/components/schemas/Foo"}
    props, required, key_props = driver_mod.resolve_schema_properties(schema, spec)
    assert "x" in props
    assert "x" in key_props


def test_resolve_schema_properties_all_of_inline():
    schema = {
        "allOf": [
            {"properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"properties": {"b": {"type": "integer"}}},
        ]
    }
    props, required, key_props = driver_mod.resolve_schema_properties(schema, {})
    assert "a" in props
    assert "b" in props
    assert "a" in required
    assert "a" in key_props
    assert "b" in key_props


def test_resolve_schema_properties_all_of_small_ref_is_key():
    spec = {"components": {"schemas": {"Small": {"properties": {
        "x": {"type": "string"}, "y": {"type": "string"}
    }}}}}
    schema = {"allOf": [{"$ref": "#/components/schemas/Small"}]}
    props, required, key_props = driver_mod.resolve_schema_properties(schema, spec)
    assert "x" in key_props
    assert "y" in key_props


def test_resolve_schema_properties_all_of_large_ref_not_key():
    # >5 properties means it's a large base schema
    large_props = {f"prop{i}": {"type": "string"} for i in range(6)}
    spec = {"components": {"schemas": {"Large": {"properties": large_props}}}}
    schema = {"allOf": [{"$ref": "#/components/schemas/Large"}]}
    props, required, key_props = driver_mod.resolve_schema_properties(schema, spec)
    assert len(props) == 6
    # key_props should be empty (large ref excluded)
    assert len(key_props) == 0


def test_resolve_schema_properties_nested_all_of():
    spec = {"components": {"schemas": {
        "Inner": {"allOf": [{"properties": {"inner_prop": {"type": "string"}}}]}
    }}}
    schema = {"allOf": [{"$ref": "#/components/schemas/Inner"}]}
    props, required, key_props = driver_mod.resolve_schema_properties(schema, spec)
    assert "inner_prop" in props


def test_resolve_schema_properties_empty_schema():
    props, required, key_props = driver_mod.resolve_schema_properties({}, {})
    assert props == {}
    assert required == []
    assert key_props == set()


# ===========================================================================
# _get_module_for_path
# ===========================================================================

@pytest.mark.parametrize("path,expected_module", [
    ("/vdbs", "dataset_endpoints"),
    ("/jobs", "job_endpoints"),
    ("/environments", "environment_endpoints"),
    ("/management/engines", "engine_endpoints"),
    ("/masking/something", "compliance_endpoints"),
    ("/reporting/data", "reports_endpoints"),
    ("/management/accounts/123", "iam_endpoints"),
    ("/roles", "iam_endpoints"),
    ("/replication-profiles", "policy_endpoints"),
    ("/virtualization-policies/v1", "policy_endpoints"),
    ("/ai/chat", "admin_endpoints"),
    ("/management/properties", "admin_endpoints"),
    ("/database-templates", "template_endpoints"),
    ("/hook-templates/abc", "template_endpoints"),
    ("/unknown/path", "misc_endpoints"),
])
def test_get_module_for_path(path, expected_module):
    assert driver_mod._get_module_for_path(path) == expected_module


def test_get_module_for_path_longer_prefix_wins():
    # /management/accounts is more specific than /management
    result = driver_mod._get_module_for_path("/management/accounts/123")
    assert result == "iam_endpoints"


def test_get_module_for_path_unknown_returns_misc():
    result = driver_mod._get_module_for_path("/something/completely/unknown")
    assert result == "misc_endpoints"


# ===========================================================================
# _generate_unified_tool
# ===========================================================================

def test_generate_unified_tool_normal():
    apis = [
        {"method": "POST", "path": "/vdbs/search", "action": "search"},
        {"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"},
        {"method": "DELETE", "path": "/vdbs/{vdbId}", "action": "delete"},
        {"method": "POST", "path": "/vdbs", "action": "provision"},
    ]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert "async def vdb_tool" in result
    assert "action" in result
    assert "search" in result
    assert "get" in result
    assert "delete" in result
    assert "provision" in result


def test_generate_unified_tool_contains_docstring():
    apis = [{"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert '"""' in result
    assert "VDB" in result


def test_generate_unified_tool_action_routing():
    apis = [{"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert "if action == 'get':" in result


def test_generate_unified_tool_wrong_method_populates_skipped():
    apis = [{"method": "PUT", "path": "/vdbs/{vdbId}", "action": "update"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    # PUT is not in MINIMAL_SPEC for /vdbs/{vdbId}, so it should be skipped
    assert len(driver_mod.SKIPPED_ENTRIES) == 1
    assert driver_mod.SKIPPED_ENTRIES[0]["action"] == "update"
    assert "available methods" in driver_mod.SKIPPED_ENTRIES[0]["hint"]


def test_generate_unified_tool_missing_path_populates_skipped():
    apis = [{"method": "GET", "path": "/nonexistent/path", "action": "list"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert len(driver_mod.SKIPPED_ENTRIES) == 1
    assert "not found" in driver_mod.SKIPPED_ENTRIES[0]["hint"]


def test_generate_unified_tool_no_valid_actions_returns_empty():
    apis = [{"method": "PATCH", "path": "/nonexistent", "action": "update"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert result == ""


def test_generate_unified_tool_environment_user_id_generates_fallback():
    apis = [{"method": "POST", "path": "/vdbs", "action": "provision"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, MINIMAL_SPEC)
    assert "environment_user_id" in result
    assert "environment_user_ref" in result


def test_generate_unified_tool_body_param_with_ref():
    spec = {
        "paths": {
            "/items": {
                "post": {
                    "summary": "Create item",
                    "operationId": "createItem",
                    "requestBody": {"content": {"application/json": {"schema": {
                        "properties": {
                            "config": {"$ref": "#/components/schemas/Config"}
                        }
                    }}}},
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {
            "Config": {"type": "object", "description": "Config object"}
        }}
    }
    apis = [{"method": "POST", "path": "/items", "action": "create"}]
    result = driver_mod._generate_unified_tool("item_tool", apis, spec)
    # Should process the $ref-resolved property
    assert "async def item_tool" in result


def test_generate_unified_tool_all_of_body_params():
    spec = {
        "paths": {
            "/items": {
                "post": {
                    "summary": "Create item",
                    "operationId": "createItem",
                    "requestBody": {"content": {"application/json": {"schema": {
                        "allOf": [
                            {"properties": {"name": {"type": "string", "description": "Name"}}},
                            {"properties": {"size": {"type": "integer", "description": "Size"}}},
                        ]
                    }}}},
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "POST", "path": "/items", "action": "create"}]
    result = driver_mod._generate_unified_tool("item_tool", apis, spec)
    assert "name" in result
    assert "size" in result


def test_generate_unified_tool_toolkit_subcommand_adds_label():
    spec = {
        "paths": {
            "/items": {
                "post": {
                    "summary": "Create item",
                    "operationId": "createItem",
                    "requestBody": {"content": {"application/json": {"schema": {
                        "properties": {
                            "oracleParam": {
                                "type": "string",
                                "description": "Oracle param",
                                "x-dct-toolkit-subcommand": "oracle"
                            }
                        }
                    }}}},
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "POST", "path": "/items", "action": "create"}]
    result = driver_mod._generate_unified_tool("item_tool", apis, spec)
    assert "Oracle only" in result


def test_generate_unified_tool_enum_query_param_in_description():
    spec = {
        "paths": {
            "/items": {
                "get": {
                    "summary": "Get items",
                    "operationId": "getItems",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["ACTIVE", "INACTIVE"]},
                            "description": "Status filter"
                        }
                    ],
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "GET", "path": "/items", "action": "list"}]
    result = driver_mod._generate_unified_tool("item_tool", apis, spec)
    assert "Valid values" in result
    assert "ACTIVE" in result


def test_generate_unified_tool_default_query_param_in_description():
    spec = {
        "paths": {
            "/items": {
                "get": {
                    "summary": "Get items",
                    "operationId": "getItems",
                    "parameters": [
                        {
                            "name": "page_size",
                            "in": "query",
                            "schema": {"type": "integer", "default": 50},
                            "description": "Page size"
                        }
                    ],
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "GET", "path": "/items", "action": "list"}]
    result = driver_mod._generate_unified_tool("item_tool", apis, spec)
    assert "Default: 50" in result


def test_generate_unified_tool_tool_domain_hint_in_docstring():
    spec = {
        "paths": {
            "/data": {
                "get": {
                    "summary": "Get data",
                    "operationId": "getData",
                    "parameters": [],
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "GET", "path": "/data", "action": "get"}]
    result = driver_mod._generate_unified_tool("data_tool", apis, spec)
    assert "dSource" in result  # data_tool has a domain hint about dSource


def test_generate_unified_tool_action_in_actions_requiring_toolkit():
    spec = {
        "paths": {
            "/vdbs/provision_by_timestamp": {
                "post": {
                    "summary": "Provision VDB by timestamp",
                    "operationId": "provisionVdbByTimestamp",
                    "requestBody": {"content": {"application/json": {"schema": {"properties": {}}}}},
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "POST", "path": "/vdbs/provision_by_timestamp", "action": "provision_by_timestamp"}]
    result = driver_mod._generate_unified_tool("vdb_tool", apis, spec)
    assert "AppData" in result  # provision hint mentions AppData


def test_generate_unified_tool_action_domain_hint():
    spec = {
        "paths": {
            "/environments": {
                "post": {
                    "summary": "Create environment",
                    "operationId": "createEnvironment",
                    "requestBody": {"content": {"application/json": {"schema": {"properties": {}}}}},
                    "responses": {}
                }
            }
        },
        "components": {"schemas": {}}
    }
    apis = [{"method": "POST", "path": "/environments", "action": "create_environment"}]
    result = driver_mod._generate_unified_tool("environment_tool", apis, spec)
    assert "SAP ASE" in result  # create_environment has an action domain hint


# ===========================================================================
# generate_tools_from_openapi
# ===========================================================================

def test_generate_tools_from_openapi_no_base_url_raises(monkeypatch):
    monkeypatch.setenv("DCT_BASE_URL", "")
    with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
        with pytest.raises(ValueError, match="DCT_BASE_URL"):
            driver_mod.generate_tools_from_openapi()


def test_generate_tools_from_openapi_writes_tool_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    driver_mod.TOOLS_BY_NAME["vdb_tool"] = [
        {"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"},
    ]

    def fake_download(url, path):
        with open(path, "w") as f:
            yaml.dump(MINIMAL_SPEC, f)

    monkeypatch.setattr(driver_mod, "TOOLS_DIR", str(tmp_path))

    with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
        with patch.object(driver_mod, "download_open_api_yaml", side_effect=fake_download):
            driver_mod.generate_tools_from_openapi()

    generated = list(tmp_path.glob("*_tool.py"))
    assert len(generated) > 0


def test_generate_tools_from_openapi_no_valid_actions_skips_module(monkeypatch, tmp_path):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    driver_mod.TOOLS_BY_NAME["vdb_tool"] = [
        {"method": "PATCH", "path": "/nonexistent", "action": "bogus"},
    ]

    def fake_download(url, path):
        with open(path, "w") as f:
            yaml.dump(MINIMAL_SPEC, f)

    monkeypatch.setattr(driver_mod, "TOOLS_DIR", str(tmp_path))

    with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
        with patch.object(driver_mod, "download_open_api_yaml", side_effect=fake_download):
            driver_mod.generate_tools_from_openapi()

    # No tool file should be written for a module with no valid tools
    generated = list(tmp_path.glob("*_tool.py"))
    assert len(generated) == 0


def test_generate_tools_from_openapi_cleans_up_existing_files(monkeypatch, tmp_path):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    # Create a stale tool file
    stale = tmp_path / "old_tool.py"
    stale.write_text("# stale")

    driver_mod.TOOLS_BY_NAME["vdb_tool"] = [
        {"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"},
    ]

    def fake_download(url, path):
        with open(path, "w") as f:
            yaml.dump(MINIMAL_SPEC, f)

    monkeypatch.setattr(driver_mod, "TOOLS_DIR", str(tmp_path))

    with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
        with patch.object(driver_mod, "download_open_api_yaml", side_effect=fake_download):
            driver_mod.generate_tools_from_openapi()

    assert not stale.exists()


def test_generate_tools_from_openapi_skipped_entries_logged(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    driver_mod.TOOLS_BY_NAME["vdb_tool"] = [
        {"method": "PATCH", "path": "/nonexistent", "action": "bogus"},
    ]

    def fake_download(url, path):
        with open(path, "w") as f:
            yaml.dump(MINIMAL_SPEC, f)

    monkeypatch.setattr(driver_mod, "TOOLS_DIR", str(tmp_path))

    import logging
    with caplog.at_level(logging.ERROR):
        with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
            with patch.object(driver_mod, "download_open_api_yaml", side_effect=fake_download):
                driver_mod.generate_tools_from_openapi()

    assert any("skipped" in r.message.lower() for r in caplog.records)


def test_generate_tools_from_openapi_download_failure_propagates(monkeypatch, tmp_path):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    monkeypatch.setattr(driver_mod, "TOOLS_DIR", str(tmp_path))

    with patch.object(driver_mod, "load_api_endpoints_from_toolsets"):
        with patch.object(driver_mod, "download_open_api_yaml",
                          side_effect=requests.exceptions.RequestException("network error")):
            with pytest.raises(requests.exceptions.RequestException):
                driver_mod.generate_tools_from_openapi()


