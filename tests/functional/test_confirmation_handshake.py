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


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _wire_path(path: str) -> str:
    return "/dct/v3" + re.sub(r"\{[^}]+\}", DUMMY, path)


def _gated_self_service():
    """All confirmation-gated (tool, action) cases in self_service, from config."""
    out, seen = [], set()
    for c in config_cases.action_cases("self_service"):
        conf = get_confirmation_for_operation(c.method, re.sub(r"\{[^}]+\}", DUMMY, c.path))
        if conf.get("level", "none") == "none":
            continue
        if (c.tool, c.action) in seen:
            continue
        seen.add((c.tool, c.action))
        kwargs = {_snake(ph): DUMMY for ph in re.findall(r"\{([^}]+)\}", c.path)}
        out.append((c.tool, c.action, c.method, conf["level"], _wire_path(c.path), kwargs))
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
