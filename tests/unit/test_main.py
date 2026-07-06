"""
Unit tests for main.py — covers lifespan, async_main, handle_shutdown,
setup_signal_handlers, and the main() entry point.

We avoid actually starting a FastMCP server by mocking out app.run_stdio_async.
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import-level coverage: just importing main.py covers module-level code
# ---------------------------------------------------------------------------


def test_import_main():
    """Importing main covers module-level setup_logging() and app creation."""
    import dct_mcp_server.main as main_mod

    assert hasattr(main_mod, "app")
    assert hasattr(main_mod, "main")
    assert hasattr(main_mod, "async_main")
    assert hasattr(main_mod, "lifespan")


def test_main_has_dct_client_global():
    import dct_mcp_server.main as main_mod

    # dct_client starts as None (gets set in async_main)
    assert "dct_client" in dir(main_mod) or hasattr(main_mod, "dct_client")


def test_main_exports():
    import dct_mcp_server.main as main_mod

    assert "main" in main_mod.__all__
    assert "app" in main_mod.__all__


# ---------------------------------------------------------------------------
# handle_shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_shutdown_first_call():
    import dct_mcp_server.main as main_mod

    orig = main_mod._shutdown_in_progress
    main_mod._shutdown_in_progress = False
    try:
        # Should not raise, sets _shutdown_in_progress=True
        with patch("asyncio.all_tasks", return_value=[]):
            await main_mod.handle_shutdown(signal.SIGINT)
        assert main_mod._shutdown_in_progress is True
    finally:
        main_mod._shutdown_in_progress = orig


@pytest.mark.asyncio
async def test_handle_shutdown_second_call_exits():
    import dct_mcp_server.main as main_mod

    orig = main_mod._shutdown_in_progress
    main_mod._shutdown_in_progress = True
    try:
        with pytest.raises(SystemExit):
            await main_mod.handle_shutdown(signal.SIGINT)
    finally:
        main_mod._shutdown_in_progress = orig


@pytest.mark.asyncio
async def test_handle_shutdown_cancels_tasks():
    import dct_mcp_server.main as main_mod

    orig = main_mod._shutdown_in_progress
    main_mod._shutdown_in_progress = False
    try:
        mock_task = MagicMock()
        with patch("asyncio.all_tasks", return_value=[mock_task]):
            with patch("asyncio.current_task", return_value=None):
                await main_mod.handle_shutdown(signal.SIGTERM)
        mock_task.cancel.assert_called_once()
    finally:
        main_mod._shutdown_in_progress = orig


# ---------------------------------------------------------------------------
# setup_signal_handlers
# ---------------------------------------------------------------------------


def test_setup_signal_handlers_no_exception():
    import dct_mcp_server.main as main_mod

    loop = asyncio.new_event_loop()
    try:
        with patch("asyncio.get_event_loop", return_value=loop):
            main_mod.setup_signal_handlers()
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# lifespan context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_with_telemetry_disabled():
    import dct_mcp_server.main as main_mod

    mock_app = MagicMock()
    orig_client = main_mod.dct_client
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()
    main_mod.dct_client = mock_client

    try:
        with patch(
            "dct_mcp_server.main.get_dct_config",
            return_value={"is_local_telemetry_enabled": False},
        ):
            with patch("dct_mcp_server.main.start_session") as mock_start:
                with patch("dct_mcp_server.main.end_session"):
                    async with main_mod.lifespan(mock_app):
                        pass  # Server "runs"

        mock_start.assert_not_called()
        mock_client.close.assert_called_once()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_lifespan_with_telemetry_enabled(tmp_path):
    import dct_mcp_server.main as main_mod

    mock_app = MagicMock()
    orig_client = main_mod.dct_client
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()
    main_mod.dct_client = mock_client

    try:
        with patch(
            "dct_mcp_server.main.get_dct_config",
            return_value={"is_local_telemetry_enabled": True},
        ):
            with patch(
                "dct_mcp_server.main.start_session", return_value="sess-123"
            ) as mock_start:
                with patch("dct_mcp_server.main.end_session") as mock_end:
                    async with main_mod.lifespan(mock_app):
                        pass

        mock_start.assert_called_once()
        mock_end.assert_called_once()
        mock_client.close.assert_called_once()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_lifespan_cleanup_on_exception():
    import dct_mcp_server.main as main_mod

    mock_app = MagicMock()
    orig_client = main_mod.dct_client
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()
    main_mod.dct_client = mock_client

    try:
        with patch(
            "dct_mcp_server.main.get_dct_config",
            return_value={"is_local_telemetry_enabled": False},
        ):
            with pytest.raises(RuntimeError):
                async with main_mod.lifespan(mock_app):
                    raise RuntimeError("server error")

        # close should be called even when exception occurs
        mock_client.close.assert_called_once()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_lifespan_no_client():
    """If dct_client is None, close should not be called."""
    import dct_mcp_server.main as main_mod

    mock_app = MagicMock()
    orig_client = main_mod.dct_client
    main_mod.dct_client = None

    try:
        with patch(
            "dct_mcp_server.main.get_dct_config",
            return_value={"is_local_telemetry_enabled": False},
        ):
            async with main_mod.lifespan(mock_app):
                pass
        # Should not raise
    finally:
        main_mod.dct_client = orig_client


# ---------------------------------------------------------------------------
# async_main
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_main_creates_client_and_registers_tools():
    import dct_mcp_server.main as main_mod

    orig_client = main_mod.dct_client

    mock_client = MagicMock()
    mock_client.base_url = "https://dct.test"
    mock_client.close = AsyncMock()

    try:
        with patch("dct_mcp_server.main.DCTAPIClient", return_value=mock_client):
            with patch("dct_mcp_server.main.is_dynamic_mode", return_value=False):
                with patch("dct_mcp_server.main.generate_tools_from_openapi"):
                    with patch("dct_mcp_server.tools.register_all_tools") as mock_reg:
                        with patch.object(
                            main_mod.app, "run_stdio_async", new_callable=AsyncMock
                        ):
                            await main_mod.async_main()

        mock_reg.assert_called_once()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_async_main_tool_generation_failure_non_fatal():
    import dct_mcp_server.main as main_mod

    orig_client = main_mod.dct_client

    mock_client = MagicMock()
    mock_client.base_url = "https://dct.test"

    try:
        with patch("dct_mcp_server.main.DCTAPIClient", return_value=mock_client):
            with patch("dct_mcp_server.main.is_dynamic_mode", return_value=False):
                with patch(
                    "dct_mcp_server.main.generate_tools_from_openapi",
                    side_effect=Exception("spec download failed"),
                ):
                    with patch("dct_mcp_server.tools.register_all_tools"):
                        with patch.object(
                            main_mod.app, "run_stdio_async", new_callable=AsyncMock
                        ):
                            # Exception in generate_tools should be swallowed
                            await main_mod.async_main()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_async_main_value_error_returns():
    """ValueError from config should be caught and return gracefully."""
    import dct_mcp_server.main as main_mod

    orig_client = main_mod.dct_client

    try:
        with patch(
            "dct_mcp_server.main.DCTAPIClient", side_effect=ValueError("missing config")
        ):
            with patch("dct_mcp_server.main.print_config_help"):
                await main_mod.async_main()
        # Should return (not raise)
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_async_main_mcp_error_exits():
    """MCPError from client should call sys.exit."""
    import dct_mcp_server.main as main_mod
    from dct_mcp_server.core.exceptions import MCPError

    orig_client = main_mod.dct_client

    try:
        with patch(
            "dct_mcp_server.main.DCTAPIClient", side_effect=MCPError("mcp failure")
        ):
            with pytest.raises(SystemExit):
                await main_mod.async_main()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_async_main_toolset_config_exception_handled():
    """Exception determining toolset should be caught as warning."""
    import dct_mcp_server.main as main_mod

    orig_client = main_mod.dct_client

    mock_client = MagicMock()
    mock_client.base_url = "https://dct.test"

    try:
        with patch("dct_mcp_server.main.DCTAPIClient", return_value=mock_client):
            with patch(
                "dct_mcp_server.main.get_configured_toolset",
                side_effect=Exception("toolset error"),
            ):
                with patch("dct_mcp_server.main.is_dynamic_mode", return_value=False):
                    with patch("dct_mcp_server.main.generate_tools_from_openapi"):
                        with patch("dct_mcp_server.tools.register_all_tools"):
                            with patch.object(
                                main_mod.app, "run_stdio_async", new_callable=AsyncMock
                            ):
                                await main_mod.async_main()
    finally:
        main_mod.dct_client = orig_client


@pytest.mark.asyncio
async def test_async_main_server_cancelled_error():
    """CancelledError from run_stdio_async should be handled gracefully."""
    import dct_mcp_server.main as main_mod

    orig_client = main_mod.dct_client

    mock_client = MagicMock()
    mock_client.base_url = "https://dct.test"

    try:
        with patch("dct_mcp_server.main.DCTAPIClient", return_value=mock_client):
            with patch("dct_mcp_server.main.is_dynamic_mode", return_value=False):
                with patch("dct_mcp_server.main.generate_tools_from_openapi"):
                    with patch("dct_mcp_server.tools.register_all_tools"):
                        with patch.object(
                            main_mod.app,
                            "run_stdio_async",
                            new_callable=AsyncMock,
                            side_effect=asyncio.CancelledError(),
                        ):
                            await main_mod.async_main()
        # Should not raise
    finally:
        main_mod.dct_client = orig_client


# ---------------------------------------------------------------------------
# main() synchronous entry point
# ---------------------------------------------------------------------------


def test_main_runs_asyncio():
    import dct_mcp_server.main as main_mod

    with patch("asyncio.run") as mock_run:
        main_mod.main()

    mock_run.assert_called_once()


def test_main_handles_keyboard_interrupt():
    import dct_mcp_server.main as main_mod

    with patch("asyncio.run", side_effect=KeyboardInterrupt()):
        # Should not raise
        main_mod.main()


def test_main_handles_exception():
    import dct_mcp_server.main as main_mod

    with patch("asyncio.run", side_effect=Exception("unexpected")):
        with pytest.raises(SystemExit):
            main_mod.main()
