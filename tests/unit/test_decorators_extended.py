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
# Mirrors tools/core/dynamic.py's _error_response convention: a DCTClientError
# raised by a pre-built tool is now returned as a structured error dict
# instead of propagating, with message_for_user added only when to_canonical()
# changes the raw text.
# ---------------------------------------------------------------------------


def test_sync_dct_client_error_translates_internal_terminology():
    from dct_mcp_server.core.exceptions import DCTClientError

    @log_tool_execution
    def failing_tool():
        raise DCTClientError("404: timeflow 'tf-1' not found for appdata source")

    result = failing_tool()

    assert result["status"] == "error"
    assert result["code"] == "DCT_API_ERROR"
    assert "timeflow" in result["message"]
    assert "message_for_user" in result
    assert "timeline" in result["message_for_user"].lower()
    assert "connector" in result["message_for_user"].lower()


def test_sync_dct_client_error_without_internal_terms_omits_translation():
    from dct_mcp_server.core.exceptions import DCTClientError

    @log_tool_execution
    def failing_tool():
        raise DCTClientError("404: VDB 'vdb-1' not found")

    result = failing_tool()

    assert result["status"] == "error"
    assert result["message"] == "404: VDB 'vdb-1' not found"
    assert "message_for_user" not in result


@pytest.mark.asyncio
async def test_async_dct_client_error_translates_internal_terminology():
    from dct_mcp_server.core.exceptions import DCTClientError

    @log_tool_execution
    async def failing_tool():
        raise DCTClientError("500: container 'cg-1' has no active timeflow")

    result = await failing_tool()

    assert result["status"] == "error"
    assert "message_for_user" in result
    assert "vdb group" in result["message_for_user"].lower()
    assert "timeline" in result["message_for_user"].lower()


def test_sync_other_exceptions_still_propagate_unchanged():
    @log_tool_execution
    def failing_tool():
        raise ValueError("not a DCT error")

    with pytest.raises(ValueError, match="not a DCT error"):
        failing_tool()
