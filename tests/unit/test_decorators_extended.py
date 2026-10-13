"""
Extended unit tests for core/decorators.py.

Covers:
- sync function path (lines 43-62)
- sync function that raises
- async function that raises
"""

from __future__ import annotations

import pytest

from dct_mcp_server.core.decorators import log_tool_execution


# ---------------------------------------------------------------------------
# Sync function — success path
# ---------------------------------------------------------------------------


def test_sync_function_returns_result():
    @log_tool_execution
    def add(a, b):
        return a + b

    result = add(2, 3)
    assert result == 5


def test_sync_function_with_kwargs():
    @log_tool_execution
    def greet(name="world"):
        return f"hello {name}"

    assert greet(name="test") == "hello test"


def test_sync_function_preserves_name():
    @log_tool_execution
    def my_tool():
        return {}

    assert my_tool.__name__ == "my_tool"


def test_sync_function_preserves_docstring():
    @log_tool_execution
    def documented_tool():
        """Tool docstring."""
        return {}

    assert "Tool docstring" in documented_tool.__doc__


# ---------------------------------------------------------------------------
# Sync function — error path
# ---------------------------------------------------------------------------


def test_sync_function_raises_propagates():
    @log_tool_execution
    def failing_tool():
        raise ValueError("sync fail")

    with pytest.raises(ValueError, match="sync fail"):
        failing_tool()


def test_sync_function_raises_with_args():
    @log_tool_execution
    def tool(x):
        if x < 0:
            raise RuntimeError("negative")
        return x

    with pytest.raises(RuntimeError):
        tool(-1)


# ---------------------------------------------------------------------------
# Async function — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_function_returns_result():
    @log_tool_execution
    async def async_add(a, b):
        return a + b

    result = await async_add(10, 20)
    assert result == 30


@pytest.mark.asyncio
async def test_async_function_preserves_name():
    @log_tool_execution
    async def async_tool():
        return {}

    assert async_tool.__name__ == "async_tool"


# ---------------------------------------------------------------------------
# Async function — error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_function_raises_propagates():
    @log_tool_execution
    async def async_fail():
        raise ValueError("async fail")

    with pytest.raises(ValueError, match="async fail"):
        await async_fail()


@pytest.mark.asyncio
async def test_async_function_raises_with_args():
    @log_tool_execution
    async def async_tool(x):
        if x < 0:
            raise RuntimeError("async negative")
        return x * 2

    with pytest.raises(RuntimeError):
        await async_tool(-5)


# ---------------------------------------------------------------------------
# Decorator identifies async vs sync correctly
# ---------------------------------------------------------------------------


def test_sync_wrapper_is_not_coroutine():
    import inspect

    @log_tool_execution
    def sync_fn():
        return 1

    assert not inspect.iscoroutinefunction(sync_fn)


def test_async_wrapper_is_coroutine():
    import inspect

    @log_tool_execution
    async def async_fn():
        return 1

    assert inspect.iscoroutinefunction(async_fn)


# ---------------------------------------------------------------------------
# Multiple calls work correctly
# ---------------------------------------------------------------------------


def test_sync_function_multiple_calls():
    call_count = {"n": 0}

    @log_tool_execution
    def counter():
        call_count["n"] += 1
        return call_count["n"]

    assert counter() == 1
    assert counter() == 2
    assert counter() == 3


# ---------------------------------------------------------------------------
# DCTClientError -- additive vocabulary translation (PPM-1129)
#
# A DCTClientError raised by a pre-built tool must still be RAISED, so FastMCP
# reports the call with isError=True exactly as before the vocabulary layer.
# The canonical rendering is attached additively: the raw text (and the HTTP
# status in it) is kept verbatim, and a "message_for_user:" line is appended
# only when to_canonical() changes the text.
# ---------------------------------------------------------------------------


def test_sync_dct_client_error_is_raised_with_translation_attached():
    from dct_mcp_server.core.exceptions import DCTClientError

    raw = "HTTP 404: timeflow 'tf-1' not found for appdata source"

    @log_tool_execution
    def failing_tool():
        raise DCTClientError(raw)

    with pytest.raises(DCTClientError) as info:
        failing_tool()

    err = info.value
    assert str(err).startswith(raw)
    assert err.raw_message == raw
    assert err.http_status == 404
    assert "timeline" in err.message_for_user.lower()
    assert "connector" in err.message_for_user.lower()
    assert f"message_for_user: {err.message_for_user}" in str(err)
    assert isinstance(err.__cause__, DCTClientError)


def test_sync_dct_client_error_without_internal_terms_is_reraised_unchanged():
    from dct_mcp_server.core.exceptions import DCTClientError

    original = DCTClientError("HTTP 404: VDB 'vdb-1' not found")

    @log_tool_execution
    def failing_tool():
        raise original

    with pytest.raises(DCTClientError) as info:
        failing_tool()

    assert info.value is original
    assert str(info.value) == "HTTP 404: VDB 'vdb-1' not found"
    assert info.value.message_for_user is None
    assert info.value.http_status == 404


@pytest.mark.asyncio
async def test_async_dct_client_error_is_raised_with_translation_attached():
    from dct_mcp_server.core.exceptions import DCTClientError

    @log_tool_execution
    async def failing_tool():
        raise DCTClientError("HTTP 500: Self-Service container 'cg-1' has no active timeflow")

    with pytest.raises(DCTClientError) as info:
        await failing_tool()

    assert info.value.http_status == 500
    assert "vdb group" in info.value.message_for_user.lower()
    assert "timeline" in info.value.message_for_user.lower()


@pytest.mark.asyncio
async def test_prebuilt_dct_error_reaches_the_mcp_client_as_iserror_with_translation():
    """End to end through FastMCP: isError is preserved AND the translation
    reaches the client."""
    from mcp.server.fastmcp import FastMCP
    from mcp.shared.memory import create_connected_server_and_client_session

    from dct_mcp_server.core.exceptions import DCTClientError

    app = FastMCP("t")

    @app.tool()
    @log_tool_execution
    def timeline_tool(action: str) -> dict:
        raise DCTClientError("HTTP 409: timeflow 'tf-1' is locked")

    @app.tool()
    @log_tool_execution
    def vdb_tool(action: str) -> dict:
        raise DCTClientError("HTTP 404: VDB 'vdb-1' not found")

    async with create_connected_server_and_client_session(app._mcp_server) as client:
        translated = await client.call_tool("timeline_tool", {"action": "get"})
        untouched = await client.call_tool("vdb_tool", {"action": "get"})

    assert translated.isError is True
    text = translated.content[0].text
    assert "HTTP 409: timeflow 'tf-1' is locked" in text
    assert "message_for_user: HTTP 409: timeline 'tf-1' is locked" in text

    assert untouched.isError is True
    assert "HTTP 404: VDB 'vdb-1' not found" in untouched.content[0].text
    assert "message_for_user" not in untouched.content[0].text


def test_sync_other_exceptions_still_propagate_unchanged():
    @log_tool_execution
    def failing_tool():
        raise ValueError("not a DCT error")

    with pytest.raises(ValueError, match="not a DCT error"):
        failing_tool()
