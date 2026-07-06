"""
Layer 3c — Confirmation handshake for continuous_data_admin (CDA), in-process.

CDA tools are dynamic-generation-only (the pre-built modules were removed), so the
subprocess+stub MCP path can't register them. Instead we drive the IN-MEMORY
generated grouped tools (via the shared `persona_tools` fixture) directly against
the `dct_stub` catch-all over real HTTP.

For every confirmation-gated CDA operation, prove the two-step contract:

    1st call (no `confirmed`)    -> status=confirmation_required, correct base level,
                                    and NO request reaches DCT.
    2nd call (`confirmed=True`)  -> request is actually issued to DCT.

Cases are derived entirely from config (`config_cases.action_cases` +
`get_confirmation_for_operation`) — nothing hardcoded. The generated tool gates on
the BASE confirmation level for every non-"none" op (standard / elevated / manual /
retention_check / policy_impact_check); it does not evaluate conditional thresholds.
"""

import re

import pytest

from dct_mcp_server.config.loader import get_confirmation_for_operation
from tests._support import config_cases

DUMMY = "X1"


def _wire_path(path: str) -> str:
    return "/dct/v3" + re.sub(r"\{\w+\}", DUMMY, path)


def _gated_cda():
    """All confirmation-gated (tool, action) cases in CDA, from config."""
    out, seen = [], set()
    for c in config_cases.action_cases("continuous_data_admin"):
        conf = get_confirmation_for_operation(
            c.method, re.sub(r"\{[^}]+\}", DUMMY, c.path)
        )
        if conf.get("level", "none") == "none":
            continue
        if (c.tool, c.action) in seen:
            continue
        seen.add((c.tool, c.action))
        # Path params take the LITERAL placeholder name as the kwarg.
        kwargs = {ph: DUMMY for ph in re.findall(r"\{(\w+)\}", c.path)}
        out.append(
            (c.tool, c.action, c.method, conf["level"], _wire_path(c.path), kwargs)
        )
    return out


GATED = _gated_cda()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,action,method,level,wire_path,kwargs",
    GATED,
    ids=[f"{t}-{a}" for t, a, *_ in GATED],
)
async def test_confirmation_handshake_cda(
    persona_tools, dct_stub, tool, action, method, level, wire_path, kwargs
):
    tools = persona_tools("continuous_data_admin")
    func = tools[tool]

    # --- Step 1: unconfirmed -> must gate, must not touch DCT ---
    first = await func(action=action, **kwargs)
    assert first.get("status") == "confirmation_required", (
        f"{tool}.{action} did not gate; got: {first}"
    )
    assert first.get("confirmation_level") == level, (
        f"{tool}.{action} level was {first.get('confirmation_level')}, expected {level}"
    )
    assert not dct_stub.received_request(method, wire_path), (
        f"{tool}.{action} sent {method} {wire_path} BEFORE confirmation"
    )

    # --- Step 2: confirmed -> request is issued to DCT ---
    second = await func(action=action, confirmed=True, **kwargs)
    assert second.get("status") != "confirmation_required", (
        f"{tool}.{action} still asked for confirmation after confirmed=True"
    )
    assert dct_stub.received_request(method, wire_path), (
        f"{tool}.{action} did NOT send {method} {wire_path} after confirmation"
    )


def test_gated_case_list_is_complete():
    """Guard: the parametrization actually found the gated CDA ops."""
    assert len(GATED) >= 50, f"expected >=50 gated CDA ops, found {len(GATED)}"
