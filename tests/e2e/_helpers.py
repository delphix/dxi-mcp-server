"""
Shared helpers for Layer 4 (real-DCT) tests.

Two real-world facts these handle:
  * fastmcp's `call_tool` RAISES `ToolError` on an error result by default — so we
    pass `raise_on_error=False` and inspect `is_error` ourselves.
  * A DCT's license may forbid whole resource types (e.g. "Current License does not
    permit operations on BOOKMARK" / VDB_GROUP). That is an ENVIRONMENT fact, not a
    code/contract bug, so we SKIP those rather than fail.
"""

import pytest

LICENSE_MARKER = "License does not permit"


def result_text(result) -> str:
    """Concatenate the text content of a CallToolResult (works for error results too)."""
    parts = []
    for c in result.content or []:
        t = getattr(c, "text", None)
        if t:
            parts.append(t)
    return " ".join(parts)


def payload(result):
    """Unwrap fastmcp's {"result": <dict>} structured_content envelope."""
    sc = result.structured_content or {}
    return sc.get("result", sc)


async def call_tool_tolerant(client, tool, args):
    """
    Call a tool with raise_on_error=False. If it fails because the DCT license forbids
    the resource, SKIP the test (environment limitation). Any other error fails.
    Returns the successful CallToolResult.
    """
    result = await client.call_tool(tool, args, raise_on_error=False)
    if result.is_error:
        text = result_text(result)
        if LICENSE_MARKER in text:
            pytest.skip(
                f"{tool}: DCT license does not permit this resource — {text[:140]}"
            )
        pytest.fail(
            f"{tool} {args.get('action')!r} failed against real DCT: {text[:300]}"
        )
    return result
