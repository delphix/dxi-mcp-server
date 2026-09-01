"""
Layer 3c — Confirmation handshake over the MCP wire.

For every confirmation-gated self_service operation, prove the two-step contract
survives end-to-end through the MCP stdio transport (not just inside the tool fn):

    1st call (no `confirmed`)    -> status=confirmation_required, correct level,
                                    and NO request reaches DCT.
    2nd call (`confirmed=True`)  -> request is actually issued to DCT.

Cases are derived from the config: every self_service action whose (method, path)
matches a rule in manual_confirmation.txt. Covers standard / manual / retention_check
levels and POST / PATCH / DELETE methods.
"""

import re

import pytest

from dct_mcp_server.config.loader import get_confirmation_for_operation
from tests._support import config_cases

DUMMY = "X1"

_TOOL_MAP = {
    "vdb_tool": "data_tool",
    "vdb_group_tool": "data_tool",
    "dsource_tool": "data_tool",
    "snapshot_tool": "snapshot_bookmark_tool",
    "bookmark_tool": "snapshot_bookmark_tool",
}

_ACTION_MAP = {
    # vdb_tool
    ("vdb_tool", "search"): "search_vdbs",
    ("vdb_tool", "get"): "get_vdb",
    ("vdb_tool", "start"): "start_vdb",
    ("vdb_tool", "stop"): "stop_vdb",
    ("vdb_tool", "enable"): "enable_vdb",
    ("vdb_tool", "disable"): "disable_vdb",
    ("vdb_tool", "refresh_by_timestamp"): "refresh_vdb_by_timestamp",
    ("vdb_tool", "refresh_by_snapshot"): "refresh_vdb_by_snapshot",
    ("vdb_tool", "refresh_from_bookmark"): "refresh_vdb_from_bookmark",
    ("vdb_tool", "rollback_by_timestamp"): "rollback_vdb_by_timestamp",
    ("vdb_tool", "rollback_by_snapshot"): "rollback_vdb_by_snapshot",
    ("vdb_tool", "rollback_from_bookmark"): "rollback_vdb_from_bookmark",
    ("vdb_tool", "list_snapshots"): "list_vdb_snapshots",
    ("vdb_tool", "list_bookmarks"): "list_vdb_bookmarks",
    ("vdb_tool", "get_tags"): "get_vdb_tags",
    ("vdb_tool", "add_tags"): "add_vdb_tags",
    ("vdb_tool", "delete_tags"): "delete_vdb_tags",
    # vdb_group_tool
    ("vdb_group_tool", "search"): "search_vdb_groups",
    ("vdb_group_tool", "get"): "get_vdb_group",
    ("vdb_group_tool", "refresh"): "refresh_vdb_group",
    ("vdb_group_tool", "refresh_from_bookmark"): "refresh_vdb_group_from_bookmark",
    ("vdb_group_tool", "refresh_by_snapshot"): "refresh_vdb_group_by_snapshot",
    ("vdb_group_tool", "refresh_by_timestamp"): "refresh_vdb_group_by_timestamp",
    ("vdb_group_tool", "rollback"): "rollback_vdb_group",
    ("vdb_group_tool", "lock"): "lock_vdb_group",
    ("vdb_group_tool", "unlock"): "unlock_vdb_group",
    ("vdb_group_tool", "start"): "start_vdb_group",
    ("vdb_group_tool", "stop"): "stop_vdb_group",
    ("vdb_group_tool", "enable"): "enable_vdb_group",
    ("vdb_group_tool", "disable"): "disable_vdb_group",
    ("vdb_group_tool", "list_bookmarks"): "list_vdb_group_bookmarks",
    ("vdb_group_tool", "get_tags"): "get_vdb_group_tags",
    ("vdb_group_tool", "add_tags"): "add_vdb_group_tags",
    ("vdb_group_tool", "delete_tags"): "delete_vdb_group_tags",
    # dsource_tool
    ("dsource_tool", "search"): "search_dsources",
    ("dsource_tool", "get"): "get_dsource",
    ("dsource_tool", "list_snapshots"): "list_dsource_snapshots",
    ("dsource_tool", "get_tags"): "get_dsource_tags",
    # snapshot_tool
    ("snapshot_tool", "search"): "search_snapshots",
    ("snapshot_tool", "get"): "get_snapshot",
    ("snapshot_tool", "get_timeflow_range"): "get_snapshot_timeflow_range",
    ("snapshot_tool", "get_runtime"): "get_runtime",
    ("snapshot_tool", "find_by_location"): "find_snapshot_by_location",
    ("snapshot_tool", "find_by_timestamp"): "find_snapshot_by_timestamp",
    ("snapshot_tool", "get_tags"): "get_snapshot_tags",
    ("snapshot_tool", "add_tags"): "add_snapshot_tags",
    ("snapshot_tool", "delete_tags"): "delete_snapshot_tags",
    # bookmark_tool
    ("bookmark_tool", "search"): "search_bookmarks",
    ("bookmark_tool", "get"): "get_bookmark",
    ("bookmark_tool", "create"): "create_bookmark",
    ("bookmark_tool", "update"): "update_bookmark",
    ("bookmark_tool", "delete"): "delete_bookmark",
    ("bookmark_tool", "get_vdb_groups"): "get_bookmark_vdb_groups",
    ("bookmark_tool", "get_tags"): "get_bookmark_tags",
    ("bookmark_tool", "add_tags"): "add_bookmark_tags",
    ("bookmark_tool", "delete_tags"): "delete_bookmark_tags",
}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _wire_path(path: str) -> str:
    return "/dct/v3" + re.sub(r"\{[^}]+\}", DUMMY, path)


_WIRE_ACTIONS_NOT_IN_PREBUILT = {
    # Actions present in the config but not implemented in the pre-built tool modules.
    ("data_tool", "delete_vdb_group_tags"),
    ("data_tool", "delete_vdb_tags"),
}


def _gated_self_service():
    """All confirmation-gated (tool, action) cases in self_service, from config."""
    out, seen = [], set()
    for c in config_cases.action_cases("self_service"):
        conf = get_confirmation_for_operation(
            c.method, re.sub(r"\{[^}]+\}", DUMMY, c.path)
        )
        # batch_check is a dynamic-mode velocity level, not a per-call static
        # handshake gate — in the pre-built/static tool path it proceeds
        # transparently below the sliding-window threshold, so it is not part of
        # this two-step confirmation sweep.
        if conf.get("level", "none") in ("none", "batch_check"):
            continue
        if (c.tool, c.action) in seen:
            continue
        seen.add((c.tool, c.action))
        kwargs = {_snake(ph): DUMMY for ph in re.findall(r"\{([^}]+)\}", c.path)}
        # Translate to pre-built tool/action names
        wire_tool = _TOOL_MAP.get(c.tool, c.tool)
        wire_action = _ACTION_MAP.get((c.tool, c.action), c.action)
        # Skip actions that are in the config but not implemented in the pre-built tools
        if (wire_tool, wire_action) in _WIRE_ACTIONS_NOT_IN_PREBUILT:
            continue
        out.append(
            (
                wire_tool,
                wire_action,
                c.method,
                conf["level"],
                _wire_path(c.path),
                kwargs,
            )
        )
    return out


GATED = _gated_self_service()


def _payload(result):
    sc = result.structured_content or {}
    return sc.get("result", sc)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,action,method,level,wire_path,kwargs",
    GATED,
    ids=[f"{t}-{a}" for t, a, *_ in GATED],
)
async def test_confirmation_handshake_over_wire(
    mcp_client_self_service, dct_stub, tool, action, method, level, wire_path, kwargs
):
    # --- Step 1: unconfirmed -> must gate, must not touch DCT ---
    first = await mcp_client_self_service.call_tool(tool, {"action": action, **kwargs})
    assert not first.is_error, f"{tool}.{action} first call errored: {first}"
    body = _payload(first)
    assert body.get("status") == "confirmation_required", (
        f"{tool}.{action} did not gate; got: {body}"
    )
    assert body.get("confirmation_level") == level, (
        f"{tool}.{action} level was {body.get('confirmation_level')}, expected {level}"
    )
    assert not dct_stub.received_request(method, wire_path), (
        f"{tool}.{action} sent {method} {wire_path} BEFORE confirmation"
    )

    # --- Step 2: confirmed -> request is issued to DCT ---
    second = await mcp_client_self_service.call_tool(
        tool, {"action": action, "confirmed": True, **kwargs}
    )
    assert not second.is_error, f"{tool}.{action} confirmed call errored: {second}"
    assert _payload(second).get("status") != "confirmation_required", (
        f"{tool}.{action} still asked for confirmation after confirmed=True"
    )
    assert dct_stub.received_request(method, wire_path), (
        f"{tool}.{action} did NOT send {method} {wire_path} after confirmation"
    )


def test_gated_case_list_is_complete():
    """Guard: the parametrization actually found the gated ops (catches a silent empty sweep)."""
    assert len(GATED) >= 12, f"expected >=12 gated self_service ops, found {len(GATED)}"
