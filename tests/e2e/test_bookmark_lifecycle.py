"""
Layer 4 — real-DCT MUTATION lifecycle (bookmark create -> verify -> delete).

Bookmarks are chosen because self_service can fully manage them end-to-end
(create + delete), unlike VDBs (no delete action in self_service). The created
bookmark is NAMED with E2E_RUN_TAG so the cleanup pass purges it even if this
test crashes mid-way.

GATED: skipped unless E2E_ALLOW_MUTATION=1 — and run only against a disposable /
cloned DCT. Also skips if the DCT has no VDB to bookmark.

NOTE: the exact create payload (vdb_ids / snapshot/timeflow refs) is DCT-shape
dependent; this encodes the common shape (name + vdb_ids). First real run may need
the payload adjusted — that's expected for the first execution against a live DCT.

Run:  E2E_ALLOW_MUTATION=1 dct-mcp-test --layer e2e --base-url https://<dct> --api-key <key>
"""

import os

import pytest

pytestmark = [pytest.mark.real_dct, pytest.mark.asyncio]

_MUTATION = os.environ.get("E2E_ALLOW_MUTATION") == "1"
_SKIP = "E2E_ALLOW_MUTATION=1 not set — this test creates+deletes a real bookmark."


def _payload(result):
    sc = result.structured_content or {}
    return sc.get("result", sc)


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
async def test_bookmark_create_verify_delete(real_mcp_client):
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    name = f"{run_tag}-bookmark"

    # Need a VDB to bookmark — pick the first one, skip if none.
    vdbs = await real_mcp_client.call_tool("vdb_tool", {"action": "search", "limit": 1})
    assert not vdbs.is_error, f"vdb search failed: {vdbs}"
    items = _payload(vdbs).get("items", [])
    if not items:
        pytest.skip("no VDBs on this DCT to bookmark (not a failure)")
    vdb_id = items[0]["id"]

    # --- CREATE ---
    created = await real_mcp_client.call_tool(
        "bookmark_tool", {"action": "create", "name": name, "vdb_ids": [vdb_id]}
    )
    assert not created.is_error, f"bookmark create failed: {created}"

    # --- VERIFY via an independent search ---
    found = await real_mcp_client.call_tool("bookmark_tool", {"action": "search", "limit": 500})
    assert not found.is_error
    matches = [b for b in _payload(found).get("items", []) if b.get("name") == name]
    assert matches, f"created bookmark {name!r} not found on real DCT"
    bookmark_id = matches[0]["id"]

    # --- DELETE (manual confirmation -> pre-confirm) ---
    deleted = await real_mcp_client.call_tool(
        "bookmark_tool", {"action": "delete", "bookmark_id": bookmark_id, "confirmed": True}
    )
    assert not deleted.is_error, f"bookmark delete failed: {deleted}"

    # --- VERIFY gone ---
    after = await real_mcp_client.call_tool("bookmark_tool", {"action": "search", "limit": 500})
    assert not after.is_error
    still = [b for b in _payload(after).get("items", []) if b.get("id") == bookmark_id]
    assert not still, f"bookmark {bookmark_id} still present after delete"
