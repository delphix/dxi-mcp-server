"""Shared helpers for self_service workflow tests (Phase L3 / 3b)."""


def payload(result):
    """Unwrap a fastmcp CallToolResult into the raw DCT response dict.

    fastmcp 3.x wraps a tool's dict return value as {"result": <dict>} inside
    structured_content; unwrap that one level so tests see the DCT shape.
    """
    sc = result.structured_content or {}
    return sc.get("result", sc)


def first_id(result):
    """The id of the first item from a search/list response."""
    items = payload(result).get("items", [])
    assert items, f"expected at least one item, got: {payload(result)}"
    return items[0]["id"]
