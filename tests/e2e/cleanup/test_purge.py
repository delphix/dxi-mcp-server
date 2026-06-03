"""
Layer 4 cleanup — purge everything tagged with the current E2E_RUN_TAG.

Invoked by `dct-mcp-test --layer e2e` AFTER the e2e tests (always, even on failure),
so a crashed mutation run still cleans up. Read-only / no-op while the e2e suite is
read-only; becomes active once mutation tests create tagged resources.

Convention: every resource a mutation test creates is NAMED with the run tag
(e.g. f"{E2E_RUN_TAG}-bookmark") so this pass can find and delete it.
"""

import os

import pytest

from tests.e2e._helpers import call_tool_tolerant, payload as _payload

pytestmark = [pytest.mark.real_dct, pytest.mark.asyncio]


async def test_purge_tagged_resources(real_mcp_client):
    run_tag = os.environ.get("E2E_RUN_TAG")
    assert run_tag and run_tag.startswith("e2e-"), (
        f"E2E_RUN_TAG must be set by the CLI before cleanup; got {run_tag!r}"
    )

    # Bookmarks are fully manageable in self_service (create + delete), so they are
    # the resource the L4 mutation test creates — purge any named with this run tag.
    # (Skips cleanly if the DCT license forbids bookmarks — then nothing was created.)
    res = await call_tool_tolerant(real_mcp_client, "bookmark_tool", {"action": "search", "limit": 500})

    leftovers = [
        b for b in _payload(res).get("items", [])
        if run_tag in (b.get("name") or "")
    ]
    for b in leftovers:
        await real_mcp_client.call_tool(
            "bookmark_tool",
            {"action": "delete", "bookmark_id": b["id"], "confirmed": True},
            raise_on_error=False,
        )

    # Best-effort verify nothing tagged remains (don't hard-fail cleanup on a race).
    after = await real_mcp_client.call_tool(
        "bookmark_tool", {"action": "search", "limit": 500}, raise_on_error=False
    )
    if not after.is_error:
        still = [b for b in _payload(after).get("items", []) if run_tag in (b.get("name") or "")]
        assert not still, f"purge left tagged bookmarks behind: {[b['id'] for b in still]}"
