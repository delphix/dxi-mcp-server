"""Smoke test: vdb_endpoints_tool must be importable and expose register_tools."""
import pytest


def test_vdb_endpoints_tool_importable():
    from dct_mcp_server.tools import vdb_endpoints_tool
    assert callable(getattr(vdb_endpoints_tool, "register_tools", None))
